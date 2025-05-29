"""OAuth utilities and token encryption/decryption."""

import base64
from typing import Optional
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


class TokenEncryption:
    """Handles encryption and decryption of OAuth tokens."""
    
    def __init__(self, secret_key: str = None):
        """Initialize encryption with a secret key.
        
        Args:
            secret_key: Secret key for encryption, defaults to app secret
        """
        secret = secret_key or settings.SECRET_KEY
        
        # Derive a proper key from the secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'origami-composer-salt',  # In production, use a random salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
        self.cipher = Fernet(key)
    
    def encrypt(self, token: str) -> str:
        """Encrypt a token.
        
        Args:
            token: Plain text token
            
        Returns:
            Encrypted token as string
        """
        if not token:
            return ""
        
        try:
            encrypted = self.cipher.encrypt(token.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            print(f"Encryption error: {str(e)}")
            return ""
    
    def decrypt(self, encrypted_token: str) -> Optional[str]:
        """Decrypt a token.
        
        Args:
            encrypted_token: Encrypted token string
            
        Returns:
            Decrypted token or None if decryption fails
        """
        if not encrypted_token:
            return None
        
        try:
            # Decode from base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode())
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {str(e)}")
            return None


# Global token encryption instance
_token_encryption = TokenEncryption()


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token.
    
    Args:
        token: Plain text token
        
    Returns:
        Encrypted token
    """
    return _token_encryption.encrypt(token)


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """Decrypt an OAuth token.
    
    Args:
        encrypted_token: Encrypted token
        
    Returns:
        Decrypted token or None
    """
    return _token_encryption.decrypt(encrypted_token)


def generate_oauth_state(user_id: int) -> str:
    """Generate a secure state parameter for OAuth flows.
    
    Args:
        user_id: User ID to encode
        
    Returns:
        Secure state string
    """
    import secrets
    import json
    
    state_data = {
        "user_id": user_id,
        "nonce": secrets.token_urlsafe(16),
        "timestamp": int(datetime.now(timezone.utc).timestamp())
    }
    
    state_json = json.dumps(state_data)
    return encrypt_token(state_json)


def verify_oauth_state(state: str, max_age_seconds: int = 600) -> Optional[int]:
    """Verify and extract user_id from OAuth state.
    
    Args:
        state: Encrypted state string
        max_age_seconds: Maximum age of state in seconds
        
    Returns:
        User ID if valid, None otherwise
    """
    import json
    
    decrypted = decrypt_token(state)
    if not decrypted:
        return None
    
    try:
        state_data = json.loads(decrypted)
        
        # Check timestamp
        timestamp = state_data.get("timestamp", 0)
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        if current_time - timestamp > max_age_seconds:
            return None
        
        return state_data.get("user_id")
        
    except (json.JSONDecodeError, KeyError):
        return None


def safe_compare_tokens(token1: str, token2: str) -> bool:
    """Safely compare two tokens in constant time.
    
    Args:
        token1: First token
        token2: Second token
        
    Returns:
        True if tokens match
    """
    import hmac
    
    return hmac.compare_digest(token1, token2)
