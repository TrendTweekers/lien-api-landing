"""
Zapier Integration Router
Provides webhook endpoints for Zapier to create projects and trigger on upcoming deadlines
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timedelta, date
import logging

from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_current_user
from api.calculators import calculate_state_deadline
from api.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["zapier"])

# --- Request Models ---

class InvoiceWebhookRequest(BaseModel):
    """Request model for invoice webhook from Zapier"""
    invoice_date: str = Field(..., description="Invoice date in YYYY-MM-DD format")
    state: str = Field(..., description="State code (2 letters) or full state name")
    project_name: Optional[str] = Field(None, description="Project name")
    client_name: Optional[str] = Field(None, description="Client/customer name")
    invoice_amount: Optional[float] = Field(None, description="Invoice amount")
    project_type: Optional[str] = Field("Commercial", description="Project type: Commercial or Residential")
    role: Optional[str] = Field("supplier", description="Role: supplier, contractor, etc.")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    @validator('invoice_date')
    def validate_date(cls, v):
        """Validate and parse invoice date"""
        try:
            # Try YYYY-MM-DD format first
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            try:
                # Try MM/DD/YYYY format
                dt = datetime.strptime(v, "%m/%d/%Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                raise ValueError("Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY")
    
    @validator('state')
    def validate_state(cls, v):
        """Normalize state to uppercase 2-letter code"""
        v = v.strip().upper()
        # If it's already a 2-letter code, return it
        if len(v) == 2:
            return v
        # Try to convert full name to code
        from api.calculators import STATE_CODE_TO_NAME
        reverse_map = {v: k for k, v in STATE_CODE_TO_NAME.items()}
        if v in reverse_map:
            return reverse_map[v]
        # If not found, return as-is (will be validated later)
        return v


class UpcomingProjectsResponse(BaseModel):
    """Response model for upcoming projects"""
    id: int
    project_name: str
    client_name: Optional[str]
    invoice_date: str
    invoice_amount: Optional[float]
    state: str
    state_code: str
    prelim_deadline: Optional[str]
    prelim_deadline_days: Optional[int]
    lien_deadline: str
    lien_deadline_days: int
    created_at: str


# --- Helper Functions ---

def parse_invoice_date(date_str: str) -> datetime:
    """Parse invoice date string to datetime object"""
    try:
        # Try YYYY-MM-DD format first
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            # Try MM/DD/YYYY format
            return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD or MM/DD/YYYY")


def normalize_state_code(state: str) -> str:
    """Normalize state input to 2-letter code"""
    state = state.strip().upper()
    
    # If already 2-letter code, return it
    if len(state) == 2:
        return state
    
    # Try to convert full name to code
    from api.calculators import STATE_CODE_TO_NAME
    reverse_map = {v.upper(): k for k, v in STATE_CODE_TO_NAME.items()}
    if state in reverse_map:
        return reverse_map[state]
    
    # If not found, raise error
    raise ValueError(f"Invalid state: {state}. Must be 2-letter code or full state name")


# --- Endpoints ---

@router.post("/webhook/invoice")
@limiter.limit("10/minute")
async def webhook_invoice(
    request: Request,
    invoice_data: InvoiceWebhookRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Webhook endpoint for Zapier to create a project from an invoice.
    
    Receives invoice data, calculates deadlines, and saves to calculations table.
    Requires authentication via Bearer token.
    """
    try:
        user_email = current_user.get('email', '').lower().strip()
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found")
        
        # Parse invoice date
        try:
            invoice_date_dt = parse_invoice_date(invoice_data.invoice_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Normalize state code
        try:
            state_code = normalize_state_code(invoice_data.state)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Calculate deadlines using existing calculator
        try:
            deadline_result = calculate_state_deadline(
                state_code=state_code,
                invoice_date=invoice_date_dt,
                role=invoice_data.role or "supplier",
                project_type=invoice_data.project_type or "Commercial"
            )
        except Exception as e:
            logger.error(f"Error calculating deadlines: {e}")
            raise HTTPException(status_code=500, detail=f"Error calculating deadlines: {str(e)}")
        
        prelim_deadline = deadline_result.get("preliminary_deadline")
        lien_deadline = deadline_result.get("lien_deadline")
        
        if not lien_deadline:
            raise HTTPException(status_code=500, detail="Failed to calculate lien deadline")
        
        # Calculate days remaining
        today = datetime.now().date()
        prelim_days = None
        if prelim_deadline:
            prelim_days = (prelim_deadline.date() - today).days
        
        lien_days = (lien_deadline.date() - today).days
        
        # Format invoice amount for Zapier (cents + formatted string)
        invoice_amount_cents = None
        invoice_amount_formatted = None
        if invoice_data.invoice_amount is not None:
            invoice_amount_cents = int(invoice_data.invoice_amount * 100)
            invoice_amount_formatted = f"{invoice_data.invoice_amount:.2f}"
        
        # Format dates as strings
        prelim_deadline_str = prelim_deadline.strftime("%Y-%m-%d") if prelim_deadline else None
        lien_deadline_str = lien_deadline.strftime("%Y-%m-%d")
        
        # Get state name for storage
        from api.calculators import STATE_CODE_TO_NAME
        state_name = STATE_CODE_TO_NAME.get(state_code, state_code)
        
        # Save to calculations table with error handling
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                try:
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO calculations (
                                user_email, project_name, client_name, invoice_amount, notes,
                                state, state_code, invoice_date,
                                prelim_deadline, prelim_deadline_days,
                                lien_deadline, lien_deadline_days,
                                project_type, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                            RETURNING id
                        """, (
                            user_email,
                            invoice_data.project_name or "",
                            invoice_data.client_name or "",
                            invoice_data.invoice_amount,
                            invoice_data.notes or "",
                            state_name,
                            state_code,
                            invoice_data.invoice_date,
                            prelim_deadline_str,
                            prelim_days,
                            lien_deadline_str,
                            lien_days,
                            invoice_data.project_type or "Commercial",
                        ))
                        result = cursor.fetchone()
                        calculation_id = result.get('id') if isinstance(result, dict) else (result[0] if result else None)
                    else:
                        cursor.execute("""
                            INSERT INTO calculations (
                                user_email, project_name, client_name, invoice_amount, notes,
                                state, state_code, invoice_date,
                                prelim_deadline, prelim_deadline_days,
                                lien_deadline, lien_deadline_days,
                                project_type, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (
                            user_email,
                            invoice_data.project_name or "",
                            invoice_data.client_name or "",
                            invoice_data.invoice_amount,
                            invoice_data.notes or "",
                            state_name,
                            state_code,
                            invoice_data.invoice_date,
                            prelim_deadline_str,
                            prelim_days,
                            lien_deadline_str,
                            lien_days,
                            invoice_data.project_type or "Commercial",
                        ))
                        calculation_id = cursor.lastrowid
                    
                    conn.commit()
                except Exception as db_error:
                    conn.rollback()
                    logger.error(f"Database error saving calculation: {db_error}")
                    raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        except HTTPException:
            raise
        except Exception as db_conn_error:
            logger.error(f"Database connection error: {db_conn_error}")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        logger.info(f"✅ Created project via Zapier webhook: ID={calculation_id}, user={user_email}")
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "id": calculation_id,
                "project_name": invoice_data.project_name or "",
                "invoice_date": invoice_data.invoice_date,
                "state": state_code,
                "invoice_amount": invoice_amount_formatted,
                "invoice_amount_cents": invoice_amount_cents,
                "preliminary_deadline": prelim_deadline_str,
                "preliminary_deadline_days": prelim_days,
                "lien_deadline": lien_deadline_str,
                "lien_deadline_days": lien_days,
                "message": "Project created successfully"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in webhook_invoice: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/trigger/upcoming")
@limiter.limit("30/minute")
async def trigger_upcoming(
    request: Request,
    current_user: dict = Depends(get_current_user),
    limit: int = 10
):
    """
    Zapier trigger endpoint that returns upcoming projects (lien_deadline > today).
    
    Returns projects sorted by lien_deadline (ascending) with a limit.
    Requires authentication via Bearer token.
    """
    try:
        user_email = current_user.get('email', '').lower().strip()
        if not user_email:
            raise HTTPException(status_code=401, detail="User email not found")
        
        # Validate limit
        if limit < 1 or limit > 100:
            limit = 10
        
        today = datetime.now().date().isoformat()
        
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                try:
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT 
                                id, project_name, client_name, invoice_date, invoice_amount,
                                state, state_code, prelim_deadline, prelim_deadline_days,
                                lien_deadline, lien_deadline_days, created_at
                            FROM calculations
                            WHERE user_email = %s
                            AND lien_deadline > %s
                            ORDER BY lien_deadline ASC
                            LIMIT %s
                        """, (user_email, today, limit))
                    else:
                        cursor.execute("""
                            SELECT 
                                id, project_name, client_name, invoice_date, invoice_amount,
                                state, state_code, prelim_deadline, prelim_deadline_days,
                                lien_deadline, lien_deadline_days, created_at
                            FROM calculations
                            WHERE user_email = ?
                            AND lien_deadline > ?
                            ORDER BY lien_deadline ASC
                            LIMIT ?
                        """, (user_email, today, limit))
                    
                    rows = cursor.fetchall()
                except Exception as db_error:
                    logger.error(f"Database error fetching upcoming projects: {db_error}")
                    raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
        except HTTPException:
            raise
        except Exception as db_conn_error:
            logger.error(f"Database connection error: {db_conn_error}")
            raise HTTPException(status_code=500, detail="Database connection failed")
        
        # Format results
        projects = []
        for row in rows:
            if isinstance(row, dict):
                project = {
                    "id": row.get('id'),
                    "project_name": row.get('project_name') or "",
                    "client_name": row.get('client_name') or "",
                    "invoice_date": row.get('invoice_date') or "",
                    "invoice_amount": float(row.get('invoice_amount')) if row.get('invoice_amount') else None,
                    "state": row.get('state') or "",
                    "state_code": row.get('state_code') or "",
                    "prelim_deadline": row.get('prelim_deadline'),
                    "prelim_deadline_days": row.get('prelim_deadline_days'),
                    "lien_deadline": row.get('lien_deadline') or "",
                    "lien_deadline_days": row.get('lien_deadline_days') or 0,
                    "created_at": row.get('created_at') or ""
                }
            else:
                project = {
                    "id": row[0] if len(row) > 0 else None,
                    "project_name": row[1] if len(row) > 1 else "",
                    "client_name": row[2] if len(row) > 2 else "",
                    "invoice_date": row[3] if len(row) > 3 else "",
                    "invoice_amount": float(row[4]) if len(row) > 4 and row[4] else None,
                    "state": row[5] if len(row) > 5 else "",
                    "state_code": row[6] if len(row) > 6 else "",
                    "prelim_deadline": row[7] if len(row) > 7 else None,
                    "prelim_deadline_days": row[8] if len(row) > 8 else None,
                    "lien_deadline": row[9] if len(row) > 9 else "",
                    "lien_deadline_days": row[10] if len(row) > 10 else 0,
                    "created_at": row[11] if len(row) > 11 else ""
                }
            
            # Ensure all date/datetime fields are JSON-serializable
            # (DB drivers often return datetime.date for DATE columns)
            from datetime import date as _date, datetime as _datetime

            for k in ("invoice_date", "prelim_deadline", "lien_deadline", "created_at"):
                v = project.get(k)
                if isinstance(v, _datetime):
                    # Keep invoice_date as YYYY-MM-DD, everything else can be full ISO
                    project[k] = v.strftime("%Y-%m-%d") if k == "invoice_date" else v.isoformat()
                elif isinstance(v, _date):
                    project[k] = v.isoformat()
            
            # Calculate prelim_deadline_days if missing but prelim_deadline exists
            if project.get('prelim_deadline') and project.get('prelim_deadline_days') is None:
                try:
                    prelim_date_str = project.get('prelim_deadline')
                    if isinstance(prelim_date_str, str):
                        # Parse date string (YYYY-MM-DD format)
                        prelim_date = datetime.strptime(prelim_date_str, "%Y-%m-%d").date()
                        today = datetime.now().date()
                        project['prelim_deadline_days'] = (prelim_date - today).days
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Could not calculate prelim_deadline_days: {e}")
            
            # Format invoice amount for Zapier (cents + formatted string)
            invoice_amount = project.get('invoice_amount')
            if invoice_amount is not None:
                project['invoice_amount_cents'] = int(invoice_amount * 100)
                project['invoice_amount'] = f"{invoice_amount:.2f}"
            else:
                project['invoice_amount_cents'] = None
                project['invoice_amount'] = None
            
            projects.append(project)
        
        logger.info(f"✅ Retrieved {len(projects)} upcoming projects for user {user_email}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "count": len(projects),
                "projects": projects
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in trigger_upcoming: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

