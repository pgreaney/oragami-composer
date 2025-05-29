"""Error handling with automatic liquidation to cash."""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
import logging

from app.models.user import User
from app.models.symphony import Symphony
from app.graphql.types.trading import LiquidationEvent


logger = logging.getLogger(__name__)


class ErrorHandlerService:
    """Service for handling errors with automatic liquidation."""
    
    async def handle_symphony_error(
        self,
        db: Session,
        user: User,
        symphony: Symphony,
        error: Exception,
        liquidate: bool = True
    ) -> Optional[LiquidationEvent]:
        """Handle symphony execution error.
        
        Args:
            db: Database session
            user: User
            symphony: Symphony that failed
            error: Exception that occurred
            liquidate: Whether to liquidate positions
            
        Returns:
            Liquidation event if liquidation occurred
        """
        error_msg = str(error)
        logger.error(f"Symphony {symphony.id} error for user {user.id}: {error_msg}")
        
        # Update symphony status
        symphony.status = "error"
        symphony.last_error = error_msg
        symphony.last_execution = datetime.utcnow()
        db.commit()
        
        if liquidate:
            # Import here to avoid circular dependency
            from app.services.alpaca_trading_service import alpaca_trading_service
            
            try:
                # Liquidate all positions
                trades = await alpaca_trading_service.close_all_positions(
                    db=db,
                    user=user,
                    symphony_id=symphony.id,
                    reason=f"Algorithm error: {error_msg}"
                )
                
                # Calculate total liquidation value
                total_value = sum(t.total_value for t in trades)
                
                return LiquidationEvent(
                    symphony_id=symphony.id,
                    reason=error_msg,
                    positions_closed=len(trades),
                    total_value=total_value,
                    timestamp=datetime.utcnow(),
                    error_details=str(error)
                )
                
            except Exception as liquidation_error:
                logger.error(
                    f"Failed to liquidate positions for symphony {symphony.id}: "
                    f"{str(liquidation_error)}"
                )
                
                # Update symphony with liquidation failure
                symphony.last_error = f"Liquidation failed: {str(liquidation_error)}"
                db.commit()
        
        return None
    
    async def handle_critical_error(
        self,
        db: Session,
        user: User,
        error: Exception
    ) -> List[LiquidationEvent]:
        """Handle critical system error by liquidating all positions.
        
        Args:
            db: Database session
            user: User
            error: Critical error
            
        Returns:
            List of liquidation events
        """
        logger.critical(f"Critical error for user {user.id}: {str(error)}")
        
        # Get all active symphonies
        active_symphonies = db.query(Symphony).filter(
            Symphony.user_id == user.id,
            Symphony.status == "active"
        ).all()
        
        liquidation_events = []
        
        for symphony in active_symphonies:
            event = await self.handle_symphony_error(
                db=db,
                user=user,
                symphony=symphony,
                error=error,
                liquidate=True
            )
            
            if event:
                liquidation_events.append(event)
        
        return liquidation_events
    
    def log_trading_error(
        self,
        user_id: int,
        symphony_id: int,
        symbol: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """Log trading error for monitoring.
        
        Args:
            user_id: User ID
            symphony_id: Symphony ID
            symbol: Asset symbol
            error_type: Type of error
            error_message: Error message
            context: Additional context
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "symphony_id": symphony_id,
            "symbol": symbol,
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {}
        }
        
        logger.error(f"Trading error: {log_data}")
    
    def should_liquidate(
        self,
        error_type: str,
        error_count: int = 1
    ) -> bool:
        """Determine if positions should be liquidated based on error.
        
        Args:
            error_type: Type of error
            error_count: Number of times error occurred
            
        Returns:
            True if should liquidate
        """
        # Critical errors that always trigger liquidation
        critical_errors = [
            "market_data_unavailable",
            "algorithm_exception",
            "risk_limit_exceeded",
            "account_blocked",
            "insufficient_funds"
        ]
        
        if error_type in critical_errors:
            return True
        
        # Errors that trigger liquidation after multiple occurrences
        threshold_errors = {
            "order_rejected": 3,
            "connection_lost": 5,
            "rate_limit": 10
        }
        
        if error_type in threshold_errors:
            return error_count >= threshold_errors[error_type]
        
        return False
    
    async def notify_user_of_liquidation(
        self,
        user: User,
        event: LiquidationEvent
    ):
        """Notify user of liquidation event.
        
        Args:
            user: User
            event: Liquidation event
        """
        # In a real system, this would send email/SMS/push notification
        logger.info(
            f"Liquidation notification for user {user.email}: "
            f"Symphony {event.symphony_id} liquidated {event.positions_closed} positions "
            f"(${event.total_value}) due to: {event.reason}"
        )


# Global service instance
error_handler_service = ErrorHandlerService()
