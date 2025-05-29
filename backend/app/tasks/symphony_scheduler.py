"""
Symphony Scheduler Tasks

This module handles the daily symphony execution scheduling,
managing the 15:50-16:00 EST execution window for all active symphonies.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import logging
import pytz
from collections import defaultdict

from celery import group, chord
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.models.symphony import Symphony
from app.models.user import User
from app.models.position import Position
from app.services.symphony_service import SymphonyService
from app.services.market_data_service import MarketDataService
from app.services.rebalancing_service import RebalancingService
from app.tasks.algorithm_execution import execute_symphony_algorithm


logger = logging.getLogger(__name__)

# EST timezone for execution window
EST = pytz.timezone('US/Eastern')


@celery_app.task(name='app.tasks.symphony_scheduler.execute_daily_symphonies')
def execute_daily_symphonies() -> Dict[str, Any]:
    """
    Main task for daily symphony execution at 15:50-16:00 EST
    
    This task:
    1. Checks market status
    2. Identifies symphonies eligible for execution
    3. Groups symphonies by priority
    4. Executes symphonies in batches
    5. Monitors execution progress
    
    Returns:
        Dictionary containing execution summary
    """
    db: Session = SessionLocal()
    execution_start = datetime.now(EST)
    
    result = {
        'execution_date': str(date.today()),
        'execution_start': execution_start.isoformat(),
        'market_status': 'unknown',
        'total_symphonies': 0,
        'eligible_symphonies': 0,
        'executed_symphonies': 0,
        'failed_symphonies': 0,
        'execution_details': []
    }
    
    try:
        logger.info(f"Starting daily symphony execution at {execution_start}")
        
        # Check if market is open
        market_data_service = MarketDataService(db)
        if not market_data_service.is_market_open():
            logger.warning("Market is closed, skipping symphony execution")
            result['market_status'] = 'closed'
            return result
            
        result['market_status'] = 'open'
        
        # Get all active symphonies with users who have valid Alpaca connections
        active_symphonies = db.query(Symphony).join(User).filter(
            Symphony.is_active == True,
            User.alpaca_access_token.isnot(None)
        ).all()
        
        result['total_symphonies'] = len(active_symphonies)
        logger.info(f"Found {len(active_symphonies)} active symphonies")
        
        # Initialize rebalancing service
        rebalancing_service = RebalancingService(db)
        
        # Group symphonies by eligibility
        eligible_symphonies = []
        execution_reasons = defaultdict(list)
        
        for symphony in active_symphonies:
            # Check if symphony is eligible for execution today
            is_eligible, reason = rebalancing_service.is_symphony_eligible_for_execution(
                symphony=symphony,
                execution_date=date.today()
            )
            
            if is_eligible:
                eligible_symphonies.append(symphony)
                execution_reasons[reason].append(symphony.id)
                
        result['eligible_symphonies'] = len(eligible_symphonies)
        result['execution_reasons'] = {
            reason: len(symphony_ids) 
            for reason, symphony_ids in execution_reasons.items()
        }
        
        if not eligible_symphonies:
            logger.info("No symphonies eligible for execution today")
            return result
            
        logger.info(f"{len(eligible_symphonies)} symphonies eligible for execution")
        
        # Group symphonies by user to optimize execution
        user_symphonies = defaultdict(list)
        for symphony in eligible_symphonies:
            user_symphonies[symphony.user_id].append(symphony)
            
        # Calculate execution batches based on time window
        # We have 10 minutes (600 seconds) to execute all symphonies
        # With 8 workers, we can process ~8 symphonies per minute = 80 total
        batch_size = min(8, len(eligible_symphonies))  # Max 8 parallel executions
        
        # Create execution tasks
        execution_tasks = []
        for symphony in eligible_symphonies:
            task_signature = execute_symphony_algorithm.signature(
                args=[symphony.id, symphony.user_id, str(date.today()), False],
                queue='algorithm',
                priority=10,
                immutable=True
            )
            execution_tasks.append(task_signature)
            
        # Execute in batches using chord for result aggregation
        batch_results = []
        for i in range(0, len(execution_tasks), batch_size):
            batch = execution_tasks[i:i + batch_size]
            
            # Check if we're still within execution window
            current_time = datetime.now(EST)
            if current_time.time() >= time(16, 0):  # Past 16:00 EST
                logger.warning("Execution window exceeded, stopping batch execution")
                break
                
            logger.info(f"Executing batch {i//batch_size + 1} with {len(batch)} symphonies")
            
            # Execute batch in parallel
            batch_group = group(batch)
            batch_result = batch_group.apply_async()
            batch_results.append(batch_result)
            
        # Collect results
        execution_summary = []
        for batch_result in batch_results:
            try:
                # Wait for batch completion with timeout
                batch_outputs = batch_result.get(timeout=300)  # 5 minute timeout per batch
                
                for output in batch_outputs:
                    execution_summary.append({
                        'symphony_id': output['symphony_id'],
                        'user_id': output['user_id'],
                        'success': output['success'],
                        'allocations': output.get('allocations', {}),
                        'trades': len(output.get('trades', [])),
                        'errors': output.get('errors', [])
                    })
                    
                    if output['success']:
                        result['executed_symphonies'] += 1
                    else:
                        result['failed_symphonies'] += 1
                        
            except Exception as batch_error:
                logger.error(f"Batch execution failed: {str(batch_error)}")
                result['failed_symphonies'] += len(batch)
                
        result['execution_details'] = execution_summary
        result['execution_end'] = datetime.now(EST).isoformat()
        
        # Log execution summary
        logger.info(
            f"Daily execution completed: "
            f"{result['executed_symphonies']} successful, "
            f"{result['failed_symphonies']} failed"
        )
        
        # Trigger post-execution tasks
        trigger_post_execution_tasks.delay(execution_summary)
        
        return result
        
    except Exception as e:
        logger.error(f"Daily symphony execution failed: {str(e)}")
        result['error'] = str(e)
        raise
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.symphony_scheduler.validate_all_symphonies')
def validate_all_symphonies() -> Dict[str, Any]:
    """
    Validate all symphonies daily to ensure they're ready for execution
    
    This task:
    1. Checks algorithm syntax
    2. Validates asset universe availability
    3. Verifies user connections
    4. Flags problematic symphonies
    
    Returns:
        Dictionary containing validation results
    """
    db: Session = SessionLocal()
    
    result = {
        'validation_date': str(date.today()),
        'total_symphonies': 0,
        'valid_symphonies': 0,
        'invalid_symphonies': 0,
        'deactivated_symphonies': 0,
        'validation_errors': []
    }
    
    try:
        symphony_service = SymphonyService(db)
        
        # Get all symphonies
        all_symphonies = db.query(Symphony).all()
        result['total_symphonies'] = len(all_symphonies)
        
        for symphony in all_symphonies:
            try:
                # Validate symphony
                is_valid, errors = symphony_service.validate_symphony(symphony)
                
                if is_valid:
                    result['valid_symphonies'] += 1
                    
                    # Ensure symphony is active if it was previously deactivated due to errors
                    if not symphony.is_active and symphony.error_message:
                        symphony.is_active = True
                        symphony.error_message = None
                        logger.info(f"Reactivated symphony {symphony.id} after successful validation")
                        
                else:
                    result['invalid_symphonies'] += 1
                    result['validation_errors'].append({
                        'symphony_id': symphony.id,
                        'symphony_name': symphony.name,
                        'user_id': symphony.user_id,
                        'errors': errors
                    })
                    
                    # Deactivate symphony if it has critical errors
                    if symphony.is_active and any('critical' in str(e).lower() for e in errors):
                        symphony.is_active = False
                        symphony.error_message = f"Validation failed: {'; '.join(errors[:3])}"
                        result['deactivated_symphonies'] += 1
                        logger.warning(f"Deactivated symphony {symphony.id} due to validation errors")
                        
            except Exception as validation_error:
                logger.error(f"Failed to validate symphony {symphony.id}: {str(validation_error)}")
                result['validation_errors'].append({
                    'symphony_id': symphony.id,
                    'error': str(validation_error)
                })
                
        db.commit()
        
        logger.info(
            f"Symphony validation completed: "
            f"{result['valid_symphonies']} valid, "
            f"{result['invalid_symphonies']} invalid, "
            f"{result['deactivated_symphonies']} deactivated"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Symphony validation failed: {str(e)}")
        raise
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.symphony_scheduler.check_execution_eligibility')
def check_execution_eligibility(symphony_id: int, execution_date: str) -> Dict[str, Any]:
    """
    Check if a specific symphony is eligible for execution on a given date
    
    Args:
        symphony_id: ID of the symphony
        execution_date: Date to check eligibility for
        
    Returns:
        Dictionary containing eligibility status and reason
    """
    db: Session = SessionLocal()
    
    try:
        symphony = db.query(Symphony).filter_by(id=symphony_id).first()
        if not symphony:
            return {
                'eligible': False,
                'reason': 'Symphony not found'
            }
            
        rebalancing_service = RebalancingService(db)
        exec_date = datetime.strptime(execution_date, '%Y-%m-%d').date()
        
        is_eligible, reason = rebalancing_service.is_symphony_eligible_for_execution(
            symphony=symphony,
            execution_date=exec_date
        )
        
        return {
            'symphony_id': symphony_id,
            'execution_date': execution_date,
            'eligible': is_eligible,
            'reason': reason,
            'rebalancing_type': symphony.algorithm_config.get('rebalancing', {}).get('type', 'time_based')
        }
        
    except Exception as e:
        logger.error(f"Failed to check eligibility for symphony {symphony_id}: {str(e)}")
        return {
            'eligible': False,
            'reason': f'Error: {str(e)}'
        }
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.symphony_scheduler.trigger_post_execution_tasks')
def trigger_post_execution_tasks(execution_summary: List[Dict[str, Any]]) -> None:
    """
    Trigger post-execution tasks after daily symphony execution
    
    Args:
        execution_summary: List of execution results
    """
    try:
        # Trigger position reconciliation
        from app.tasks.position_tasks import reconcile_positions
        reconcile_positions.apply_async(queue='positions', priority=8)
        
        # Trigger performance calculation for executed symphonies
        from app.tasks.performance_tasks import calculate_daily_performance
        
        successful_symphony_ids = [
            result['symphony_id'] 
            for result in execution_summary 
            if result['success']
        ]
        
        if successful_symphony_ids:
            calculate_daily_performance.apply_async(
                args=[successful_symphony_ids],
                queue='performance',
                priority=7
            )
            
        # Trigger error analysis for failed symphonies
        failed_symphonies = [
            result for result in execution_summary 
            if not result['success']
        ]
        
        if failed_symphonies:
            from app.tasks.error_tasks import analyze_execution_failures
            analyze_execution_failures.apply_async(
                args=[failed_symphonies],
                queue='errors',
                priority=9
            )
            
        logger.info("Post-execution tasks triggered successfully")
        
    except Exception as e:
        logger.error(f"Failed to trigger post-execution tasks: {str(e)}")


@celery_app.task(name='app.tasks.symphony_scheduler.execute_symphony_batch')
def execute_symphony_batch(symphony_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Execute a batch of symphonies in parallel
    
    Args:
        symphony_ids: List of symphony IDs to execute
        
    Returns:
        List of execution results
    """
    # Create task group
    tasks = []
    for symphony_id in symphony_ids:
        task = execute_symphony_algorithm.signature(
            args=[symphony_id, None, str(date.today()), False],
            queue='algorithm',
            immutable=True
        )
        tasks.append(task)
        
    # Execute in parallel
    job = group(tasks)
    result = job.apply_async()
    
    # Return results
    return result.get(timeout=300)  # 5 minute timeout


@celery_app.task(name='app.tasks.symphony_scheduler.monitor_execution_window')
def monitor_execution_window() -> Dict[str, Any]:
    """
    Monitor the execution window and alert if issues arise
    
    Returns:
        Dictionary containing monitoring results
    """
    current_time = datetime.now(EST)
    
    # Check if we're in execution window
    if current_time.time() < time(15, 50) or current_time.time() > time(16, 0):
        return {
            'status': 'outside_window',
            'current_time': current_time.isoformat()
        }
        
    # Check execution progress
    from celery import current_app
    inspect = current_app.control.inspect()
    
    active_tasks = inspect.active()
    scheduled_tasks = inspect.scheduled()
    
    # Count algorithm execution tasks
    algorithm_tasks = 0
    for worker, tasks in (active_tasks or {}).items():
        for task in tasks:
            if 'algorithm_execution' in task.get('name', ''):
                algorithm_tasks += 1
                
    return {
        'status': 'monitoring',
        'current_time': current_time.isoformat(),
        'active_algorithm_tasks': algorithm_tasks,
        'time_remaining': str(time(16, 0) - current_time.time())
    }
