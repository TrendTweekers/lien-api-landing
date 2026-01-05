"""
Temporary internal migration endpoints
Used for one-time database migrations that cannot be run via Railway UI
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
import logging

from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal", tags=["internal"])

# Admin email allowed to run migrations
ADMIN_EMAIL = "admin@stackedboost.com"

def verify_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Verify the current user is an admin.
    Raises 401 if not authenticated, 403 if not admin.
    """
    user_email = current_user.get('email', '').lower().strip()
    if not user_email:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if user_email != ADMIN_EMAIL.lower():
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return current_user

@router.post("/migrate/notification-settings")
async def migrate_notification_settings():
    """
    Temporary endpoint to create notification_settings table in production.
    
    ⚠️ TEMPORARY: Auth removed for one-time migration.
    This endpoint should be removed after the migration is confirmed.
    """
    try:
        if DB_TYPE != 'postgresql':
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "This migration is for PostgreSQL only"
                }
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create notification_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_settings (
                    id SERIAL PRIMARY KEY,
                    project_id INTEGER NOT NULL UNIQUE,
                    reminders JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            
            # Create index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_settings_project_id
                ON notification_settings(project_id);
            """)
            
            conn.commit()
        
        logger.info("✅ Created notification_settings table via migration endpoint")
        
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "message": "notification_settings ensured"
            }
        )
    except Exception as e:
        logger.error(f"Error creating notification_settings table: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(e)
            }
        )

