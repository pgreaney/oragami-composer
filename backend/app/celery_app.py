"""
Celery Application Configuration for Origami Composer

This module configures Celery for background task processing, including:
- Daily symphony execution at 15:50-16:00 EST
- Real-time position updates
- Error handling and recovery
"""

import os
from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue
from datetime import timedelta

from app.config import settings

# Create Celery instance
celery_app = Celery(
    'origami_composer',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        'app.tasks.algorithm_execution',
        'app.tasks.technical_indicators',
        'app.tasks.symphony_scheduler',
        'app.tasks.error_tasks',
        'app.tasks.market_data_tasks',
        'app.tasks.position_tasks',
    ]
)

# Celery configuration
celery_app.conf.update(
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='US/Eastern',  # EST timezone for daily execution
    enable_utc=True,
    
    # Task routing
    task_routes={
        'app.tasks.algorithm_execution.*': {'queue': 'algorithm'},
        'app.tasks.technical_indicators.*': {'queue': 'indicators'},
        'app.tasks.symphony_scheduler.*': {'queue': 'scheduler'},
        'app.tasks.error_tasks.*': {'queue': 'errors'},
        'app.tasks.market_data_tasks.*': {'queue': 'market_data'},
        'app.tasks.position_tasks.*': {'queue': 'positions'},
    },
    
    # Queue configuration
    task_queues=(
        Queue('default', Exchange('default'), routing_key='default'),
        Queue('algorithm', Exchange('algorithm'), routing_key='algorithm', 
              queue_arguments={'x-max-priority': 10}),
        Queue('indicators', Exchange('indicators'), routing_key='indicators'),
        Queue('scheduler', Exchange('scheduler'), routing_key='scheduler',
              queue_arguments={'x-max-priority': 10}),
        Queue('errors', Exchange('errors'), routing_key='errors',
              queue_arguments={'x-max-priority': 10}),
        Queue('market_data', Exchange('market_data'), routing_key='market_data'),
        Queue('positions', Exchange('positions'), routing_key='positions'),
    ),
    
    # Worker settings
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Task execution limits
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Performance optimizations
    worker_pool='prefork',  # Use prefork pool for CPU-bound tasks
    worker_concurrency=8,  # 8 concurrent workers
    
    # Redis optimizations
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    redis_max_connections=100,
    redis_socket_keepalive=True,
    redis_socket_keepalive_options={
        1: 3,  # TCP_KEEPIDLE
        2: 3,  # TCP_KEEPINTVL
        3: 3,  # TCP_KEEPCNT
    },
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Daily symphony execution window (15:50-16:00 EST)
    'daily-symphony-execution': {
        'task': 'app.tasks.symphony_scheduler.execute_daily_symphonies',
        'schedule': crontab(hour=15, minute=50, day_of_week='1-5'),  # Monday-Friday at 15:50 EST
        'options': {
            'queue': 'scheduler',
            'priority': 10,
            'expires': 600,  # Expire after 10 minutes if not executed
        }
    },
    
    # Pre-execution market data fetch (15:45 EST)
    'pre-execution-market-data': {
        'task': 'app.tasks.market_data_tasks.prefetch_market_data',
        'schedule': crontab(hour=15, minute=45, day_of_week='1-5'),  # 5 minutes before execution
        'options': {
            'queue': 'market_data',
            'priority': 9,
        }
    },
    
    # Position reconciliation (16:05 EST - after execution window)
    'position-reconciliation': {
        'task': 'app.tasks.position_tasks.reconcile_positions',
        'schedule': crontab(hour=16, minute=5, day_of_week='1-5'),
        'options': {
            'queue': 'positions',
            'priority': 8,
        }
    },
    
    # Error recovery check (every 30 minutes)
    'error-recovery-check': {
        'task': 'app.tasks.error_tasks.check_failed_executions',
        'schedule': timedelta(minutes=30),
        'options': {
            'queue': 'errors',
            'priority': 7,
        }
    },
    
    # Market data cache refresh (every hour during market hours)
    'market-data-cache-refresh': {
        'task': 'app.tasks.market_data_tasks.refresh_cache',
        'schedule': crontab(minute=0, hour='9-16', day_of_week='1-5'),  # Every hour 9AM-4PM EST
        'options': {
            'queue': 'market_data',
            'priority': 5,
        }
    },
    
    # Symphony validation (daily at 3 AM EST)
    'daily-symphony-validation': {
        'task': 'app.tasks.symphony_scheduler.validate_all_symphonies',
        'schedule': crontab(hour=3, minute=0),
        'options': {
            'queue': 'scheduler',
            'priority': 3,
        }
    },
}

# Task-specific configuration
celery_app.conf.task_annotations = {
    'app.tasks.algorithm_execution.execute_symphony_algorithm': {
        'rate_limit': '200/m',  # Max 200 executions per minute
        'time_limit': 480,  # 8 minute time limit
        'soft_time_limit': 420,  # 7 minute soft limit
    },
    'app.tasks.technical_indicators.calculate_indicators': {
        'rate_limit': '1000/m',  # Max 1000 calculations per minute
        'time_limit': 60,  # 1 minute time limit
    },
    'app.tasks.symphony_scheduler.execute_daily_symphonies': {
        'rate_limit': '1/m',  # Only 1 execution per minute
        'time_limit': 600,  # 10 minute time limit (entire execution window)
        'soft_time_limit': 540,  # 9 minute soft limit
    },
}

# Error handling configuration
class ErrorHandlingConfig:
    """Configuration for error handling and recovery"""
    
    # Maximum retries for different error types
    MAX_RETRIES = {
        'market_data_error': 5,
        'algorithm_error': 3,
        'network_error': 10,
        'database_error': 3,
    }
    
    # Retry delays (in seconds)
    RETRY_DELAYS = {
        'market_data_error': [10, 30, 60, 120, 300],  # Exponential backoff
        'algorithm_error': [60, 180, 300],
        'network_error': [5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560],
        'database_error': [30, 60, 120],
    }
    
    # Error recovery strategies
    RECOVERY_STRATEGIES = {
        'algorithm_failure': 'liquidate_to_cash',
        'partial_execution': 'rollback_and_retry',
        'market_closed': 'queue_for_next_day',
        'insufficient_funds': 'scale_down_allocations',
    }

# Initialize error handling
celery_app.conf.error_handling = ErrorHandlingConfig()

# Custom task base class for enhanced error handling
from celery import Task

class BaseTask(Task):
    """Base task with automatic error handling and monitoring"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        from app.services.error_handler_service import ErrorHandlerService
        error_handler = ErrorHandlerService()
        error_handler.handle_task_failure(
            task_id=task_id,
            task_name=self.name,
            exception=exc,
            args=args,
            kwargs=kwargs,
            traceback=einfo
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        from app.services.monitoring_service import MonitoringService
        monitoring = MonitoringService()
        monitoring.record_task_retry(
            task_id=task_id,
            task_name=self.name,
            retry_count=self.request.retries,
            exception=exc
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        from app.services.monitoring_service import MonitoringService
        monitoring = MonitoringService()
        monitoring.record_task_success(
            task_id=task_id,
            task_name=self.name,
            duration=self.request.runtime
        )
        super().on_success(retval, task_id, args, kwargs)

# Set default task base
celery_app.Task = BaseTask

# Signals for monitoring and alerting
from celery.signals import (
    task_prerun, task_postrun, task_failure,
    worker_ready, worker_shutting_down,
    beat_init
)

@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Handler for when worker is ready"""
    from app.services.monitoring_service import MonitoringService
    monitoring = MonitoringService()
    monitoring.record_worker_start(sender.hostname)

@worker_shutting_down.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Handler for worker shutdown"""
    from app.services.monitoring_service import MonitoringService
    monitoring = MonitoringService()
    monitoring.record_worker_shutdown(sender.hostname)

@beat_init.connect
def beat_init_handler(sender=None, **kwargs):
    """Handler for beat scheduler initialization"""
    from app.services.monitoring_service import MonitoringService
    monitoring = MonitoringService()
    monitoring.record_beat_start()

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Handler before task execution"""
    # Set up task context
    from app.database.connection import SessionLocal
    task.db = SessionLocal()

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Handler after task execution"""
    # Clean up task context
    if hasattr(task, 'db'):
        task.db.close()

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Handler for task failures"""
    from app.services.alert_service import AlertService
    alert_service = AlertService()
    
    # Send alerts for critical failures
    if sender.name in ['app.tasks.symphony_scheduler.execute_daily_symphonies',
                       'app.tasks.algorithm_execution.execute_symphony_algorithm']:
        alert_service.send_critical_alert(
            task_name=sender.name,
            task_id=task_id,
            exception=str(exception)
        )

# Performance monitoring
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True

# Export celery app
__all__ = ['celery_app']
