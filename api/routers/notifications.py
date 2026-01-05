"""
Notification Settings Router
Manages per-project notification settings for deadline reminders
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime
import json
import logging

from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])

# --- Request/Response Models ---

class ReminderChannel(BaseModel):
    """Channel configuration for a reminder"""
    email: bool = False
    slack: bool = False
    zapier: bool = False

class ReminderConfig(BaseModel):
    """Single reminder configuration"""
    offset_days: int = Field(..., gt=0, description="Days before deadline (e.g., 1, 7, 14)")
    channels: ReminderChannel

class NotificationSettingsRequest(BaseModel):
    """Request model for updating notification settings"""
    reminders: List[ReminderConfig] = Field(..., min_items=0, description="List of reminder configurations")
    
    @validator('reminders')
    def validate_no_duplicate_offsets(cls, v):
        """Ensure no duplicate offset_days"""
        offsets = [r.offset_days for r in v]
        if len(offsets) != len(set(offsets)):
            raise ValueError("Duplicate offset_days not allowed. Each reminder must have a unique offset.")
        return v

class NotificationSettingsResponse(BaseModel):
    """Response model for notification settings"""
    project_id: int
    reminders: List[ReminderConfig]
    created_at: str
    updated_at: str

# --- Helper Functions ---

def create_default_notification_settings(project_id: int) -> bool:
    """
    Create default notification settings for a project.
    Default: offset_days=7, email=true, slack=false, zapier=false
    
    Returns True if created successfully, False otherwise.
    """
    try:
        default_reminders = [
            {
                "offset_days": 7,
                "channels": {
                    "email": True,
                    "slack": False,
                    "zapier": False
                }
            }
        ]
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                    VALUES (%s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (project_id) DO NOTHING
                    RETURNING id
                """, (project_id, json.dumps(default_reminders)))
                result = cursor.fetchone()
                created = result is not None
            else:
                # SQLite
                cursor.execute("""
                    INSERT OR IGNORE INTO notification_settings (project_id, reminders, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (project_id, json.dumps(default_reminders)))
                created = cursor.rowcount > 0
            
            conn.commit()
            return created
    except Exception as e:
        logger.error(f"Error creating default notification settings for project {project_id}: {e}")
        return False

def get_notification_settings(project_id: int) -> Optional[Dict]:
    """
    Get notification settings for a project.
    Returns None if not found, otherwise returns dict with reminders.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT reminders, created_at, updated_at
                    FROM notification_settings
                    WHERE project_id = %s
                """, (project_id,))
            else:
                cursor.execute("""
                    SELECT reminders, created_at, updated_at
                    FROM notification_settings
                    WHERE project_id = ?
                """, (project_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            if isinstance(row, dict):
                reminders_json = row.get('reminders')
                created_at = row.get('created_at')
                updated_at = row.get('updated_at')
            else:
                reminders_json = row[0] if len(row) > 0 else None
                created_at = row[1] if len(row) > 1 else None
                updated_at = row[2] if len(row) > 2 else None
            
            # Parse JSON
            if isinstance(reminders_json, str):
                reminders = json.loads(reminders_json)
            else:
                reminders = reminders_json
            
            return {
                "reminders": reminders,
                "created_at": created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
                "updated_at": updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)
            }
    except Exception as e:
        logger.error(f"Error getting notification settings for project {project_id}: {e}")
        return None

def get_project_user_email(project_id: int) -> Optional[str]:
    """
    Get the user_email for a project (from calculations table).
    Returns None if project not found.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT user_email FROM calculations WHERE id = %s", (project_id,))
            else:
                cursor.execute("SELECT user_email FROM calculations WHERE id = ?", (project_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            if isinstance(row, dict):
                return row.get('user_email')
            else:
                return row[0] if len(row) > 0 else None
    except Exception as e:
        logger.error(f"Error getting user_email for project {project_id}: {e}")
        return None

# --- Endpoints ---

@router.get("/api/projects/{project_id}/notifications")
async def get_notifications(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get notification settings for a project.
    Requires authentication and project ownership.
    """
    try:
        user_email = current_user.get('email', '').lower().strip()
        if not user_email:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Verify project ownership
        project_user_email = get_project_user_email(project_id)
        if project_user_email is None:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if project_user_email.lower().strip() != user_email:
            raise HTTPException(status_code=403, detail="Access denied. You can only view your own projects.")
        
        # Get settings (create default if missing)
        settings = get_notification_settings(project_id)
        if settings is None:
            # Create default settings
            created = create_default_notification_settings(project_id)
            if created:
                settings = get_notification_settings(project_id)
            else:
                raise HTTPException(status_code=500, detail="Failed to create default notification settings")
        
        return JSONResponse(content={
            "success": True,
            "project_id": project_id,
            "reminders": settings["reminders"],
            "created_at": settings["created_at"],
            "updated_at": settings["updated_at"]
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_notifications: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/api/projects/{project_id}/notifications")
async def create_notifications(
    project_id: int,
    settings: NotificationSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create notification settings for a project.
    Requires authentication and project ownership.
    """
    try:
        user_id = current_user.get('id')
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Verify project ownership
        project_user_id = get_project_user_id(project_id)
        if project_user_id is None:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if project_user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only modify your own projects.")
        
        # Check if settings already exist
        existing = get_notification_settings(project_id)
        if existing:
            raise HTTPException(status_code=409, detail="Notification settings already exist. Use PUT to update.")
        
        # Prepare reminders JSON
        reminders_data = [
            {
                "offset_days": r.offset_days,
                "channels": {
                    "email": r.channels.email,
                    "slack": r.channels.slack,
                    "zapier": r.channels.zapier
                }
            }
            for r in settings.reminders
        ]
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                    VALUES (%s, %s::jsonb, NOW(), NOW())
                    RETURNING id
                """, (project_id, json.dumps(reminders_data)))
                result = cursor.fetchone()
                settings_id = result.get('id') if isinstance(result, dict) else (result[0] if result else None)
            else:
                cursor.execute("""
                    INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (project_id, json.dumps(reminders_data)))
                settings_id = cursor.lastrowid
            
            conn.commit()
        
        # Return created settings
        created_settings = get_notification_settings(project_id)
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "project_id": project_id,
                "reminders": created_settings["reminders"],
                "created_at": created_settings["created_at"],
                "updated_at": created_settings["updated_at"]
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_notifications: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.put("/api/projects/{project_id}/notifications")
async def update_notifications(
    project_id: int,
    settings: NotificationSettingsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update notification settings for a project.
    Requires authentication and project ownership.
    """
    try:
        user_id = current_user.get('id')
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Verify project ownership
        project_user_id = get_project_user_id(project_id)
        if project_user_id is None:
            raise HTTPException(status_code=404, detail="Project not found")
        
        if project_user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only modify your own projects.")
        
        # Prepare reminders JSON
        reminders_data = [
            {
                "offset_days": r.offset_days,
                "channels": {
                    "email": r.channels.email,
                    "slack": r.channels.slack,
                    "zapier": r.channels.zapier
                }
            }
            for r in settings.reminders
        ]
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE notification_settings
                    SET reminders = %s::jsonb, updated_at = NOW()
                    WHERE project_id = %s
                    RETURNING id
                """, (json.dumps(reminders_data), project_id))
                result = cursor.fetchone()
                if not result:
                    # Create if doesn't exist
                    cursor.execute("""
                        INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                        VALUES (%s, %s::jsonb, NOW(), NOW())
                        RETURNING id
                    """, (project_id, json.dumps(reminders_data)))
            else:
                cursor.execute("""
                    UPDATE notification_settings
                    SET reminders = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE project_id = ?
                """, (json.dumps(reminders_data), project_id))
                if cursor.rowcount == 0:
                    # Create if doesn't exist
                    cursor.execute("""
                        INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (project_id, json.dumps(reminders_data)))
            
            conn.commit()
        
        # Return updated settings
        updated_settings = get_notification_settings(project_id)
        
        return JSONResponse(content={
            "success": True,
            "project_id": project_id,
            "reminders": updated_settings["reminders"],
            "created_at": updated_settings["created_at"],
            "updated_at": updated_settings["updated_at"]
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_notifications: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

