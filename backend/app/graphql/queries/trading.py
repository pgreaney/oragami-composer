"""Trading GraphQL query resolvers."""

from typing import List, Optional, Dict
from datetime import datetime, timedelta
from decimal import Decimal
import strawberry
from strawberry.types import Info
from sqlalchemy import and_, desc

from app.graphql.context import GraphQLContext
from app.graphql.types.trading import (
    Position,
    Trade,
    PerformanceMetric,
    PortfolioSummary
)
from app.models.position import Position as PositionModel
from app.models.trade import Trade as TradeModel
from app.models.performance import PerformanceMetric as PerformanceModel


@strawberry.type
class TradingQueries:
    """Trading-related queries."""
    
    @strawberry.field
    async def positions(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None,
        active_only: bool = True
    ) -> List[Position]:
        """Get current positions.
        
        Args:
            info: GraphQL context info
            symphony_id: Filter by symphony
            active_only: Only return non-zero positions
            
        Returns:
            List of positions
        """
        # Require authentication
        user = info.context.require_auth()
        
        query = info.context.db.query(PositionModel).filter(
            PositionModel.user_id == user.id
        )
        
        if symphony_id:
            query = query.filter(PositionModel.symphony_id == symphony_id)
        
        if active_only:
            query = query.filter(PositionModel.quantity != 0)
        
        positions = query.order_by(desc(PositionModel.market_value)).all()
        
        return [Position.from_model(p) for p in positions]
    
    @strawberry.field
    async def position(
        self,
        info: Info[GraphQLContext],
        symbol: str,
        symphony_id: Optional[int] = None
    ) -> Optional[Position]:
        """Get position for a specific symbol.
        
        Args:
            info: GraphQL context info
            symbol: Asset symbol
            symphony_id: Symphony ID
            
        Returns:
            Position or None
        """
        # Require authentication
        user = info.context.require_auth()
        
        query = info.context.db.query(PositionModel).filter(
            and_(
                PositionModel.user_id == user.id,
                PositionModel.symbol == symbol.upper()
            )
        )
        
        if symphony_id:
            query = query.filter(PositionModel.symphony_id == symphony_id)
        
        position = query.first()
        
        if position:
            return Position.from_model(position)
        
        return None
    
    @strawberry.field
    async def trades(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Trade]:
        """Get trade history.
        
        Args:
            info: GraphQL context info
            symphony_id: Filter by symphony
            symbol: Filter by symbol
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            offset: Result offset
            
        Returns:
            List of trades
        """
        # Require authentication
        user = info.context.require_auth()
        
        query = info.context.db.query(TradeModel).filter(
            TradeModel.user_id == user.id
        )
        
        if symphony_id:
            query = query.filter(TradeModel.symphony_id == symphony_id)
        
        if symbol:
            query = query.filter(TradeModel.symbol == symbol.upper())
        
        if start_date:
            query = query.filter(TradeModel.executed_at >= start_date)
        
        if end_date:
            query = query.filter(TradeModel.executed_at <= end_date)
        
        trades = query.order_by(desc(TradeModel.executed_at)).limit(limit).offset(offset).all()
        
        return [Trade.from_model(t) for t in trades]
    
    @strawberry.field
    async def recent_trades(
        self,
        info: Info[GraphQLContext],
        days: int = 7,
        limit: int = 50
    ) -> List[Trade]:
        """Get recent trades.
        
        Args:
            info: GraphQL context info
            days: Number of days to look back
            limit: Maximum results
            
        Returns:
            List of recent trades
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        return await self.trades(
            info=info,
            start_date=start_date,
            limit=limit
        )
    
    @strawberry.field
    async def performance_metrics(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        interval: str = "daily"
    ) -> List[PerformanceMetric]:
        """Get performance metrics.
        
        Args:
            info: GraphQL context info
            symphony_id: Filter by symphony
            start_date: Start date
            end_date: End date
            interval: Data interval (daily, weekly, monthly)
            
        Returns:
            List of performance metrics
        """
        # Require authentication
        user = info.context.require_auth()
        
        query = info.context.db.query(PerformanceModel).filter(
            PerformanceModel.user_id == user.id
        )
        
        if symphony_id:
            query = query.filter(PerformanceModel.symphony_id == symphony_id)
        
        if start_date:
            query = query.filter(PerformanceModel.date >= start_date)
        
        if end_date:
            query = query.filter(PerformanceModel.date <= end_date)
        
        metrics = query.order_by(PerformanceModel.date).all()
        
        return [PerformanceMetric.from_model(m) for m in metrics]
    
    @strawberry.field
    async def latest_performance(
        self,
        info: Info[GraphQLContext],
        symphony_id: Optional[int] = None
    ) -> Optional[PerformanceMetric]:
        """Get latest performance metric.
        
        Args:
            info: GraphQL context info
            symphony_id: Symphony ID
            
        Returns:
            Latest performance metric
        """
        # Require authentication
        user = info.context.require_auth()
        
        query = info.context.db.query(PerformanceModel).filter(
            PerformanceModel.user_id == user.id
        )
        
        if symphony_id:
            query = query.filter(PerformanceModel.symphony_id == symphony_id)
        
        metric = query.order_by(desc(PerformanceModel.date)).first()
        
        if metric:
            return PerformanceMetric.from_model(metric)
        
        return None
    
    @strawberry.field
    async def portfolio_summary(
        self,
        info: Info[GraphQLContext]
    ) -> PortfolioSummary:
        """Get overall portfolio summary.
        
        Args:
            info: GraphQL context info
            
        Returns:
            Portfolio summary
        """
        # Require authentication
        user = info.context.require_auth()
        
        # Get all active positions
        positions = info.context.db.query(PositionModel).filter(
            and_(
                PositionModel.user_id == user.id,
                PositionModel.quantity != 0
            )
        ).all()
        
        # Calculate totals
        positions_value = sum(p.market_value for p in positions)
        total_cost = sum(p.cost_basis for p in positions)
        
        # Get cash balance from Alpaca (mock for now)
        cash_balance = Decimal("10000.00")  # TODO: Get from Alpaca
        
        total_value = positions_value + cash_balance
        
        # Calculate P&L
        total_pnl = positions_value - total_cost if positions else Decimal("0")
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal("0")
        
        # Get today's performance
        latest_metric = await self.latest_performance(info)
        daily_pnl = latest_metric.daily_return if latest_metric else Decimal("0")
        daily_pnl_percent = daily_pnl
        
        return PortfolioSummary(
            total_value=total_value,
            cash_balance=cash_balance,
            positions_value=positions_value,
            daily_pnl=daily_pnl,
            daily_pnl_percent=daily_pnl_percent,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            position_count=len(positions)
        )
    
    @strawberry.field
    async def symphony_positions(
        self,
        info: Info[GraphQLContext],
        symphony_id: int
    ) -> List[Position]:
        """Get positions for a specific symphony.
        
        Args:
            info: GraphQL context info
            symphony_id: Symphony ID
            
        Returns:
            List of positions
        """
        return await self.positions(info, symphony_id=symphony_id)
    
    @strawberry.field
    async def symphony_trades(
        self,
        info: Info[GraphQLContext],
        symphony_id: int,
        limit: int = 50
    ) -> List[Trade]:
        """Get trades for a specific symphony.
        
        Args:
            info: GraphQL context info
            symphony_id: Symphony ID
            limit: Maximum results
            
        Returns:
            List of trades
        """
        return await self.trades(info, symphony_id=symphony_id, limit=limit)
    
    @strawberry.field
    async def symphony_performance(
        self,
        info: Info[GraphQLContext],
        symphony_id: int,
        days: int = 30
    ) -> List[PerformanceMetric]:
        """Get performance metrics for a symphony.
        
        Args:
            info: GraphQL context info
            symphony_id: Symphony ID
            days: Number of days to look back
            
        Returns:
            List of performance metrics
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        return await self.performance_metrics(
            info,
            symphony_id=symphony_id,
            start_date=start_date
        )
