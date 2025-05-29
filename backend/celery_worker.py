#!/usr/bin/env python
"""
Celery Worker Startup Script

This script starts Celery workers for the Origami Composer application.
It handles worker configuration, logging setup, and graceful shutdown.
"""

import os
import sys
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.celery_app import celery_app
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/celery_worker.log')
    ]
)

logger = logging.getLogger(__name__)


def setup_worker():
    """Setup worker environment"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Log startup information
    logger.info("Starting Origami Composer Celery Worker")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Redis URL: {settings.REDIS_URL}")
    logger.info(f"Database URL: {settings.DATABASE_URL[:30]}...")  # Log partial URL for security
    
    # Verify database connection
    try:
        from app.database.connection import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        sys.exit(1)
        
    # Verify Redis connection
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    # Setup worker environment
    setup_worker()
    
    # Start the worker
    logger.info("Starting Celery worker...")
    
    # Default worker arguments
    argv = [
        'worker',
        '--loglevel=info',
        '--concurrency=8',  # 8 concurrent worker processes
        '--max-tasks-per-child=1000',  # Restart worker after 1000 tasks
        '--time-limit=600',  # 10 minute hard time limit
        '--soft-time-limit=540',  # 9 minute soft time limit
        '-Q', 'default,algorithm,indicators,scheduler,errors,market_data,positions',  # Queues to consume
        '--heartbeat-interval=30',  # Heartbeat every 30 seconds
        '--without-gossip',  # Disable gossip for better performance
        '--without-mingle',  # Disable synchronization on startup
        '--without-heartbeat',  # Use Redis for heartbeat instead
        '-E',  # Send task events for monitoring
    ]
    
    # Add any command line arguments
    if len(sys.argv) > 1:
        argv.extend(sys.argv[1:])
        
    try:
        celery_app.worker_main(argv)
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
    except Exception as e:
        logger.error(f"Worker crashed: {str(e)}")
        raise
