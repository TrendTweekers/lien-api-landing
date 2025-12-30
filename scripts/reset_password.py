#!/usr/bin/env python3
"""
Reset password for a user in the database.

Usage:
    python scripts/reset_password.py polishlofihaven@gmail.com

Or set EMAIL environment variable:
    EMAIL=polishlofihaven@gmail.com python scripts/reset_password.py
"""

import os
import sys
import bcrypt
from pathlib import Path

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import get_db, get_db_cursor, DB_TYPE

def reset_password(email: str, temp_password: str = None):
    """
    Reset password for a user.
    
    Args:
        email: User email address
        temp_password: Optional temporary password (if not provided, generates one)
    """
    if not temp_password:
        import secrets
        temp_password = "TempPass123!"
    
    # Hash the password using bcrypt (same method as signup)
    password_hash = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt())
    
    # For PostgreSQL, decode the hash to string
    if DB_TYPE == 'postgresql':
        password_hash_str = password_hash.decode('utf-8')
    else:
        password_hash_str = password_hash
    
    print(f"🔐 Resetting password for: {email}")
    print(f"📝 Temporary password: {temp_password}")
    print(f"🔒 Password hash: {password_hash_str[:50]}...")
    print(f"🗄️  Database Type: {DB_TYPE}")
    print()
    
    # Warn if using local SQLite (likely not the production database)
    if DB_TYPE == 'sqlite':
        print("⚠️  WARNING: Using local SQLite database.")
        print("   For Railway production, ensure DATABASE_URL environment variable is set.")
        print()
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if user exists
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, email FROM users WHERE email = %s", (email.lower(),))
            else:
                cursor.execute("SELECT id, email FROM users WHERE email = ?", (email.lower(),))
            
            user = cursor.fetchone()
            
            if not user:
                print(f"❌ Error: User with email '{email}' not found in database.")
                return False
            
            # Extract user ID
            if isinstance(user, dict):
                user_id = user.get('id')
                user_email = user.get('email')
            else:
                user_id = user[0] if len(user) > 0 else None
                user_email = user[1] if len(user) > 1 else None
            
            print(f"✅ Found user: {user_email} (ID: {user_id})")
            
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
            
            print(f"✅ Password updated successfully!")
            print()
            print("=" * 60)
            print("📋 LOGIN CREDENTIALS")
            print("=" * 60)
            print(f"Email:    {email}")
            print(f"Password: {temp_password}")
            print("=" * 60)
            print()
            print("⚠️  IMPORTANT: User should change this password after logging in.")
            
            return True
            
    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Get email from command line argument or environment variable
    email = None
    
    if len(sys.argv) > 1:
        email = sys.argv[1]
    else:
        email = os.getenv('EMAIL')
    
    if not email:
        print("Usage: python scripts/reset_password.py <email>")
        print("   Or: EMAIL=<email> python scripts/reset_password.py")
        sys.exit(1)
    
    # Reset password
    success = reset_password(email)
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

