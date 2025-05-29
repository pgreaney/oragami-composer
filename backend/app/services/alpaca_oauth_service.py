"""OAuth flow implementation for Alpaca paper trading."""

import secrets
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.user import User
from app.config import settings
from app.auth.oauth_utils import encrypt_token, decrypt_token


class AlpacaOAuthService:
    """Service for handling Alpaca OAuth 2.0 flow (paper trading only)."""
    
    def __init__(self):
        self.client_id = settings.ALPACA_CLIENT_ID
        self.client_secret = settings.ALPACA_CLIENT_SECRET
        self.redirect_uri = settings.ALPACA_REDIRECT_URI
        self.oauth_base_url = settings.ALPACA_OAUTH_BASE_URL
        self.api_base_url = settings.ALPACA_PAPER_BASE_URL
        
        # OAuth endpoints
        self.authorize_url = f"{self.oauth_base_url}/authorize"
        self.token_url = f"{self.oauth_base_url}/token"
        
    def generate_state_token(self, user_id: int) -> str:
        """Generate a secure state token for OAuth flow.
        
        Args:
            user_id: User ID to encode in state
            
        Returns:
            Secure state token
        """
        # Generate random state
        random_state = secrets.token_urlsafe(32)
        # Combine with user_id for validation
        state = f"{user_id}:{random_state}"
        return state
    
    def verify_state_token(self, state: str) -> Optional[int]:
        """Verify and extract user_id from state token.
        
        Args:
            state: State token from OAuth callback
            
        Returns:
            User ID if valid, None otherwise
        """
        try:
            user_id_str, _ = state.split(":", 1)
            return int(user_id_str)
        except (ValueError, AttributeError):
            return None
    
    def get_authorization_url(self, user_id: int) -> str:
        """Generate OAuth authorization URL.
        
        Args:
            user_id: User requesting authorization
            
        Returns:
            Authorization URL for Alpaca OAuth
        """
        if not self.client_id:
            raise ValueError("Alpaca OAuth not configured. Please set ALPACA_CLIENT_ID")
        
        state = self.generate_state_token(user_id)
        
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "trading:paper",  # Paper trading only
        }
        
        return f"{self.authorize_url}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(
        self, 
        code: str
    ) -> Optional[Dict[str, str]]:
        """Exchange authorization code for access tokens.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            Token response or None if failed
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Alpaca OAuth not configured")
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Token exchange failed: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Token exchange error: {str(e)}")
                return None
    
    async def refresh_access_token(
        self, 
        refresh_token: str
    ) -> Optional[Dict[str, str]]:
        """Refresh access token using refresh token.
        
        Args:
            refresh_token: Encrypted refresh token
            
        Returns:
            New token response or None if failed
        """
        if not self.client_id or not self.client_secret:
            raise ValueError("Alpaca OAuth not configured")
        
        # Decrypt refresh token
        decrypted_token = decrypt_token(refresh_token)
        if not decrypted_token:
            return None
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": decrypted_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Token refresh failed: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"Token refresh error: {str(e)}")
                return None
    
    def save_tokens(
        self,
        db: Session,
        user: User,
        token_response: Dict[str, str]
    ) -> bool:
        """Save OAuth tokens to user record.
        
        Args:
            db: Database session
            user: User to update
            token_response: Token response from Alpaca
            
        Returns:
            True if saved successfully
        """
        try:
            # Encrypt tokens before saving
            access_token = encrypt_token(token_response.get("access_token", ""))
            refresh_token = encrypt_token(token_response.get("refresh_token", ""))
            
            # Calculate token expiry
            expires_in = token_response.get("expires_in", 3600)  # Default 1 hour
            token_expires_at = datetime.now(timezone.utc).timestamp() + expires_in
            
            # Update user record
            user.alpaca_access_token = access_token
            user.alpaca_refresh_token = refresh_token
            user.alpaca_token_expires_at = datetime.fromtimestamp(
                token_expires_at, 
                timezone.utc
            )
            user.alpaca_account_id = token_response.get("account_id")
            user.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            return True
            
        except Exception as e:
            print(f"Error saving tokens: {str(e)}")
            db.rollback()
            return False
    
    def revoke_tokens(self, db: Session, user: User) -> bool:
        """Revoke and remove Alpaca OAuth tokens.
        
        Args:
            db: Database session
            user: User to revoke tokens for
            
        Returns:
            True if revoked successfully
        """
        try:
            user.alpaca_access_token = None
            user.alpaca_refresh_token = None
            user.alpaca_token_expires_at = None
            user.alpaca_account_id = None
            user.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            return True
            
        except Exception as e:
            print(f"Error revoking tokens: {str(e)}")
            db.rollback()
            return False
    
    async def get_account_info(self, access_token: str) -> Optional[Dict[str, any]]:
        """Get Alpaca account information.
        
        Args:
            access_token: Encrypted access token
            
        Returns:
            Account info or None if failed
        """
        # Decrypt access token
        decrypted_token = decrypt_token(access_token)
        if not decrypted_token:
            return None
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.api_base_url}/v2/account",
                    headers={
                        "Authorization": f"Bearer {decrypted_token}",
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get account info: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"Error getting account info: {str(e)}")
                return None
    
    async def check_token_validity(
        self, 
        db: Session, 
        user: User
    ) -> Tuple[bool, Optional[str]]:
        """Check if user's Alpaca tokens are valid.
        
        Args:
            db: Database session
            user: User to check
            
        Returns:
            Tuple of (is_valid, access_token)
        """
        if not user.alpaca_access_token:
            return False, None
        
        # Check if token is expired
        if user.alpaca_token_expires_at:
            if datetime.now(timezone.utc) >= user.alpaca_token_expires_at:
                # Try to refresh token
                if user.alpaca_refresh_token:
                    token_response = await self.refresh_access_token(
                        user.alpaca_refresh_token
                    )
                    
                    if token_response:
                        self.save_tokens(db, user, token_response)
                        return True, user.alpaca_access_token
                
                return False, None
        
        # Verify token by making a test API call
        account_info = await self.get_account_info(user.alpaca_access_token)
        if account_info:
            return True, user.alpaca_access_token
        
        return False, None


# Global Alpaca OAuth service instance
alpaca_oauth_service = AlpacaOAuthService()
