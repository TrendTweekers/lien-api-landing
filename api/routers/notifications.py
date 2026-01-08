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

class NotificationSettingsRequestV1(BaseModel):
    """Request model for v1 notification settings (Email + Zapier)"""
    reminder_offsets_days: Optional[List[int]] = Field(default=None, min_items=0, description="List of reminder offset days for Zapier (e.g., [1, 7, 14])")
    zapier_enabled: bool = Field(default=False, description="Whether Zapier reminders are enabled")
    email_enabled: Optional[bool] = Field(default=None, description="Whether email reminders are enabled for this project")
    email_reminder_offsets_days: Optional[List[int]] = Field(default=None, min_items=0, description="List of reminder offset days for Email (e.g., [1, 7, 14])")
    
    @validator('reminder_offsets_days')
    def validate_zapier_offsets(cls, v):
        """Ensure no duplicate offsets and all > 0"""
        if v is None:
            return v
        if len(v) != len(set(v)):
            raise ValueError("Duplicate offset_days not allowed.")
        for offset in v:
            if offset <= 0:
                raise ValueError("All offset_days must be > 0")
        return v
    
    @validator('email_reminder_offsets_days')
    def validate_email_offsets(cls, v):
        """Ensure no duplicate offsets and all > 0"""
        if v is None:
            return v
        if len(v) != len(set(v)):
            raise ValueError("Duplicate email_reminder_offsets_days not allowed.")
        for offset in v:
            if offset <= 0:
                raise ValueError("All email_reminder_offsets_days must be > 0")
        return v

class NotificationSettingsRequest(BaseModel):
    """Request model for updating notification settings (legacy format)"""
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
    reminders: List[ReminderConfig] = Field(default_factory=list)
    reminder_offsets_days: List[int] = Field(default_factory=list)
    zapier_enabled: bool = False
    created_at: str
    updated_at: str

# --- Helper Functions ---

def create_default_notification_settings(project_id: int) -> bool:
    """
    Create default notification settings for a project (v1 format).
    Default: reminder_offsets_days=[7], zapier_enabled=false
    
    Returns True if created successfully, False otherwise.
    """
    try:
        # V1 format: simple array of offsets + zapier_enabled flag
        default_reminders = [7]  # Single offset: 7 days
        zapier_enabled = False
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Store as JSONB with both formats for backwards compatibility
            # New format: {reminder_offsets_days: [7], zapier_enabled: false}
            # Legacy format: [{offset_days: 7, channels: {email: true, slack: false, zapier: false}}]
            settings_data = {
                "reminder_offsets_days": default_reminders,
                "zapier_enabled": zapier_enabled,
                # Legacy format for backwards compatibility
                "reminders": [
                    {
                        "offset_days": 7,
                        "channels": {
                            "email": True,
                            "slack": False,
                            "zapier": False
                        }
                    }
                ]
            }
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                    VALUES (%s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (project_id) DO NOTHING
                    RETURNING id
                """, (project_id, json.dumps(settings_data)))
                result = cursor.fetchone()
                created = result is not None
            else:
                # SQLite
                cursor.execute("""
                    INSERT OR IGNORE INTO notification_settings (project_id, reminders, created_at, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (project_id, json.dumps(settings_data)))
                created = cursor.rowcount > 0
            
            conn.commit()
            return created
    except Exception as e:
        logger.error(f"Error creating default notification settings for project {project_id}: {e}")
        return False

def get_notification_settings(project_id: int) -> Optional[Dict]:
    """
    Get notification settings for a project.
    Returns None if not found, otherwise returns dict with both v1 and legacy formats.
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
                settings_data = json.loads(reminders_json)
            else:
                settings_data = reminders_json
            
            # Handle both v1 format and legacy format
            if isinstance(settings_data, dict):
                # V1 format: {reminder_offsets_days: [7], zapier_enabled: false, email_enabled: false, email_reminder_offsets_days: [1,7], reminders: [...]}
                reminder_offsets_days = settings_data.get("reminder_offsets_days", [])
                zapier_enabled = settings_data.get("zapier_enabled", False)
                email_enabled = settings_data.get("email_enabled", False)
                email_reminder_offsets_days = settings_data.get("email_reminder_offsets_days", [])
                reminders = settings_data.get("reminders", [])
            elif isinstance(settings_data, list):
                # Legacy format: [{offset_days: 7, channels: {...}}]
                reminders = settings_data
                # Extract offsets and zapier_enabled from legacy format
                reminder_offsets_days = [r.get("offset_days") for r in reminders if isinstance(r, dict) and "offset_days" in r]
                zapier_enabled = any(
                    r.get("channels", {}).get("zapier", False) 
                    for r in reminders 
                    if isinstance(r, dict) and "channels" in r
                )
            else:
                # Fallback
                reminders = []
                reminder_offsets_days = []
                zapier_enabled = False
                email_enabled = False
                email_reminder_offsets_days = []
            
            return {
                "reminders": reminders,  # Legacy format
                "reminder_offsets_days": reminder_offsets_days,  # V1 format
                "zapier_enabled": zapier_enabled,  # V1 format
                "email_enabled": email_enabled,  # Email support
                "email_reminder_offsets_days": email_reminder_offsets_days,  # Email support
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

def get_project_user_id(project_id: int) -> Optional[int]:
    """
    Get the user_id for a project (from calculations table via users table lookup).
    Returns None if project not found or user not found.
    """
    try:
        # First get user_email from calculations table
        user_email = get_project_user_email(project_id)
        if not user_email:
            return None
        
        # Then get user_id from users table
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id FROM users WHERE email = %s", (user_email.lower().strip(),))
            else:
                cursor.execute("SELECT id FROM users WHERE email = ?", (user_email.lower().strip(),))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            if isinstance(row, dict):
                return row.get('id')
            else:
                return row[0] if len(row) > 0 else None
    except Exception as e:
        logger.error(f"Error getting user_id for project {project_id}: {e}")
        return None

# --- Endpoints ---

@router.get("/api/projects/{project_id}/notifications")
async def get_notifications(
    project_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get notification settings for a project (v1 format).
    Requires authentication and project ownership.
    Email settings: Basic+ plans
    Zapier settings: Automated/Enterprise plans only
    Returns v1 format: reminder_offsets_days, zapier_enabled, email_enabled, email_reminder_offsets_days.
    """
    from api.routers.billing import get_user_plan_and_usage
    
    # Check plan (no gate - Basic+ can view email settings, Automated+ can view Zapier)
    user_id = current_user.get('id')
    user_email = current_user.get('email', '').lower().strip()
    if user_id:
        plan_info = get_user_plan_and_usage(user_id, user_email)
        plan = plan_info.get('plan', 'free')
    else:
        plan = 'free'
    
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
        
        # Return v1 format with email support
        return JSONResponse(content={
            "success": True,
            "project_id": project_id,
            "reminder_offsets_days": settings.get("reminder_offsets_days", [7]),
            "zapier_enabled": settings.get("zapier_enabled", False),
            "email_enabled": settings.get("email_enabled", False),
            "email_reminder_offsets_days": settings.get("email_reminder_offsets_days", [1, 7]),
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
    Requires authentication, project ownership, and Automated/Enterprise plan.
    """
    from api.routers.billing import require_plan
    
    # Gate: Automated/Enterprise plans only
    require_plan(current_user, ["automated", "enterprise"], route_name=f"/api/projects/{project_id}/notifications")
    
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
    settings: NotificationSettingsRequestV1,
    current_user: dict = Depends(get_current_user)
):
    """
    Update notification settings for a project (v1 format).
    Requires authentication and project ownership.
    Email settings: Basic+ plans
    Zapier settings: Automated/Enterprise plans only
    Accepts v1 format: reminder_offsets_days, zapier_enabled, email_enabled, email_reminder_offsets_days.
    """
    from api.routers.billing import get_user_plan_and_usage, validate_reminder_offsets
    
    # Check plan (Basic+ for email, Automated+ for Zapier)
    user_id = current_user.get('id')
    user_email = current_user.get('email', '').lower().strip()
    if user_id:
        plan_info = get_user_plan_and_usage(user_id, user_email)
        plan = plan_info.get('plan', 'free')
    else:
        plan = 'free'
    
    # If trying to enable Zapier, require Automated+
    if settings.zapier_enabled and plan not in ['automated', 'enterprise']:
        raise HTTPException(status_code=403, detail="Zapier automation requires Automated or Enterprise plan")
    
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
        
        # Validate reminder offsets by plan (only for Zapier)
        reminder_offsets_days = settings.reminder_offsets_days or []
        zapier_enabled = settings.zapier_enabled
        
        if zapier_enabled and reminder_offsets_days:
            # Only validate Zapier offsets if Zapier is enabled
            is_valid, error_msg = validate_reminder_offsets(reminder_offsets_days, plan)
            if not is_valid:
                logger.warning(f"PLAN_DENY route=/api/projects/{project_id}/notifications plan={plan} user={current_user.get('email')} reason=invalid_offsets offsets={reminder_offsets_days}")
                raise HTTPException(status_code=400, detail=error_msg)
        
        # Email settings (Basic+ plans can use email)
        email_enabled = settings.email_enabled if settings.email_enabled is not None else False
        email_reminder_offsets_days = settings.email_reminder_offsets_days or []
        
        # Validate email settings
        if email_enabled:
            # Check plan for email
            if plan == 'free':
                raise HTTPException(status_code=403, detail="Email reminders require Basic plan or higher")
            
            # Validate email offsets
            if email_reminder_offsets_days:
                # Basic plan: max 2 offsets (7, 1)
                # Automated/Enterprise: unlimited
                if plan == 'basic' and len(email_reminder_offsets_days) > 2:
                    raise HTTPException(status_code=400, detail="Basic plan allows maximum 2 email reminder offsets (e.g., [7, 1])")
                if len(email_reminder_offsets_days) != len(set(email_reminder_offsets_days)):
                    raise HTTPException(status_code=400, detail="Duplicate email_reminder_offsets_days not allowed")
                for offset in email_reminder_offsets_days:
                    if offset <= 0:
                        raise HTTPException(status_code=400, detail="All email_reminder_offsets_days must be > 0")
            else:
                # If email enabled but no offsets, use default
                email_reminder_offsets_days = [7, 1] if plan == 'basic' else [7, 3, 1]
        
        # Build legacy format for backwards compatibility
        reminders_legacy = [
            {
                "offset_days": offset,
                "channels": {
                    "email": False,  # Email/Slack disabled in v1
                    "slack": False,
                    "zapier": zapier_enabled
                }
            }
            for offset in reminder_offsets_days
        ]
        
        # Store both formats with email support
        settings_data = {
            "reminder_offsets_days": reminder_offsets_days,
            "zapier_enabled": zapier_enabled,
            "email_enabled": email_enabled,
            "email_reminder_offsets_days": email_reminder_offsets_days,
            "reminders": reminders_legacy  # Legacy format for backwards compatibility
        }
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE notification_settings
                    SET reminders = %s::jsonb, updated_at = NOW()
                    WHERE project_id = %s
                    RETURNING id
                """, (json.dumps(settings_data), project_id))
                result = cursor.fetchone()
                if not result:
                    # Create if doesn't exist
                    cursor.execute("""
                        INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                        VALUES (%s, %s::jsonb, NOW(), NOW())
                        RETURNING id
                    """, (project_id, json.dumps(settings_data)))
            else:
                cursor.execute("""
                    UPDATE notification_settings
                    SET reminders = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE project_id = ?
                """, (json.dumps(settings_data), project_id))
                if cursor.rowcount == 0:
                    # Create if doesn't exist
                    cursor.execute("""
                        INSERT INTO notification_settings (project_id, reminders, created_at, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (project_id, json.dumps(settings_data)))
            
            conn.commit()
        
        # Return updated settings (v1 format with email support)
        updated_settings = get_notification_settings(project_id)
        
        return JSONResponse(content={
            "success": True,
            "project_id": project_id,
            "reminder_offsets_days": updated_settings.get("reminder_offsets_days", []),
            "zapier_enabled": updated_settings.get("zapier_enabled", False),
            "email_enabled": updated_settings.get("email_enabled", False),
            "email_reminder_offsets_days": updated_settings.get("email_reminder_offsets_days", []),
            "created_at": updated_settings["created_at"],
            "updated_at": updated_settings["updated_at"]
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_notifications: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

