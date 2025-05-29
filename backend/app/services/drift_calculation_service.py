"""
Drift Calculation Service for Threshold-Based Rebalancing

This service calculates portfolio drift from target allocations to determine
when threshold-based symphonies should be rebalanced.
"""
from typing import Dict, List, Optional
import numpy as np
from app.models import Position

class DriftCalculationService:
    """Calculates portfolio drift for threshold-based rebalancing decisions"""
    
    async def calculate_max_drift(
        self,
        positions: List[Position],
        target_allocations: Dict[str, float]
    ) -> float:
        """
        Calculate maximum drift across all positions
        
        Args:
            positions: Current portfolio positions
            target_allocations: Target allocation percentages by symbol
            
        Returns:
            Maximum drift percentage (0.0 to 1.0)
        """
        # Calculate total portfolio value
        total_value = sum(pos.market_value for pos in positions)
        
        if total_value == 0:
            return 1.0  # 100% drift if no positions
        
        # Calculate current allocations
        current_allocations = {}
        for pos in positions:
            current_allocations[pos.symbol] = pos.market_value / total_value
        
        # Calculate drift for each asset
        max_drift = 0.0
        
        # Check drift for assets in target but not in current
        for symbol, target_weight in target_allocations.items():
            current_weight = current_allocations.get(symbol, 0.0)
            drift = abs(target_weight - current_weight)
            max_drift = max(max_drift, drift)
        
        # Check drift for assets in current but not in target
        for symbol, current_weight in current_allocations.items():
            if symbol not in target_allocations:
                # Asset should have 0 weight but doesn't
                max_drift = max(max_drift, current_weight)
        
        return max_drift
    
    async def calculate_all_drifts(
        self,
        positions: List[Position],
        target_allocations: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate drift for each position
        
        Returns:
            Dictionary mapping symbol to drift percentage
        """
        # Calculate total portfolio value
        total_value = sum(pos.market_value for pos in positions)
        
        if total_value == 0:
            # Return target allocations as drift if no positions
            return {symbol: weight for symbol, weight in target_allocations.items()}
        
        # Calculate current allocations
        current_allocations = {}
        for pos in positions:
            current_allocations[pos.symbol] = pos.market_value / total_value
        
        # Calculate drift for all assets
        drifts = {}
        
        # All symbols from both current and target
        all_symbols = set(current_allocations.keys()) | set(target_allocations.keys())
        
        for symbol in all_symbols:
            current_weight = current_allocations.get(symbol, 0.0)
            target_weight = target_allocations.get(symbol, 0.0)
            drifts[symbol] = abs(target_weight - current_weight)
        
        return drifts
    
    def calculate_rebalancing_trades(
        self,
        positions: List[Position],
        target_allocations: Dict[str, float],
        total_portfolio_value: float
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate trades needed to rebalance portfolio
        
        Returns:
            Dictionary with 'buy' and 'sell' orders by symbol
        """
        trades = {'buy': {}, 'sell': {}}
        
        # Calculate current allocations
        current_allocations = {}
        current_values = {}
        
        for pos in positions:
            current_allocations[pos.symbol] = pos.market_value / total_portfolio_value
            current_values[pos.symbol] = pos.market_value
        
        # Calculate target values
        target_values = {}
        for symbol, target_weight in target_allocations.items():
            target_values[symbol] = total_portfolio_value * target_weight
        
        # Determine trades
        all_symbols = set(current_values.keys()) | set(target_values.keys())
        
        for symbol in all_symbols:
            current_value = current_values.get(symbol, 0.0)
            target_value = target_values.get(symbol, 0.0)
            
            difference = target_value - current_value
            
            if difference > 0:
                # Need to buy
                trades['buy'][symbol] = difference
            elif difference < 0:
                # Need to sell
                trades['sell'][symbol] = abs(difference)
        
        return trades
    
    def is_drift_above_threshold(
        self,
        max_drift: float,
        threshold: float
    ) -> bool:
        """
        Check if drift exceeds threshold
        
        Args:
            max_drift: Maximum drift across all positions
            threshold: Corridor width threshold
            
        Returns:
            True if rebalancing is needed
        """
        return max_drift > threshold
