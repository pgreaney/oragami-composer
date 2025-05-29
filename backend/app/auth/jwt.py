"""JWT utilities and token management for authentication."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from pydantic import BaseModel
from app.config import settings


class TokenData(BaseModel):
    """Token data model for JWT payload."""
    user_id: int
    email: str
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None


class JWTManager:
    """Manages JWT token creation, validation, and decoding."""
    
    def __init__(
        self,
        secret_key: str = settings.JWT_SECRET,
        algorithm: str = settings.JWT_ALGORITHM,
        access_token_expire_minutes: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days: int = settings.REFRESH_TOKEN_EXPIRE_DAYS
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create a new access token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create a new refresh token."""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> Optional[TokenData]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            
            # Validate token type if present
            if "type" in payload and payload["type"] not in ["access", "refresh"]:
                return None
            
            return TokenData(
                user_id=payload.get("user_id"),
                email=payload.get("email"),
                exp=payload.get("exp"),
                iat=payload.get("iat")
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenData]:
        """Verify a token and check its type."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check token type
            if payload.get("type") != token_type:
                return None
            
            return TokenData(
                user_id=payload.get("user_id"),
                email=payload.get("email"),
                exp=payload.get("exp"),
                iat=payload.get("iat")
            )
        except Exception:
            return None
    
    def create_token_pair(self, user_id: int, email: str) -> Dict[str, str]:
        """Create both access and refresh tokens."""
        data = {"user_id": user_id, "email": email}
        
        return {
            "access_token": self.create_access_token(data),
            "refresh_token": self.create_refresh_token(data),
            "token_type": "bearer"
        }


# Global JWT manager instance
jwt_manager = JWTManager()
