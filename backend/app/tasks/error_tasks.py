"""
Error Handling Tasks

This module contains Celery tasks for error handling, recovery,
and automatic liquidation to cash on algorithm failures.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
import traceback
from collections import defaultdict

from celery import current_task
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.models.symphony import Symphony
from app.models.user import User
from app.models.trade import Trade
from app.services.error_handler_service import ErrorHandlerService
from app.services.alpaca_trading_service import AlpacaTradingService
from app.services.symphony_service import SymphonyService


logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.error_tasks.check_failed_executions')
def check_failed_executions() -> Dict[str, Any]:
    """
    Periodic task to check for failed executions and trigger recovery
    
    This task runs every 30 minutes to:
    1. Identify failed symphony executions
    2. Analyze failure patterns
    3. Trigger appropriate recovery actions
    4. Send notifications
    
    Returns:
        Dictionary containing recovery summary
    """
    db: Session = SessionLocal()
    
    result = {
        'check_time': datetime.utcnow().isoformat(),
        'failed_symphonies': 0,
        'recovered_symphonies': 0,
        'liquidated_users': 0,
        'notifications_sent': 0,
        'recovery_actions': []
    }
    
    try:
        error_handler = ErrorHandlerService(db)
        
        # Get recent failures (last 30 minutes)
        recent_failures = error_handler.get_recent_failures(
            minutes=30,
            include_recovered=False
        )
        
        result['failed_symphonies'] = len(recent_failures)
        
        if not recent_failures:
            logger.info("No recent failures found")
            return result
            
        # Group failures by type
        failures_by_type = defaultdict(list)
        for failure in recent_failures:
            failures_by_type[failure.error_type].append(failure)
            
        # Handle different failure types
        for error_type, failures in failures_by_type.items():
            if error_type == 'algorithm_execution':
                recovery_result = handle_algorithm_execution_failures(failures, db)
                result['recovery_actions'].append(recovery_result)
                
            elif error_type == 'trade_execution':
                recovery_result = handle_trade_execution_failures(failures, db)
                result['recovery_actions'].append(recovery_result)
                
            elif error_type == 'market_data':
                recovery_result = handle_market_data_failures(failures, db)
                result['recovery_actions'].append(recovery_result)
                
            elif error_type == 'insufficient_funds':
                recovery_result = handle_insufficient_funds_failures(failures, db)
                result['recovery_actions'].append(recovery_result)
                
        # Update counters
        for action in result['recovery_actions']:
            result['recovered_symphonies'] += action.get('recovered', 0)
            result['liquidated_users'] += action.get('liquidated', 0)
            result['notifications_sent'] += action.get('notifications', 0)
            
        logger.info(
            f"Error recovery check completed: "
            f"{result['recovered_symphonies']} recovered, "
            f"{result['liquidated_users']} liquidated"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to check failed executions: {str(e)}")
        result['error'] = str(e)
        return result
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.error_tasks.analyze_execution_failures')
def analyze_execution_failures(failed_executions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze failed symphony executions to identify patterns
    
    Args:
        failed_executions: List of failed execution results
        
    Returns:
        Dictionary containing failure analysis
    """
    analysis = {
        'total_failures': len(failed_executions),
        'failure_categories': defaultdict(int),
        'failure_patterns': [],
        'recommended_actions': []
    }
    
    # Categorize failures
    for execution in failed_executions:
        errors = execution.get('errors', [])
        
        for error in errors:
            error_str = str(error).lower()
            
            if 'market data' in error_str or 'price' in error_str:
                analysis['failure_categories']['market_data'] += 1
                
            elif 'insufficient' in error_str or 'funds' in error_str:
                analysis['failure_categories']['insufficient_funds'] += 1
                
            elif 'algorithm' in error_str or 'calculation' in error_str:
                analysis['failure_categories']['algorithm_error'] += 1
                
            elif 'timeout' in error_str or 'time limit' in error_str:
                analysis['failure_categories']['timeout'] += 1
                
            elif 'connection' in error_str or 'network' in error_str:
                analysis['failure_categories']['network_error'] += 1
                
            else:
                analysis['failure_categories']['unknown'] += 1
                
    # Identify patterns
    if analysis['failure_categories']['market_data'] > 3:
        analysis['failure_patterns'].append({
            'pattern': 'market_data_outage',
            'severity': 'high',
            'count': analysis['failure_categories']['market_data']
        })
        analysis['recommended_actions'].append('switch_market_data_provider')
        
    if analysis['failure_categories']['timeout'] > 5:
        analysis['failure_patterns'].append({
            'pattern': 'system_overload',
            'severity': 'medium',
            'count': analysis['failure_categories']['timeout']
        })
        analysis['recommended_actions'].append('scale_workers')
        
    # Generate alerts for patterns
    if analysis['failure_patterns']:
        trigger_pattern_alerts.delay(analysis['failure_patterns'])
        
    return dict(analysis)


def handle_algorithm_execution_failures(
    failures: List[Any],
    db: Session
) -> Dict[str, Any]:
    """
    Handle algorithm execution failures
    
    Args:
        failures: List of failure records
        db: Database session
        
    Returns:
        Dictionary containing recovery results
    """
    result = {
        'failure_type': 'algorithm_execution',
        'total_failures': len(failures),
        'recovered': 0,
        'liquidated': 0,
        'notifications': 0
    }
    
    alpaca_service = AlpacaTradingService(db)
    
    # Group by user to avoid multiple liquidations
    failures_by_user = defaultdict(list)
    for failure in failures:
        failures_by_user[failure.user_id].append(failure)
        
    for user_id, user_failures in failures_by_user.items():
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                continue
                
            # Check if multiple failures for same user
            if len(user_failures) >= 3:
                # Multiple failures - liquidate to cash
                logger.warning(f"Multiple algorithm failures for user {user_id}, liquidating positions")
                
                liquidation_result = alpaca_service.liquidate_all_positions(user)
                
                if liquidation_result.get('success'):
                    result['liquidated'] += 1
                    
                    # Deactivate all user symphonies
                    db.query(Symphony).filter_by(
                        user_id=user_id,
                        is_active=True
                    ).update({
                        'is_active': False,
                        'error_message': 'Deactivated due to multiple algorithm failures'
                    })
                    
                    # Send critical alert
                    send_critical_alert.delay(
                        user_id=user_id,
                        alert_type='multiple_failures_liquidation',
                        message='Your positions have been liquidated due to multiple algorithm failures'
                    )
                    result['notifications'] += 1
                    
            else:
                # Single failure - attempt recovery
                for failure in user_failures:
                    symphony = db.query(Symphony).filter_by(
                        id=failure.symphony_id
                    ).first()
                    
                    if symphony and symphony.is_active:
                        # Retry execution once
                        from app.tasks.algorithm_execution import execute_symphony_algorithm
                        
                        retry_task = execute_symphony_algorithm.apply_async(
                            args=[symphony.id, user_id, str(date.today()), False],
                            queue='algorithm',
                            countdown=60  # Wait 1 minute before retry
                        )
                        
                        logger.info(f"Retrying symphony {symphony.id} execution")
                        result['recovered'] += 1
                        
        except Exception as e:
            logger.error(f"Failed to handle failures for user {user_id}: {str(e)}")
            
    db.commit()
    return result


def handle_trade_execution_failures(
    failures: List[Any],
    db: Session
) -> Dict[str, Any]:
    """
    Handle trade execution failures
    
    Args:
        failures: List of failure records
        db: Database session
        
    Returns:
        Dictionary containing recovery results
    """
    result = {
        'failure_type': 'trade_execution',
        'total_failures': len(failures),
        'recovered': 0,
        'liquidated': 0,
        'notifications': 0
    }
    
    alpaca_service = AlpacaTradingService(db)
    
    for failure in failures:
        try:
            # Check if partial execution occurred
            partial_trades = failure.metadata.get('partial_trades', [])
            
            if partial_trades:
                # Attempt to complete or rollback partial trades
                user = db.query(User).filter_by(id=failure.user_id).first()
                if not user:
                    continue
                    
                # Try to complete remaining trades
                remaining_trades = failure.metadata.get('remaining_trades', [])
                
                if remaining_trades:
                    try:
                        completion_result = alpaca_service.execute_trades(
                            user=user,
                            trades=remaining_trades,
                            symphony_id=failure.symphony_id
                        )
                        
                        if completion_result:
                            result['recovered'] += 1
                            logger.info(f"Completed remaining trades for symphony {failure.symphony_id}")
                            
                    except Exception as completion_error:
                        # If completion fails, rollback everything
                        logger.error(f"Failed to complete trades: {str(completion_error)}")
                        
                        rollback_result = alpaca_service.rollback_trades(
                            user=user,
                            trades=partial_trades
                        )
                        
                        if rollback_result.get('success'):
                            result['recovered'] += 1
                        else:
                            # Rollback failed - liquidate
                            alpaca_service.liquidate_all_positions(user)
                            result['liquidated'] += 1
                            
            # Update failure record
            failure.recovery_attempted = True
            failure.recovery_action = 'trade_completion' if result['recovered'] > 0 else 'liquidation'
            
        except Exception as e:
            logger.error(f"Failed to handle trade failure {failure.id}: {str(e)}")
            
    db.commit()
    return result


def handle_market_data_failures(
    failures: List[Any],
    db: Session
) -> Dict[str, Any]:
    """
    Handle market data failures
    
    Args:
        failures: List of failure records
        db: Database session
        
    Returns:
        Dictionary containing recovery results
    """
    result = {
        'failure_type': 'market_data',
        'total_failures': len(failures),
        'recovered': 0,
        'notifications': 0
    }
    
    # Check if market data service is responsive
    from app.services.market_data_service import MarketDataService
    market_data_service = MarketDataService(db)
    
    try:
        # Test market data service
        test_symbol = 'SPY'
        test_price = market_data_service.get_current_price(test_symbol)
        
        if test_price:
            # Service is back online - retry failed executions
            for failure in failures:
                from app.tasks.algorithm_execution import execute_symphony_algorithm
                
                retry_task = execute_symphony_algorithm.apply_async(
                    args=[failure.symphony_id, failure.user_id, str(date.today()), False],
                    queue='algorithm',
                    countdown=30  # Wait 30 seconds
                )
                
                result['recovered'] += 1
                logger.info(f"Retrying symphony {failure.symphony_id} after market data recovery")
                
        else:
            # Service still down - notify and wait
            logger.error("Market data service still unavailable")
            
            # Send alerts for first occurrence only
            if not any(f.notification_sent for f in failures):
                send_system_alert.delay(
                    alert_type='market_data_outage',
                    message='Market data service is unavailable',
                    severity='critical'
                )
                result['notifications'] += 1
                
                # Mark notifications as sent
                for failure in failures:
                    failure.notification_sent = True
                    
    except Exception as e:
        logger.error(f"Market data service check failed: {str(e)}")
        
    db.commit()
    return result


def handle_insufficient_funds_failures(
    failures: List[Any],
    db: Session
) -> Dict[str, Any]:
    """
    Handle insufficient funds failures
    
    Args:
        failures: List of failure records
        db: Database session
        
    Returns:
        Dictionary containing recovery results
    """
    result = {
        'failure_type': 'insufficient_funds',
        'total_failures': len(failures),
        'recovered': 0,
        'notifications': 0
    }
    
    for failure in failures:
        try:
            # Scale down allocations and retry
            symphony = db.query(Symphony).filter_by(
                id=failure.symphony_id
            ).first()
            
            if symphony:
                # Add cash buffer to algorithm config
                if 'allocation' not in symphony.algorithm_config:
                    symphony.algorithm_config['allocation'] = {}
                    
                # Increase cash buffer by 10%
                current_buffer = float(symphony.algorithm_config['allocation'].get('cash_buffer', 0))
                symphony.algorithm_config['allocation']['cash_buffer'] = min(current_buffer + 0.1, 0.5)
                
                db.commit()
                
                # Retry with scaled allocations
                from app.tasks.algorithm_execution import execute_symphony_algorithm
                
                retry_task = execute_symphony_algorithm.apply_async(
                    args=[symphony.id, failure.user_id, str(date.today()), False],
                    queue='algorithm',
                    countdown=60
                )
                
                result['recovered'] += 1
                logger.info(f"Retrying symphony {symphony.id} with increased cash buffer")
                
                # Notify user
                send_user_notification.delay(
                    user_id=failure.user_id,
                    notification_type='insufficient_funds',
                    message=f'Your symphony "{symphony.name}" allocations have been scaled down due to insufficient funds'
                )
                result['notifications'] += 1
                
        except Exception as e:
            logger.error(f"Failed to handle insufficient funds for failure {failure.id}: {str(e)}")
            
    return result


@celery_app.task(name='app.tasks.error_tasks.trigger_pattern_alerts')
def trigger_pattern_alerts(patterns: List[Dict[str, Any]]) -> None:
    """
    Trigger alerts for identified failure patterns
    
    Args:
        patterns: List of identified patterns
    """
    for pattern in patterns:
        if pattern['severity'] == 'high':
            send_system_alert.delay(
                alert_type='failure_pattern',
                message=f"High severity pattern detected: {pattern['pattern']} ({pattern['count']} occurrences)",
                severity='critical',
                metadata=pattern
            )
        elif pattern['severity'] == 'medium':
            logger.warning(f"Medium severity pattern: {pattern['pattern']} ({pattern['count']} occurrences)")


@celery_app.task(name='app.tasks.error_tasks.send_critical_alert')
def send_critical_alert(
    user_id: int,
    alert_type: str,
    message: str
) -> None:
    """Send critical alert to user"""
    logger.critical(f"Critical alert for user {user_id}: {alert_type} - {message}")
    # Implementation would integrate with notification service


@celery_app.task(name='app.tasks.error_tasks.send_system_alert')
def send_system_alert(
    alert_type: str,
    message: str,
    severity: str,
    metadata: Optional[Dict] = None
) -> None:
    """Send system-wide alert"""
    logger.error(f"System alert [{severity}]: {alert_type} - {message}")
    # Implementation would integrate with monitoring service


@celery_app.task(name='app.tasks.error_tasks.send_user_notification')
def send_user_notification(
    user_id: int,
    notification_type: str,
    message: str
) -> None:
    """Send notification to user"""
    logger.info(f"User notification for {user_id}: {notification_type} - {message}")
    # Implementation would integrate with notification service


@celery_app.task(name='app.tasks.error_tasks.cleanup_old_errors')
def cleanup_old_errors(days: int = 30) -> Dict[str, int]:
    """
    Clean up old error records
    
    Args:
        days: Number of days to keep error records
        
    Returns:
        Dictionary containing cleanup statistics
    """
    db: Session = SessionLocal()
    
    try:
        error_handler = ErrorHandlerService(db)
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        deleted_count = error_handler.cleanup_old_errors(cutoff_date)
        
        logger.info(f"Cleaned up {deleted_count} error records older than {days} days")
        
        return {
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup old errors: {str(e)}")
        return {'error': str(e)}
        
    finally:
        db.close()
