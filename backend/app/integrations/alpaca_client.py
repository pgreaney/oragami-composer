"""Alpaca paper trading API client with OAuth authentication."""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import httpx
import asyncio
from decimal import Decimal

from app.config import settings
from app.auth.oauth_utils import decrypt_token


class AlpacaPaperClient:
    """Client for Alpaca paper trading API with OAuth authentication."""
    
    def __init__(self, access_token: str = None):
        """Initialize Alpaca client.
        
        Args:
            access_token: Encrypted OAuth access token
        """
        self.base_url = settings.ALPACA_PAPER_BASE_URL
        self._encrypted_token = access_token
        self._decrypted_token = None
        
        if access_token:
            self._decrypted_token = decrypt_token(access_token)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        if not self._decrypted_token:
            raise ValueError("No access token available")
        
        return {
            "Authorization": f"Bearer {self._decrypted_token}",
            "Accept": "application/json"
        }
    
    async def get_account(self) -> Optional[Dict[str, Any]]:
        """Get account information.
        
        Returns:
            Account data or None if failed
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v2/account",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get account: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Error getting account: {str(e)}")
                return None
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions.
        
        Returns:
            List of positions
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v2/positions",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get positions: {response.status_code}")
                    return []
                    
            except Exception as e:
                print(f"Error getting positions: {str(e)}")
                return []
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Position data or None
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v2/positions/{symbol}",
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    print(f"Failed to get position: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"Error getting position: {str(e)}")
                return None
    
    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        extended_hours: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Place an order.
        
        Args:
            symbol: Stock symbol
            qty: Quantity (fractional for fractional shares)
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            time_in_force: 'day', 'gtc', 'ioc', 'fok'
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
            extended_hours: Allow extended hours trading
            
        Returns:
            Order data or None if failed
        """
        order_data = {
            "symbol": symbol,
            "qty": str(qty),  # Convert to string for API
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "extended_hours": extended_hours
        }
        
        if limit_price is not None:
            order_data["limit_price"] = str(limit_price)
        
        if stop_price is not None:
            order_data["stop_price"] = str(stop_price)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/v2/orders",
                    json=order_data,
                    headers=self._get_headers()
                )
                
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    print(f"Failed to place order: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Error placing order: {str(e)}")
                return None
    
    async def get_orders(
        self,
        status: str = "open",
        limit: int = 100,
        after: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get orders.
        
        Args:
            status: Order status filter ('open', 'closed', 'all')
            limit: Maximum number of orders
            after: Filter orders after this time
            until: Filter orders until this time
            
        Returns:
            List of orders
        """
        params = {
            "status": status,
            "limit": limit,
            "direction": "desc"
        }
        
        if after:
            params["after"] = after.isoformat()
        
        if until:
            params["until"] = until.isoformat()
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v2/orders",
                    params=params,
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get orders: {response.status_code}")
                    return []
                    
            except Exception as e:
                print(f"Error getting orders: {str(e)}")
                return []
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/v2/orders/{order_id}",
                    headers=self._get_headers()
                )
                
                return response.status_code in [200, 204]
                
            except Exception as e:
                print(f"Error cancelling order: {str(e)}")
                return False
    
    async def cancel_all_orders(self) -> bool:
        """Cancel all open orders.
        
        Returns:
            True if all orders cancelled
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/v2/orders",
                    headers=self._get_headers()
                )
                
                return response.status_code in [200, 204, 207]
                
            except Exception as e:
                print(f"Error cancelling all orders: {str(e)}")
                return False
    
    async def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Close a position completely.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Order data from closing position
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/v2/positions/{symbol}",
                    headers=self._get_headers()
                )
                
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    print(f"Failed to close position: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"Error closing position: {str(e)}")
                return None
    
    async def close_all_positions(self) -> bool:
        """Close all open positions.
        
        Returns:
            True if all positions closed successfully
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/v2/positions",
                    headers=self._get_headers()
                )
                
                return response.status_code in [200, 204, 207]
                
            except Exception as e:
                print(f"Error closing all positions: {str(e)}")
                return False
    
    async def get_portfolio_history(
        self,
        period: str = "1M",
        timeframe: str = "1D",
        extended_hours: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get portfolio history.
        
        Args:
            period: Time period (1D, 1W, 1M, 3M, 6M, 1Y, all)
            timeframe: Data timeframe (1Min, 5Min, 15Min, 1H, 1D)
            extended_hours: Include extended hours
            
        Returns:
            Portfolio history data
        """
        params = {
            "period": period,
            "timeframe": timeframe,
            "extended_hours": extended_hours
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/v2/account/portfolio/history",
                    params=params,
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Failed to get portfolio history: {response.status_code}")
                    return None
                    
            except Exception as e:
                print(f"Error getting portfolio history: {str(e)}")
                return None
    
    async def liquidate_to_cash(self) -> bool:
        """Liquidate all positions to cash (error handling).
        
        This is used when an algorithm error occurs and we need to
        move everything to cash positions.
        
        Returns:
            True if liquidation successful
        """
        try:
            # Cancel all open orders first
            await self.cancel_all_orders()
            
            # Wait a moment for orders to cancel
            await asyncio.sleep(0.5)
            
            # Close all positions
            return await self.close_all_positions()
            
        except Exception as e:
            print(f"Error during liquidation: {str(e)}")
            return False
