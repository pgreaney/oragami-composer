"""
Celery Worker Configuration and Startup

This module configures Celery workers with appropriate settings
for algorithm execution and task processing.
"""

import os
import logging
from typing import Dict, Any

from celery import Celery, Task
from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.config import settings


logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """
    Custom task class that provides database session management
    """
    _db: Session = None
    
    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Clean up database session after task completion"""
        if self._db is not None:
            self._db.close()
            self._db = None


# Set custom task class
celery_app.Task = DatabaseTask


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """
    Handler called when worker is ready to accept tasks
    """
    worker_name = sender.hostname if sender else 'unknown'
    logger.info(f"Worker {worker_name} is ready to accept tasks")
    
    # Pre-warm connections
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Failed to verify database connection: {str(e)}")


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """
    Handler called when worker is shutting down
    """
    worker_name = sender.hostname if sender else 'unknown'
    logger.info(f"Worker {worker_name} is shutting down")


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **other_kwargs):
    """
    Handler called before task execution
    """
    logger.debug(f"Starting task {task.name} with ID {task_id}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **other_kwargs):
    """
    Handler called after task execution
    """
    logger.debug(f"Completed task {task.name} with ID {task_id}, state: {state}")


def configure_worker(concurrency: int = None, pool: str = 'prefork') -> Dict[str, Any]:
    """
    Configure worker settings for optimal performance
    
    Args:
        concurrency: Number of concurrent workers
        pool: Worker pool type ('prefork', 'gevent', 'eventlet')
        
    Returns:
        Worker configuration dictionary
    """
    if concurrency is None:
        # Calculate based on CPU cores for algorithm execution
        # Reserve some cores for the system
        cpu_count = os.cpu_count() or 4
        concurrency = max(2, cpu_count - 2)
    
    config = {
        'concurrency': concurrency,
        'pool': pool,
        'loglevel': settings.LOG_LEVEL,
        'optimization': 'fair',  # Better for long-running tasks
        'prefetch_multiplier': 1,  # Prevent worker from prefetching too many tasks
        'max_tasks_per_child': 100,  # Restart worker after 100 tasks to prevent memory leaks
        'task_time_limit': 300,  # 5 minute hard time limit
        'task_soft_time_limit': 240,  # 4 minute soft time limit
        'worker_hijacking_timeout': 30,  # Wait 30 seconds for worker to start
    }
    
    # Queue-specific configurations
    queue_configs = {
        'high_priority': {
            'concurrency': max(2, concurrency // 2),
            'prefetch_multiplier': 1
        },
        'low_priority': {
            'concurrency': 2,
            'prefetch_multiplier': 4
        },
        'market_data': {
            'concurrency': 4,
            'prefetch_multiplier': 10,
            'pool': 'gevent'  # Better for I/O-bound tasks
        }
    }
    
    return {
        'base_config': config,
        'queue_configs': queue_configs
    }


def start_worker(queue: str = 'celery', **kwargs):
    """
    Start a Celery worker with appropriate configuration
    
    Args:
        queue: Queue name to listen on
        **kwargs: Additional worker configuration
    """
    config = configure_worker()
    
    # Get queue-specific config if available
    if queue in config['queue_configs']:
        worker_config = {**config['base_config'], **config['queue_configs'][queue]}
    else:
        worker_config = config['base_config']
    
    # Override with any provided kwargs
    worker_config.update(kwargs)
    
    logger.info(f"Starting worker for queue '{queue}' with config: {worker_config}")
    
    # Start the worker
    celery_app.worker_main([
        'worker',
        f'--queues={queue}',
        f'--concurrency={worker_config["concurrency"]}',
        f'--pool={worker_config["pool"]}',
        f'--loglevel={worker_config["loglevel"]}',
        f'--optimization={worker_config["optimization"]}',
        f'--prefetch-multiplier={worker_config["prefetch_multiplier"]}',
        f'--max-tasks-per-child={worker_config["max_tasks_per_child"]}',
    ])


# Export worker configurations for different environments
WORKER_CONFIGS = {
    'development': {
        'concurrency': 2,
        'pool': 'prefork',
        'loglevel': 'DEBUG'
    },
    'production': {
        'concurrency': 8,
        'pool': 'prefork',
        'loglevel': 'INFO'
    },
    'high_load': {
        'concurrency': 16,
        'pool': 'prefork',
        'loglevel': 'WARNING',
        'prefetch_multiplier': 1,
        'max_tasks_per_child': 50
    }
}
