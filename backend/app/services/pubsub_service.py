"""
Pub/Sub Service for Real-time Updates

This service handles real-time communication via Redis pub/sub
for GraphQL subscriptions and WebSocket connections.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

import redis
from redis.client import PubSub

from app.config import settings


logger = logging.getLogger(__name__)


class PubSubService:
    """
    Service for managing real-time updates via Redis pub/sub
    """
    
    def __init__(self):
        self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        
    def publish(self, channel: str, data: Dict[str, Any]) -> None:
        """
        Publish data to a channel
        
        Args:
            channel: Channel name
            data: Data to publish
        """
        try:
            message = json.dumps({
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            self.redis_client.publish(channel, message)
            logger.debug(f"Published to channel {channel}: {data}")
            
        except Exception as e:
            logger.error(f"Failed to publish to channel {channel}: {str(e)}")
            
    def publish_position_update(self, user_id: int, position_data: Dict[str, Any]) -> None:
        """
        Publish position update for a user
        
        Args:
            user_id: User ID
            position_data: Position data to publish
        """
        channel = f"positions:{user_id}"
        self.publish(channel, {
            'type': 'position_update',
            'position': position_data
        })
        
    def publish_trade_execution(self, user_id: int, trade_data: Dict[str, Any]) -> None:
        """
        Publish trade execution notification
        
        Args:
            user_id: User ID
            trade_data: Trade data to publish
        """
        channel = f"trades:{user_id}"
        self.publish(channel, {
            'type': 'trade_execution',
            'trade': trade_data
        })
        
    def publish_symphony_status(self, user_id: int, symphony_id: int, status: str, details: Optional[Dict] = None) -> None:
        """
        Publish symphony execution status update
        
        Args:
            user_id: User ID
            symphony_id: Symphony ID
            status: Execution status
            details: Additional details
        """
        channel = f"symphonies:{user_id}"
        self.publish(channel, {
            'type': 'symphony_status',
            'symphony_id': symphony_id,
            'status': status,
            'details': details or {}
        })
        
    def publish_portfolio_metrics(self, user_id: int, metrics: Dict[str, Any]) -> None:
        """
        Publish portfolio metrics update
        
        Args:
            user_id: User ID
            metrics: Portfolio metrics
        """
        channel = f"portfolio:{user_id}"
        self.publish(channel, {
            'type': 'portfolio_metrics',
            'metrics': metrics
        })
        
    def publish_error_alert(self, user_id: int, error_type: str, message: str, details: Optional[Dict] = None) -> None:
        """
        Publish error alert to user
        
        Args:
            user_id: User ID
            error_type: Type of error
            message: Error message
            details: Additional error details
        """
        channel = f"alerts:{user_id}"
        self.publish(channel, {
            'type': 'error_alert',
            'error_type': error_type,
            'message': message,
            'details': details or {}
        })
        
    async def subscribe(self, channel: str) -> asyncio.Queue:
        """
        Subscribe to a channel (async)
        
        Args:
            channel: Channel name
            
        Returns:
            Queue for receiving messages
        """
        queue = asyncio.Queue()
        
        if channel not in self._subscribers:
            self._subscribers[channel] = []
            
        self._subscribers[channel].append(queue)
        
        # Start listening to Redis channel if not already
        asyncio.create_task(self._listen_to_channel(channel))
        
        return queue
        
    async def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe from a channel
        
        Args:
            channel: Channel name
            queue: Queue to remove
        """
        if channel in self._subscribers:
            self._subscribers[channel].remove(queue)
            
            if not self._subscribers[channel]:
                del self._subscribers[channel]
                
    async def _listen_to_channel(self, channel: str) -> None:
        """
        Listen to Redis channel and distribute messages to subscribers
        
        Args:
            channel: Channel name
        """
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(channel)
        
        try:
            while channel in self._subscribers:
                message = await asyncio.get_event_loop().run_in_executor(
                    None, self._get_message, pubsub
                )
                
                if message and message['type'] == 'message':
                    data = json.loads(message['data'])
                    
                    # Send to all subscribers
                    for queue in self._subscribers.get(channel, []):
                        await queue.put(data)
                        
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
                
        except Exception as e:
            logger.error(f"Error listening to channel {channel}: {str(e)}")
            
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()
            
    def _get_message(self, pubsub: PubSub) -> Optional[Dict]:
        """
        Get message from Redis pub/sub (blocking)
        
        Args:
            pubsub: Redis pub/sub client
            
        Returns:
            Message dict or None
        """
        message = pubsub.get_message(timeout=1.0)
        return message
        
    def get_channel_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active channels and subscribers
        
        Returns:
            Dictionary with channel statistics
        """
        stats = {
            'active_channels': len(self._subscribers),
            'total_subscribers': sum(len(subs) for subs in self._subscribers.values()),
            'channels': {}
        }
        
        for channel, subscribers in self._subscribers.items():
            stats['channels'][channel] = {
                'subscriber_count': len(subscribers)
            }
            
        return stats
        
    def broadcast_system_message(self, message: str, severity: str = 'info') -> None:
        """
        Broadcast a system-wide message to all users
        
        Args:
            message: Message to broadcast
            severity: Message severity (info, warning, error)
        """
        self.publish('system:broadcast', {
            'type': 'system_message',
            'message': message,
            'severity': severity
        })
