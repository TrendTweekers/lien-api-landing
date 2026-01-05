"""
Zapier Integration Router
Provides webhook endpoints for Zapier to create projects and trigger on upcoming deadlines
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
import logging

from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_current_user_zapier
from api.calculators import calculate_state_deadline
from api.rate_limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["zapier"])

# --- Request Models ---

class InvoiceWebhookRequest(BaseModel):
    """Request model for invoice webhook from Zapier
    
    Accepts invoice amount in two formats:
    - invoice_amount: dollars as float/string (e.g., 49.92)
    - invoice_amount_cents: cents as integer (e.g., 4992)
    
    Example payloads:
    1. {"invoice_date": "2025-01-15", "state": "CA", "invoice_amount": 49.92}
    2. {"invoice_date": "2025-01-15", "state": "CA", "invoice_amount_cents": 4992}
    """
    invoice_date: str = Field(..., description="Invoice date in YYYY-MM-DD format")
    state: str = Field(..., description="State code (2 letters) or full state name")
    project_name: Optional[str] = Field(None, description="Project name")
    client_name: Optional[str] = Field(None, description="Client/customer name")
    invoice_amount: Optional[float] = Field(None, description="Invoice amount in dollars")
    invoice_amount_cents: Optional[int] = Field(None, description="Invoice amount in cents (integer)")
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
    
    @validator('invoice_amount_cents')
    def validate_invoice_amount_cents(cls, v):
        """Validate invoice_amount_cents is non-negative integer"""
        if v is not None:
            if not isinstance(v, int):
                raise ValueError("invoice_amount_cents must be an integer")
            if v < 0:
                raise ValueError("invoice_amount_cents must be >= 0")
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
    current_user: dict = Depends(get_current_user_zapier)
):
    """
    Webhook endpoint for Zapier to create a project from an invoice.
    
    Receives invoice data, calculates deadlines, and saves to calculations table.
    Requires authentication via Bearer token.
    """
    try:
        user_email = current_user.get('email', '').lower().strip()
        if not user_email:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Invalid Zapier token. Generate a new one in Dashboard → Integrations."
                }
            )
        
        # Parse invoice date
        try:
            invoice_date_dt = parse_invoice_date(invoice_data.invoice_date)
        except ValueError as e:
            error_msg = str(e)
            if "date" in error_msg.lower():
                error_msg = "invoice_date is required (YYYY-MM-DD)."
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "version": "v1",
                    "error": error_msg
                }
            )
        
        # Normalize state code
        try:
            state_code = normalize_state_code(invoice_data.state)
        except ValueError as e:
            error_msg = str(e)
            if "state" in error_msg.lower():
                error_msg = "state is required (2-letter code like TX)."
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "version": "v1",
                    "error": error_msg
                }
            )
        
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
        
        # Process invoice amount: accept both invoice_amount (dollars) and invoice_amount_cents
        # Rules:
        # 1) If invoice_amount_cents is provided (int): dollars = invoice_amount_cents / 100
        # 2) Else if invoice_amount is provided (string/float): dollars = invoice_amount
        # 3) If neither provided: return 400 error
        
        invoice_amount_dollars = None
        invoice_amount_cents = None
        invoice_amount_formatted = None
        
        if invoice_data.invoice_amount_cents is not None:
            # Format 1: invoice_amount_cents provided (integer)
            # Convert cents → dollars using Decimal for precision
            try:
                invoice_amount_dollars = Decimal(invoice_data.invoice_amount_cents) / Decimal(100)
                invoice_amount_cents = invoice_data.invoice_amount_cents
                invoice_amount_formatted = f"{invoice_amount_dollars:.2f}"
            except (InvalidOperation, ValueError, TypeError) as e:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "version": "v1",
                        "error": f"Invalid invoice_amount_cents: {str(e)}"
                    }
                )
        elif invoice_data.invoice_amount is not None:
            # Format 2: invoice_amount provided (dollars as float/string)
            # Convert dollars → cents using Decimal for precision
            try:
                invoice_amount_dollars = Decimal(str(invoice_data.invoice_amount))
                if invoice_amount_dollars < 0:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "version": "v1",
                            "error": "invoice_amount must be >= 0"
                        }
                    )
                invoice_amount_cents = int(round(invoice_amount_dollars * 100))
                invoice_amount_formatted = f"{invoice_amount_dollars:.2f}"
            except (InvalidOperation, ValueError, TypeError) as e:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "version": "v1",
                        "error": f"Invalid invoice_amount: {str(e)}"
                    }
                )
        else:
            # Format 3: Neither provided
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "invoice_amount_cents is required (integer cents)."
                }
            )
        
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
                            float(invoice_amount_dollars),  # Store dollars in DB
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
                            float(invoice_amount_dollars),  # Store dollars in DB
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
                "version": "v1",
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
        
    except HTTPException as e:
        # Convert HTTPException to standardized JSONResponse for Zapier API
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Invalid Zapier token. Generate a new one in Dashboard → Integrations."
                }
            )
        # Re-raise other HTTPExceptions (they may already be JSONResponse from above)
        raise
    except Exception as e:
        logger.error(f"❌ Error in webhook_invoice: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "version": "v1",
                "error": "Internal server error. Please try again."
            }
        )


@router.get("/trigger/upcoming")
@limiter.limit("30/minute")
async def trigger_upcoming(
    request: Request,
    current_user: dict = Depends(get_current_user_zapier),
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
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Invalid Zapier token. Generate a new one in Dashboard → Integrations."
                }
            )
        
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
            # DB stores DOLLARS, so we convert dollars → cents for response
            invoice_amount = project.get('invoice_amount')
            if invoice_amount is not None:
                # invoice_amount from DB is in DOLLARS (e.g., 4992.00)
                # Convert to cents: dollars * 100
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
                "version": "v1",
                "count": len(projects),
                "projects": projects
            }
        )
        
    except HTTPException as e:
        # Convert HTTPException to standardized JSONResponse for Zapier API
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Invalid Zapier token. Generate a new one in Dashboard → Integrations."
                }
            )
        # Re-raise other HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"❌ Error in trigger_upcoming: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "version": "v1",
                "error": "Internal server error. Please try again."
            }
        )


@router.get("/api/zapier/trigger/reminders")
@limiter.limit("30/minute")
async def trigger_reminders(
    request: Request,
    current_user: dict = Depends(get_current_user_zapier),
    days: str = "1,7",
    limit: int = 10
):
    """
    Zapier trigger endpoint that returns reminders due now for configured day offsets.
    
    Returns reminders that haven't been sent yet (deduplicated via zapier_notification_events table).
    Requires authentication via Bearer token.
    
    Query params:
    - days: comma-separated integers (e.g., "1,7") - default "1,7"
    - limit: max number of reminders to return (default 10, max 100)
    """
    try:
        user_email = current_user.get('email', '').lower().strip()
        user_id = current_user.get('id')
        
        if not user_email or not user_id:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Invalid Zapier token. Generate a new one in Dashboard → Integrations."
                }
            )
        
        # Parse days parameter
        try:
            days_list = [int(d.strip()) for d in days.split(',') if d.strip()]
            if not days_list:
                raise ValueError("Empty days list")
        except (ValueError, AttributeError):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "days must be a comma-separated list of integers (e.g. days=1,7)"
                }
            )
        
        # Validate limit
        if limit < 1 or limit > 100:
            limit = 10
        
        today = datetime.now().date()
        
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                # Verify table exists (migrations should have created it)
                try:
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT 1 FROM information_schema.tables 
                                WHERE table_name = 'zapier_notification_events'
                            )
                        """)
                        result = cursor.fetchone()
                        table_exists = result[0] if result else False
                    else:
                        cursor.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' AND name='zapier_notification_events'
                        """)
                        table_exists = cursor.fetchone() is not None
                    
                    if not table_exists:
                        logger.error("zapier_notification_events table does not exist. Migration 006_add_zapier_notification_events.sql must be run.")
                        return JSONResponse(
                            status_code=500,
                            content={
                                "success": False,
                                "version": "v1",
                                "error": "Zapier reminders are temporarily unavailable. Please try again later."
                            }
                        )
                except Exception as table_error:
                    logger.error(f"Error checking zapier_notification_events table: {table_error}")
                    return JSONResponse(
                        status_code=500,
                        content={
                            "success": False,
                            "version": "v1",
                            "error": "Zapier reminders are temporarily unavailable. Please try again later."
                        }
                    )
                
                # Find candidate projects where prelim_deadline_days or lien_deadline_days matches requested days
                reminders = []
                
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT 
                            id, project_name, client_name, invoice_date, invoice_amount,
                            state, state_code, prelim_deadline, prelim_deadline_days,
                            lien_deadline, lien_deadline_days, created_at
                        FROM calculations
                        WHERE user_email = %s
                        AND (
                            (prelim_deadline_days IS NOT NULL AND prelim_deadline_days = ANY(%s))
                            OR (lien_deadline_days IS NOT NULL AND lien_deadline_days = ANY(%s))
                        )
                        ORDER BY 
                            CASE 
                                WHEN prelim_deadline_days IS NOT NULL AND prelim_deadline_days = ANY(%s) 
                                THEN prelim_deadline_days 
                                ELSE lien_deadline_days 
                            END ASC,
                            lien_deadline ASC
                        LIMIT %s
                    """, (user_email, days_list, days_list, days_list, limit * 2))
                else:
                    # SQLite: build OR conditions manually
                    days_placeholders = ','.join(['?'] * len(days_list))
                    params = [user_email] + days_list + days_list + days_list + [limit * 2]
                    cursor.execute(f"""
                        SELECT 
                            id, project_name, client_name, invoice_date, invoice_amount,
                            state, state_code, prelim_deadline, prelim_deadline_days,
                            lien_deadline, lien_deadline_days, created_at
                        FROM calculations
                        WHERE user_email = ?
                        AND (
                            (prelim_deadline_days IS NOT NULL AND prelim_deadline_days IN ({days_placeholders}))
                            OR (lien_deadline_days IS NOT NULL AND lien_deadline_days IN ({days_placeholders}))
                        )
                        ORDER BY 
                            CASE 
                                WHEN prelim_deadline_days IS NOT NULL AND prelim_deadline_days IN ({days_placeholders}) 
                                THEN prelim_deadline_days 
                                ELSE lien_deadline_days 
                            END ASC,
                            lien_deadline ASC
                        LIMIT ?
                    """, params)
                
                candidate_rows = cursor.fetchall()
                
                # Helper function to format project data
                def format_project(row):
                    if isinstance(row, dict):
                        return {
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
                        return {
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
                
                # Process each candidate and dedupe via insert
                for row in candidate_rows:
                    if len(reminders) >= limit:
                        break
                    
                    project_data = format_project(row)
                    project_id = project_data['id']
                    prelim_deadline_days = project_data.get('prelim_deadline_days')
                    lien_deadline_days = project_data.get('lien_deadline_days')
                    prelim_deadline = project_data.get('prelim_deadline')
                    lien_deadline = project_data.get('lien_deadline')
                    
                    if not project_id:
                        continue
                    
                    # Check prelim reminders
                    if prelim_deadline_days is not None and prelim_deadline_days in days_list and prelim_deadline:
                        try:
                            if isinstance(prelim_deadline, str):
                                deadline_date = datetime.strptime(prelim_deadline, "%Y-%m-%d").date()
                            elif hasattr(prelim_deadline, 'date'):
                                deadline_date = prelim_deadline.date()
                            else:
                                deadline_date = prelim_deadline
                            
                            # Try to insert (dedupe via unique constraint)
                            try:
                                if DB_TYPE == 'postgresql':
                                    cursor.execute("""
                                        INSERT INTO zapier_notification_events 
                                        (user_id, project_id, reminder_type, reminder_days, deadline_date)
                                        VALUES (%s, %s, 'prelim', %s, %s)
                                        ON CONFLICT (user_id, project_id, reminder_type, reminder_days, deadline_date) DO NOTHING
                                        RETURNING id
                                    """, (user_id, project_id, prelim_deadline_days, deadline_date))
                                    inserted = cursor.fetchone() is not None
                                else:
                                    # SQLite: check if exists first, then insert
                                    cursor.execute("""
                                        SELECT id FROM zapier_notification_events
                                        WHERE user_id = ? AND project_id = ? 
                                        AND reminder_type = 'prelim' AND reminder_days = ? AND deadline_date = ?
                                    """, (user_id, project_id, prelim_deadline_days, deadline_date))
                                    if cursor.fetchone() is None:
                                        cursor.execute("""
                                            INSERT INTO zapier_notification_events 
                                            (user_id, project_id, reminder_type, reminder_days, deadline_date)
                                            VALUES (?, ?, 'prelim', ?, ?)
                                        """, (user_id, project_id, prelim_deadline_days, deadline_date))
                                        inserted = True
                                    else:
                                        inserted = False
                                
                                if inserted:
                                    # Format dates and invoice amount
                                    from datetime import date as _date, datetime as _datetime
                                    for k in ("invoice_date", "prelim_deadline", "lien_deadline", "created_at"):
                                        v = project_data.get(k)
                                        if isinstance(v, _datetime):
                                            project_data[k] = v.strftime("%Y-%m-%d") if k == "invoice_date" else v.isoformat()
                                        elif isinstance(v, _date):
                                            project_data[k] = v.isoformat()
                                    
                                    invoice_amount = project_data.get('invoice_amount')
                                    if invoice_amount is not None:
                                        project_data['invoice_amount_cents'] = int(invoice_amount * 100)
                                        project_data['invoice_amount'] = f"{invoice_amount:.2f}"
                                    else:
                                        project_data['invoice_amount_cents'] = None
                                        project_data['invoice_amount'] = None
                                    
                                    reminders.append({
                                        "project_id": project_id,
                                        "reminder_type": "prelim",
                                        "reminder_days": prelim_deadline_days,
                                        "deadline_date": deadline_date.isoformat() if isinstance(deadline_date, date) else str(deadline_date),
                                        "project": project_data
                                    })
                            except Exception as insert_error:
                                # Unique constraint violation = already sent, skip
                                if 'unique' in str(insert_error).lower() or 'duplicate' in str(insert_error).lower():
                                    continue
                                logger.warning(f"Insert error (non-critical): {insert_error}")
                        except Exception as date_error:
                            logger.warning(f"Date parsing error: {date_error}")
                            continue
                    
                    # Check lien reminders
                    if len(reminders) >= limit:
                        break
                    
                    if lien_deadline_days is not None and lien_deadline_days in days_list and lien_deadline:
                        try:
                            if isinstance(lien_deadline, str):
                                deadline_date = datetime.strptime(lien_deadline, "%Y-%m-%d").date()
                            elif hasattr(lien_deadline, 'date'):
                                deadline_date = lien_deadline.date()
                            else:
                                deadline_date = lien_deadline
                            
                            try:
                                if DB_TYPE == 'postgresql':
                                    cursor.execute("""
                                        INSERT INTO zapier_notification_events 
                                        (user_id, project_id, reminder_type, reminder_days, deadline_date)
                                        VALUES (%s, %s, 'lien', %s, %s)
                                        ON CONFLICT (user_id, project_id, reminder_type, reminder_days, deadline_date) DO NOTHING
                                        RETURNING id
                                    """, (user_id, project_id, lien_deadline_days, deadline_date))
                                    inserted = cursor.fetchone() is not None
                                else:
                                    cursor.execute("""
                                        SELECT id FROM zapier_notification_events
                                        WHERE user_id = ? AND project_id = ? 
                                        AND reminder_type = 'lien' AND reminder_days = ? AND deadline_date = ?
                                    """, (user_id, project_id, lien_deadline_days, deadline_date))
                                    if cursor.fetchone() is None:
                                        cursor.execute("""
                                            INSERT INTO zapier_notification_events 
                                            (user_id, project_id, reminder_type, reminder_days, deadline_date)
                                            VALUES (?, ?, 'lien', ?, ?)
                                        """, (user_id, project_id, lien_deadline_days, deadline_date))
                                        inserted = True
                                    else:
                                        inserted = False
                                
                                if inserted:
                                    # Format dates and invoice amount
                                    from datetime import date as _date, datetime as _datetime
                                    for k in ("invoice_date", "prelim_deadline", "lien_deadline", "created_at"):
                                        v = project_data.get(k)
                                        if isinstance(v, _datetime):
                                            project_data[k] = v.strftime("%Y-%m-%d") if k == "invoice_date" else v.isoformat()
                                        elif isinstance(v, _date):
                                            project_data[k] = v.isoformat()
                                    
                                    invoice_amount = project_data.get('invoice_amount')
                                    if invoice_amount is not None:
                                        project_data['invoice_amount_cents'] = int(invoice_amount * 100)
                                        project_data['invoice_amount'] = f"{invoice_amount:.2f}"
                                    else:
                                        project_data['invoice_amount_cents'] = None
                                        project_data['invoice_amount'] = None
                                    
                                    reminders.append({
                                        "project_id": project_id,
                                        "reminder_type": "lien",
                                        "reminder_days": lien_deadline_days,
                                        "deadline_date": deadline_date.isoformat() if isinstance(deadline_date, date) else str(deadline_date),
                                        "project": project_data
                                    })
                            except Exception as insert_error:
                                if 'unique' in str(insert_error).lower() or 'duplicate' in str(insert_error).lower():
                                    continue
                                logger.warning(f"Insert error (non-critical): {insert_error}")
                        except Exception as date_error:
                            logger.warning(f"Date parsing error: {date_error}")
                            continue
                
                conn.commit()
                
        except HTTPException:
            raise
        except Exception as db_error:
            logger.error(f"Database error in trigger_reminders: {db_error}")
            import traceback
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Internal server error. Please try again."
                }
            )
        
        logger.info(f"✅ Retrieved {len(reminders)} reminders for user {user_email}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "version": "v1",
                "count": len(reminders),
                "days": days_list,
                "reminders": reminders
            }
        )
        
    except HTTPException as e:
        if e.status_code == 401:
            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "version": "v1",
                    "error": "Invalid Zapier token. Generate a new one in Dashboard → Integrations."
                }
            )
        raise
    except Exception as e:
        logger.error(f"❌ Error in trigger_reminders: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "version": "v1",
                "error": "Internal server error. Please try again."
            }
        )

