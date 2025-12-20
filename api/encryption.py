"""
Encryption utilities for sensitive broker payment data
Uses Fernet symmetric encryption (AES 128)
"""
import os
from cryptography.fernet import Fernet
import base64

# Generate or load encryption key from environment
def get_encryption_key():
    """Get encryption key from environment or generate new one"""
    key = os.environ.get('ENCRYPTION_KEY')
    if not key:
        # Generate new key (should be set in production)
        key = Fernet.generate_key().decode()
        print(f"⚠️ WARNING: Generated new encryption key. Set ENCRYPTION_KEY={key} in environment")
    else:
        # Ensure key is bytes
        if isinstance(key, str):
            key = key.encode()
    return key

# Initialize Fernet cipher
try:
    _key = get_encryption_key()
    _cipher = Fernet(_key)
except Exception as e:
    print(f"⚠️ Encryption initialization error: {e}")
    _cipher = None

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data (bank account numbers, etc.)"""
    if not data:
        return ""
    
    if not _cipher:
        # Fallback: base64 encoding (not secure, but better than plaintext)
        print("⚠️ Encryption not available, using base64 encoding")
        return base64.b64encode(data.encode()).decode()
    
    try:
        encrypted = _cipher.encrypt(data.encode())
        return encrypted.decode()
    except Exception as e:
        print(f"❌ Encryption error: {e}")
        # Fallback to base64
        return base64.b64encode(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    if not encrypted_data:
        return ""
    
    if not _cipher:
        # Fallback: base64 decoding
        try:
            return base64.b64decode(encrypted_data.encode()).decode()
        except:
            return ""
    
    try:
        decrypted = _cipher.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"❌ Decryption error: {e}")
        # Try base64 fallback
        try:
            return base64.b64decode(encrypted_data.encode()).decode()
        except:
            return ""

def mask_sensitive_data(data: str, show_last: int = 4) -> str:
    """Mask sensitive data for display (show last N characters)"""
    if not data or len(data) <= show_last:
        return "****"
    return "*" * (len(data) - show_last) + data[-show_last:]

