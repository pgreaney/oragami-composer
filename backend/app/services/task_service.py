"""
Task Management Service

This service manages Celery task execution tracking, monitoring,
and coordination for algorithm execution.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
import json

from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.celery_app import celery_app
from app.models.symphony import Symphony
from app.models.user import User
from app.database.connection import get_db


logger = logging.getLogger(__name__)


class TaskService:
    """
    Service for managing background task execution
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._execution_tasks: Dict[str, AsyncResult] = {}
        
    def schedule_symphony_execution(
        self, symphony_id: int, execution_date: Optional[date] = None
    ) -> str:
        """
        Schedule a symphony for execution
        
        Args:
            symphony_id: ID of symphony to execute
            execution_date: Date to execute (defaults to today)
            
        Returns:
            Task ID
        """
        from app.tasks.algorithm_execution import execute_symphony_algorithm
        
        if execution_date is None:
            execution_date = date.today()
            
        # Schedule the task
        task = execute_symphony_algorithm.apply_async(
            args=[symphony_id, execution_date.isoformat()],
            queue='high_priority'
        )
        
        # Track the task
        self._execution_tasks[f"symphony:{symphony_id}"] = task
        
        logger.info(f"Scheduled symphony {symphony_id} for execution, task: {task.id}")
        
        return task.id
        
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get status of a Celery task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status information
        """
        result = AsyncResult(task_id, app=celery_app)
        
        status = {
            'task_id': task_id,
            'state': result.state,
            'ready': result.ready(),
            'successful': result.successful() if result.ready() else None,
            'failed': result.failed() if result.ready() else None
        }
        
        if result.ready():
            if result.successful():
                status['result'] = result.result
            elif result.failed():
                status['error'] = str(result.info)
                
        return status
        
    def get_execution_summary(self, user_id: int, date: Optional[date] = None) -> Dict[str, Any]:
        """
        Get summary of symphony executions for a user
        
        Args:
            user_id: User ID
            date: Execution date (defaults to today)
            
        Returns:
            Execution summary
        """
        if date is None:
            date = date.today()
            
        # Get user's symphonies
        symphonies = self.db.query(Symphony).filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        summary = {
            'user_id': user_id,
            'execution_date': date.isoformat(),
            'total_symphonies': len(symphonies),
            'executed': 0,
            'pending': 0,
            'failed': 0,
            'symphonies': []
        }
        
        for symphony in symphonies:
            task_key = f"symphony:{symphony.id}"
            task = self._execution_tasks.get(task_key)
            
            symphony_status = {
                'id': symphony.id,
                'name': symphony.name,
                'status': 'not_scheduled'
            }
            
            if task:
                if task.ready():
                    if task.successful():
                        symphony_status['status'] = 'completed'
                        summary['executed'] += 1
                    else:
                        symphony_status['status'] = 'failed'
                        summary['failed'] += 1
                else:
                    symphony_status['status'] = 'pending'
                    summary['pending'] += 1
                    
            summary['symphonies'].append(symphony_status)
            
        return summary
        
    def batch_execute_symphonies(self, symphony_ids: List[int]) -> Dict[str, str]:
        """
        Execute multiple symphonies in batch
        
        Args:
            symphony_ids: List of symphony IDs
            
        Returns:
            Map of symphony ID to task ID
        """
        from app.tasks.symphony_scheduler import execute_symphony_batch
        
        # Schedule batch execution
        task = execute_symphony_batch.apply_async(
            args=[symphony_ids],
            queue='high_priority'
        )
        
        # Track individual tasks
        task_map = {}
        for symphony_id in symphony_ids:
            task_map[str(symphony_id)] = task.id
            self._execution_tasks[f"symphony:{symphony_id}"] = task
            
        logger.info(f"Scheduled batch execution for {len(symphony_ids)} symphonies")
        
        return task_map
        
    def get_daily_execution_stats(self, date: Optional[date] = None) -> Dict[str, Any]:
        """
        Get statistics for daily execution window
        
        Args:
            date: Date to get stats for
            
        Returns:
            Daily execution statistics
        """
        if date is None:
            date = date.today()
            
        # Get all active symphonies
        total_symphonies = self.db.query(Symphony).filter_by(is_active=True).count()
        
        # Get active users
        active_users = self.db.query(User).filter(
            User.alpaca_access_token.isnot(None)
        ).count()
        
        # Calculate expected execution time
        # Assuming 0.375 seconds per symphony (1600 symphonies in 10 minutes)
        expected_duration = total_symphonies * 0.375
        
        stats = {
            'date': date.isoformat(),
            'total_symphonies': total_symphonies,
            'active_users': active_users,
            'expected_duration_seconds': expected_duration,
            'required_workers': max(1, int(expected_duration / 600)),  # For 10 minute window
            'execution_window': {
                'start': '15:50 EST',
                'end': '16:00 EST',
                'duration_minutes': 10
            }
        }
        
        return stats
        
    def monitor_execution_progress(self) -> Dict[str, Any]:
        """
        Monitor current execution progress
        
        Returns:
            Current execution progress
        """
        active_tasks = celery_app.control.inspect().active()
        scheduled_tasks = celery_app.control.inspect().scheduled()
        
        progress = {
            'timestamp': datetime.utcnow().isoformat(),
            'active_workers': len(active_tasks) if active_tasks else 0,
            'active_tasks': 0,
            'scheduled_tasks': 0,
            'task_details': []
        }
        
        if active_tasks:
            for worker, tasks in active_tasks.items():
                progress['active_tasks'] += len(tasks)
                for task in tasks:
                    progress['task_details'].append({
                        'worker': worker,
                        'name': task.get('name'),
                        'id': task.get('id'),
                        'args': task.get('args')
                    })
                    
        if scheduled_tasks:
            for worker, tasks in scheduled_tasks.items():
                progress['scheduled_tasks'] += len(tasks)
                
        return progress
        
    def cancel_execution(self, symphony_id: int) -> bool:
        """
        Cancel a symphony execution
        
        Args:
            symphony_id: Symphony ID
            
        Returns:
            True if cancelled successfully
        """
        task_key = f"symphony:{symphony_id}"
        task = self._execution_tasks.get(task_key)
        
        if task and not task.ready():
            task.revoke(terminate=True)
            logger.info(f"Cancelled execution for symphony {symphony_id}")
            return True
            
        return False
        
    def retry_failed_executions(self, date: Optional[date] = None) -> Dict[str, Any]:
        """
        Retry failed symphony executions
        
        Args:
            date: Date of executions to retry
            
        Returns:
            Retry results
        """
        if date is None:
            date = date.today()
            
        retry_results = {
            'date': date.isoformat(),
            'retried': 0,
            'failed': 0,
            'symphonies': []
        }
        
        # Find failed tasks
        for task_key, task in self._execution_tasks.items():
            if task.failed():
                symphony_id = int(task_key.split(':')[1])
                
                try:
                    # Reschedule the symphony
                    new_task_id = self.schedule_symphony_execution(symphony_id, date)
                    
                    retry_results['retried'] += 1
                    retry_results['symphonies'].append({
                        'symphony_id': symphony_id,
                        'status': 'retried',
                        'new_task_id': new_task_id
                    })
                    
                except Exception as e:
                    retry_results['failed'] += 1
                    retry_results['symphonies'].append({
                        'symphony_id': symphony_id,
                        'status': 'retry_failed',
                        'error': str(e)
                    })
                    
        return retry_results
