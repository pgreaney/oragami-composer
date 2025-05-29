"""Alpaca paper trading API integration with algorithm execution."""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import asyncio
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.symphony import Symphony
from app.integrations.alpaca_client import get_alpaca_client, AlpacaClient
from app.services.trading_service import trading_service, TradingService
from app.services.error_handler_service import error_handler_service
from app.schemas.alpaca import Order, Position as AlpacaPosition


class AlpacaTradingServiceError(Exception):
    """Alpaca trading service error."""
    pass


class AlpacaTradingService:
    """Service for executing trades through Alpaca paper trading API."""
    
    def __init__(
        self,
        alpaca_client: Optional[AlpacaClient] = None,
        trading: Optional[TradingService] = None
    ):
        """Initialize Alpaca trading service.
        
        Args:
            alpaca_client: Alpaca API client
            trading: Trading service
        """
        self.alpaca_client = alpaca_client
        self.trading = trading or trading_service
    
    async def _get_alpaca_client(self, user: User) -> AlpacaClient:
        """Get Alpaca client for user.
        
        Args:
            user: User with Alpaca credentials
            
        Returns:
            Alpaca client
            
        Raises:
            AlpacaTradingServiceError: If no credentials
        """
        if not user.alpaca_access_token:
            raise AlpacaTradingServiceError("User has not connected Alpaca account")
        
        return get_alpaca_client(user.alpaca_access_token)
    
    async def execute_symphony_trades(
        self,
        db: Session,
        user: User,
        symphony: Symphony,
        target_allocations: Dict[str, Decimal]
    ) -> Tuple[List[Any], List[str]]:
        """Execute trades to reach target allocations.
        
        Args:
            db: Database session
            user: User
            symphony: Symphony being executed
            target_allocations: Dict of symbol -> target percentage
            
        Returns:
            Tuple of (executed_trades, errors)
        """
        trades = []
        errors = []
        
        try:
            # Get Alpaca client
            client = await self._get_alpaca_client(user)
            
            # Get account info
            account = await client.get_account()
            total_equity = Decimal(account["equity"])
            
            # Get current positions
            current_positions = await self._get_current_positions(client)
            
            # Calculate required trades
            orders = self._calculate_rebalancing_orders(
                total_equity,
                current_positions,
                target_allocations
            )
            
            # Execute orders
            for symbol, order_data in orders.items():
                try:
                    if order_data["quantity"] == 0:
                        continue
                    
                    # Submit order to Alpaca
                    order = await client.submit_order(
                        symbol=symbol,
                        qty=abs(order_data["quantity"]),
                        side="buy" if order_data["quantity"] > 0 else "sell",
                        type="market",
                        time_in_force="day"
                    )
                    
                    # Record trade in database
                    trade = self.trading.record_trade(
                        db=db,
                        user=user,
                        symphony_id=symphony.id,
                        symbol=symbol,
                        side="buy" if order_data["quantity"] > 0 else "sell",
                        quantity=abs(order_data["quantity"]),
                        price=order_data["estimated_price"],
                        alpaca_order_id=order["id"],
                        status="pending"
                    )
                    
                    trades.append(trade)
                    
                except Exception as e:
                    error_msg = f"Failed to execute trade for {symbol}: {str(e)}"
                    errors.append(error_msg)
                    
                    # Record failed trade
                    self.trading.record_trade(
                        db=db,
                        user=user,
                        symphony_id=symphony.id,
                        symbol=symbol,
                        side="buy" if order_data["quantity"] > 0 else "sell",
                        quantity=abs(order_data["quantity"]),
                        price=order_data["estimated_price"],
                        status="failed",
                        error_message=error_msg
                    )
            
            # Wait for orders to fill
            await self._wait_for_order_fills(client, trades, db)
            
        except Exception as e:
            error_msg = f"Symphony execution failed: {str(e)}"
            errors.append(error_msg)
            
            # Trigger error handler for liquidation
            await error_handler_service.handle_symphony_error(
                db=db,
                user=user,
                symphony=symphony,
                error=e,
                liquidate=True
            )
        
        return trades, errors
    
    async def _get_current_positions(self, client: AlpacaClient) -> Dict[str, Dict[str, Any]]:
        """Get current positions from Alpaca.
        
        Args:
            client: Alpaca client
            
        Returns:
            Dict of symbol -> position data
        """
        positions = await client.list_positions()
        
        result = {}
        for pos in positions:
            result[pos["symbol"]] = {
                "quantity": Decimal(pos["qty"]),
                "market_value": Decimal(pos["market_value"]),
                "cost_basis": Decimal(pos["cost_basis"]),
                "current_price": Decimal(pos["current_price"])
            }
        
        return result
    
    def _calculate_rebalancing_orders(
        self,
        total_equity: Decimal,
        current_positions: Dict[str, Dict[str, Any]],
        target_allocations: Dict[str, Decimal]
    ) -> Dict[str, Dict[str, Any]]:
        """Calculate orders needed for rebalancing.
        
        Args:
            total_equity: Total account equity
            current_positions: Current positions
            target_allocations: Target allocations (percentages)
            
        Returns:
            Dict of symbol -> order data
        """
        orders = {}
        
        # Calculate target values
        for symbol, target_pct in target_allocations.items():
            target_value = total_equity * (target_pct / 100)
            current_value = current_positions.get(symbol, {}).get("market_value", Decimal("0"))
            current_price = current_positions.get(symbol, {}).get("current_price", Decimal("1"))
            
            # Calculate difference
            value_diff = target_value - current_value
            
            # Skip small differences (less than $10)
            if abs(value_diff) < 10:
                continue
            
            # Calculate quantity
            quantity = int(value_diff / current_price)
            
            if quantity != 0:
                orders[symbol] = {
                    "quantity": quantity,
                    "estimated_price": current_price,
                    "target_value": target_value,
                    "current_value": current_value
                }
        
        # Handle positions that need to be closed
        for symbol, position in current_positions.items():
            if symbol not in target_allocations and position["quantity"] > 0:
                orders[symbol] = {
                    "quantity": -int(position["quantity"]),
                    "estimated_price": position["current_price"],
                    "target_value": Decimal("0"),
                    "current_value": position["market_value"]
                }
        
        return orders
    
    async def _wait_for_order_fills(
        self,
        client: AlpacaClient,
        trades: List[Any],
        db: Session,
        timeout: int = 60
    ):
        """Wait for orders to fill and update trade records.
        
        Args:
            client: Alpaca client
            trades: List of trade records
            db: Database session
            timeout: Timeout in seconds
        """
        start_time = datetime.utcnow()
        
        while (datetime.utcnow() - start_time).seconds < timeout:
            all_filled = True
            
            for trade in trades:
                if trade.status != "executed":
                    # Check order status
                    order = await client.get_order(trade.alpaca_order_id)
                    
                    if order["status"] == "filled":
                        # Update trade record
                        trade.status = "executed"
                        trade.price = Decimal(order["filled_avg_price"])
                        trade.quantity = Decimal(order["filled_qty"])
                        trade.total_value = trade.price * trade.quantity
                        trade.executed_at = datetime.utcnow()
                        
                        # Update position
                        position_quantity = trade.quantity if trade.side == "buy" else -trade.quantity
                        self.trading.create_or_update_position(
                            db=db,
                            user=trade.user,
                            symphony_id=trade.symphony_id,
                            symbol=trade.symbol,
                            quantity=position_quantity,
                            price=trade.price
                        )
                    elif order["status"] in ["cancelled", "rejected", "expired"]:
                        trade.status = "failed"
                        trade.error_message = f"Order {order['status']}"
                    else:
                        all_filled = False
            
            db.commit()
            
            if all_filled:
                break
            
            await asyncio.sleep(1)
    
    async def get_account_summary(self, user: User) -> Dict[str, Any]:
        """Get Alpaca account summary.
        
        Args:
            user: User with Alpaca credentials
            
        Returns:
            Account summary
        """
        client = await self._get_alpaca_client(user)
        account = await client.get_account()
        
        return {
            "equity": Decimal(account["equity"]),
            "cash": Decimal(account["cash"]),
            "buying_power": Decimal(account["buying_power"]),
            "portfolio_value": Decimal(account["portfolio_value"]),
            "pattern_day_trader": account.get("pattern_day_trader", False),
            "trading_blocked": account.get("trading_blocked", False),
            "account_blocked": account.get("account_blocked", False)
        }
    
    async def sync_positions(self, db: Session, user: User):
        """Sync positions from Alpaca to database.
        
        Args:
            db: Database session
            user: User
        """
        client = await self._get_alpaca_client(user)
        alpaca_positions = await client.list_positions()
        
        # Update database positions
        for pos in alpaca_positions:
            position = self.trading.get_position(
                db=db,
                user=user,
                symbol=pos["symbol"]
            )
            
            if position:
                position.quantity = Decimal(pos["qty"])
                position.current_price = Decimal(pos["current_price"])
                position.market_value = Decimal(pos["market_value"])
                position.cost_basis = Decimal(pos["cost_basis"])
                position.average_price = Decimal(pos["avg_entry_price"])
                position.unrealized_pnl = Decimal(pos["unrealized_pl"])
                position.unrealized_pnl_percent = Decimal(pos["unrealized_plpc"]) * 100
                position.last_updated = datetime.utcnow()
            else:
                # Create new position
                self.trading.create_or_update_position(
                    db=db,
                    user=user,
                    symphony_id=0,  # Default symphony
                    symbol=pos["symbol"],
                    quantity=Decimal(pos["qty"]),
                    price=Decimal(pos["avg_entry_price"])
                )
        
        db.commit()
    
    async def close_all_positions(
        self,
        db: Session,
        user: User,
        symphony_id: int,
        reason: str = "Manual liquidation"
    ) -> List[Any]:
        """Close all positions for a symphony.
        
        Args:
            db: Database session
            user: User
            symphony_id: Symphony ID
            reason: Reason for closing
            
        Returns:
            List of closing trades
        """
        client = await self._get_alpaca_client(user)
        positions = self.trading.get_positions(db, user, symphony_id)
        trades = []
        
        for position in positions:
            if position.quantity != 0:
                try:
                    # Submit sell order
                    order = await client.submit_order(
                        symbol=position.symbol,
                        qty=abs(position.quantity),
                        side="sell" if position.quantity > 0 else "buy",
                        type="market",
                        time_in_force="day"
                    )
                    
                    # Record trade
                    trade = self.trading.record_trade(
                        db=db,
                        user=user,
                        symphony_id=symphony_id,
                        symbol=position.symbol,
                        side="sell" if position.quantity > 0 else "buy",
                        quantity=abs(position.quantity),
                        price=position.current_price,
                        alpaca_order_id=order["id"],
                        status="pending",
                        error_message=f"Liquidation: {reason}"
                    )
                    
                    trades.append(trade)
                    
                except Exception as e:
                    # Record failed liquidation
                    self.trading.record_trade(
                        db=db,
                        user=user,
                        symphony_id=symphony_id,
                        symbol=position.symbol,
                        side="sell" if position.quantity > 0 else "buy",
                        quantity=abs(position.quantity),
                        price=position.current_price,
                        status="failed",
                        error_message=f"Liquidation failed: {str(e)}"
                    )
        
        # Wait for liquidation orders to fill
        if trades:
            await self._wait_for_order_fills(client, trades, db)
        
        return trades


# Global service instance
alpaca_trading_service = AlpacaTradingService()
