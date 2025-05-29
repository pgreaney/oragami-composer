"""
Rebalancing Service for Symphony Execution Eligibility

This service determines whether a symphony should be executed based on its
rebalancing configuration (time-based or threshold-based).
"""
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Symphony, Position
from app.services.drift_calculation_service import DriftCalculationService
import pytz

class RebalancingService:
    """Determines symphony execution eligibility during daily evaluation window"""
    
    def __init__(self, db: AsyncSession, drift_calculator: DriftCalculationService):
        self.db = db
        self.drift_calculator = drift_calculator
        self.est_tz = pytz.timezone('US/Eastern')
    
    async def check_symphony_eligibility(
        self, 
        symphony: Symphony,
        evaluation_time: datetime
    ) -> Tuple[bool, str]:
        """
        Check if a symphony should be executed based on its rebalancing rules
        
        Returns:
            Tuple[bool, str]: (should_execute, reason)
        """
        # Parse symphony JSON to get rebalancing configuration
        symphony_data = symphony.json_data
        rebalance_type = symphony_data.get('rebalance', 'daily')
        
        if rebalance_type == 'none':
            # Threshold-based rebalancing
            return await self._check_threshold_rebalancing(symphony, symphony_data)
        else:
            # Time-based rebalancing
            return self._check_time_based_rebalancing(
                symphony, rebalance_type, evaluation_time
            )
    
    def _check_time_based_rebalancing(
        self,
        symphony: Symphony,
        frequency: str,
        evaluation_time: datetime
    ) -> Tuple[bool, str]:
        """Check if it's time to rebalance based on schedule"""
        
        # Convert to EST for consistent scheduling
        est_time = evaluation_time.astimezone(self.est_tz)
        last_executed = symphony.last_executed_at
        
        if not last_executed:
            return True, f"First execution for {frequency} symphony"
        
        last_executed_est = last_executed.astimezone(self.est_tz)
        
        if frequency == 'daily':
            return True, "Daily rebalancing scheduled"
            
        elif frequency == 'weekly':
            # Check if it's been at least a week
            days_diff = (est_time.date() - last_executed_est.date()).days
            if days_diff >= 7:
                return True, f"Weekly rebalancing due (last: {days_diff} days ago)"
            return False, f"Weekly rebalancing not due (last: {days_diff} days ago)"
            
        elif frequency == 'monthly':
            # Check if we're in a new month
            if (est_time.year > last_executed_est.year or 
                est_time.month > last_executed_est.month):
                return True, "Monthly rebalancing due (new month)"
            return False, "Monthly rebalancing not due (same month)"
            
        elif frequency == 'quarterly':
            # Check if we're in a new quarter
            current_quarter = (est_time.month - 1) // 3
            last_quarter = (last_executed_est.month - 1) // 3
            
            if (est_time.year > last_executed_est.year or 
                current_quarter > last_quarter):
                return True, "Quarterly rebalancing due (new quarter)"
            return False, "Quarterly rebalancing not due (same quarter)"
            
        elif frequency == 'yearly':
            # Check if we're in a new year
            if est_time.year > last_executed_est.year:
                return True, "Yearly rebalancing due (new year)"
            return False, "Yearly rebalancing not due (same year)"
        
        # Default to daily if unknown frequency
        return True, f"Unknown frequency '{frequency}', defaulting to daily"
    
    async def _check_threshold_rebalancing(
        self,
        symphony: Symphony,
        symphony_data: Dict
    ) -> Tuple[bool, str]:
        """Check if portfolio drift exceeds threshold"""
        
        corridor_width = symphony_data.get('rebalance-corridor-width', 0.05)
        
        # Get current positions
        positions = await self._get_symphony_positions(symphony.id)
        
        if not positions:
            return True, "No positions found, initial allocation needed"
        
        # Calculate target allocations from symphony algorithm
        target_allocations = await self._calculate_target_allocations(symphony_data)
        
        # Calculate drift
        max_drift = await self.drift_calculator.calculate_max_drift(
            positions, target_allocations
        )
        
        if max_drift > corridor_width:
            return True, f"Drift {max_drift:.2%} exceeds threshold {corridor_width:.2%}"
        
        return False, f"Drift {max_drift:.2%} within threshold {corridor_width:.2%}"
    
    async def _get_symphony_positions(self, symphony_id: str) -> List[Position]:
        """Get current positions for a symphony"""
        # Implementation would query the database
        # This is a placeholder
        return []
    
    async def _calculate_target_allocations(
        self, 
        symphony_data: Dict
    ) -> Dict[str, float]:
        """Extract target allocations from symphony algorithm"""
        # This would parse the symphony algorithm tree
        # and determine target weights for each asset
        # This is a placeholder
        return {}
    
    async def get_eligible_symphonies(
        self,
        user_id: str,
        evaluation_time: datetime
    ) -> List[Tuple[Symphony, str]]:
        """
        Get all symphonies eligible for execution in the current evaluation window
        
        Returns:
            List of tuples containing (symphony, reason_for_execution)
        """
        # Get all active symphonies for user
        symphonies = await self._get_active_symphonies(user_id)
        
        eligible = []
        for symphony in symphonies:
            should_execute, reason = await self.check_symphony_eligibility(
                symphony, evaluation_time
            )
            if should_execute:
                eligible.append((symphony, reason))
        
        return eligible
    
    async def _get_active_symphonies(self, user_id: str) -> List[Symphony]:
        """Get all active symphonies for a user"""
        # Implementation would query the database
        # This is a placeholder
        return []
