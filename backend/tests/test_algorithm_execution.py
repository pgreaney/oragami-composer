"""
Tests for Algorithm Execution

This module tests the symphony algorithm execution engine,
including complex decision trees and technical indicators.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from app.algorithms.executor import AlgorithmExecutor, ExecutionResult, AssetData
from app.models.symphony import Symphony
from app.models.position import Position
from app.services.market_data_service import MarketDataService


class TestAlgorithmExecutor:
    """Test algorithm execution engine"""
    
    @pytest.fixture
    def executor(self):
        """Create algorithm executor with mocked dependencies"""
        db_mock = Mock()
        market_data_mock = Mock(spec=MarketDataService)
        return AlgorithmExecutor(db_mock, market_data_mock)
    
    @pytest.fixture
    def sample_symphony(self):
        """Create a sample symphony for testing"""
        symphony = Symphony(
            id=1,
            user_id=1,
            name="Test Symphony",
            algorithm_config={
                "universe": ["SPY", "AGG", "GLD"],
                "rebalancing": {
                    "type": "time_based",
                    "frequency": "daily"
                },
                "steps": [
                    {
                        "type": "scoring",
                        "metrics": [
                            {"type": "momentum", "lookback": 20, "weight": 0.5},
                            {"type": "volatility", "weight": 0.5}
                        ]
                    },
                    {
                        "type": "ranking",
                        "metric": "score",
                        "direction": "descending",
                        "limit": 2
                    },
                    {
                        "type": "weighting",
                        "method": "equal"
                    }
                ],
                "allocation": {
                    "min_allocation": 0.1,
                    "max_allocation": 0.5,
                    "cash_buffer": 0.05
                }
            }
        )
        return symphony
    
    def test_execute_symphony_basic(self, executor, sample_symphony):
        """Test basic symphony execution"""
        # Mock market data
        executor.market_data_service.get_current_price = Mock(return_value=100.0)
        executor.market_data_service.get_historical_prices = Mock(
            return_value=[95.0, 96.0, 97.0, 98.0, 99.0, 100.0] * 42  # 252 days
        )
        executor.market_data_service.get_quote = Mock(return_value={
            'volume': 1000000,
            'marketCap': 1000000000
        })
        
        # Execute symphony
        result = executor.execute_symphony(
            symphony=sample_symphony,
            current_positions=[],
            execution_date=date.today()
        )
        
        # Verify result
        assert isinstance(result, ExecutionResult)
        assert len(result.target_allocations) > 0
        assert 'SPY' in result.target_allocations or 'AGG' in result.target_allocations
        assert sum(result.target_allocations.values()) <= Decimal('1.0')
        assert len(result.errors) == 0
    
    def test_conditional_execution(self, executor):
        """Test conditional logic execution"""
        symphony = Symphony(
            id=2,
            user_id=1,
            name="Conditional Symphony",
            algorithm_config={
                "universe": ["SPY", "TLT"],
                "steps": [
                    {
                        "type": "conditional",
                        "condition": {
                            "type": "indicator",
                            "symbol": "SPY",
                            "indicator": "rsi",
                            "threshold": 30,
                            "operator": "<"
                        },
                        "then_steps": [
                            {
                                "type": "weighting",
                                "method": "custom",
                                "weights": {"SPY": 0.8, "TLT": 0.2}
                            }
                        ],
                        "else_steps": [
                            {
                                "type": "weighting",
                                "method": "custom",
                                "weights": {"SPY": 0.2, "TLT": 0.8}
                            }
                        ]
                    }
                ]
            }
        )
        
        # Mock RSI calculation
        with patch.object(executor.technical_indicators, 'calculate_rsi', return_value=25.0):
            executor.market_data_service.get_current_price = Mock(return_value=100.0)
            executor.market_data_service.get_historical_prices = Mock(
                return_value=[100.0] * 252
            )
            executor.market_data_service.get_quote = Mock(return_value={'volume': 1000000})
            
            result = executor.execute_symphony(symphony, [], date.today())
            
            # Should take the "then" branch (RSI < 30)
            assert result.target_allocations['SPY'] == Decimal('0.8')
            assert result.target_allocations['TLT'] == Decimal('0.2')
    
    def test_threshold_based_rebalancing(self, executor, sample_symphony):
        """Test threshold-based rebalancing logic"""
        # Modify symphony for threshold-based rebalancing
        sample_symphony.algorithm_config['rebalancing'] = {
            'type': 'threshold_based',
            'threshold': 0.075  # 7.5%
        }
        sample_symphony.algorithm_config['target_allocations'] = {
            'SPY': 0.6,
            'AGG': 0.4
        }
        
        # Current positions with drift
        current_positions = [
            Position(symbol='SPY', quantity=Decimal('10'), current_price=Decimal('100')),
            Position(symbol='AGG', quantity=Decimal('5'), current_price=Decimal('100'))
        ]
        
        # Total value: 1000 + 500 = 1500
        # SPY weight: 1000/1500 = 0.667 (target: 0.6, drift: 0.067)
        # AGG weight: 500/1500 = 0.333 (target: 0.4, drift: 0.067)
        # Drift < 0.075, so no rebalancing needed
        
        result = executor._should_rebalance(
            sample_symphony, current_positions, date.today()
        )
        
        assert result == False
    
    def test_screening_step(self, executor):
        """Test asset screening functionality"""
        # Create asset data
        assets = {
            'SPY': AssetData(
                symbol='SPY',
                current_price=Decimal('400'),
                historical_prices=[Decimal('380')] * 252,
                volume=Decimal('100000000')
            ),
            'PENNY': AssetData(
                symbol='PENNY',
                current_price=Decimal('0.50'),
                historical_prices=[Decimal('0.45')] * 252,
                volume=Decimal('1000')
            )
        }
        
        step = {
            'type': 'screening',
            'criteria': [
                {'type': 'price', 'min': 1.0},
                {'type': 'volume', 'min': 1000000}
            ]
        }
        
        result = ExecutionResult()
        filtered = executor._execute_screening_step(step, assets, result)
        
        assert 'SPY' in filtered
        assert 'PENNY' not in filtered
        assert 'PENNY' in result.excluded_assets
    
    def test_technical_indicator_calculation(self, executor):
        """Test technical indicator calculations"""
        asset_data = AssetData(
            symbol='TEST',
            current_price=Decimal('100'),
            historical_prices=[Decimal(str(90 + i)) for i in range(100)],
            volume=Decimal('1000000')
        )
        
        # Calculate RSI
        executor._calculate_indicators(asset_data, ['rsi', 'volatility', 'sma_20'])
        
        assert 'rsi' in asset_data.indicators
        assert 'volatility' in asset_data.indicators
        assert 'sma_20' in asset_data.indicators
        assert all(isinstance(v, Decimal) for v in asset_data.indicators.values())
    
    def test_error_handling(self, executor, sample_symphony):
        """Test error handling in execution"""
        # Mock market data service to raise exception
        executor.market_data_service.get_current_price = Mock(
            side_effect=Exception("API Error")
        )
        
        result = executor.execute_symphony(
            symphony=sample_symphony,
            current_positions=[],
            execution_date=date.today()
        )
        
        assert len(result.errors) > 0
        assert "API Error" in result.errors[0]
        assert result.target_allocations == {}


class TestExecutionTiming:
    """Test execution timing and performance"""
    
    def test_execution_within_window(self, executor):
        """Test that execution completes within time window"""
        import time
        
        # Create symphony with 40 assets (max per user)
        symphony = Symphony(
            id=3,
            user_id=1,
            name="Large Symphony",
            algorithm_config={
                "universe": [f"ASSET{i}" for i in range(40)],
                "steps": [
                    {"type": "scoring", "metrics": [{"type": "momentum"}]},
                    {"type": "ranking", "limit": 20},
                    {"type": "weighting", "method": "equal"}
                ]
            }
        )
        
        # Mock market data
        executor.market_data_service.get_current_price = Mock(return_value=100.0)
        executor.market_data_service.get_historical_prices = Mock(
            return_value=[100.0] * 252
        )
        executor.market_data_service.get_quote = Mock(return_value={'volume': 1000000})
        
        # Time execution
        start_time = time.time()
        result = executor.execute_symphony(symphony, [], date.today())
        execution_time = time.time() - start_time
        
        # Should complete in reasonable time (< 10 seconds per symphony)
        assert execution_time < 10.0
        assert len(result.errors) == 0
