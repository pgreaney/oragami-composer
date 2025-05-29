#!/usr/bin/env python
"""
Celery Beat Scheduler Startup Script

This script starts the Celery Beat scheduler for periodic tasks,
including the critical 15:50-16:00 EST daily symphony execution window.
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
        logging.FileHandler('logs/celery_beat.log')
    ]
)

logger = logging.getLogger(__name__)


def setup_beat():
    """Setup beat scheduler environment"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Log startup information
    logger.info("Starting Origami Composer Celery Beat Scheduler")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("Timezone: US/Eastern (for 15:50-16:00 EST execution window)")
    
    # Verify Redis connection
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        logger.info("Redis connection verified")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        sys.exit(1)
        
    # Log scheduled tasks
    logger.info("Scheduled tasks:")
    for task_name, task_config in celery_app.conf.beat_schedule.items():
        logger.info(f"  - {task_name}: {task_config['schedule']}")


if __name__ == '__main__':
    # Setup beat environment
    setup_beat()
    
    # Start the beat scheduler
    logger.info("Starting Celery Beat scheduler...")
    
    # Default beat arguments
    argv = [
        'beat',
        '--loglevel=info',
        '--pidfile=logs/celerybeat.pid',
        '--schedule=logs/celerybeat-schedule.db',
        '--max-interval=10',  # Maximum seconds to sleep between schedule checks
    ]
    
    # Add any command line arguments
    if len(sys.argv) > 1:
        argv.extend(sys.argv[1:])
        
    try:
        celery_app.start(argv)
    except KeyboardInterrupt:
        logger.info("Beat scheduler shutting down...")
    except Exception as e:
        logger.error(f"Beat scheduler crashed: {str(e)}")
        raise
