"""Trading business logic."""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User
from app.models.position import Position
from app.models.trade import Trade
from app.models.performance import PerformanceMetric
from app.models.symphony import Symphony
from app.services.market_data_service import get_market_data_service, MarketDataService
from app.schemas.market_data import Quote


class TradingServiceError(Exception):
    """Trading service error."""
    pass


class TradingService:
    """Service for managing trading operations."""
    
    def __init__(self, market_data: Optional[MarketDataService] = None):
        """Initialize trading service.
        
        Args:
            market_data: Market data service
        """
        self.market_data = market_data or get_market_data_service()
    
    def get_position(
        self,
        db: Session,
        user: User,
        symbol: str,
        symphony_id: Optional[int] = None
    ) -> Optional[Position]:
        """Get position for a symbol.
        
        Args:
            db: Database session
            user: User
            symbol: Asset symbol
            symphony_id: Symphony ID
            
        Returns:
            Position or None
        """
        query = db.query(Position).filter(
            and_(
                Position.user_id == user.id,
                Position.symbol == symbol.upper()
            )
        )
        
        if symphony_id:
            query = query.filter(Position.symphony_id == symphony_id)
        
        return query.first()
    
    def get_positions(
        self,
        db: Session,
        user: User,
        symphony_id: Optional[int] = None,
        active_only: bool = True
    ) -> List[Position]:
        """Get all positions.
        
        Args:
            db: Database session
            user: User
            symphony_id: Filter by symphony
            active_only: Only return non-zero positions
            
        Returns:
            List of positions
        """
        query = db.query(Position).filter(Position.user_id == user.id)
        
        if symphony_id:
            query = query.filter(Position.symphony_id == symphony_id)
        
        if active_only:
            query = query.filter(Position.quantity != 0)
        
        return query.all()
    
    def create_or_update_position(
        self,
        db: Session,
        user: User,
        symphony_id: int,
        symbol: str,
        quantity: Decimal,
        price: Decimal
    ) -> Position:
        """Create or update a position.
        
        Args:
            db: Database session
            user: User
            symphony_id: Symphony ID
            symbol: Asset symbol
            quantity: Position quantity (positive for long, negative for short)
            price: Current price
            
        Returns:
            Updated position
        """
        position = self.get_position(db, user, symbol, symphony_id)
        
        if position:
            # Update existing position
            old_quantity = position.quantity
            old_cost = position.cost_basis
            
            # Calculate new average price
            if quantity > 0:  # Adding to position
                total_cost = old_cost + (quantity * price)
                new_quantity = old_quantity + quantity
                position.average_price = total_cost / new_quantity if new_quantity != 0 else Decimal("0")
                position.cost_basis = total_cost
            else:  # Reducing position
                new_quantity = old_quantity + quantity  # quantity is negative
                if new_quantity != 0:
                    position.cost_basis = position.average_price * new_quantity
                else:
                    position.cost_basis = Decimal("0")
                    position.average_price = Decimal("0")
            
            position.quantity = new_quantity
        else:
            # Create new position
            position = Position(
                user_id=user.id,
                symphony_id=symphony_id,
                symbol=symbol.upper(),
                quantity=quantity,
                average_price=price,
                cost_basis=quantity * price
            )
            db.add(position)
        
        # Update current market data
        position.current_price = price
        position.market_value = position.quantity * price
        position.unrealized_pnl = position.market_value - position.cost_basis
        position.unrealized_pnl_percent = (
            (position.unrealized_pnl / position.cost_basis * 100) 
            if position.cost_basis != 0 else Decimal("0")
        )
        position.last_updated = datetime.utcnow()
        
        db.commit()
        db.refresh(position)
        
        return position
    
    def record_trade(
        self,
        db: Session,
        user: User,
        symphony_id: int,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal("0"),
        alpaca_order_id: Optional[str] = None,
        status: str = "executed",
        error_message: Optional[str] = None
    ) -> Trade:
        """Record a trade execution.
        
        Args:
            db: Database session
            user: User
            symphony_id: Symphony ID
            symbol: Asset symbol
            side: 'buy' or 'sell'
            quantity: Trade quantity
            price: Execution price
            commission: Commission amount
            alpaca_order_id: Alpaca order ID
            status: Trade status
            error_message: Error message if failed
            
        Returns:
            Trade record
        """
        total_value = quantity * price
        
        trade = Trade(
            user_id=user.id,
            symphony_id=symphony_id,
            symbol=symbol.upper(),
            side=side,
            quantity=quantity,
            price=price,
            total_value=total_value,
            commission=commission,
            status=status,
            alpaca_order_id=alpaca_order_id,
            executed_at=datetime.utcnow(),
            error_message=error_message
        )
        
        db.add(trade)
        db.commit()
        db.refresh(trade)
        
        # Update position if trade was executed
        if status == "executed":
            # For sells, quantity should be negative
            position_quantity = quantity if side == "buy" else -quantity
            self.create_or_update_position(
                db, user, symphony_id, symbol, position_quantity, price
            )
        
        return trade
    
    async def update_position_prices(
        self,
        db: Session,
        user: User,
        positions: Optional[List[Position]] = None
    ) -> List[Position]:
        """Update current prices for positions.
        
        Args:
            db: Database session
            user: User
            positions: Specific positions to update (or all if None)
            
        Returns:
            Updated positions
        """
        if positions is None:
            positions = self.get_positions(db, user)
        
        if not positions:
            return []
        
        # Get quotes for all symbols
        symbols = [p.symbol for p in positions]
        quotes = await self.market_data.get_batch_quotes(symbols)
        
        # Update each position
        for position in positions:
            if position.symbol in quotes:
                quote = quotes[position.symbol]
                position.current_price = quote.price
                position.market_value = position.quantity * quote.price
                position.unrealized_pnl = position.market_value - position.cost_basis
                position.unrealized_pnl_percent = (
                    (position.unrealized_pnl / position.cost_basis * 100) 
                    if position.cost_basis != 0 else Decimal("0")
                )
                position.last_updated = datetime.utcnow()
        
        db.commit()
        
        return positions
    
    def calculate_portfolio_value(
        self,
        db: Session,
        user: User,
        cash_balance: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """Calculate total portfolio value.
        
        Args:
            db: Database session
            user: User
            cash_balance: Current cash balance
            
        Returns:
            Tuple of (total_value, positions_value, cash_percentage)
        """
        positions = self.get_positions(db, user)
        
        positions_value = sum(p.market_value for p in positions)
        total_value = positions_value + cash_balance
        cash_percentage = (cash_balance / total_value * 100) if total_value > 0 else Decimal("100")
        
        return total_value, positions_value, cash_percentage
    
    def record_performance(
        self,
        db: Session,
        user: User,
        symphony_id: Optional[int] = None,
        total_value: Optional[Decimal] = None,
        calculate_metrics: bool = True
    ) -> PerformanceMetric:
        """Record performance metrics.
        
        Args:
            db: Database session
            user: User
            symphony_id: Symphony ID (None for overall portfolio)
            total_value: Current total value
            calculate_metrics: Whether to calculate advanced metrics
            
        Returns:
            Performance metric
        """
        # Get previous metric
        previous = db.query(PerformanceMetric).filter(
            and_(
                PerformanceMetric.user_id == user.id,
                PerformanceMetric.symphony_id == symphony_id
            )
        ).order_by(PerformanceMetric.date.desc()).first()
        
        # Calculate returns
        if previous and total_value:
            daily_return = ((total_value - previous.total_value) / previous.total_value * 100)
            cumulative_return = previous.cumulative_return + daily_return
        else:
            daily_return = Decimal("0")
            cumulative_return = Decimal("0")
        
        metric = PerformanceMetric(
            user_id=user.id,
            symphony_id=symphony_id,
            date=datetime.utcnow(),
            total_value=total_value or Decimal("0"),
            daily_return=daily_return,
            cumulative_return=cumulative_return
        )
        
        if calculate_metrics:
            # Calculate additional metrics
            # This would involve more complex calculations using historical data
            pass
        
        db.add(metric)
        db.commit()
        db.refresh(metric)
        
        return metric
    
    def get_trades(
        self,
        db: Session,
        user: User,
        symphony_id: Optional[int] = None,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get trade history.
        
        Args:
            db: Database session
            user: User
            symphony_id: Filter by symphony
            symbol: Filter by symbol
            start_date: Start date
            end_date: End date
            limit: Maximum results
            
        Returns:
            List of trades
        """
        query = db.query(Trade).filter(Trade.user_id == user.id)
        
        if symphony_id:
            query = query.filter(Trade.symphony_id == symphony_id)
        
        if symbol:
            query = query.filter(Trade.symbol == symbol.upper())
        
        if start_date:
            query = query.filter(Trade.executed_at >= start_date)
        
        if end_date:
            query = query.filter(Trade.executed_at <= end_date)
        
        return query.order_by(Trade.executed_at.desc()).limit(limit).all()
    
    def close_all_positions(
        self,
        db: Session,
        user: User,
        symphony_id: int,
        reason: str = "Manual close"
    ) -> List[Trade]:
        """Close all positions for a symphony (liquidation).
        
        Args:
            db: Database session
            user: User
            symphony_id: Symphony ID
            reason: Reason for closing
            
        Returns:
            List of closing trades
        """
        positions = self.get_positions(db, user, symphony_id)
        trades = []
        
        for position in positions:
            if position.quantity != 0:
                # Record closing trade
                side = "sell" if position.quantity > 0 else "buy"
                quantity = abs(position.quantity)
                
                trade = self.record_trade(
                    db=db,
                    user=user,
                    symphony_id=symphony_id,
                    symbol=position.symbol,
                    side=side,
                    quantity=quantity,
                    price=position.current_price,
                    status="executed",
                    error_message=f"Liquidation: {reason}"
                )
                
                trades.append(trade)
        
        return trades


# Global service instance
trading_service = TradingService()
