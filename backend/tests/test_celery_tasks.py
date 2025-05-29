"""
Tests for Celery Tasks

This module tests the Celery background tasks for
algorithm execution and task management.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, patch, MagicMock
from celery import states
from celery.result import AsyncResult

from app.celery_app import celery_app
from app.tasks.algorithm_execution import (
    execute_symphony_algorithm,
    execute_user_symphonies,
    handle_algorithm_failure
)
from app.tasks.symphony_scheduler import (
    execute_daily_symphonies,
    check_execution_eligibility,
    monitor_execution_window
)
from app.tasks.technical_indicators import (
    calculate_indicators,
    batch_calculate_indicators,
    detect_signals
)
from app.tasks.error_tasks import (
    check_failed_executions,
    analyze_execution_failures,
    handle_algorithm_execution_failures
)


# Configure Celery for testing
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


class TestAlgorithmExecutionTasks:
    """Test algorithm execution tasks"""
    
    @patch('app.tasks.algorithm_execution.SessionLocal')
    @patch('app.tasks.algorithm_execution.AlgorithmExecutor')
    @patch('app.tasks.algorithm_execution.AlpacaTradingService')
    def test_execute_symphony_algorithm(self, mock_alpaca, mock_executor, mock_db):
        """Test symphony algorithm execution task"""
        # Mock database session
        mock_session = Mock()
        mock_db.return_value = mock_session
        
        # Mock symphony
        mock_symphony = Mock(id=1, user_id=1, is_active=True)
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_symphony
        
        # Mock execution result
        mock_result = Mock(
            target_allocations={'SPY': 0.6, 'AGG': 0.4},
            errors=[]
        )
        mock_executor.return_value.execute_symphony.return_value = mock_result
        
        # Mock trading service
        mock_alpaca.return_value.execute_rebalancing.return_value = {
            'orders': [{'symbol': 'SPY', 'qty': 10}],
            'errors': []
        }
        
        # Execute task
        result = execute_symphony_algorithm(1, date.today().isoformat())
        
        assert result['symphony_id'] == 1
        assert result['status'] == 'completed'
        assert 'target_allocations' in result
        assert 'execution_time' in result
    
    @patch('app.tasks.algorithm_execution.SessionLocal')
    def test_execute_user_symphonies(self, mock_db):
        """Test executing all symphonies for a user"""
        # Mock database session
        mock_session = Mock()
        mock_db.return_value = mock_session
        
        # Mock symphonies
        mock_symphonies = [
            Mock(id=1, name="Symphony 1"),
            Mock(id=2, name="Symphony 2")
        ]
        mock_session.query.return_value.filter_by.return_value.all.return_value = mock_symphonies
        
        # Mock execute_symphony_algorithm
        with patch('app.tasks.algorithm_execution.execute_symphony_algorithm.apply_async') as mock_apply:
            mock_apply.return_value = Mock(id='task_123')
            
            result = execute_user_symphonies(1)
            
            assert result['user_id'] == 1
            assert result['symphonies_count'] == 2
            assert len(result['task_ids']) == 2
            assert mock_apply.call_count == 2
    
    @patch('app.tasks.algorithm_execution.SessionLocal')
    @patch('app.tasks.algorithm_execution.ErrorHandlerService')
    def test_handle_algorithm_failure(self, mock_error_handler, mock_db):
        """Test algorithm failure handling"""
        # Mock database session
        mock_session = Mock()
        mock_db.return_value = mock_session
        
        # Mock error handler
        mock_error_handler.return_value.handle_symphony_error.return_value = {
            'action': 'liquidated',
            'orders': []
        }
        
        result = handle_algorithm_failure(
            1, "Test error", {"traceback": "..."}
        )
        
        assert result['symphony_id'] == 1
        assert result['action'] == 'error_handled'
        assert 'error' in result


class TestSymphonySchedulerTasks:
    """Test symphony scheduling tasks"""
    
    @patch('app.tasks.symphony_scheduler.SessionLocal')
    @patch('app.tasks.symphony_scheduler.execute_symphony_algorithm')
    def test_execute_daily_symphonies(self, mock_execute, mock_db):
        """Test daily symphony execution scheduling"""
        # Mock database session
        mock_session = Mock()
        mock_db.return_value = mock_session
        
        # Mock active symphonies
        mock_symphonies = [
            Mock(id=1, user_id=1),
            Mock(id=2, user_id=1),
            Mock(id=3, user_id=2)
        ]
        mock_session.query.return_value.filter_by.return_value.all.return_value = mock_symphonies
        
        # Mock task application
        mock_execute.apply_async = Mock(return_value=Mock(id='task_123'))
        
        result = execute_daily_symphonies()
        
        assert result['total_symphonies'] == 3
        assert result['scheduled'] == 3
        assert result['failed'] == 0
        assert 'execution_time' in result
    
    @patch('app.tasks.symphony_scheduler.SessionLocal')
    @patch('app.tasks.symphony_scheduler.RebalancingService')
    def test_check_execution_eligibility(self, mock_rebalancing, mock_db):
        """Test symphony execution eligibility check"""
        # Mock database session
        mock_session = Mock()
        mock_db.return_value = mock_session
        
        # Mock symphony
        mock_symphony = Mock(
            id=1,
            algorithm_config={
                'rebalancing': {
                    'type': 'time_based',
                    'frequency': 'daily'
                }
            }
        )
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_symphony
        
        # Mock rebalancing service
        mock_rebalancing.return_value.should_rebalance.return_value = True
        
        result = check_execution_eligibility(1, date.today().isoformat())
        
        assert result['symphony_id'] == 1
        assert result['eligible'] == True
        assert result['reason'] == 'time_based_schedule'
    
    @patch('app.tasks.symphony_scheduler.datetime')
    def test_monitor_execution_window(self, mock_datetime):
        """Test execution window monitoring"""
        # Mock current time within execution window
        mock_datetime.now.return_value = datetime(2024, 1, 1, 15, 55, 0)  # 3:55 PM
        
        result = monitor_execution_window()
        
        assert result['in_window'] == True
        assert result['window_start'] == '15:50'
        assert result['window_end'] == '16:00'
        assert 'time_remaining_seconds' in result


class TestTechnicalIndicatorTasks:
    """Test technical indicator calculation tasks"""
    
    @patch('app.tasks.technical_indicators.MarketDataService')
    @patch('app.tasks.technical_indicators.TechnicalIndicators')
    def test_calculate_indicators(self, mock_indicators, mock_market_data):
        """Test indicator calculation task"""
        # Mock market data
        mock_market_data.return_value.get_historical_prices.return_value = [100] * 100
        
        # Mock indicator calculations
        mock_indicators.return_value.calculate_rsi.return_value = 50.0
        mock_indicators.return_value.calculate_sma.return_value = 100.0
        
        result = calculate_indicators(
            'SPY',
            ['rsi', 'sma_20'],
            date.today().isoformat()
        )
        
        assert result['symbol'] == 'SPY'
        assert 'rsi' in result['indicators']
        assert 'sma_20' in result['indicators']
        assert result['indicators']['rsi'] == 50.0
    
    def test_batch_calculate_indicators(self):
        """Test batch indicator calculation"""
        with patch('app.tasks.technical_indicators.calculate_indicators.apply_async') as mock_apply:
            mock_apply.return_value = Mock(id='task_123')
            
            result = batch_calculate_indicators(
                ['SPY', 'AGG', 'GLD'],
                ['rsi', 'macd']
            )
            
            assert result['symbols_count'] == 3
            assert len(result['task_ids']) == 3
            assert mock_apply.call_count == 3
    
    @patch('app.tasks.technical_indicators.TechnicalIndicators')
    def test_detect_signals(self, mock_indicators):
        """Test signal detection"""
        # Mock indicators with signal conditions
        indicators = {
            'SPY': {'rsi': 25, 'sma_50': 100, 'sma_200': 95},
            'AGG': {'rsi': 75, 'sma_50': 50, 'sma_200': 52}
        }
        
        result = detect_signals(indicators)
        
        assert 'signals' in result
        assert any(s['symbol'] == 'SPY' and s['signal'] == 'oversold' for s in result['signals'])
        assert any(s['symbol'] == 'AGG' and s['signal'] == 'overbought' for s in result['signals'])


class TestErrorTasks:
    """Test error handling tasks"""
    
    @patch('app.tasks.error_tasks.SessionLocal')
    def test_check_failed_executions(self, mock_db):
        """Test checking for failed executions"""
        # Mock database session
        mock_session = Mock()
        mock_db.return_value = mock_session
        
        # Mock failed execution records
        mock_failures = [
            Mock(symphony_id=1, error_type='algorithm_error'),
            Mock(symphony_id=2, error_type='market_data_error')
        ]
        
        # This would query an execution log table
        mock_session.query.return_value.filter.return_value.all.return_value = mock_failures
        
        result = check_failed_executions()
        
        assert 'failed_count' in result
        assert 'failures' in result
    
    def test_analyze_execution_failures(self):
        """Test failure pattern analysis"""
        failures = [
            {'symphony_id': 1, 'error_type': 'algorithm_error', 'timestamp': datetime.now()},
            {'symphony_id': 2, 'error_type': 'algorithm_error', 'timestamp': datetime.now()},
            {'symphony_id': 3, 'error_type': 'market_data_error', 'timestamp': datetime.now()}
        ]
        
        result = analyze_execution_failures(failures)
        
        assert 'patterns' in result
        assert any(p['type'] == 'frequent_error_type' for p in result['patterns'])
        assert result['summary']['total_failures'] == 3
    
    @patch('app.tasks.error_tasks.handle_algorithm_failure')
    def test_handle_algorithm_execution_failures(self, mock_handle):
        """Test handling algorithm execution failures"""
        # Mock celery inspect
        with patch('app.celery_app.control.inspect') as mock_inspect:
            mock_active = {
                'worker1': [
                    {'id': 'task1', 'name': 'execute_symphony_algorithm', 'state': 'FAILURE'}
                ]
            }
            mock_inspect.return_value.active.return_value = mock_active
            
            result = handle_algorithm_execution_failures()
            
            assert 'handled_count' in result


class TestCeleryIntegration:
    """Test Celery configuration and integration"""
    
    def test_celery_beat_schedule(self):
        """Test that Celery beat schedule is properly configured"""
        from app.celery_app import celery_app
        
        schedule = celery_app.conf.beat_schedule
        
        # Check daily execution task
        assert 'execute-daily-symphonies' in schedule
        daily_task = schedule['execute-daily-symphonies']
        assert daily_task['task'] == 'app.tasks.symphony_scheduler.execute_daily_symphonies'
        
        # Check monitoring task
        assert 'monitor-execution-window' in schedule
        
        # Check error checking task
        assert 'check-failed-executions' in schedule
    
    def test_task_routing(self):
        """Test that tasks are routed to correct queues"""
        from app.celery_app import celery_app
        
        routes = celery_app.conf.task_routes
        
        # Algorithm execution should go to high priority
        assert routes.get('app.tasks.algorithm_execution.execute_symphony_algorithm') == {
            'queue': 'high_priority'
        }
        
        # Market data tasks should go to market_data queue
        assert routes.get('app.tasks.market_data_tasks.prefetch_market_data') == {
            'queue': 'market_data'
        }
    
    def test_task_time_limits(self):
        """Test task time limits are configured"""
        from app.celery_app import celery_app
        
        # Algorithm execution should have reasonable time limit
        assert celery_app.conf.task_time_limit <= 300  # 5 minutes max
        assert celery_app.conf.task_soft_time_limit <= 240  # 4 minute warning
