"""OAuth callback handling and endpoints."""

from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.dependencies import get_current_active_user
from app.models.user import User
from app.services.alpaca_oauth_service import alpaca_oauth_service
from app.schemas.alpaca import (
    AlpacaConnectionStatus,
    AlpacaAccountInfo,
    OAuthInitResponse
)
from app.config import settings


router = APIRouter(prefix="/oauth", tags=["OAuth"])


@router.get("/alpaca/connect", response_model=OAuthInitResponse)
async def initiate_alpaca_oauth(
    current_user: User = Depends(get_current_active_user)
) -> OAuthInitResponse:
    """Initiate Alpaca OAuth connection for paper trading.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        OAuth URL to redirect user to
        
    Raises:
        HTTPException: If OAuth not configured
    """
    try:
        auth_url = alpaca_oauth_service.get_authorization_url(current_user.id)
        
        return OAuthInitResponse(
            auth_url=auth_url,
            message="Redirect user to the authorization URL"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )


@router.get("/alpaca/callback")
async def alpaca_oauth_callback(
    code: str = Query(..., description="Authorization code from Alpaca"),
    state: str = Query(..., description="State token for security"),
    db: Session = Depends(get_db)
) -> RedirectResponse:
    """Handle Alpaca OAuth callback.
    
    Args:
        code: Authorization code from Alpaca
        state: State token for verification
        db: Database session
        
    Returns:
        Redirect to frontend success or error page
    """
    frontend_url = settings.FRONTEND_URL
    
    # Verify state token
    user_id = alpaca_oauth_service.verify_state_token(state)
    if not user_id:
        return RedirectResponse(
            url=f"{frontend_url}/settings?error=invalid_state"
        )
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return RedirectResponse(
            url=f"{frontend_url}/settings?error=user_not_found"
        )
    
    # Exchange code for tokens
    try:
        token_response = await alpaca_oauth_service.exchange_code_for_tokens(code)
        
        if not token_response:
            return RedirectResponse(
                url=f"{frontend_url}/settings?error=token_exchange_failed"
            )
        
        # Save tokens
        success = alpaca_oauth_service.save_tokens(db, user, token_response)
        
        if success:
            return RedirectResponse(
                url=f"{frontend_url}/settings?success=alpaca_connected"
            )
        else:
            return RedirectResponse(
                url=f"{frontend_url}/settings?error=token_save_failed"
            )
            
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        return RedirectResponse(
            url=f"{frontend_url}/settings?error=oauth_error"
        )


@router.get("/alpaca/status", response_model=AlpacaConnectionStatus)
async def get_alpaca_connection_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> AlpacaConnectionStatus:
    """Check Alpaca OAuth connection status.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Connection status
    """
    is_valid, _ = await alpaca_oauth_service.check_token_validity(db, current_user)
    
    account_info = None
    if is_valid and current_user.alpaca_access_token:
        # Get account info if connected
        account_data = await alpaca_oauth_service.get_account_info(
            current_user.alpaca_access_token
        )
        
        if account_data:
            account_info = AlpacaAccountInfo(
                account_number=account_data.get("account_number", ""),
                buying_power=float(account_data.get("buying_power", 0)),
                cash=float(account_data.get("cash", 0)),
                portfolio_value=float(account_data.get("portfolio_value", 0)),
                pattern_day_trader=account_data.get("pattern_day_trader", False),
                trading_blocked=account_data.get("trading_blocked", False),
                account_blocked=account_data.get("account_blocked", False)
            )
    
    return AlpacaConnectionStatus(
        connected=is_valid,
        account_id=current_user.alpaca_account_id,
        token_expires_at=current_user.alpaca_token_expires_at,
        account_info=account_info
    )


@router.post("/alpaca/disconnect", response_model=Dict[str, str])
async def disconnect_alpaca(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Disconnect Alpaca OAuth connection.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
    """
    success = alpaca_oauth_service.revoke_tokens(db, current_user)
    
    if success:
        return {"message": "Alpaca account disconnected successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect Alpaca account"
        )


@router.post("/alpaca/refresh", response_model=Dict[str, str])
async def refresh_alpaca_tokens(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Manually refresh Alpaca OAuth tokens.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If refresh fails
    """
    if not current_user.alpaca_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available"
        )
    
    try:
        token_response = await alpaca_oauth_service.refresh_access_token(
            current_user.alpaca_refresh_token
        )
        
        if not token_response:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh tokens"
            )
        
        success = alpaca_oauth_service.save_tokens(db, current_user, token_response)
        
        if success:
            return {"message": "Tokens refreshed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save refreshed tokens"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh error: {str(e)}"
        )
