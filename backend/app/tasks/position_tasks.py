"""
Position Tasks

This module contains Celery tasks for position tracking, reconciliation,
and real-time updates.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

from celery import current_task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database.connection import SessionLocal
from app.models.position import Position
from app.models.user import User
from app.services.trading_service import TradingService
from app.services.alpaca_trading_service import AlpacaTradingService
from app.services.pubsub_service import PubSubService


logger = logging.getLogger(__name__)


@celery_app.task(name='app.tasks.position_tasks.reconcile_positions')
def reconcile_positions() -> Dict[str, Any]:
    """
    Reconcile database positions with Alpaca positions
    
    This task runs after the daily execution window to ensure
    database positions match actual Alpaca account positions.
    
    Returns:
        Dictionary containing reconciliation results
    """
    db: Session = SessionLocal()
    
    result = {
        'reconciliation_time': datetime.utcnow().isoformat(),
        'users_processed': 0,
        'positions_reconciled': 0,
        'discrepancies_found': 0,
        'errors': []
    }
    
    try:
        trading_service = TradingService(db)
        alpaca_service = AlpacaTradingService(db)
        
        # Get all users with Alpaca connections
        users_with_alpaca = db.query(User).filter(
            User.alpaca_access_token.isnot(None)
        ).all()
        
        for user in users_with_alpaca:
            try:
                # Get positions from Alpaca
                alpaca_positions = alpaca_service.get_positions(user)
                
                # Get positions from database
                db_positions = db.query(Position).filter_by(
                    user_id=user.id,
                    is_open=True
                ).all()
                
                # Create position maps for comparison
                alpaca_map = {p['symbol']: p for p in alpaca_positions}
                db_map = {p.symbol: p for p in db_positions}
                
                # Check for discrepancies
                all_symbols = set(alpaca_map.keys()) | set(db_map.keys())
                
                for symbol in all_symbols:
                    alpaca_pos = alpaca_map.get(symbol)
                    db_pos = db_map.get(symbol)
                    
                    if alpaca_pos and not db_pos:
                        # Position in Alpaca but not in database
                        logger.warning(f"Position {symbol} found in Alpaca but not in database for user {user.id}")
                        
                        # Create position in database
                        new_position = Position(
                            user_id=user.id,
                            symbol=symbol,
                            quantity=Decimal(str(alpaca_pos['qty'])),
                            cost_basis=Decimal(str(alpaca_pos['avg_entry_price'])) * Decimal(str(alpaca_pos['qty'])),
                            current_price=Decimal(str(alpaca_pos['current_price'])),
                            is_open=True,
                            opened_at=datetime.utcnow()
                        )
                        db.add(new_position)
                        result['discrepancies_found'] += 1
                        
                    elif db_pos and not alpaca_pos:
                        # Position in database but not in Alpaca
                        logger.warning(f"Position {symbol} found in database but not in Alpaca for user {user.id}")
                        
                        # Close position in database
                        db_pos.is_open = False
                        db_pos.closed_at = datetime.utcnow()
                        result['discrepancies_found'] += 1
                        
                    elif alpaca_pos and db_pos:
                        # Check quantity and price discrepancies
                        alpaca_qty = Decimal(str(alpaca_pos['qty']))
                        
                        if abs(db_pos.quantity - alpaca_qty) > Decimal('0.0001'):
                            logger.warning(
                                f"Quantity mismatch for {symbol}: "
                                f"DB={db_pos.quantity}, Alpaca={alpaca_qty}"
                            )
                            db_pos.quantity = alpaca_qty
                            result['discrepancies_found'] += 1
                            
                        # Update current price
                        db_pos.current_price = Decimal(str(alpaca_pos['current_price']))
                        
                    result['positions_reconciled'] += 1
                    
                result['users_processed'] += 1
                
            except Exception as user_error:
                logger.error(f"Failed to reconcile positions for user {user.id}: {str(user_error)}")
                result['errors'].append({
                    'user_id': user.id,
                    'error': str(user_error)
                })
                
        db.commit()
        
        logger.info(
            f"Position reconciliation completed: "
            f"{result['users_processed']} users, "
            f"{result['positions_reconciled']} positions, "
            f"{result['discrepancies_found']} discrepancies"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Position reconciliation failed: {str(e)}")
        result['error'] = str(e)
        return result
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.position_tasks.update_position_prices')
def update_position_prices() -> Dict[str, Any]:
    """
    Update current prices for all open positions
    
    Returns:
        Dictionary containing update results
    """
    db: Session = SessionLocal()
    
    result = {
        'update_time': datetime.utcnow().isoformat(),
        'positions_updated': 0,
        'errors': []
    }
    
    try:
        trading_service = TradingService(db)
        pubsub_service = PubSubService()
        
        # Get all open positions
        open_positions = db.query(Position).filter_by(is_open=True).all()
        
        # Group positions by symbol to optimize API calls
        positions_by_symbol = {}
        for position in open_positions:
            if position.symbol not in positions_by_symbol:
                positions_by_symbol[position.symbol] = []
            positions_by_symbol[position.symbol].append(position)
            
        # Update prices
        for symbol, positions in positions_by_symbol.items():
            try:
                # Get current price
                current_price = trading_service.get_current_price(symbol)
                
                # Update all positions for this symbol
                for position in positions:
                    position.current_price = current_price
                    position.updated_at = datetime.utcnow()
                    
                    # Publish update via GraphQL subscription
                    pubsub_service.publish_position_update(
                        user_id=position.user_id,
                        position_data={
                            'id': position.id,
                            'symbol': position.symbol,
                            'quantity': float(position.quantity),
                            'current_price': float(current_price),
                            'cost_basis': float(position.cost_basis),
                            'current_value': float(position.quantity * current_price),
                            'unrealized_pnl': float((position.quantity * current_price) - position.cost_basis)
                        }
                    )
                    
                    result['positions_updated'] += 1
                    
            except Exception as symbol_error:
                logger.error(f"Failed to update price for {symbol}: {str(symbol_error)}")
                result['errors'].append({
                    'symbol': symbol,
                    'error': str(symbol_error)
                })
                
        db.commit()
        
        logger.info(f"Updated prices for {result['positions_updated']} positions")
        
        return result
        
    except Exception as e:
        logger.error(f"Position price update failed: {str(e)}")
        result['error'] = str(e)
        return result
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.position_tasks.calculate_position_metrics')
def calculate_position_metrics(user_id: int) -> Dict[str, Any]:
    """
    Calculate detailed metrics for user positions
    
    Args:
        user_id: ID of the user
        
    Returns:
        Dictionary containing position metrics
    """
    db: Session = SessionLocal()
    
    try:
        trading_service = TradingService(db)
        
        # Get user positions
        positions = db.query(Position).filter_by(
            user_id=user_id,
            is_open=True
        ).all()
        
        if not positions:
            return {
                'user_id': user_id,
                'total_value': 0,
                'total_cost': 0,
                'total_pnl': 0,
                'position_count': 0,
                'positions': []
            }
            
        # Calculate metrics
        total_value = Decimal('0')
        total_cost = Decimal('0')
        position_metrics = []
        
        for position in positions:
            current_value = position.quantity * position.current_price
            pnl = current_value - position.cost_basis
            pnl_percentage = (pnl / position.cost_basis * 100) if position.cost_basis > 0 else Decimal('0')
            
            total_value += current_value
            total_cost += position.cost_basis
            
            position_metrics.append({
                'symbol': position.symbol,
                'quantity': float(position.quantity),
                'cost_basis': float(position.cost_basis),
                'current_value': float(current_value),
                'current_price': float(position.current_price),
                'pnl': float(pnl),
                'pnl_percentage': float(pnl_percentage),
                'weight': 0  # Will be calculated after totals
            })
            
        # Calculate weights
        if total_value > 0:
            for metric in position_metrics:
                metric['weight'] = metric['current_value'] / float(total_value)
                
        total_pnl = total_value - total_cost
        total_pnl_percentage = (total_pnl / total_cost * 100) if total_cost > 0 else Decimal('0')
        
        return {
            'user_id': user_id,
            'total_value': float(total_value),
            'total_cost': float(total_cost),
            'total_pnl': float(total_pnl),
            'total_pnl_percentage': float(total_pnl_percentage),
            'position_count': len(positions),
            'positions': position_metrics,
            'calculated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate position metrics for user {user_id}: {str(e)}")
        return {
            'user_id': user_id,
            'error': str(e)
        }
        
    finally:
        db.close()


@celery_app.task(name='app.tasks.position_tasks.sync_symphony_positions')
def sync_symphony_positions(symphony_id: int) -> Dict[str, Any]:
    """
    Sync positions related to a specific symphony
    
    Args:
        symphony_id: ID of the symphony
        
    Returns:
        Dictionary containing sync results
    """
    db: Session = SessionLocal()
    
    try:
        # Get symphony target allocations
        from app.models.symphony import Symphony
        symphony = db.query(Symphony).filter_by(id=symphony_id).first()
        
        if not symphony:
            return {
                'error': f'Symphony {symphony_id} not found'
            }
            
        # Get latest target allocations
        target_allocations = symphony.algorithm_config.get('target_allocations', {})
        
        # Update position metadata
        positions_updated = 0
        for symbol, target_weight in target_allocations.items():
            positions = db.query(Position).filter_by(
                user_id=symphony.user_id,
                symbol=symbol,
                is_open=True
            ).all()
            
            for position in positions:
                if not position.metadata:
                    position.metadata = {}
                    
                position.metadata['symphony_id'] = symphony_id
                position.metadata['target_weight'] = float(target_weight)
                positions_updated += 1
                
        db.commit()
        
        return {
            'symphony_id': symphony_id,
            'positions_updated': positions_updated,
            'target_allocations': target_allocations
        }
        
    except Exception as e:
        logger.error(f"Failed to sync positions for symphony {symphony_id}: {str(e)}")
        return {
            'symphony_id': symphony_id,
            'error': str(e)
        }
        
    finally:
        db.close()
