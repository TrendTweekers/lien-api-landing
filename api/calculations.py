from fastapi import APIRouter, HTTPException, Depends, Header
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional, Dict
import json
from api.database import get_db, get_db_cursor, DB_TYPE

router = APIRouter()

# Pydantic models for request validation
class ReminderPreferences(BaseModel):
    prelim7: bool = False
    prelim1: bool = False
    lien7: bool = False
    lien1: bool = False

class SaveCalculationRequest(BaseModel):
    projectName: str
    clientName: str
    invoiceAmount: Optional[float] = None
    notes: Optional[str] = None
    state: str
    stateCode: str
    invoiceDate: str
    prelimDeadline: Optional[str] = None
    prelimDeadlineDays: Optional[int] = None
    lienDeadline: str
    lienDeadlineDays: int
    reminders: ReminderPreferences
    quickbooksInvoiceId: Optional[str] = None

# Dependency to get current user from session token
async def get_current_user(authorization: str = Header(None)):
    """Get current user from session token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="No token provided")
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT email, subscription_status FROM users WHERE session_token = ?", (token,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            # Extract fields - handle both dict-like and tuple results
            try:
                if isinstance(user, dict):
                    email = user.get('email', '')
                    subscription_status = user.get('subscription_status', '')
                else:
                    # Tuple/list result
                    email = user[0] if len(user) > 0 else ''
                    subscription_status = user[1] if len(user) > 1 else ''
            except (TypeError, KeyError, IndexError):
                raise HTTPException(status_code=401, detail="Invalid user data")
            
            if subscription_status not in ['active', 'trialing']:
                raise HTTPException(status_code=403, detail="Subscription expired")
            
            return {
                "email": email,
                "subscription_status": subscription_status
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Session verification error: {repr(e)}")
        raise HTTPException(status_code=500, detail="Session verification failed")

def create_reminder(cursor, calculation_id, user_email, project_name, client_name, 
                   invoice_amount, state, notes, deadline_type, deadline_date, days_before):
    """Helper function to create a single email reminder"""
    
    # Calculate when to send the reminder
    deadline_dt = datetime.strptime(deadline_date, '%Y-%m-%d')
    send_date = deadline_dt - timedelta(days=days_before)
    
    if DB_TYPE == 'postgresql':
        cursor.execute("""
            INSERT INTO email_reminders (
                calculation_id,
                user_email,
                project_name,
                client_name,
                invoice_amount,
                state,
                notes,
                deadline_type,
                deadline_date,
                days_before,
                send_date,
                alert_sent,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            calculation_id,
            user_email,
            project_name,
            client_name,
            invoice_amount,
            state,
            notes,
            deadline_type,
            deadline_date,
            days_before,
            send_date,
            False,
            datetime.now()
        ))
    else:
        cursor.execute("""
            INSERT INTO email_reminders (
                calculation_id,
                user_email,
                project_name,
                client_name,
                invoice_amount,
                state,
                notes,
                deadline_type,
                deadline_date,
                days_before,
                send_date,
                alert_sent,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            calculation_id,
            user_email,
            project_name,
            client_name,
            invoice_amount,
            state,
            notes,
            deadline_type,
            deadline_date,
            days_before,
            send_date,
            False,
            datetime.now()
        ))

@router.post("/api/calculations/save")
async def save_calculation(data: SaveCalculationRequest, current_user: dict = Depends(get_current_user)):
    """Save a calculation with project details and set up email reminders"""
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Ensure tables exist
            if DB_TYPE == 'postgresql':
                # Create calculations table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calculations (
                        id SERIAL PRIMARY KEY,
                        user_email VARCHAR NOT NULL,
                        project_name VARCHAR NOT NULL,
                        client_name VARCHAR NOT NULL,
                        invoice_amount DECIMAL(10, 2),
                        notes TEXT,
                        state VARCHAR NOT NULL,
                        state_code VARCHAR(2) NOT NULL,
                        invoice_date DATE NOT NULL,
                        prelim_deadline DATE,
                        prelim_deadline_days INTEGER,
                        lien_deadline DATE NOT NULL,
                        lien_deadline_days INTEGER NOT NULL,
                        quickbooks_invoice_id VARCHAR,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Create email_reminders table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_reminders (
                        id SERIAL PRIMARY KEY,
                        calculation_id INTEGER REFERENCES calculations(id) ON DELETE CASCADE,
                        user_email VARCHAR NOT NULL,
                        project_name VARCHAR NOT NULL,
                        client_name VARCHAR NOT NULL,
                        invoice_amount DECIMAL(10, 2),
                        state VARCHAR NOT NULL,
                        notes TEXT,
                        deadline_type VARCHAR NOT NULL,
                        deadline_date DATE NOT NULL,
                        days_before INTEGER NOT NULL,
                        send_date DATE NOT NULL,
                        alert_sent BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            else:
                # SQLite
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calculations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email TEXT NOT NULL,
                        project_name TEXT NOT NULL,
                        client_name TEXT NOT NULL,
                        invoice_amount REAL,
                        notes TEXT,
                        state TEXT NOT NULL,
                        state_code TEXT NOT NULL,
                        invoice_date TEXT NOT NULL,
                        prelim_deadline TEXT,
                        prelim_deadline_days INTEGER,
                        lien_deadline TEXT NOT NULL,
                        lien_deadline_days INTEGER NOT NULL,
                        quickbooks_invoice_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        calculation_id INTEGER REFERENCES calculations(id) ON DELETE CASCADE,
                        user_email TEXT NOT NULL,
                        project_name TEXT NOT NULL,
                        client_name TEXT NOT NULL,
                        invoice_amount REAL,
                        state TEXT NOT NULL,
                        notes TEXT,
                        deadline_type TEXT NOT NULL,
                        deadline_date TEXT NOT NULL,
                        days_before INTEGER NOT NULL,
                        send_date TEXT NOT NULL,
                        alert_sent INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # 1. Save the calculation/project
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO calculations (
                        user_email,
                        project_name,
                        client_name,
                        invoice_amount,
                        notes,
                        state,
                        state_code,
                        invoice_date,
                        prelim_deadline,
                        prelim_deadline_days,
                        lien_deadline,
                        lien_deadline_days,
                        quickbooks_invoice_id,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    current_user['email'],
                    data.projectName,
                    data.clientName,
                    data.invoiceAmount,
                    data.notes,
                    data.state,
                    data.stateCode,
                    data.invoiceDate,
                    data.prelimDeadline,
                    data.prelimDeadlineDays,
                    data.lienDeadline,
                    data.lienDeadlineDays,
                    data.quickbooksInvoiceId,
                    datetime.now()
                ))
                result = cursor.fetchone()
                if not result:
                    conn.rollback()
                    raise Exception("Failed to insert calculation into database")
                calculation_id = result[0]
            else:
                cursor.execute("""
                    INSERT INTO calculations (
                        user_email,
                        project_name,
                        client_name,
                        invoice_amount,
                        notes,
                        state,
                        state_code,
                        invoice_date,
                        prelim_deadline,
                        prelim_deadline_days,
                        lien_deadline,
                        lien_deadline_days,
                        quickbooks_invoice_id,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    current_user['email'],
                    data.projectName,
                    data.clientName,
                    data.invoiceAmount,
                    data.notes,
                    data.state,
                    data.stateCode,
                    data.invoiceDate,
                    data.prelimDeadline,
                    data.prelimDeadlineDays,
                    data.lienDeadline,
                    data.lienDeadlineDays,
                    data.quickbooksInvoiceId,
                    datetime.now()
                ))
                calculation_id = cursor.lastrowid
            
            # 2. Set up email reminders based on user preferences
            reminders_created = 0
            
            # Preliminary notice reminders (only if prelim deadline exists)
            if data.prelimDeadline:
                if data.reminders.prelim7:
                    create_reminder(
                        cursor,
                        calculation_id,
                        current_user['email'],
                        data.projectName,
                        data.clientName,
                        data.invoiceAmount,
                        data.state,
                        data.notes,
                        'preliminary',
                        data.prelimDeadline,
                        7
                    )
                    reminders_created += 1
                
                if data.reminders.prelim1:
                    create_reminder(
                        cursor,
                        calculation_id,
                        current_user['email'],
                        data.projectName,
                        data.clientName,
                        data.invoiceAmount,
                        data.state,
                        data.notes,
                        'preliminary',
                        data.prelimDeadline,
                        1
                    )
                    reminders_created += 1
            
            # Lien filing reminders
            if data.reminders.lien7:
                create_reminder(
                    cursor,
                    calculation_id,
                    current_user['email'],
                    data.projectName,
                    data.clientName,
                    data.invoiceAmount,
                    data.state,
                    data.notes,
                    'lien',
                    data.lienDeadline,
                    7
                )
                reminders_created += 1
            
            if data.reminders.lien1:
                create_reminder(
                    cursor,
                    calculation_id,
                    current_user['email'],
                    data.projectName,
                    data.clientName,
                    data.invoiceAmount,
                    data.state,
                    data.notes,
                    'lien',
                    data.lienDeadline,
                    1
                )
                reminders_created += 1
            
            conn.commit()
        
        return {
            "success": True,
            "calculationId": calculation_id,
            "remindersCreated": reminders_created,
            "message": f"Project saved with {reminders_created} email reminders"
        }
        
    except Exception as e:
        print(f"Error saving calculation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/calculations/history")
async def get_calculation_history(current_user: dict = Depends(get_current_user)):
    """Get user's calculation history with project details"""
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.project_name,
                        c.client_name,
                        c.invoice_amount,
                        c.state,
                        c.state_code,
                        c.invoice_date,
                        c.prelim_deadline,
                        c.lien_deadline,
                        c.notes,
                        c.created_at,
                        COUNT(r.id) as active_reminders
                    FROM calculations c
                    LEFT JOIN email_reminders r ON c.id = r.calculation_id AND r.alert_sent = false
                    WHERE c.user_email = %s
                    GROUP BY c.id
                    ORDER BY c.created_at DESC
                    LIMIT 50
                """, (current_user['email'],))
            else:
                cursor.execute("""
                    SELECT 
                        c.id,
                        c.project_name,
                        c.client_name,
                        c.invoice_amount,
                        c.state,
                        c.state_code,
                        c.invoice_date,
                        c.prelim_deadline,
                        c.lien_deadline,
                        c.notes,
                        c.created_at,
                        COUNT(r.id) as active_reminders
                    FROM calculations c
                    LEFT JOIN email_reminders r ON c.id = r.calculation_id AND r.alert_sent = 0
                    WHERE c.user_email = ?
                    GROUP BY c.id
                    ORDER BY c.created_at DESC
                    LIMIT 50
                """, (current_user['email'],))
            
            calculations = []
            for row in cursor.fetchall():
                # Handle both dict and tuple results
                if isinstance(row, dict):
                    calculations.append({
                        'id': row['id'],
                        'projectName': row['project_name'],
                        'clientName': row['client_name'],
                        'invoiceAmount': float(row['invoice_amount']) if row['invoice_amount'] else None,
                        'state': row['state'],
                        'stateCode': row['state_code'],
                        'invoiceDate': row['invoice_date'],
                        'prelimDeadline': row['prelim_deadline'],
                        'lienDeadline': row['lien_deadline'],
                        'notes': row['notes'],
                        'createdAt': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']),
                        'activeReminders': row['active_reminders']
                    })
                else:
                    # Tuple result
                    calculations.append({
                        'id': row[0],
                        'projectName': row[1],
                        'clientName': row[2],
                        'invoiceAmount': float(row[3]) if row[3] else None,
                        'state': row[4],
                        'stateCode': row[5],
                        'invoiceDate': row[6],
                        'prelimDeadline': row[7],
                        'lienDeadline': row[8],
                        'notes': row[9],
                        'createdAt': row[10].isoformat() if hasattr(row[10], 'isoformat') else str(row[10]),
                        'activeReminders': row[11]
                    })
        
        return {
            "success": True,
            "calculations": calculations
        }
        
    except Exception as e:
        print(f"Error fetching calculation history: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

