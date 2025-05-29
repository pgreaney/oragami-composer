"""
Algorithm Execution Tasks

This module contains Celery tasks for executing symphony algorithms,
handling the complex decision trees and trading logic.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
import logging
import traceback

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.models.symphony import Symphony
from app.models.user import User
from app.models.position import Position
from app.models.trade import Trade
from app.algorithms.executor import AlgorithmExecutor, ExecutionResult
from app.services.market_data_service import MarketDataService
from app.services.alpaca_trading_service import AlpacaTradingService
from app.services.error_handler_service import ErrorHandlerService
from app.services.symphony_service import SymphonyService
from app.services.trading_service import TradingService


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='app.tasks.algorithm_execution.execute_symphony_algorithm')
def execute_symphony_algorithm(
    self,
    symphony_id: int,
    user_id: int,
    execution_date: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Execute a single symphony's algorithm
    
    Args:
        symphony_id: ID of the symphony to execute
        user_id: ID of the user who owns the symphony
        execution_date: Optional execution date (defaults to today)
        dry_run: If True, calculate allocations but don't execute trades
        
    Returns:
        Dictionary containing execution results and metadata
    """
    db: Session = SessionLocal()
    result = {
        'success': False,
        'symphony_id': symphony_id,
        'user_id': user_id,
        'execution_date': execution_date or str(date.today()),
        'allocations': {},
        'trades': [],
        'errors': [],
        'logs': []
    }
    
    try:
        # Update task state
        self.update_state(
            state='EXECUTING',
            meta={'symphony_id': symphony_id, 'status': 'Loading symphony...'}
        )
        
        # Load symphony and user
        symphony = db.query(Symphony).filter_by(
            id=symphony_id,
            user_id=user_id,
            is_active=True
        ).first()
        
        if not symphony:
            raise ValueError(f"Symphony {symphony_id} not found or not active")
            
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
            
        # Check if user has valid Alpaca connection
        if not user.alpaca_access_token:
            raise ValueError("User does not have a valid Alpaca connection")
            
        # Parse execution date
        exec_date = datetime.strptime(
            execution_date or str(date.today()), 
            '%Y-%m-%d'
        ).date()
        
        # Initialize services
        market_data_service = MarketDataService(db)
        trading_service = TradingService(db)
        alpaca_service = AlpacaTradingService(db)
        
        # Get current positions
        self.update_state(
            state='EXECUTING',
            meta={'symphony_id': symphony_id, 'status': 'Fetching current positions...'}
        )
        
        current_positions = trading_service.get_user_positions(user_id)
        
        # Initialize algorithm executor
        executor = AlgorithmExecutor(db, market_data_service)
        
        # Execute algorithm
        self.update_state(
            state='EXECUTING',
            meta={'symphony_id': symphony_id, 'status': 'Executing algorithm...'}
        )
        
        execution_result: ExecutionResult = executor.execute_symphony(
            symphony=symphony,
            current_positions=current_positions,
            execution_date=exec_date
        )
        
        # Store execution results
        result['allocations'] = {
            symbol: float(allocation) 
            for symbol, allocation in execution_result.target_allocations.items()
        }
        result['logs'] = execution_result.execution_logs
        result['errors'] = execution_result.errors
        
        # Check for execution errors
        if execution_result.errors:
            logger.error(f"Algorithm execution errors: {execution_result.errors}")
            if not dry_run:
                # Trigger error recovery
                handle_algorithm_failure.delay(
                    symphony_id=symphony_id,
                    user_id=user_id,
                    errors=execution_result.errors
                )
            return result
            
        # Calculate required trades
        self.update_state(
            state='EXECUTING',
            meta={'symphony_id': symphony_id, 'status': 'Calculating trades...'}
        )
        
        required_trades = trading_service.calculate_required_trades(
            current_positions=current_positions,
            target_allocations=execution_result.target_allocations,
            portfolio_value=alpaca_service.get_portfolio_value(user)
        )
        
        # Execute trades if not dry run
        if not dry_run and required_trades:
            self.update_state(
                state='EXECUTING',
                meta={'symphony_id': symphony_id, 'status': 'Executing trades...'}
            )
            
            try:
                executed_trades = alpaca_service.execute_trades(
                    user=user,
                    trades=required_trades,
                    symphony_id=symphony_id
                )
                
                # Record trades in database
                for trade_data in executed_trades:
                    trade = Trade(
                        user_id=user_id,
                        symphony_id=symphony_id,
                        symbol=trade_data['symbol'],
                        side=trade_data['side'],
                        quantity=trade_data['quantity'],
                        price=trade_data['price'],
                        alpaca_order_id=trade_data['order_id'],
                        status='executed',
                        executed_at=datetime.utcnow()
                    )
                    db.add(trade)
                    
                db.commit()
                
                result['trades'] = [
                    {
                        'symbol': t['symbol'],
                        'side': t['side'],
                        'quantity': float(t['quantity']),
                        'price': float(t['price'])
                    }
                    for t in executed_trades
                ]
                
            except Exception as trade_error:
                logger.error(f"Trade execution failed: {str(trade_error)}")
                result['errors'].append(f"Trade execution error: {str(trade_error)}")
                
                # Trigger error recovery
                if not dry_run:
                    handle_trade_failure.delay(
                        symphony_id=symphony_id,
                        user_id=user_id,
                        error=str(trade_error),
                        partial_trades=result['trades']
                    )
                    
        # Update symphony execution timestamp
        symphony.last_executed_at = datetime.utcnow()
        db.commit()
        
        result['success'] = True
        
        # Send execution notification
        send_execution_notification.delay(
            user_id=user_id,
            symphony_id=symphony_id,
            execution_result=result
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Symphony execution failed: {str(e)}")
        logger.error(traceback.format_exc())
        
        result['errors'].append(str(e))
        
        # Trigger error recovery
        if not dry_run:
            handle_algorithm_failure.delay(
                symphony_id=symphony_id,
                user_id=user_id,
                errors=[str(e)]
            )
            
        return result
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.algorithm_execution.execute_user_symphonies')
def execute_user_symphonies(user_id: int, execution_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute all active symphonies for a user
    
    Args:
        user_id: ID of the user
        execution_date: Optional execution date
        
    Returns:
        Dictionary containing results for all symphonies
    """
    db: Session = SessionLocal()
    results = {
        'user_id': user_id,
        'execution_date': execution_date or str(date.today()),
        'symphonies': [],
        'summary': {
            'total': 0,
            'successful': 0,
            'failed': 0
        }
    }
    
    try:
        # Get all active symphonies for user
        symphonies = db.query(Symphony).filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        results['summary']['total'] = len(symphonies)
        
        # Execute each symphony
        for symphony in symphonies:
            logger.info(f"Executing symphony {symphony.id} for user {user_id}")
            
            # Use group to execute symphonies in parallel
            task_result = execute_symphony_algorithm.apply_async(
                args=[symphony.id, user_id, execution_date, False],
                queue='algorithm',
                priority=8
            )
            
            # Store task ID for monitoring
            results['symphonies'].append({
                'symphony_id': symphony.id,
                'symphony_name': symphony.name,
                'task_id': task_result.id
            })
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to execute user symphonies: {str(e)}")
        raise
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.algorithm_execution.handle_algorithm_failure')
def handle_algorithm_failure(
    symphony_id: int,
    user_id: int,
    errors: List[str]
) -> Dict[str, Any]:
    """
    Handle algorithm execution failures with automatic liquidation to cash
    
    Args:
        symphony_id: ID of the failed symphony
        user_id: ID of the user
        errors: List of error messages
        
    Returns:
        Dictionary containing recovery results
    """
    db: Session = SessionLocal()
    
    try:
        error_handler = ErrorHandlerService(db)
        alpaca_service = AlpacaTradingService(db)
        
        # Log failure
        logger.error(f"Algorithm failure for symphony {symphony_id}: {errors}")
        
        # Get user
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
            
        # Liquidate positions to cash
        logger.info(f"Liquidating positions for user {user_id} due to algorithm failure")
        
        liquidation_result = alpaca_service.liquidate_all_positions(user)
        
        # Record error in database
        error_handler.record_algorithm_failure(
            symphony_id=symphony_id,
            user_id=user_id,
            errors=errors,
            recovery_action='liquidated_to_cash',
            recovery_result=liquidation_result
        )
        
        # Deactivate symphony
        symphony = db.query(Symphony).filter_by(id=symphony_id).first()
        if symphony:
            symphony.is_active = False
            symphony.error_message = f"Algorithm failed: {'; '.join(errors)}"
            db.commit()
            
        # Send alert to user
        send_error_alert.delay(
            user_id=user_id,
            symphony_id=symphony_id,
            error_type='algorithm_failure',
            message=f"Your symphony '{symphony.name}' failed and positions were liquidated to cash",
            errors=errors
        )
        
        return {
            'success': True,
            'action': 'liquidated_to_cash',
            'liquidation_result': liquidation_result
        }
        
    except Exception as e:
        logger.error(f"Failed to handle algorithm failure: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.algorithm_execution.handle_trade_failure')
def handle_trade_failure(
    symphony_id: int,
    user_id: int,
    error: str,
    partial_trades: List[Dict]
) -> Dict[str, Any]:
    """
    Handle trade execution failures with rollback or partial execution handling
    
    Args:
        symphony_id: ID of the symphony
        user_id: ID of the user
        error: Error message
        partial_trades: List of trades that were executed before failure
        
    Returns:
        Dictionary containing recovery results
    """
    db: Session = SessionLocal()
    
    try:
        error_handler = ErrorHandlerService(db)
        alpaca_service = AlpacaTradingService(db)
        
        # Get user
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
            
        recovery_result = {}
        
        if partial_trades:
            # Attempt to rollback partial trades
            logger.info(f"Attempting to rollback {len(partial_trades)} partial trades")
            
            rollback_trades = []
            for trade in partial_trades:
                # Create opposite trade to rollback
                rollback_trade = {
                    'symbol': trade['symbol'],
                    'side': 'sell' if trade['side'] == 'buy' else 'buy',
                    'quantity': trade['quantity']
                }
                rollback_trades.append(rollback_trade)
                
            try:
                rollback_result = alpaca_service.execute_trades(
                    user=user,
                    trades=rollback_trades,
                    symphony_id=symphony_id
                )
                recovery_result['rollback'] = rollback_result
                recovery_result['action'] = 'rollback_successful'
                
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {str(rollback_error)}")
                # If rollback fails, liquidate everything
                liquidation_result = alpaca_service.liquidate_all_positions(user)
                recovery_result['liquidation'] = liquidation_result
                recovery_result['action'] = 'liquidated_after_rollback_failure'
                
        # Record error
        error_handler.record_trade_failure(
            symphony_id=symphony_id,
            user_id=user_id,
            error=error,
            partial_trades=partial_trades,
            recovery_result=recovery_result
        )
        
        # Send alert
        send_error_alert.delay(
            user_id=user_id,
            symphony_id=symphony_id,
            error_type='trade_failure',
            message=f"Trade execution failed for your symphony. Recovery action: {recovery_result.get('action', 'unknown')}",
            errors=[error]
        )
        
        return {
            'success': True,
            'recovery_result': recovery_result
        }
        
    except Exception as e:
        logger.error(f"Failed to handle trade failure: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.algorithm_execution.send_execution_notification')
def send_execution_notification(
    user_id: int,
    symphony_id: int,
    execution_result: Dict[str, Any]
) -> None:
    """Send notification about symphony execution results"""
    # Implementation would integrate with notification service
    logger.info(f"Sending execution notification for symphony {symphony_id} to user {user_id}")
    pass


@celery_app.task(name='app.tasks.algorithm_execution.send_error_alert')
def send_error_alert(
    user_id: int,
    symphony_id: int,
    error_type: str,
    message: str,
    errors: List[str]
) -> None:
    """Send error alert to user"""
    # Implementation would integrate with alert service
    logger.error(f"Sending error alert for symphony {symphony_id} to user {user_id}: {message}")
    pass
