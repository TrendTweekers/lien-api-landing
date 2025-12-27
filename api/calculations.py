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
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = ?", (token,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            # Extract fields - handle both dict-like and tuple results
            try:
                if isinstance(user, dict):
                    user_id = user.get('id')
                    email = user.get('email', '')
                    subscription_status = user.get('subscription_status', '')
                else:
                    # Tuple/list result
                    user_id = user[0] if len(user) > 0 else None
                    email = user[1] if len(user) > 1 else ''
                    subscription_status = user[2] if len(user) > 2 else ''
            except (TypeError, KeyError, IndexError):
                raise HTTPException(status_code=401, detail="Invalid user data")
            
            if subscription_status not in ['active', 'trialing']:
                raise HTTPException(status_code=403, detail="Subscription expired")
            
            return {
                "id": user_id,
                "email": email,
                "subscription_status": subscription_status,
                "unlimited": True
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
    
    print(f"=" * 60)
    print(f"🔍 SAVE CALCULATION DEBUG")
    print(f"=" * 60)
    print(f"User email: {current_user.get('email')}")
    print(f"Project name: {data.projectName}")
    print(f"Client name: {data.clientName}")
    print(f"Invoice amount: {data.invoiceAmount}")
    print(f"Notes: {data.notes}")
    print(f"State: {data.state}")
    print(f"State code: {data.stateCode}")
    print(f"Invoice date: {data.invoiceDate}")
    print(f"Prelim deadline: {data.prelimDeadline}")
    print(f"Prelim days: {data.prelimDeadlineDays}")
    print(f"Lien deadline: {data.lienDeadline}")
    print(f"Lien days: {data.lienDeadlineDays}")
    print(f"Reminders: {data.reminders}")
    print(f"QuickBooks Invoice ID: {data.quickbooksInvoiceId}")
    print(f"DB Type: {DB_TYPE}")
    print(f"=" * 60)
    
    try:
        print(f"📝 Getting database connection...")
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            print(f"✅ Database connection established")
            
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
                print(f"📝 Executing PostgreSQL INSERT query...")
                print(f"   Values: email={current_user['email']}, project={data.projectName}, client={data.clientName}")
                print(f"   invoice_amount={data.invoiceAmount}, state={data.state}, state_code={data.stateCode}")
                print(f"   invoice_date={data.invoiceDate}, prelim_deadline={data.prelimDeadline}")
                print(f"   lien_deadline={data.lienDeadline}, quickbooks_id={data.quickbooksInvoiceId}")
                
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
                print(f"✅ INSERT executed successfully")
                
                result = cursor.fetchone()
                print(f"📊 Result from fetchone(): {result}")
                print(f"📊 Result type: {type(result)}")
                
                if not result:
                    conn.rollback()
                    print(f"❌ ERROR: fetchone() returned None!")
                    raise Exception("Failed to insert calculation into database - no ID returned")
                
                # RealDictCursor (PostgreSQL) and sqlite3.Row both support dict-like access
                calculation_id = result['id']
                print(f"✅ Calculation ID: {calculation_id}")
            else:
                print(f"📝 Executing SQLite INSERT query...")
                print(f"   Values: email={current_user['email']}, project={data.projectName}, client={data.clientName}")
                print(f"   invoice_amount={data.invoiceAmount}, state={data.state}, state_code={data.stateCode}")
                print(f"   invoice_date={data.invoiceDate}, prelim_deadline={data.prelimDeadline}")
                print(f"   lien_deadline={data.lienDeadline}, quickbooks_id={data.quickbooksInvoiceId}")
                
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
                print(f"✅ INSERT executed successfully")
                
                calculation_id = cursor.lastrowid
                print(f"✅ Calculation ID (from lastrowid): {calculation_id}")
            
            # 2. Set up email reminders based on user preferences
            print(f"📧 Setting up email reminders...")
            reminders_created = 0
            
            # Preliminary notice reminders (only if prelim deadline exists)
            if data.prelimDeadline:
                print(f"   Prelim deadline exists: {data.prelimDeadline}")
                if data.reminders.prelim7:
                    print(f"   Creating prelim 7-day reminder...")
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
                    print(f"   ✅ Prelim 7-day reminder created")
                
                if data.reminders.prelim1:
                    print(f"   Creating prelim 1-day reminder...")
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
                    print(f"   ✅ Prelim 1-day reminder created")
            else:
                print(f"   No prelim deadline, skipping prelim reminders")
            
            # Lien filing reminders
            if data.reminders.lien7:
                print(f"   Creating lien 7-day reminder...")
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
                print(f"   ✅ Lien 7-day reminder created")
            
            if data.reminders.lien1:
                print(f"   Creating lien 1-day reminder...")
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
                print(f"   ✅ Lien 1-day reminder created")
            
            print(f"📊 Total reminders created: {reminders_created}")
            print(f"💾 Committing transaction...")
            conn.commit()
            print(f"✅ Transaction committed successfully")
        
            print(f"=" * 60)
            print(f"✅ SAVE CALCULATION SUCCESS")
            print(f"   Calculation ID: {calculation_id}")
            print(f"   Reminders Created: {reminders_created}")
            print(f"=" * 60)
        
        return {
            "success": True,
            "calculationId": calculation_id,
            "remindersCreated": reminders_created,
            "message": f"Project saved with {reminders_created} email reminders"
        }
        
    except Exception as e:
        print(f"=" * 60)
        print(f"❌ EXCEPTION in save_calculation:")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)}")
        print(f"=" * 60)
        import traceback
        traceback.print_exc()
        print(f"=" * 60)
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

