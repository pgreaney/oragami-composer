"""
Subscription Manager Service

This service manages GraphQL subscription lifecycle and coordination
with the pub/sub system.
"""

from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import asyncio
import logging

from sqlalchemy.orm import Session

from app.services.pubsub_service import PubSubService
from app.models.user import User


logger = logging.getLogger(__name__)


class SubscriptionManager:
    """
    Manages GraphQL subscription connections and lifecycle
    """
    
    def __init__(self):
        self.pubsub = PubSubService()
        self._active_subscriptions: Dict[int, Set[str]] = {}  # user_id -> set of channels
        self._subscription_tasks: Dict[str, asyncio.Task] = {}  # channel -> task
        
    async def register_subscription(self, user_id: int, channel: str) -> None:
        """
        Register a new subscription for a user
        
        Args:
            user_id: User ID
            channel: Channel name
        """
        if user_id not in self._active_subscriptions:
            self._active_subscriptions[user_id] = set()
            
        self._active_subscriptions[user_id].add(channel)
        logger.info(f"Registered subscription for user {user_id} on channel {channel}")
        
    async def unregister_subscription(self, user_id: int, channel: str) -> None:
        """
        Unregister a subscription for a user
        
        Args:
            user_id: User ID
            channel: Channel name
        """
        if user_id in self._active_subscriptions:
            self._active_subscriptions[user_id].discard(channel)
            
            if not self._active_subscriptions[user_id]:
                del self._active_subscriptions[user_id]
                
        logger.info(f"Unregistered subscription for user {user_id} on channel {channel}")
        
    async def broadcast_to_user(self, user_id: int, event_type: str, data: Dict[str, Any]) -> None:
        """
        Broadcast an event to all subscriptions for a user
        
        Args:
            user_id: User ID
            event_type: Type of event
            data: Event data
        """
        channels = self._active_subscriptions.get(user_id, set())
        
        for channel in channels:
            if event_type in channel:
                self.pubsub.publish(channel, data)
                
    async def start_position_monitoring(self, user_id: int) -> None:
        """
        Start monitoring positions for a user
        
        Args:
            user_id: User ID
        """
        channel = f"position_monitor:{user_id}"
        
        if channel not in self._subscription_tasks:
            task = asyncio.create_task(self._monitor_positions(user_id))
            self._subscription_tasks[channel] = task
            
    async def stop_position_monitoring(self, user_id: int) -> None:
        """
        Stop monitoring positions for a user
        
        Args:
            user_id: User ID
        """
        channel = f"position_monitor:{user_id}"
        
        if channel in self._subscription_tasks:
            self._subscription_tasks[channel].cancel()
            del self._subscription_tasks[channel]
            
    async def _monitor_positions(self, user_id: int) -> None:
        """
        Monitor position changes for a user
        
        Args:
            user_id: User ID
        """
        from app.tasks.position_tasks import update_position_prices
        
        try:
            while True:
                # Update position prices every 30 seconds during market hours
                update_position_prices.delay()
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            logger.info(f"Stopped position monitoring for user {user_id}")
            raise
            
    async def start_metrics_calculation(self, user_id: int, interval: int = 60) -> None:
        """
        Start calculating metrics for a user
        
        Args:
            user_id: User ID
            interval: Calculation interval in seconds
        """
        channel = f"metrics_calc:{user_id}"
        
        if channel not in self._subscription_tasks:
            task = asyncio.create_task(self._calculate_metrics(user_id, interval))
            self._subscription_tasks[channel] = task
            
    async def _calculate_metrics(self, user_id: int, interval: int) -> None:
        """
        Calculate and publish metrics for a user
        
        Args:
            user_id: User ID
            interval: Calculation interval
        """
        from app.tasks.position_tasks import calculate_position_metrics
        
        try:
            while True:
                # Calculate metrics
                result = calculate_position_metrics.apply_async(args=[user_id])
                metrics = result.get(timeout=30)
                
                # Publish metrics
                self.pubsub.publish_portfolio_metrics(user_id, metrics)
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info(f"Stopped metrics calculation for user {user_id}")
            raise
            
    def get_subscription_stats(self) -> Dict[str, Any]:
        """
        Get subscription statistics
        
        Returns:
            Subscription statistics
        """
        total_subscriptions = sum(len(channels) for channels in self._active_subscriptions.values())
        
        return {
            'active_users': len(self._active_subscriptions),
            'total_subscriptions': total_subscriptions,
            'active_monitoring_tasks': len(self._subscription_tasks),
            'users': {
                user_id: list(channels) 
                for user_id, channels in self._active_subscriptions.items()
            }
        }
        
    async def cleanup_user_subscriptions(self, user_id: int) -> None:
        """
        Clean up all subscriptions for a user
        
        Args:
            user_id: User ID
        """
        if user_id in self._active_subscriptions:
            channels = list(self._active_subscriptions[user_id])
            
            for channel in channels:
                await self.unregister_subscription(user_id, channel)
                
        # Stop monitoring tasks
        await self.stop_position_monitoring(user_id)
        
        # Stop metrics calculation
        channel = f"metrics_calc:{user_id}"
        if channel in self._subscription_tasks:
            self._subscription_tasks[channel].cancel()
            del self._subscription_tasks[channel]


# Global subscription manager instance
subscription_manager = SubscriptionManager()
