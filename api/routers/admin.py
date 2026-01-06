from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Query, Header
from starlette.requests import Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from api.database import get_db, get_db_cursor, DB_TYPE, BASE_DIR
from api.services.email import send_broker_notification, send_email_sync
from api.services.payout_ledger import compute_broker_ledger, compute_all_brokers_ledgers
from api.calculators import STATE_CODE_TO_NAME
from api.routers.auth import get_current_user
import os
import json
import csv
import io
import traceback
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import subprocess
import sys
import sqlite3
import secrets

# Feature flags
PAYOUT_LEDGER_AVAILABLE = True

# Initialize router
router = APIRouter()
logger = logging.getLogger(__name__)

def require_admin_api_key(request: Request):
    """Require admin API key via X-ADMIN-KEY header (case-insensitive)"""
    admin_api_key = os.getenv("ADMIN_API_KEY", "")
    # Read header case-insensitively
    x_admin_key = ""
    for header_name, header_value in request.headers.items():
        if header_name.lower() == "x-admin-key":
            x_admin_key = header_value.strip()
            break
    
    # Debug logging (do NOT log secret values)
    env_present = bool(admin_api_key)
    header_present = bool(x_admin_key)
    header_len = len(x_admin_key) if x_admin_key else 0
    logger.info(f"[Admin Auth] env_present={env_present} header_present={header_present} header_len={header_len}")
    
    if not admin_api_key:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_API_KEY not configured"
        )
    
    if not x_admin_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-ADMIN-KEY"
        )
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_admin_key, admin_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid X-ADMIN-KEY"
        )
    
    return {"authenticated": True}

def require_admin(user: dict = Depends(get_current_user)):
    """Require admin access via session-based auth (no Basic Auth popup)"""
    # Allowlist admins (env first, with safe defaults)
    env = os.getenv("ADMIN_EMAILS", "")
    allow = [e.strip().lower() for e in env.split(",") if e.strip()]
    allow += ["admin@stackedboost.com"]  # keep your current admin working

    email = (user.get("email") or "").lower()
    if email not in allow:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def ensure_users_table():
    """Ensure users table exists (helper for migration)"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        session_token VARCHAR(255),
                        token_expires TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW(),
                        last_login TIMESTAMP
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE NOT NULL,
                        session_token TEXT,
                        token_expires TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP
                    )
                """)
            conn.commit()
            return True
    except Exception as e:
        print(f"Error creating users table: {e}")
        return False

# ==========================================
# Dashboard Serving Endpoints
# ==========================================

# Admin dashboard routes REMOVED - now handled directly in api/main.py as public routes
# These routes were causing 401 errors due to require_admin dependency
# Routes are now defined in api/main.py without authentication

# ==========================================
# Admin API Endpoints - Stats & General
# ==========================================

@router.get("/api/admin/stats")
async def get_admin_stats(_auth: dict = Depends(require_admin_api_key)):
    """Get admin dashboard statistics"""
    try:
        with get_db() as db:
            # Check if tables exist
            table_names = []
            if DB_TYPE != 'postgresql':
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                table_names = [t[0] for t in tables]
            
            # Count active customers
            customers_count = 0
            if DB_TYPE == 'postgresql' or 'customers' in table_names:
                try:
                    if DB_TYPE == 'postgresql':
                         with db.cursor() as cursor:
                            cursor.execute("SELECT COUNT(*) FROM customers WHERE status='active'")
                            customers_count = cursor.fetchone()[0]
                    else:
                        result = db.execute("SELECT COUNT(*) FROM customers WHERE status='active'").fetchone()
                        customers_count = result[0] if result else 0
                except Exception as e:
                    print(f"Error counting customers: {e}")
            
            # Count approved brokers
            brokers_count = 0
            if DB_TYPE == 'postgresql' or 'brokers' in table_names:
                try:
                    if DB_TYPE == 'postgresql':
                         with db.cursor() as cursor:
                            cursor.execute("SELECT COUNT(*) FROM brokers")
                            brokers_count = cursor.fetchone()[0]
                    else:
                        result = db.execute("SELECT COUNT(*) FROM brokers").fetchone()
                        brokers_count = result[0] if result else 0
                except Exception as e:
                    print(f"Error counting brokers: {e}")
            
            # Calculate revenue
            revenue_result = 0
            if DB_TYPE == 'postgresql' or 'customers' in table_names:
                try:
                    if DB_TYPE == 'postgresql':
                         with db.cursor() as cursor:
                            cursor.execute("SELECT SUM(amount) FROM customers WHERE status='active'")
                            res = cursor.fetchone()
                            revenue_result = float(res[0]) if res and res[0] else 0
                    else:
                        result = db.execute("SELECT SUM(amount) FROM customers WHERE status='active'").fetchone()
                        revenue_result = float(result[0]) if result and result[0] else 0
                except Exception as e:
                    print(f"Error calculating revenue: {e}")
            
            return {
                "customers": customers_count,
                "brokers": brokers_count,
                "revenue": float(revenue_result)
            }
    except Exception as e:
        print(f"Error getting admin stats: {e}")
        return {
            "customers": 0,
            "brokers": 0,
            "revenue": 0,
            "error": str(e)
        }

@router.get("/api/admin/api-usage-stats")
async def get_api_usage_stats(_auth: dict = Depends(require_admin_api_key)):
    """Get API usage statistics"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Initialize stats
            stats = {
                "total_calls_today": 0,
                "total_calls_week": 0,
                "total_calls_month": 0,
                "error_rate": 0,
                "most_used_states": []
            }
            
            # Date ranges
            now = datetime.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=7)
            month_start = now - timedelta(days=30)
            
            # 1. Count calls by period (using calculations table)
            # Check if calculations table exists
            table_check = "SELECT name FROM sqlite_master WHERE type='table' AND name='calculations'"
            if DB_TYPE == 'postgresql':
                table_check = "SELECT to_regclass('public.calculations')"
            
            cursor.execute(table_check)
            if cursor.fetchone():
                # Today
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM calculations WHERE created_at >= %s", (today_start,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM calculations WHERE created_at >= ?", (today_start,))
                result = cursor.fetchone()
                stats["total_calls_today"] = result[0] if result else 0
                
                # Week
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM calculations WHERE created_at >= %s", (week_start,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM calculations WHERE created_at >= ?", (week_start,))
                result = cursor.fetchone()
                stats["total_calls_week"] = result[0] if result else 0
                
                # Month
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM calculations WHERE created_at >= %s", (month_start,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM calculations WHERE created_at >= ?", (month_start,))
                result = cursor.fetchone()
                stats["total_calls_month"] = result[0] if result else 0
                
                # Most used states
                cursor.execute("""
                    SELECT state, COUNT(*) as count 
                    FROM calculations 
                    GROUP BY state 
                    ORDER BY count DESC 
                    LIMIT 5
                """)
                rows = cursor.fetchall()
                for row in rows:
                    if isinstance(row, dict):
                        stats["most_used_states"].append({"state": row.get('state') or 'Unknown', "count": row.get('count')})
                    else:
                        stats["most_used_states"].append({"state": row[0] or 'Unknown', "count": row[1]})
            
            # 2. Error rate (using error_logs table)
            # Check if error_logs table exists
            table_check = "SELECT name FROM sqlite_master WHERE type='table' AND name='error_logs'"
            if DB_TYPE == 'postgresql':
                table_check = "SELECT to_regclass('public.error_logs')"
            
            cursor.execute(table_check)
            if cursor.fetchone():
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM error_logs WHERE created_at >= %s", (month_start,))
                else:
                    cursor.execute("SELECT COUNT(*) FROM error_logs WHERE created_at >= ?", (month_start,))
                result = cursor.fetchone()
                error_count = result[0] if result else 0
                
                total_calls = stats["total_calls_month"]
                if total_calls > 0:
                    stats["error_rate"] = round((error_count / total_calls) * 100, 2)
            
            return {"stats": stats}
            
    except Exception as e:
        logger.error(f"Error getting API usage stats: {e}")
        # Return empty stats on error so frontend doesn't crash
        return {
            "stats": {
                "total_calls_today": 0,
                "total_calls_week": 0,
                "total_calls_month": 0,
                "error_rate": 0,
                "most_used_states": []
            }
        }

@router.get("/api/admin/analytics/comprehensive")
async def get_comprehensive_analytics(_auth: dict = Depends(require_admin_api_key)):
    """Get comprehensive analytics for charts"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # 1. Daily Usage (Last 30 days)
            daily_usage = []
            month_start = datetime.now() - timedelta(days=30)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count 
                    FROM calculations 
                    WHERE created_at >= %s 
                    GROUP BY DATE(created_at) 
                    ORDER BY date
                """, (month_start,))
            else:
                cursor.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count 
                    FROM calculations 
                    WHERE created_at >= ? 
                    GROUP BY DATE(created_at) 
                    ORDER BY date
                """, (month_start,))
            
            rows = cursor.fetchall()
            for row in rows:
                if isinstance(row, dict):
                    daily_usage.append({"date": str(row['date']), "count": row['count']})
                else:
                    daily_usage.append({"date": str(row[0]), "count": row[1]})
            
            # 2. State Distribution (All time)
            state_distribution = []
            cursor.execute("""
                SELECT state, COUNT(*) as count 
                FROM calculations 
                GROUP BY state 
                ORDER BY count DESC
            """)
            rows = cursor.fetchall()
            for row in rows:
                if isinstance(row, dict):
                    state_distribution.append({"name": row.get('state') or "Unknown", "value": row.get('count')})
                else:
                    state_distribution.append({"name": row[0] or "Unknown", "value": row[1]})
            
            # 3. Top Users (All time)
            user_activity = []
            try:
                cursor.execute("""
                    SELECT user_email, COUNT(*) as count 
                    FROM calculations 
                    WHERE user_email IS NOT NULL AND user_email != ''
                    GROUP BY user_email 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
                rows = cursor.fetchall()
                for row in rows:
                    if isinstance(row, dict):
                        user_activity.append({"email": row.get('user_email'), "calls": row.get('count')})
                    else:
                        user_activity.append({"email": row[0], "calls": row[1]})
            except Exception as e:
                logger.warning(f"Could not fetch user activity (schema mismatch?): {e}")
                # Try fallback to user_id if available (for local testing support)
                try:
                     cursor.execute("""
                        SELECT user_id, COUNT(*) as count 
                        FROM calculations 
                        WHERE user_id IS NOT NULL
                        GROUP BY user_id 
                        ORDER BY count DESC 
                        LIMIT 10
                    """)
                     rows = cursor.fetchall()
                     for row in rows:
                        uid = row.get('user_id') if isinstance(row, dict) else row[0]
                        count = row.get('count') if isinstance(row, dict) else row[1]
                        user_activity.append({"email": f"User {uid}", "calls": count})
                except:
                    pass
            
            return {
                "daily_usage": daily_usage,
                "state_distribution": state_distribution,
                "user_activity": user_activity
            }
            
    except Exception as e:
        logger.error(f"Error getting comprehensive analytics: {e}")
        return {
            "daily_usage": [],
            "state_distribution": [],
            "user_activity": [],
            "error": str(e)
        }

@router.get("/api/admin/customers")
async def get_customers_api(_auth: dict = Depends(require_admin_api_key)):
    """Return list of customers"""
    try:
        with get_db() as db:
            # Check if table exists (SQLite only)
            if DB_TYPE != 'postgresql':
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                table_names = [t[0] for t in tables]
                if 'customers' not in table_names:
                    return []
            
            # Try different column names for compatibility
            try:
                if DB_TYPE == 'postgresql':
                     with db.cursor() as cursor:
                        cursor.execute("""
                            SELECT email, calls_used, status 
                            FROM customers 
                            ORDER BY created_at DESC
                        """)
                        columns = [desc[0] for desc in cursor.description]
                        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                else:
                    rows = db.execute("""
                        SELECT email, calls_used, status 
                        FROM customers 
                        ORDER BY created_at DESC
                    """).fetchall()
            except Exception:
                # Fallback if created_at doesn't exist
                try:
                    if DB_TYPE == 'postgresql':
                         with db.cursor() as cursor:
                            cursor.execute("""
                                SELECT email, api_calls, status 
                                FROM customers 
                                ORDER BY email
                            """)
                            columns = [desc[0] for desc in cursor.description]
                            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    else:
                        rows = db.execute("""
                            SELECT email, api_calls, status 
                            FROM customers 
                            ORDER BY email
                        """).fetchall()
                except Exception as e:
                    print(f"Error querying customers: {e}")
                    return []
            
            return [
                {
                    "email": row['email'] if isinstance(row, dict) else (row['email'] if 'email' in row.keys() else row[0]),
                    "calls": (row.get('calls_used') if isinstance(row, dict) else row.get('calls_used')) or (row.get('api_calls') if isinstance(row, dict) else row.get('api_calls')) or 0,
                    "status": row.get('status') if isinstance(row, dict) else (row.get('status') or 'active')
                }
                for row in rows
            ]
    except Exception as e:
        print(f"Error in get_customers_api: {e}")
        return []

@router.get("/api/admin/brokers")
async def get_brokers_api(_auth: dict = Depends(require_admin_api_key)):
    """Return list of brokers with payment info"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Log database path for debugging
            db_info = "Unknown"
            if DB_TYPE != 'postgresql':
                try:
                    # Get list of attached databases
                    db_list_rows = conn.execute("PRAGMA database_list").fetchall()
                    # Convert row objects to list of dicts/tuples for readability
                    db_list = []
                    for row in db_list_rows:
                        # Row object to tuple/dict
                        if hasattr(row, 'keys'):
                            db_list.append(dict(row))
                        else:
                            db_list.append(tuple(row))
                            
                    logger.info(f"Connected to databases: {db_list}")
                    db_info = str(db_list)
                    
                    # Debug: check table count directly
                    count_check = conn.execute("SELECT COUNT(*) FROM brokers").fetchone()
                    logger.info(f"Direct count from brokers table: {count_check[0]}")
                except Exception as e:
                    logger.error(f"Could not get database list: {e}")
                    db_info = f"Error: {str(e)}"

            # Get brokers with verified columns
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, commission_model, total_referrals, total_earned, status, created_at, referral_code, payment_method
                    FROM brokers
                    ORDER BY id DESC
                """)
            else:
                # SQLite: Use the schema that actually exists (referrals, earned)
                # verified via check_schema.py: id, name, email, model, referrals, earned
                cursor.execute("""
                    SELECT id, name, email, model, referrals, earned, 'active' as status, CURRENT_TIMESTAMP as created_at, id as referral_code, 'Unlinked' as payment_method
                    FROM brokers
                    ORDER BY id DESC
                """)
            
            rows = cursor.fetchall()
            logger.info(f"Database query result: {rows}")
            logger.info(f"Number of brokers found: {len(rows)}")
            
            brokers_list = []
            for row in rows:
                if isinstance(row, dict):
                    # Row factory might be returning dict
                    # Map earned to total_paid because that's what the frontend displays
                    earned_val = row.get('total_earned') if row.get('total_earned') is not None else row.get('earned', 0.0)
                    
                    broker_dict = {
                        "id": row.get('id'),
                        "name": row.get('name') or row.get('email') or 'N/A',
                        "email": row.get('email') or 'N/A',
                        "referrals": row.get('total_referrals') if row.get('total_referrals') is not None else row.get('referrals', 0),
                        "total_referrals": row.get('total_referrals') if row.get('total_referrals') is not None else row.get('referrals', 0),
                        "earned": earned_val,
                        "total_earned": earned_val,
                        "status": row.get('status', 'active'),
                        "payment_method": row.get('payment_method') or 'Unlinked',
                        "commission_model": row.get('commission_model') or row.get('model'),
                        "referral_code": row.get('referral_code') or row.get('id'),
                        "payment_status": 'active', # Default to active so badges show up
                        "last_payment_date": None,
                        "total_paid": earned_val, # Map earned to total_paid for frontend display
                        "created_at": row.get('created_at'),
                        "stripe_account_id": None
                    }
                else:
                    # Tuple Mapping (Matches both PostgreSQL and SQLite query structure)
                    # 0: id, 1: name, 2: email, 3: commission_model/model, 4: total_referrals/referrals, 
                    # 5: total_earned/earned, 6: status, 7: created_at, 8: referral_code, 9: payment_method
                    
                    referrals_val = row[4] if row[4] is not None else 0
                    earned_val = row[5] if row[5] is not None else 0.0
                    
                    broker_dict = {
                        "id": row[0],
                        "name": row[1] if row[1] else (row[2] if len(row) > 2 else 'N/A'),
                        "email": row[2],
                        "commission_model": row[3],
                        "referrals": referrals_val,
                        "total_referrals": referrals_val,
                        "earned": earned_val,
                        "total_earned": earned_val,
                        "status": row[6] if row[6] else 'active',
                        "created_at": row[7],
                        "referral_code": row[8] if row[8] else row[0],
                        "payment_method": row[9] if row[9] else 'Unlinked',
                        "stripe_account_id": None,
                        # Synthetic fields
                        "payment_status": 'active',
                        "last_payment_date": None,
                        "total_paid": earned_val # Map earned to total_paid for frontend display

                    }
                brokers_list.append(broker_dict)
            
            return {
                "brokers": brokers_list,
                "debug_info": {
                    "db_type": DB_TYPE,
                    "connected_dbs": db_info,
                    "rows_found": len(rows)
                }
            }
            
    except Exception as e:
        logger.error(f"Error in get_brokers_api: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "brokers": [],
            "error": str(e),
            "trace": traceback.format_exc()
        }

@router.delete("/api/admin/delete-broker/{broker_id}")
async def delete_broker(broker_id: int, _auth: dict = Depends(require_admin_api_key)):
    """Delete a broker and all their referrals"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if broker exists
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT id FROM brokers WHERE id = ?", (broker_id,))
            
            broker = cursor.fetchone()
            if not broker:
                raise HTTPException(status_code=404, detail=f"Broker with id {broker_id} not found")
            
            # Delete referrals first (foreign key constraint)
            # Cast broker_id to text for PostgreSQL since referrals.broker_id is VARCHAR
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM referrals WHERE broker_id = %s::text", (str(broker_id),))
                cursor.execute("DELETE FROM brokers WHERE id = %s", (broker_id,))
            else:
                # SQLite: broker_id might be stored as text in referrals table
                cursor.execute("DELETE FROM referrals WHERE broker_id = ?", (str(broker_id),))
                cursor.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
            
            conn.commit()
            
            logger.info(f"Broker {broker_id} and all associated referrals deleted by {user.get('email', 'unknown')}")
            
            return {
                "success": True,
                "message": f"Broker {broker_id} and all associated referrals deleted successfully"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting broker {broker_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete broker: {str(e)}"
        )

@router.get("/api/admin/email-captures")
async def get_email_captures_api(_auth: dict = Depends(require_admin_api_key)):
    """Get all email captures from calculator email gate"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Query email captures
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, ip_address as ip, created_at::text as timestamp
                    FROM email_captures 
                    ORDER BY created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT email, ip, timestamp
                    FROM email_captures 
                    ORDER BY timestamp DESC
                """)
            
            captures = cursor.fetchall()
            
            result = []
            for c in captures:
                if isinstance(c, dict):
                    result.append({
                        "email": c.get('email', ''),
                        "ip": c.get('ip') or "N/A",
                        "timestamp": c.get('timestamp', '')
                    })
                elif hasattr(c, 'keys'):
                    result.append({
                        "email": c['email'] if 'email' in c.keys() else (c[0] if len(c) > 0 else ""),
                        "ip": (c['ip'] if 'ip' in c.keys() else (c[1] if len(c) > 1 else "N/A")) or "N/A",
                        "timestamp": c['timestamp'] if 'timestamp' in c.keys() else (c[2] if len(c) > 2 else "")
                    })
                else:
                    result.append({
                        "email": c[0] if len(c) > 0 else "",
                        "ip": c[1] if len(c) > 1 and c[1] else "N/A",
                        "timestamp": c[2] if len(c) > 2 else ""
                    })
            
            return result
    except Exception as e:
        print(f"Error in get_email_captures_api: {e}")
        return []

# ==========================================
# Partner & Broker Management
# ==========================================

@router.get("/api/admin/partner-applications")
async def get_partner_applications(request: Request, status: str = "all", _auth: dict = Depends(require_admin_api_key)):
    """Get partner applications for admin dashboard"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            else:
                # Check if table exists (SQLite)
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='partner_applications'
                """)
                if not cursor.fetchone():
                    return {"applications": [], "total": 0}
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            applications = []
            for row in rows:
                if isinstance(row, dict):
                    applications.append(row)
                else:
                    # Convert sqlite3.Row to dict
                    applications.append(dict(row))
            
            # Apply status filter
            if status != "all":
                applications = [app for app in applications if app.get('status') == status]
            
            # Convert datetimes to strings
            for app in applications:
                if app.get('created_at'):
                    app['created_at'] = str(app['created_at'])
            
            return {
                "applications": applications,
                "total": len(applications)
            }
            
    except Exception as e:
        print(f"ERROR fetching applications: {e}")
        return {
            "applications": [],
            "total": 0,
            "error": str(e)
        }

@router.get("/api/debug/partner-applications")
async def debug_partner_applications():
    """Debug endpoint to check partner_applications table"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Count total rows
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT COUNT(*) as count FROM partner_applications")
            else:
                # Check if table exists (SQLite)
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='partner_applications'
                """)
                if not cursor.fetchone():
                    return {"message": "Table 'partner_applications' does not exist"}
                cursor.execute("SELECT COUNT(*) as count FROM partner_applications")
            
            count_result = cursor.fetchone()
            if isinstance(count_result, dict):
                total = count_result.get('count', 0)
            elif isinstance(count_result, tuple):
                total = count_result[0] if len(count_result) > 0 else 0
            else:
                total = count_result if count_result else 0
            
            # Get all rows
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            applications = [dict(row) if not isinstance(row, dict) else row for row in rows]
            
            return {
                "total_count": total,
                "rows_returned": len(applications),
                "applications": applications
            }
    except Exception as e:
        return {"error": str(e)}

@router.post("/api/admin/approve-partner")
async def approve_partner(request: Request, _auth: dict = Depends(require_admin_api_key)):
    """Approve a partner application"""
    try:
        data = await request.json()
        email = data.get('email')
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
            
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Update application status
            if DB_TYPE == 'postgresql':
                cursor.execute("UPDATE partner_applications SET status = 'approved' WHERE email = %s", (email,))
            else:
                cursor.execute("UPDATE partner_applications SET status = 'approved' WHERE email = ?", (email,))
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Application not found")
                
            conn.commit()
            
            # Trigger notification (placeholder)
            # send_broker_notification(email, ...)
            
            return {"status": "success", "message": f"Partner {email} approved"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error approving partner: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/deny-partner")
async def deny_partner(request: Request, _auth: dict = Depends(require_admin_api_key)):
    """Deny a partner application"""
    try:
        data = await request.json()
        email = data.get('email')
        
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
            
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("UPDATE partner_applications SET status = 'denied' WHERE email = %s", (email,))
            else:
                cursor.execute("UPDATE partner_applications SET status = 'denied' WHERE email = ?", (email,))
            
            conn.commit()
            return {"status": "success", "message": f"Partner {email} denied"}
    except Exception as e:
        print(f"Error denying partner: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/update-user-email")
async def update_user_email(
    request: Request,
    old_email: str = Query(None, description="Current email (for updates)"),
    new_email: str = Query(None, description="New email address"),
    new_password: str = Query(None, description="New password"),
    _auth: dict = Depends(require_admin_api_key)
):
    """
    Update or create a user account.
    - If old_email exists: Updates email and password
    - If old_email doesn't exist: Creates new user with new_email and password
    """
    import bcrypt
    
    try:
        # Try to get from query params first (for form submission)
        if not old_email or not new_email:
            try:
                data = await request.json()
                old_email = old_email or data.get('old_email')
                new_email = new_email or data.get('new_email')
                new_password = new_password or data.get('new_password')
            except:
                pass
        
        if not new_email:
            raise HTTPException(status_code=400, detail="New email is required")
        
        if not new_password:
            raise HTTPException(status_code=400, detail="Password is required")
        
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Hash the password
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        if DB_TYPE == 'postgresql':
            password_hash_str = password_hash.decode('utf-8')
        else:
            password_hash_str = password_hash
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if old_email exists (for update) or if new_email already exists
            user_exists = False
            user_id = None
            
            if old_email:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT id FROM users WHERE email = %s", (old_email.lower(),))
                else:
                    cursor.execute("SELECT id FROM users WHERE email = ?", (old_email.lower(),))
                user_result = cursor.fetchone()
                if user_result:
                    user_exists = True
                    if isinstance(user_result, dict):
                        user_id = user_result.get('id')
                    else:
                        user_id = user_result[0] if len(user_result) > 0 else None
            
            # Check if new_email already exists (to prevent duplicates)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id FROM users WHERE email = %s", (new_email.lower(),))
            else:
                cursor.execute("SELECT id FROM users WHERE email = ?", (new_email.lower(),))
            existing_user = cursor.fetchone()
            
            if existing_user and (not user_exists or (isinstance(existing_user, dict) and existing_user.get('id') != user_id if user_exists else True)):
                raise HTTPException(status_code=400, detail=f"Email {new_email} already exists")
            
            if user_exists:
                # UPDATE existing user
                if DB_TYPE == 'postgresql':
                    cursor.execute(
                        "UPDATE users SET email = %s, password_hash = %s WHERE id = %s",
                        (new_email.lower(), password_hash_str, user_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE users SET email = ?, password_hash = ? WHERE id = ?",
                        (new_email.lower(), password_hash_str, user_id)
                    )
                conn.commit()
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "success",
                        "message": "User updated successfully",
                        "old_email": old_email,
                        "new_email": new_email,
                        "password": new_password,
                        "note": "User can now login with the new email and password"
                    }
                )
            else:
                # CREATE new user
                if DB_TYPE == 'postgresql':
                    cursor.execute(
                        """INSERT INTO users (email, password_hash, subscription_status, created_at)
                           VALUES (%s, %s, 'active', NOW())""",
                        (new_email.lower(), password_hash_str)
                    )
                else:
                    cursor.execute(
                        """INSERT INTO users (email, password_hash, subscription_status, created_at)
                           VALUES (?, ?, 'active', datetime('now'))""",
                        (new_email.lower(), password_hash_str)
                    )
                conn.commit()
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "success",
                        "message": "User created successfully",
                        "old_email": None,
                        "new_email": new_email,
                        "password": new_password,
                        "note": "New user account created. User can login with this email and password."
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating/creating user: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# Migrations
# ==========================================

@router.get("/api/admin/fix-state-names-now")
async def fix_state_names_endpoint(_auth: dict = Depends(require_admin_api_key)):
    """Temporary endpoint to fix state names in database"""
    try:
        from api.migrations.fix_state_names import fix_state_names
        result = fix_state_names()
        return {
            "success": True,
            "message": "State names fixed successfully",
            "updates_count": result.get("updates_count", 0),
            "updated_states": result.get("updated_states", []),
            "oklahoma_status": result.get("oklahoma_status"),
            "errors": result.get("errors", [])
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/admin/migrate-payout-batches")
async def migrate_payout_batches(_auth: dict = Depends(require_admin_api_key)):
    """
    Migration endpoint to create broker_payout_batches table.
    Safe and idempotent - can be run multiple times.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payout_batches (
                        id SERIAL PRIMARY KEY,
                        broker_id INTEGER NOT NULL,
                        broker_name VARCHAR(255) NOT NULL,
                        broker_email VARCHAR(255) NOT NULL,
                        total_amount DECIMAL(10,2) NOT NULL,
                        currency VARCHAR(10) DEFAULT 'USD',
                        payment_method VARCHAR(50) NOT NULL,
                        transaction_id VARCHAR(255),
                        notes TEXT,
                        status VARCHAR(50) DEFAULT 'pending',
                        referral_ids TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP,
                        created_by_admin VARCHAR(255)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_broker ON broker_payout_batches(broker_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_status ON broker_payout_batches(status)
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payout_batches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_id INTEGER NOT NULL,
                        broker_name TEXT NOT NULL,
                        broker_email TEXT NOT NULL,
                        total_amount REAL NOT NULL,
                        currency TEXT DEFAULT 'USD',
                        payment_method TEXT NOT NULL,
                        transaction_id TEXT,
                        notes TEXT,
                        status TEXT DEFAULT 'pending',
                        referral_ids TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP,
                        created_by_admin TEXT
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_broker ON broker_payout_batches(broker_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_status ON broker_payout_batches(status)
                """)
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Payout batches migration completed successfully",
                    "database_type": DB_TYPE
                }
            )
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "database_type": DB_TYPE,
                "traceback": traceback.format_exc()
            }
        )

@router.get("/api/admin/migrate-payout-ledger")
async def migrate_payout_ledger(_auth: dict = Depends(require_admin_api_key)):
    """
    Migration endpoint to add payout ledger columns to referrals table.
    Safe and idempotent - can be run multiple times.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # Add payment_date column if it doesn't exist
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'referrals' 
                            AND column_name = 'payment_date'
                        ) THEN
                            ALTER TABLE referrals ADD COLUMN payment_date TIMESTAMP;
                            RAISE NOTICE 'Added payment_date column';
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'referrals' 
                            AND column_name = 'paid_batch_id'
                        ) THEN
                            ALTER TABLE referrals ADD COLUMN paid_batch_id VARCHAR(255);
                            RAISE NOTICE 'Added paid_batch_id column';
                        END IF;
                    END $$;
                """)
                
                # Update existing referrals: set payment_date = created_at if null
                cursor.execute("""
                    UPDATE referrals 
                    SET payment_date = created_at 
                    WHERE payment_date IS NULL
                """)
                
                # Add paid_batch_id column to broker_payments if it doesn't exist
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'broker_payments' 
                            AND column_name = 'paid_referral_ids'
                        ) THEN
                            ALTER TABLE broker_payments ADD COLUMN paid_referral_ids TEXT;
                            RAISE NOTICE 'Added paid_referral_ids column';
                        END IF;
                    END $$;
                """)
            else:
                # SQLite: Add columns if they don't exist
                try:
                    cursor.execute("ALTER TABLE referrals ADD COLUMN payment_date TIMESTAMP")
                except Exception:
                    pass  # Column already exists
                
                try:
                    cursor.execute("ALTER TABLE referrals ADD COLUMN paid_batch_id TEXT")
                except Exception:
                    pass  # Column already exists
                
                try:
                    cursor.execute("ALTER TABLE broker_payments ADD COLUMN paid_referral_ids TEXT")
                except Exception:
                    pass  # Column already exists
                
                # Update existing referrals: set payment_date = created_at if null
                cursor.execute("""
                    UPDATE referrals 
                    SET payment_date = created_at 
                    WHERE payment_date IS NULL
                """)
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Payout ledger migration completed successfully",
                    "database_type": DB_TYPE
                }
            )
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "database_type": DB_TYPE,
                "traceback": traceback.format_exc()
            }
        )

@router.get("/api/admin/migrate-payment-tracking")
async def migrate_payment_tracking(_auth: dict = Depends(require_admin_api_key)):
    """Migration endpoint to add payment tracking columns to brokers table"""
    migrations = []
    db_type = None
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            db_type = DB_TYPE

            # Add payment tracking columns
            column_definitions = [
                ("first_payment_date", "TIMESTAMP"),
                ("last_payment_date", "TIMESTAMP"),
                ("next_payment_due", "TIMESTAMP"),
                ("total_paid", "DECIMAL(10,2) DEFAULT 0"),
                ("payment_status", "VARCHAR(50) DEFAULT 'pending_first_payment'")
            ]

            for col_name, col_type in column_definitions:
                if db_type == 'postgresql':
                    cursor.execute(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = 'brokers' AND column_name = '{col_name}'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN {col_name} {col_type};
                            END IF;
                        END $$;
                    """)
                    migrations.append(f'✅ Added column: {col_name}')
                else: # SQLite
                    try:
                        cursor.execute(f"ALTER TABLE brokers ADD COLUMN {col_name} {col_type}")
                        migrations.append(f'✅ Added column: {col_name}')
                    except Exception as e:
                        if "duplicate column name" in str(e).lower():
                            migrations.append(f'ℹ️ Column already exists: {col_name}')
                        else:
                            migrations.append(f'❌ Failed to add column {col_name}: {e}')

            conn.commit()
            return {
                "status": "success",
                "message": "Payment tracking migration completed",
                "migrations": migrations,
                "database_type": db_type
            }

    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {e}",
                "traceback": traceback.format_exc(),
                "database_type": db_type
            }
        )

@router.get("/api/admin/migrate-users-table")
async def migrate_users_table(_auth: dict = Depends(require_admin_api_key)):
    """
    Migration endpoint to create users table.
    Safe and idempotent - can be run multiple times.
    """
    import traceback
    
    try:
        created = ensure_users_table()
        return {
            "status": "ok",
            "created": bool(created)  # Ensure boolean, not int
        }
    except Exception as e:
        error_repr = repr(e)
        error_msg = str(e)
        # Try to get SQLSTATE if available (PostgreSQL)
        sqlstate = getattr(e, 'pgcode', None) or getattr(e, 'sqlstate', None)
        
        # Build detailed error message
        if sqlstate:
            detail_msg = f"{error_repr} (SQLSTATE: {sqlstate})"
        else:
            detail_msg = error_repr
        
        # Log full exception
        print(f"❌ Migration error: {detail_msg}")
        print(f"   Error message: {error_msg}")
        traceback.print_exc()
        
        # Return JSON error response
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "detail": detail_msg
            }
        )

@router.get("/api/admin/migrate-payment-columns")
async def migrate_payment_columns(_auth: dict = Depends(require_admin_api_key)):
    """Migration endpoint to add international payment columns to brokers table"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # PostgreSQL migration
                migrations = []
                
                # Add new international payment columns
                new_columns = [
                    ('payment_method', 'VARCHAR(50)'),
                    ('payment_email', 'VARCHAR(255)'),
                    ('iban', 'VARCHAR(255)'),
                    ('swift_code', 'VARCHAR(100)'),
                    ('bank_name', 'VARCHAR(255)'),
                    ('bank_address', 'TEXT'),
                    ('account_holder_name', 'VARCHAR(255)'),
                    ('crypto_wallet', 'VARCHAR(255)'),
                    ('crypto_currency', 'VARCHAR(50)'),
                    ('tax_id', 'VARCHAR(100)')
                ]
                
                for column_name, column_type in new_columns:
                    try:
                        cursor.execute(f"""
                            DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name = 'brokers' AND column_name = '{column_name}'
                                ) THEN
                                    ALTER TABLE brokers ADD COLUMN {column_name} {column_type};
                                END IF;
                            END $$;
                        """)
                        migrations.append(f"✅ Added column: {column_name}")
                        print(f"✅ Added column: {column_name}")
                    except Exception as e:
                        migrations.append(f"⚠️ Column {column_name}: {str(e)}")
                        print(f"⚠️ Column {column_name} error: {e}")
                
                # Remove old US-only columns (if they exist)
                old_columns = ['bank_account_number', 'bank_routing_number']
                for column_name in old_columns:
                    try:
                        cursor.execute(f"""
                            DO $$ 
                            BEGIN
                                IF EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name = 'brokers' AND column_name = '{column_name}'
                                ) THEN
                                    ALTER TABLE brokers DROP COLUMN {column_name};
                                END IF;
                            END $$;
                        """)
                        migrations.append(f"✅ Removed column: {column_name}")
                        print(f"✅ Removed column: {column_name}")
                    except Exception as e:
                        migrations.append(f"⚠️ Could not remove {column_name}: {str(e)}")
                        print(f"⚠️ Could not remove {column_name}: {e}")
                
                conn.commit()
                
                return {
                    "status": "success",
                    "message": "Migration completed",
                    "migrations": migrations,
                    "database_type": "postgresql"
                }
            else:
                # SQLite migration
                migrations = []
                
                # Add new columns
                new_columns = [
                    ('payment_method', 'TEXT'),
                    ('payment_email', 'TEXT'),
                    ('iban', 'TEXT'),
                    ('swift_code', 'TEXT'),
                    ('bank_name', 'TEXT'),
                    ('bank_address', 'TEXT'),
                    ('account_holder_name', 'TEXT'),
                    ('crypto_wallet', 'TEXT'),
                    ('crypto_currency', 'TEXT'),
                    ('tax_id', 'TEXT')
                ]
                
                for column_name, column_type in new_columns:
                    try:
                        cursor.execute(f"ALTER TABLE brokers ADD COLUMN {column_name} {column_type}")
                        migrations.append(f"✅ Added column: {column_name}")
                        print(f"✅ Added column: {column_name}")
                    except Exception as e:
                        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                            migrations.append(f"ℹ️ Column {column_name} already exists")
                        else:
                            migrations.append(f"⚠️ Column {column_name}: {str(e)}")
                
                conn.commit()
                
                return {
                    "status": "success",
                    "message": "Migration completed",
                    "migrations": migrations,
                    "database_type": "sqlite"
                }
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {str(e)}"
            }
        )

@router.get("/api/admin/run-state-migration")
async def run_state_migration(_auth: dict = Depends(require_admin_api_key)):
    """Admin endpoint to run state data migration"""
    try:
        from api.migrations.add_all_states import migrate_states
        result = migrate_states()
        return {
            "success": result.get("success", True),
            "message": "State migration completed successfully",
            "states_updated": ["IN", "LA", "MA", "NJ", "OH", "TX"],
            "migration_result": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/admin/run-sage-migration")
async def run_sage_migration(_auth: dict = Depends(require_admin_api_key)):
    """Run Sage tokens table migration"""
    try:
        from api.migrations.add_sage_tokens import run_migration
        run_migration()
        return {"success": True, "message": "Sage migration completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/run-procore-migration")
async def run_procore_migration(_auth: dict = Depends(require_admin_api_key)):
    """Run Procore tokens table migration"""
    try:
        from api.migrations.add_procore_tokens import run_migration
        run_migration()
        return {"success": True, "message": "Procore migration completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/setup-referrals-table")
async def setup_referrals_table(_auth: dict = Depends(require_admin_api_key)):
    """One-time setup to create referrals table"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create referrals table (PostgreSQL compatible)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        id SERIAL PRIMARY KEY,
                        broker_id VARCHAR(255) NOT NULL,
                        broker_email VARCHAR(255) NOT NULL,
                        customer_email VARCHAR(255) NOT NULL,
                        customer_stripe_id VARCHAR(255),
                        amount DECIMAL(10,2) NOT NULL DEFAULT 299.00,
                        payout DECIMAL(10,2) NOT NULL,
                        payout_type VARCHAR(50) NOT NULL,
                        status VARCHAR(50) DEFAULT 'on_hold',
                        fraud_flags TEXT,
                        hold_until DATE,
                        clawback_until DATE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP,
                        FOREIGN KEY (broker_id) REFERENCES brokers(referral_code)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_broker_id ON referrals(broker_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)")
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_id TEXT NOT NULL,
                        broker_email TEXT NOT NULL,
                        customer_email TEXT NOT NULL,
                        customer_stripe_id TEXT,
                        amount REAL NOT NULL DEFAULT 299.00,
                        payout REAL NOT NULL,
                        payout_type TEXT NOT NULL,
                        status TEXT DEFAULT 'on_hold',
                        fraud_flags TEXT,
                        hold_until DATE,
                        clawback_until DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP,
                        FOREIGN KEY (broker_id) REFERENCES brokers(referral_code)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_broker_id ON referrals(broker_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)")
            
            conn.commit()
            return {"success": True, "message": "Referrals table created successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}



# ==========================================
# Debug & Fixes
# ==========================================

@router.get("/api/admin/debug-pdf-data/{state}")
async def debug_pdf_data(state: str, _auth: dict = Depends(require_admin_api_key)):
    """Debug endpoint to see what data PDF generation uses"""
    try:
        state_upper = state.upper()
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM lien_deadlines WHERE UPPER(state_code) = %s LIMIT 1", (state_upper,))
            else:
                cursor.execute("SELECT * FROM lien_deadlines WHERE UPPER(state_code) = ? LIMIT 1", (state_upper,))
            db_state = cursor.fetchone()
            
            if db_state:
                if isinstance(db_state, dict):
                    db_dict = dict(db_state)
                else:
                    # Generic fetch logic for tuple
                    db_dict = {"data": str(db_state)}
                return {"success": True, "database_row": db_dict}
            else:
                return {"success": False, "error": f"State '{state}' not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/admin/debug/payout-data")
async def get_payout_debug_data(_auth: dict = Depends(require_admin_api_key)):
    """Get debug data for payout system (last 20 records of each type)"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get last 20 referrals
            # Check if subscription_id column exists
            has_subscription_id = False
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'referrals' AND column_name = 'subscription_id'
                    """)
                    has_subscription_id = cursor.fetchone() is not None
                else:
                    cursor.execute("PRAGMA table_info(referrals)")
                    columns = cursor.fetchall()
                    column_names = []
                    for col in columns:
                        if isinstance(col, (list, tuple)):
                            column_names.append(col[1] if len(col) > 1 else '')
                        elif isinstance(col, dict):
                            column_names.append(col.get('name', ''))
                    has_subscription_id = 'subscription_id' in column_names
            except Exception as e:
                print(f"⚠️ Could not check for subscription_id column: {e}")
                has_subscription_id = False
            
            if has_subscription_id:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC LIMIT 20
                    """)
                else:
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC LIMIT 20
                    """)
            else:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, NULL as subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC LIMIT 20
                    """)
                else:
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, NULL as subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC LIMIT 20
                    """)
            
            referrals = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    referrals.append(dict(row))
                else:
                    # Map tuple to dict
                    referrals.append({
                        "id": row[0] if len(row) > 0 else None,
                        "broker_id": row[1] if len(row) > 1 else None,
                        "customer_email": row[2] if len(row) > 2 else None,
                        "customer_stripe_id": row[3] if len(row) > 3 else None,
                        "subscription_id": row[4] if len(row) > 4 else None,
                        "status": row[5] if len(row) > 5 else None,
                        "payment_date": str(row[6]) if len(row) > 6 and row[6] else None,
                        "payout": float(row[7]) if len(row) > 7 and row[7] else 0,
                        "payout_type": row[8] if len(row) > 8 else None,
                        "created_at": str(row[9]) if len(row) > 9 and row[9] else None,
                        "paid_at": str(row[10]) if len(row) > 10 and row[10] else None,
                        "paid_batch_id": row[11] if len(row) > 11 else None
                    })

            # Get last 20 payments
            payments = []
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT * FROM broker_payments ORDER BY paid_at DESC LIMIT 20")
                else:
                    cursor.execute("SELECT * FROM broker_payments ORDER BY paid_at DESC LIMIT 20")
                
                for row in cursor.fetchall():
                     if isinstance(row, dict):
                        payments.append(dict(row))
                     else:
                        # Simplify for tuple
                        payments.append({"data": str(row)})
            except Exception as e:
                print(f"⚠️ Could not fetch broker_payments: {e}")

            # Get last 20 batches
            batches = []
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT * FROM broker_payout_batches ORDER BY created_at DESC LIMIT 20")
                else:
                    cursor.execute("SELECT * FROM broker_payout_batches ORDER BY created_at DESC LIMIT 20")
                
                for row in cursor.fetchall():
                     if isinstance(row, dict):
                        batches.append(dict(row))
                     else:
                        # Simplify for tuple
                        batches.append({"data": str(row)})
            except Exception as e:
                print(f"⚠️ Could not fetch broker_payout_batches: {e}")
            
            return {
                "referrals": referrals,
                "payments": payments,
                "batches": batches
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# Payouts & Finance
# ==========================================

@router.get("/api/admin/brokers-ready-to-pay")
async def get_brokers_ready_to_pay(_auth: dict = Depends(require_admin_api_key)):
    """Get list of brokers who are ready to be paid - Uses canonical payout ledger"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if PAYOUT_LEDGER_AVAILABLE:
                ledgers = compute_all_brokers_ledgers(cursor, DB_TYPE)
                return [l.to_dict() for l in ledgers if l.total_due_now > 0]
            else:
                return []
    except Exception as e:
        print(f"Error getting brokers ready to pay: {e}")
        return []

@router.get("/api/admin/broker-payment-info/{broker_id}")
async def get_broker_payment_info(broker_id: int, _auth: dict = Depends(require_admin_api_key)):
    """Get payment info for a specific broker"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            # Use unmasked query from main.py logic
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, payment_method, payment_email, iban, swift_code,
                           bank_name, bank_address, account_holder_name, crypto_wallet, 
                           crypto_currency, tax_id
                    FROM brokers WHERE id = %s
                """, (broker_id,))
            else:
                cursor.execute("""
                    SELECT id, name, email, payment_method, payment_email, iban, swift_code,
                           bank_name, bank_address, account_holder_name, crypto_wallet, 
                           crypto_currency, tax_id
                    FROM brokers WHERE id = ?
                """, (broker_id,))
            
            broker = cursor.fetchone()
            if not broker:
                raise HTTPException(status_code=404, detail="Broker not found")
                
            if isinstance(broker, dict):
                return broker
            else:
                # Basic tuple to dict mapping if needed, or rely on row factory
                return {"id": broker[0], "name": broker[1], "email": broker[2]} # Simplified
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/broker-ledger/{broker_id}")
async def get_broker_ledger(broker_id: int, _auth: dict = Depends(require_admin_api_key)):
    """Get full payout ledger for a specific broker"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            ledger = compute_broker_ledger(cursor, broker_id, DB_TYPE)
            return ledger.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/mark-paid")
async def mark_payment_paid(request: Request, _auth: dict = Depends(require_admin_api_key)):
    """Mark a broker payment as paid (Manual)"""
    try:
        data = await request.json()
        broker_id = data.get('broker_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method')
        transaction_id = data.get('transaction_id')
        notes = data.get('notes', '')
        
        if not all([broker_id, amount, payment_method, transaction_id]):
            raise HTTPException(status_code=400, detail="Missing required fields")
            
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, amount, payment_method, transaction_id, notes, status, created_at, paid_at)
                    VALUES (%s, %s, %s, %s, %s, 'paid', NOW(), NOW())
                """, (broker_id, amount, payment_method, transaction_id, notes))
            else:
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, amount, payment_method, transaction_id, notes, status, created_at, paid_at)
                    VALUES (?, ?, ?, ?, ?, 'paid', datetime('now'), datetime('now'))
                """, (broker_id, amount, payment_method, transaction_id, notes))
            
            conn.commit()
            return {"status": "success", "message": "Payment marked as paid"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/payment-history")
async def get_payment_history(time_filter: str = "all", _auth: dict = Depends(require_admin_api_key)):
    """Get payment history for admin dashboard"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create broker_payments table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payments (
                        id SERIAL PRIMARY KEY,
                        broker_id INTEGER NOT NULL,
                        broker_name VARCHAR(255) NOT NULL,
                        broker_email VARCHAR(255) NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        payment_method VARCHAR(50) NOT NULL,
                        transaction_id VARCHAR(255),
                        notes TEXT,
                        status VARCHAR(50) DEFAULT 'completed',
                        payment_date TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_id INTEGER NOT NULL,
                        broker_name TEXT NOT NULL,
                        broker_email TEXT NOT NULL,
                        amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        transaction_id TEXT,
                        notes TEXT,
                        status TEXT DEFAULT 'completed',
                        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
            
            # Build query based on time_filter
            if time_filter == "month":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= NOW() - INTERVAL '30 days'
                        ORDER BY bp.paid_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= datetime('now', '-30 days')
                        ORDER BY bp.paid_at DESC
                    """)
            elif time_filter == "week":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= NOW() - INTERVAL '7 days'
                        ORDER BY bp.paid_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= datetime('now', '-7 days')
                        ORDER BY bp.paid_at DESC
                    """)
            else:
                cursor.execute("""
                    SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                           bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                           bp.status, bp.paid_at, bp.created_at
                    FROM broker_payments bp
                    ORDER BY bp.paid_at DESC
                """)
            
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                if isinstance(row, dict):
                    history.append({
                        "id": row.get('id'),
                        "broker_id": row.get('broker_id'),
                        "broker_name": row.get('broker_name'),
                        "broker_email": row.get('broker_email'),
                        "amount": float(row.get('amount') or 0),
                        "payment_method": row.get('payment_method'),
                        "transaction_id": row.get('transaction_id'),
                        "notes": row.get('notes'),
                        "status": row.get('status'),
                        "paid_at": row.get('paid_at')
                    })
                else:
                    history.append({
                        "id": row[0] if len(row) > 0 else None,
                        "broker_id": row[1] if len(row) > 1 else None,
                        "broker_name": row[2] if len(row) > 2 else None,
                        "broker_email": row[3] if len(row) > 3 else None,
                        "amount": float(row[4] if len(row) > 4 else 0),
                        "payment_method": row[5] if len(row) > 5 else None,
                        "transaction_id": row[6] if len(row) > 6 else None,
                        "notes": row[7] if len(row) > 7 else None,
                        "status": row[8] if len(row) > 8 else None,
                        "paid_at": row[9] if len(row) > 9 else None
                    })
            
            return history
            
    except Exception as e:
        print(f"❌ Admin payment info get error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to retrieve payment information"}
        )

@router.get("/api/admin/payment-history/export")
async def export_payment_history(_auth: dict = Depends(require_admin_api_key)):
    """Export payment history as CSV"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            query = """
                SELECT bp.id, b.name, b.email, bp.amount, bp.payment_method, bp.transaction_id, bp.paid_at
                FROM broker_payments bp
                JOIN brokers b ON bp.broker_id = b.id
                ORDER BY bp.paid_at DESC
            """
            cursor.execute(query)
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Payment ID', 'Broker Name', 'Broker Email', 'Amount', 'Method', 'Transaction ID', 'Date'])
            
            for row in cursor.fetchall():
                # Handle dict or tuple
                if isinstance(row, dict):
                     writer.writerow([row['id'], row['name'], row['email'], row['amount'], row['payment_method'], row['transaction_id'], row['paid_at']])
                else:
                     writer.writerow(row)
                
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=payment_history.csv"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/payouts/pending")
async def get_pending_payouts_api(_auth: dict = Depends(require_admin_api_key)):
    """Return pending broker payouts"""
    try:
        with get_db() as db:
            
            # Check if tables exist
            if DB_TYPE == 'postgresql':
                 # PostgreSQL check
                 with db.cursor() as cursor:
                     cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'referrals')")
                     if not cursor.fetchone()[0]:
                         print("Referrals table does not exist")
                         return []
            else:
                # SQLite check
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                table_names = [t[0] for t in tables]
                
                if 'referrals' not in table_names:
                    print("Referrals table does not exist")
                    return []
            
            # Try query with different column names for compatibility
            try:
                if DB_TYPE == 'postgresql':
                    with db.cursor() as cursor:
                        cursor.execute("""
                            SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, r.status,
                                   b.name as broker_name
                            FROM referrals r
                            LEFT JOIN brokers b ON r.broker_id = b.id
                            WHERE r.status = 'pending'
                            ORDER BY r.created_at DESC
                        """)
                        columns = [desc[0] for desc in cursor.description]
                        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                else:
                    rows = db.execute("""
                        SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, r.status,
                               b.name as broker_name
                        FROM referrals r
                        LEFT JOIN brokers b ON r.broker_id = b.id
                        WHERE r.status = 'pending'
                        ORDER BY r.created_at DESC
                    """).fetchall()
            except (sqlite3.OperationalError, Exception) as e:
                # Fallback if columns don't match
                try:
                    if DB_TYPE == 'postgresql':
                        with db.cursor() as cursor:
                            cursor.execute("""
                                SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.status,
                                       b.name as broker_name, r.days_active
                                FROM referrals r
                                LEFT JOIN brokers b ON r.broker_ref = b.id
                                WHERE r.status = 'ready'
                                ORDER BY r.date ASC
                            """)
                            columns = [desc[0] for desc in cursor.description]
                            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    else:
                        rows = db.execute("""
                            SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.status,
                                   b.name as broker_name, r.days_active
                            FROM referrals r
                            LEFT JOIN brokers b ON r.broker_ref = b.id
                            WHERE r.status = 'ready'
                            ORDER BY r.date ASC
                        """).fetchall()
                except Exception as e:
                    print(f"Error querying pending payouts: {e}")
                    return []
            
            result = []
            for row in rows:
                if isinstance(row, dict):
                     result.append({
                        "id": row.get('id') or 0,
                        "broker_name": row.get('broker_name') or 'Unknown',
                        "broker_id": row.get('broker_id') or row.get('broker_ref') or '',
                        "customer_email": row.get('customer_email') or '',
                        "amount": float(row.get('amount') or 0),
                        "payout": float(row.get('payout') or row.get('amount') or 0),
                        "status": row.get('status') or 'pending',
                        "days_active": row.get('days_active') or 0
                    })
                else:
                     # SQLite row
                     result.append({
                        "id": row['id'] if 'id' in row.keys() else row[0],
                        "broker_name": row['broker_name'] if 'broker_name' in row.keys() else (row[5] if len(row) > 5 else 'Unknown'),
                        "broker_id": row['broker_id'] if 'broker_id' in row.keys() else (row[1] if len(row) > 1 else ''),
                        "customer_email": row['customer_email'] if 'customer_email' in row.keys() else (row[2] if len(row) > 2 else ''),
                        "amount": float(row['amount'] if 'amount' in row.keys() else (row[3] if len(row) > 3 else 0)),
                        "payout": float(row['payout'] if 'payout' in row.keys() else (row[4] if len(row) > 4 else 0)),
                        "status": row['status'] if 'status' in row.keys() else (row[5] if len(row) > 5 else 'pending'),
                        "days_active": 0
                     })
    
            return result
    except Exception as e:
        print(f"Error in get_pending_payouts_api: {e}")
        import traceback
        traceback.print_exc()
        return []

@router.get("/api/admin/payout-batches")
async def get_payout_batches(_auth: dict = Depends(require_admin_api_key)):
    """Get all payout batches"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM broker_payout_batches ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM broker_payout_batches ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            return [dict(row) if isinstance(row, dict) else dict(zip([c[0] for c in cursor.description], row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/admin/payout-batches/create")
async def create_payout_batch(request: Request, _auth: dict = Depends(require_admin_api_key)):
    """Create a payout batch and mark referrals as paid atomically"""
    try:
        data = await request.json()
        broker_id = data.get('broker_id')
        referral_ids = data.get('referral_ids', [])
        payment_method = data.get('payment_method')
        transaction_id = data.get('transaction_id', '')
        notes = data.get('notes', '')
        
        if not broker_id or not referral_ids or not payment_method:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing required fields: broker_id, referral_ids, payment_method"}
            )
        
        if not isinstance(referral_ids, list) or len(referral_ids) == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "referral_ids must be a non-empty array"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker info
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, name, email FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT id, name, email FROM brokers WHERE id = ?", (broker_id,))
            
            broker = cursor.fetchone()
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            if isinstance(broker, dict):
                broker_name = broker.get('name', 'Unknown')
                broker_email = broker.get('email', '')
            else:
                broker_name = broker[1] if len(broker) > 1 else 'Unknown'
                broker_email = broker[2] if len(broker) > 2 else ''
            
            # Calculate total amount from selected referrals
            if DB_TYPE == 'postgresql':
                placeholders = ','.join(['%s'] * len(referral_ids))
                cursor.execute(f"""
                    SELECT COALESCE(SUM(payout), 0) as total
                    FROM referrals
                    WHERE id IN ({placeholders})
                    AND status != 'paid'
                """, referral_ids)
            else:
                placeholders = ','.join(['?'] * len(referral_ids))
                cursor.execute(f"""
                    SELECT COALESCE(SUM(payout), 0) as total
                    FROM referrals
                    WHERE id IN ({placeholders})
                    AND status != 'paid'
                """, referral_ids)
            
            total_result = cursor.fetchone()
            total_amount = 0.0
            if total_result:
                if isinstance(total_result, dict):
                    total_amount = float(total_result.get('total', 0))
                else:
                    total_amount = float(total_result[0] if len(total_result) > 0 else 0)
            
            if total_amount <= 0:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Selected referrals have no unpaid amount or are already paid"}
                )
            
            # Generate batch ID if transaction_id not provided
            if not transaction_id:
                import secrets as secrets_module
                transaction_id = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{secrets_module.token_hex(4).upper()}"
            
            # Create batch record
            referral_ids_json = json.dumps(referral_ids)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO broker_payout_batches 
                    (broker_id, broker_name, broker_email, total_amount, currency, payment_method, 
                     transaction_id, notes, status, referral_ids, created_at, created_by_admin)
                    VALUES (%s, %s, %s, %s, 'USD', %s, %s, %s, 'pending', %s, NOW(), %s)
                    RETURNING id
                """, (broker_id, broker_name, broker_email, total_amount, payment_method, 
                      transaction_id, notes, referral_ids_json, user.get('email', 'unknown')))
                batch_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO broker_payout_batches 
                    (broker_id, broker_name, broker_email, total_amount, currency, payment_method, 
                     transaction_id, notes, status, referral_ids, created_at, created_by_admin)
                    VALUES (?, ?, ?, ?, 'USD', ?, ?, ?, 'pending', ?, datetime('now'), ?)
                """, (broker_id, broker_name, broker_email, total_amount, payment_method, 
                      transaction_id, notes, referral_ids_json, user.get('email', 'unknown')))
                batch_id = cursor.lastrowid
            
            # Update referrals status
            if DB_TYPE == 'postgresql':
                placeholders = ','.join(['%s'] * len(referral_ids))
                cursor.execute(f"""
                    UPDATE referrals 
                    SET status = 'paid', 
                        payment_date = NOW(),
                        payout_batch_id = %s
                    WHERE id IN ({placeholders})
                """, [batch_id] + referral_ids)
            else:
                placeholders = ','.join(['?'] * len(referral_ids))
                cursor.execute(f"""
                    UPDATE referrals 
                    SET status = 'paid', 
                        payment_date = datetime('now'),
                        payout_batch_id = ?
                    WHERE id IN ({placeholders})
                """, [batch_id] + referral_ids)
            
            # Also insert into broker_payments (legacy table support)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, broker_name, broker_email, amount, payment_method, 
                     transaction_id, notes, status, paid_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', NOW())
                """, (broker_id, broker_name, broker_email, total_amount, payment_method, 
                      transaction_id, f"Batch #{batch_id}: {notes}"))
            else:
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, broker_name, broker_email, amount, payment_method, 
                     transaction_id, notes, status, paid_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', datetime('now'))
                """, (broker_id, broker_name, broker_email, total_amount, payment_method, 
                      transaction_id, f"Batch #{batch_id}: {notes}"))
            
            conn.commit()
            
            # Send notification email to broker
            try:
                # Use background task if possible, but here we'll just try sync or skip
                # We can't easily access background_tasks here unless we change signature
                # For now, let's just log it or try sync send if imported
                send_broker_notification(
                    broker_email, 
                    "Commission Payout Processed",
                    f"Good news! We've processed a payout of ${total_amount:.2f} via {payment_method}. Transaction ID: {transaction_id}"
                )
            except Exception as e:
                print(f"Error sending broker notification: {e}")
            
            return {
                "status": "success", 
                "message": "Payout batch created successfully",
                "batch_id": batch_id,
                "amount": total_amount,
                "referrals_count": len(referral_ids)
            }
            
    except Exception as e:
        print(f"❌ Create batch error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/payout-batches/{broker_id}")
async def get_broker_batches(broker_id: int, _auth: dict = Depends(require_admin_api_key)):
    """Get all payout batches for a broker"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM broker_payout_batches WHERE broker_id = %s ORDER BY created_at DESC", (broker_id,))
            else:
                cursor.execute("SELECT * FROM broker_payout_batches WHERE broker_id = ? ORDER BY created_at DESC", (broker_id,))
            rows = cursor.fetchall()
            return [dict(row) if isinstance(row, dict) else dict(zip([c[0] for c in cursor.description], row)) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/admin/payout-batches/export/{batch_id}")
async def export_batch_csv(batch_id: int, _auth: dict = Depends(require_admin_api_key)):
    """Export a payout batch as CSV"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get batch info
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, total_amount, currency,
                           payment_method, transaction_id, notes, status, referral_ids,
                           created_at, paid_at
                    FROM broker_payout_batches
                    WHERE id = %s
                """, (batch_id,))
            else:
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, total_amount, currency,
                           payment_method, transaction_id, notes, status, referral_ids,
                           created_at, paid_at
                    FROM broker_payout_batches
                    WHERE id = ?
                """, (batch_id,))
            
            batch = cursor.fetchone()
            if not batch:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Batch not found"}
                )
            
            # Parse batch data
            if isinstance(batch, dict):
                referral_ids = json.loads(batch.get('referral_ids', '[]'))
                broker_name = batch.get('broker_name')
                broker_email = batch.get('broker_email')
                total_amount = batch.get('total_amount')
                transaction_id = batch.get('transaction_id')
                created_at = batch.get('created_at')
            else:
                referral_ids = json.loads(batch[10] if len(batch) > 10 else '[]')
                broker_name = batch[2] if len(batch) > 2 else None
                broker_email = batch[3] if len(batch) > 3 else None
                total_amount = batch[4] if len(batch) > 4 else 0
                transaction_id = batch[7] if len(batch) > 7 else None
                created_at = batch[11] if len(batch) > 11 else None
            
            # Get referral details
            if len(referral_ids) > 0:
                placeholders = ','.join(['%s'] * len(referral_ids)) if DB_TYPE == 'postgresql' else ','.join(['?'] * len(referral_ids))
                cursor.execute(f"""
                    SELECT id, customer_email, customer_stripe_id, payout, payout_type, payment_date
                    FROM referrals
                    WHERE id IN ({placeholders})
                    ORDER BY id
                """, referral_ids)
                
                referrals = cursor.fetchall()
            else:
                referrals = []
            
            # Build CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Batch ID', 'Transaction ID', 'Broker Name', 'Broker Email', 
                           'Total Amount', 'Currency', 'Payment Method', 'Created At', 'Status'])
            
            created_at_str = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at) if created_at else ''
            
            writer.writerow([batch_id, transaction_id or '', broker_name or '', broker_email or '',
                           total_amount, 'USD', 'N/A', created_at_str, 'completed'])
            
            writer.writerow([])  # Empty row
            writer.writerow(['Referral Details'])
            writer.writerow(['Referral ID', 'Customer Email', 'Customer Stripe ID', 
                           'Amount', 'Type', 'Payment Date'])
            
            # Referral rows
            for ref in referrals:
                if isinstance(ref, dict):
                    payment_date = ref.get('payment_date', '')
                    payment_date_str = payment_date.isoformat() if hasattr(payment_date, 'isoformat') else str(payment_date) if payment_date else ''
                    
                    writer.writerow([
                        ref.get('id'),
                        ref.get('customer_email', ''),
                        ref.get('customer_stripe_id', ''),
                        ref.get('payout', 0),
                        ref.get('payout_type', ''),
                        payment_date_str
                    ])
                else:
                    payment_date = ref[5] if len(ref) > 5 else ''
                    payment_date_str = payment_date.isoformat() if hasattr(payment_date, 'isoformat') else str(payment_date) if payment_date else ''
                    
                    writer.writerow([
                        ref[0] if len(ref) > 0 else '',
                        ref[1] if len(ref) > 1 else '',
                        ref[2] if len(ref) > 2 else '',
                        ref[3] if len(ref) > 3 else 0,
                        ref[4] if len(ref) > 4 else '',
                        payment_date_str
                    ])
                
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_export.csv"}
            )
            
    except Exception as e:
        print(f"❌ Export batch error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to export batch: {str(e)}"}
        )

# ==========================================
# Tests
# ==========================================

@router.get("/api/admin/test-send-reminders")
async def test_send_reminders(_auth: dict = Depends(require_admin_api_key)):
    """Test the reminder system manually (admin only)"""
    import subprocess
    import sys
    try:
        result = subprocess.run(
            [sys.executable, "api/cron_send_reminders.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "errors": result.stderr if result.stderr else None,
            "message": "Reminder cron job executed"
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out after 60 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/admin/test-set-broker-ready/{broker_id}")
async def test_set_broker_ready(broker_id: int, _auth: dict = Depends(require_admin_api_key)):
    """TEST ONLY: Simulate broker ready for payment"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, name, email, referral_code, commission_model FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT id, name, email, referral_code, commission_model FROM brokers WHERE id = ?", (broker_id,))
            
            broker_row = cursor.fetchone()
            if not broker_row:
                raise HTTPException(status_code=404, detail=f"Broker {broker_id} not found")
            
            # Parse broker data
            if isinstance(broker_row, dict):
                broker_name = broker_row.get('name', '')
                broker_email = broker_row.get('email', '')
                referral_code = broker_row.get('referral_code', '')
                commission_model = broker_row.get('commission_model', 'bounty')
            else:
                broker_name = broker_row[1] if len(broker_row) > 1 else ''
                broker_email = broker_row[2] if len(broker_row) > 2 else ''
                referral_code = broker_row[3] if len(broker_row) > 3 else ''
                commission_model = broker_row[4] if len(broker_row) > 4 else 'bounty'
            
            # Calculate commission amount
            commission = 500.00 if commission_model == 'bounty' else 50.00
            payout_type = 'bounty' if commission_model == 'bounty' else 'recurring'
            
            # Set dates (61 days ago to pass 60-day hold)
            now = datetime.now()
            activated_date = now - timedelta(days=61)
            hold_until = activated_date + timedelta(days=60)  # Already passed
            clawback_until = activated_date + timedelta(days=90)
            
            # Create test customer
            test_customer_email = f'test_customer_{broker_id}@example.com'
            test_customer_stripe_id = f'cus_test_{broker_id}'
            test_subscription_id = f'sub_test_{broker_id}'
            
            # Insert test customer
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO customers (email, stripe_customer_id, subscription_id, status, plan, amount)
                    VALUES (%s, %s, %s, 'active', 'unlimited', 299.00)
                    ON CONFLICT (email) DO UPDATE SET
                        stripe_customer_id = EXCLUDED.stripe_customer_id,
                        subscription_id = EXCLUDED.subscription_id,
                        status = 'active'
                """, (test_customer_email, test_customer_stripe_id, test_subscription_id))
            else:
                cursor.execute("""
                    INSERT INTO customers (email, stripe_customer_id, subscription_id, status, plan, amount)
                    VALUES (?, ?, ?, 'active', 'unlimited', 299.00)
                    ON CONFLICT(email) DO UPDATE SET
                        stripe_customer_id = excluded.stripe_customer_id,
                        subscription_id = excluded.subscription_id,
                        status = 'active'
                """, (test_customer_email, test_customer_stripe_id, test_subscription_id))
            
            # Create test referral with ready_to_pay status
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO referrals (
                        broker_id, broker_email, customer_email, customer_stripe_id,
                        amount, payout, payout_type, status,
                        hold_until, clawback_until, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'ready_to_pay', %s, %s, %s)
                """, (
                    referral_code, broker_email, test_customer_email, test_customer_stripe_id,
                    commission, commission, payout_type,
                    hold_until.date(), clawback_until.date(), activated_date
                ))
            else:
                cursor.execute("""
                    INSERT INTO referrals (
                        broker_id, broker_email, customer_email, customer_stripe_id,
                        amount, payout, payout_type, status,
                        hold_until, clawback_until, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ready_to_pay', ?, ?, ?)
                """, (
                    referral_code, broker_email, test_customer_email, test_customer_stripe_id,
                    commission, commission, payout_type,
                    hold_until.date(), clawback_until.date(), activated_date
                ))
            
            conn.commit()
            
            return {"success": True, "message": f"Broker {broker_id} set to ready (simulated)"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/admin/list-broker-ids")
async def list_broker_ids(_auth: dict = Depends(require_admin_api_key)):
    """List all broker IDs for testing"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, name, email FROM brokers ORDER BY id")
            else:
                cursor.execute("SELECT id, name, email FROM brokers ORDER BY id")
            brokers = [dict(row) if isinstance(row, dict) else {"id": row[0], "name": row[1], "email": row[2]} for row in cursor.fetchall()]
            return {"success": True, "brokers": brokers}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/admin/calculations-today")
async def get_calculations_today(_auth: dict = Depends(require_admin_api_key)):
    """Get today's calculations - Fixed counting with UTC timezone"""
    try:
        # Use UTC date for consistency
        today_utc = datetime.now(timezone.utc).date()
        
        print(f"🔍 Counting calculations for today (UTC): {today_utc}")
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Count ALL calculations from today (UTC)
            if DB_TYPE == 'postgresql':
                # PostgreSQL: created_at is TIMESTAMP
                # Convert created_at TIMESTAMP to UTC date
                cursor.execute('''
                    SELECT COUNT(*) as count 
                    FROM calculations 
                    WHERE DATE(created_at AT TIME ZONE 'UTC') = %s
                ''', (today_utc,))
            else:
                # SQLite: Use DATE() function
                cursor.execute('''
                    SELECT COUNT(*) as count 
                    FROM calculations 
                    WHERE DATE(created_at) = DATE('now')
                ''')
            
            result = cursor.fetchone()
            
            # Handle different row formats
            if isinstance(result, dict):
                count = result.get('count', 0)
            elif hasattr(result, 'keys'):
                count = result['count'] if 'count' in result.keys() else (result[0] if len(result) > 0 else 0)
            else:
                count = result[0] if result and len(result) > 0 else 0
            
            count = int(count) if count else 0
            print(f"✅ Found {count} calculations for today (UTC: {today_utc})")
            
            return {"calculations_today": count, "date": str(today_utc), "timezone": "UTC"}
        
    except Exception as e:
        print(f"❌ Error getting calculations today: {e}")
        return {"calculations_today": 0, "error": str(e)}

@router.post("/api/admin/reset-password-emergency")
async def reset_password_emergency(
    email: str = Query(..., description="User email address"),
    new_password: str = Query("TempPass123!", description="New temporary password"),
    _auth: dict = Depends(require_admin_api_key)
):
    """
    TEMPORARY EMERGENCY ENDPOINT - Remove after use!
    Resets a user's password without authentication.
    """
    import bcrypt
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if user exists
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id FROM users WHERE email = %s", (email.lower(),))
            else:
                cursor.execute("SELECT id FROM users WHERE email = ?", (email.lower(),))
            
            user = cursor.fetchone()
            
            if not user:
                return JSONResponse(
                    status_code=404,
                    content={"error": "User not found", "email": email}
                )
            
            # Hash the new password
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            # For PostgreSQL, decode the hash to string
            if DB_TYPE == 'postgresql':
                password_hash_str = password_hash.decode('utf-8')
            else:
                password_hash_str = password_hash
            
            # Update password
            if DB_TYPE == 'postgresql':
                cursor.execute(
                    "UPDATE users SET password_hash = %s WHERE email = %s",
                    (password_hash_str, email.lower())
                )
            else:
                cursor.execute(
                    "UPDATE users SET password_hash = ? WHERE email = ?",
                    (password_hash_str, email.lower())
                )
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "email": email,
                    "temporary_password": new_password,
                    "message": "Password reset successfully. Login with this password."
                }
            )
            
    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "message": "Failed to reset password"}
        )


