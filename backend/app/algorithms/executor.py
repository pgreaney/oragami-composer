"""
Algorithm Execution Engine for Origami Composer

This module implements the core algorithmic execution engine that interprets and executes
the complex decision trees, conditional logic, technical indicators, and asset selection
rules defined in Composer.trade symphony JSON files.
"""

from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.algorithms.indicators import TechnicalIndicators
from app.services.market_data_service import MarketDataService
from app.models.symphony import Symphony
from app.models.position import Position
from app.parsers.schemas import (
    SymphonyStep, ConditionalStep, ScreeningStep, WeightingStep,
    ScoringStep, FilteringStep, RankingStep, AssetGroupStep,
    ComparisonOperator, TimeComparison, RebalancingType
)


logger = logging.getLogger(__name__)


class ExecutionResult:
    """Result of algorithm execution"""
    def __init__(self):
        self.target_allocations: Dict[str, Decimal] = {}
        self.signals: Dict[str, Any] = {}
        self.excluded_assets: List[str] = []
        self.execution_logs: List[str] = []
        self.errors: List[str] = []
        self.metadata: Dict[str, Any] = {}


@dataclass
class AssetData:
    """Container for asset market data and calculations"""
    symbol: str
    current_price: Decimal
    historical_prices: List[Decimal]
    volume: Decimal
    market_cap: Optional[Decimal] = None
    indicators: Dict[str, Decimal] = None
    score: Decimal = Decimal('0')
    weight: Decimal = Decimal('0')
    
    def __post_init__(self):
        if self.indicators is None:
            self.indicators = {}


class AlgorithmExecutor:
    """
    Main algorithm execution engine that processes symphony decision trees
    """
    
    def __init__(self, db: Session, market_data_service: MarketDataService):
        self.db = db
        self.market_data_service = market_data_service
        self.technical_indicators = TechnicalIndicators()
        
    def execute_symphony(
        self,
        symphony: Symphony,
        current_positions: List[Position],
        execution_date: date
    ) -> ExecutionResult:
        """
        Execute a symphony's algorithm to generate target allocations
        
        Args:
            symphony: Symphony model containing algorithm JSON
            current_positions: Current portfolio positions
            execution_date: Date of execution
            
        Returns:
            ExecutionResult with target allocations and metadata
        """
        result = ExecutionResult()
        
        try:
            # Parse symphony algorithm
            algorithm = symphony.algorithm_config
            
            # Check if rebalancing is needed
            if not self._should_rebalance(symphony, current_positions, execution_date):
                result.execution_logs.append("Rebalancing not needed based on schedule/threshold")
                return result
            
            # Get universe of assets
            universe = self._get_asset_universe(algorithm.get('universe', []))
            
            # Fetch market data for all assets
            asset_data_map = self._fetch_asset_data(universe, execution_date)
            
            # Execute main algorithm steps
            for step in algorithm.get('steps', []):
                asset_data_map = self._execute_step(
                    step, asset_data_map, execution_date, result
                )
            
            # Generate final allocations
            result.target_allocations = self._generate_allocations(
                asset_data_map, algorithm.get('allocation', {})
            )
            
            result.execution_logs.append(
                f"Algorithm execution completed successfully with {len(result.target_allocations)} allocations"
            )
            
        except Exception as e:
            logger.error(f"Algorithm execution failed: {str(e)}")
            result.errors.append(f"Execution failed: {str(e)}")
            
        return result
    
    def _should_rebalance(
        self,
        symphony: Symphony,
        current_positions: List[Position],
        execution_date: date
    ) -> bool:
        """
        Determine if rebalancing should occur based on schedule or threshold
        """
        rebalancing = symphony.algorithm_config.get('rebalancing', {})
        rebalancing_type = rebalancing.get('type', 'time_based')
        
        if rebalancing_type == 'time_based':
            return self._check_time_based_rebalancing(rebalancing, execution_date)
        elif rebalancing_type == 'threshold_based':
            return self._check_threshold_based_rebalancing(
                rebalancing, current_positions, symphony
            )
        
        return True  # Default to rebalancing if no specific rules
    
    def _check_time_based_rebalancing(
        self, rebalancing: Dict, execution_date: date
    ) -> bool:
        """Check if time-based rebalancing is due"""
        frequency = rebalancing.get('frequency', 'daily')
        
        if frequency == 'daily':
            return True
        elif frequency == 'weekly':
            return execution_date.weekday() == 0  # Monday
        elif frequency == 'monthly':
            return execution_date.day == 1
        elif frequency == 'quarterly':
            return execution_date.month in [1, 4, 7, 10] and execution_date.day == 1
        elif frequency == 'yearly':
            return execution_date.month == 1 and execution_date.day == 1
            
        return False
    
    def _check_threshold_based_rebalancing(
        self, rebalancing: Dict, current_positions: List[Position], symphony: Symphony
    ) -> bool:
        """Check if portfolio drift exceeds threshold"""
        threshold = Decimal(str(rebalancing.get('threshold', 0.075)))  # Default 7.5%
        
        # Calculate current allocations
        total_value = sum(p.quantity * p.current_price for p in current_positions)
        if total_value == 0:
            return True  # Rebalance if no positions
        
        # Get target allocations from symphony
        target_allocations = symphony.algorithm_config.get('target_allocations', {})
        
        # Check drift for each position
        for position in current_positions:
            current_weight = (position.quantity * position.current_price) / total_value
            target_weight = Decimal(str(target_allocations.get(position.symbol, 0)))
            
            drift = abs(current_weight - target_weight)
            if drift > threshold:
                return True
                
        return False
    
    def _get_asset_universe(self, universe_config: List[str]) -> List[str]:
        """Get list of assets to consider"""
        # Default universe if not specified
        if not universe_config:
            return ['SPY', 'AGG', 'GLD', 'VNQ', 'EFA', 'EEM', 'TLT', 'IEF', 'SHY', 'BIL']
        
        return universe_config
    
    def _fetch_asset_data(
        self, symbols: List[str], execution_date: date
    ) -> Dict[str, AssetData]:
        """Fetch market data for all assets"""
        asset_data_map = {}
        
        for symbol in symbols:
            try:
                # Get current price
                current_price = self.market_data_service.get_current_price(symbol)
                
                # Get historical prices (252 trading days for 1 year)
                historical_prices = self.market_data_service.get_historical_prices(
                    symbol, 
                    execution_date - timedelta(days=365),
                    execution_date,
                    252
                )
                
                # Get volume and market cap
                quote = self.market_data_service.get_quote(symbol)
                
                asset_data_map[symbol] = AssetData(
                    symbol=symbol,
                    current_price=Decimal(str(current_price)),
                    historical_prices=[Decimal(str(p)) for p in historical_prices],
                    volume=Decimal(str(quote.get('volume', 0))),
                    market_cap=Decimal(str(quote.get('marketCap', 0))) if quote.get('marketCap') else None
                )
                
            except Exception as e:
                logger.error(f"Failed to fetch data for {symbol}: {str(e)}")
                
        return asset_data_map
    
    def _execute_step(
        self,
        step: Dict[str, Any],
        asset_data_map: Dict[str, AssetData],
        execution_date: date,
        result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Execute a single algorithm step"""
        step_type = step.get('type')
        
        if step_type == 'conditional':
            return self._execute_conditional_step(step, asset_data_map, execution_date, result)
        elif step_type == 'screening':
            return self._execute_screening_step(step, asset_data_map, result)
        elif step_type == 'scoring':
            return self._execute_scoring_step(step, asset_data_map, result)
        elif step_type == 'ranking':
            return self._execute_ranking_step(step, asset_data_map, result)
        elif step_type == 'weighting':
            return self._execute_weighting_step(step, asset_data_map, result)
        elif step_type == 'filtering':
            return self._execute_filtering_step(step, asset_data_map, result)
        elif step_type == 'asset_group':
            return self._execute_asset_group_step(step, asset_data_map, result)
        else:
            logger.warning(f"Unknown step type: {step_type}")
            return asset_data_map
    
    def _execute_conditional_step(
        self,
        step: Dict,
        asset_data_map: Dict[str, AssetData],
        execution_date: date,
        result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Execute conditional if-then-else logic"""
        condition = step.get('condition', {})
        
        # Evaluate condition
        condition_met = self._evaluate_condition(condition, asset_data_map, execution_date)
        
        # Execute appropriate branch
        if condition_met:
            result.execution_logs.append(f"Condition met: {condition.get('description', 'unnamed')}")
            for sub_step in step.get('then_steps', []):
                asset_data_map = self._execute_step(sub_step, asset_data_map, execution_date, result)
        else:
            result.execution_logs.append(f"Condition not met: {condition.get('description', 'unnamed')}")
            for sub_step in step.get('else_steps', []):
                asset_data_map = self._execute_step(sub_step, asset_data_map, execution_date, result)
                
        return asset_data_map
    
    def _evaluate_condition(
        self,
        condition: Dict,
        asset_data_map: Dict[str, AssetData],
        execution_date: date
    ) -> bool:
        """Evaluate a condition expression"""
        condition_type = condition.get('type')
        
        if condition_type == 'comparison':
            return self._evaluate_comparison(condition, asset_data_map)
        elif condition_type == 'time':
            return self._evaluate_time_condition(condition, execution_date)
        elif condition_type == 'indicator':
            return self._evaluate_indicator_condition(condition, asset_data_map)
        elif condition_type == 'composite':
            return self._evaluate_composite_condition(condition, asset_data_map, execution_date)
            
        return False
    
    def _evaluate_comparison(
        self, condition: Dict, asset_data_map: Dict[str, AssetData]
    ) -> bool:
        """Evaluate a simple comparison condition"""
        left = self._get_value(condition.get('left'), asset_data_map)
        right = self._get_value(condition.get('right'), asset_data_map)
        operator = condition.get('operator', '>')
        
        if operator == '>':
            return left > right
        elif operator == '<':
            return left < right
        elif operator == '>=':
            return left >= right
        elif operator == '<=':
            return left <= right
        elif operator == '==':
            return left == right
        elif operator == '!=':
            return left != right
            
        return False
    
    def _evaluate_time_condition(
        self, condition: Dict, execution_date: date
    ) -> bool:
        """Evaluate time-based conditions"""
        time_type = condition.get('time_type')
        
        if time_type == 'day_of_week':
            return execution_date.weekday() == condition.get('value')
        elif time_type == 'day_of_month':
            return execution_date.day == condition.get('value')
        elif time_type == 'month':
            return execution_date.month == condition.get('value')
        elif time_type == 'quarter':
            quarter = (execution_date.month - 1) // 3 + 1
            return quarter == condition.get('value')
            
        return False
    
    def _evaluate_indicator_condition(
        self, condition: Dict, asset_data_map: Dict[str, AssetData]
    ) -> bool:
        """Evaluate technical indicator conditions"""
        symbol = condition.get('symbol')
        indicator = condition.get('indicator')
        threshold = Decimal(str(condition.get('threshold', 0)))
        operator = condition.get('operator', '>')
        
        if symbol not in asset_data_map:
            return False
            
        asset_data = asset_data_map[symbol]
        
        # Calculate indicator if not already calculated
        if indicator not in asset_data.indicators:
            self._calculate_indicators(asset_data, [indicator])
            
        value = asset_data.indicators.get(indicator, Decimal('0'))
        
        if operator == '>':
            return value > threshold
        elif operator == '<':
            return value < threshold
        elif operator == '>=':
            return value >= threshold
        elif operator == '<=':
            return value <= threshold
            
        return False
    
    def _evaluate_composite_condition(
        self, condition: Dict, asset_data_map: Dict[str, AssetData], execution_date: date
    ) -> bool:
        """Evaluate composite AND/OR conditions"""
        operator = condition.get('operator', 'AND')
        conditions = condition.get('conditions', [])
        
        if operator == 'AND':
            return all(
                self._evaluate_condition(c, asset_data_map, execution_date) 
                for c in conditions
            )
        elif operator == 'OR':
            return any(
                self._evaluate_condition(c, asset_data_map, execution_date) 
                for c in conditions
            )
            
        return False
    
    def _execute_screening_step(
        self, step: Dict, asset_data_map: Dict[str, AssetData], result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Screen assets based on criteria"""
        criteria = step.get('criteria', [])
        screened_assets = {}
        
        for symbol, asset_data in asset_data_map.items():
            passes_all = True
            
            for criterion in criteria:
                if not self._check_screening_criterion(criterion, asset_data):
                    passes_all = False
                    result.excluded_assets.append(symbol)
                    break
                    
            if passes_all:
                screened_assets[symbol] = asset_data
                
        result.execution_logs.append(
            f"Screening: {len(screened_assets)} of {len(asset_data_map)} assets passed"
        )
        
        return screened_assets
    
    def _check_screening_criterion(
        self, criterion: Dict, asset_data: AssetData
    ) -> bool:
        """Check if asset meets screening criterion"""
        criterion_type = criterion.get('type')
        
        if criterion_type == 'price':
            min_price = Decimal(str(criterion.get('min', 0)))
            max_price = Decimal(str(criterion.get('max', float('inf'))))
            return min_price <= asset_data.current_price <= max_price
            
        elif criterion_type == 'volume':
            min_volume = Decimal(str(criterion.get('min', 0)))
            return asset_data.volume >= min_volume
            
        elif criterion_type == 'market_cap':
            if asset_data.market_cap is None:
                return False
            min_cap = Decimal(str(criterion.get('min', 0)))
            max_cap = Decimal(str(criterion.get('max', float('inf'))))
            return min_cap <= asset_data.market_cap <= max_cap
            
        elif criterion_type == 'indicator':
            indicator = criterion.get('indicator')
            threshold = Decimal(str(criterion.get('threshold', 0)))
            operator = criterion.get('operator', '>')
            
            # Calculate indicator if needed
            if indicator not in asset_data.indicators:
                self._calculate_indicators(asset_data, [indicator])
                
            value = asset_data.indicators.get(indicator, Decimal('0'))
            
            if operator == '>':
                return value > threshold
            elif operator == '<':
                return value < threshold
            elif operator == '>=':
                return value >= threshold
            elif operator == '<=':
                return value <= threshold
                
        return True
    
    def _execute_scoring_step(
        self, step: Dict, asset_data_map: Dict[str, AssetData], result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Calculate scores for assets based on metrics"""
        metrics = step.get('metrics', [])
        
        for symbol, asset_data in asset_data_map.items():
            total_score = Decimal('0')
            
            for metric in metrics:
                score = self._calculate_metric_score(metric, asset_data)
                weight = Decimal(str(metric.get('weight', 1.0)))
                total_score += score * weight
                
            asset_data.score = total_score
            
        result.execution_logs.append(f"Scoring completed for {len(asset_data_map)} assets")
        return asset_data_map
    
    def _calculate_metric_score(
        self, metric: Dict, asset_data: AssetData
    ) -> Decimal:
        """Calculate score for a single metric"""
        metric_type = metric.get('type')
        
        if metric_type == 'momentum':
            # Calculate momentum score based on returns
            lookback = metric.get('lookback', 20)
            if len(asset_data.historical_prices) >= lookback:
                returns = (
                    asset_data.current_price / asset_data.historical_prices[-lookback]
                ) - Decimal('1')
                return returns * Decimal('100')  # Convert to percentage
                
        elif metric_type == 'volatility':
            # Calculate volatility score (inverse - lower is better)
            indicator = 'volatility'
            if indicator not in asset_data.indicators:
                self._calculate_indicators(asset_data, [indicator])
            volatility = asset_data.indicators.get(indicator, Decimal('1'))
            return Decimal('1') / volatility if volatility > 0 else Decimal('0')
            
        elif metric_type == 'rsi':
            # RSI score (favor neutral RSI)
            indicator = 'rsi'
            if indicator not in asset_data.indicators:
                self._calculate_indicators(asset_data, [indicator])
            rsi = asset_data.indicators.get(indicator, Decimal('50'))
            return Decimal('100') - abs(rsi - Decimal('50'))
            
        elif metric_type == 'trend':
            # Trend following score
            if 'sma_50' not in asset_data.indicators:
                self._calculate_indicators(asset_data, ['sma_50', 'sma_200'])
            sma_50 = asset_data.indicators.get('sma_50', asset_data.current_price)
            sma_200 = asset_data.indicators.get('sma_200', asset_data.current_price)
            
            if sma_200 > 0:
                return (sma_50 / sma_200 - Decimal('1')) * Decimal('100')
                
        return Decimal('0')
    
    def _execute_ranking_step(
        self, step: Dict, asset_data_map: Dict[str, AssetData], result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Rank assets and select top N"""
        metric = step.get('metric', 'score')
        direction = step.get('direction', 'descending')
        limit = step.get('limit', len(asset_data_map))
        
        # Sort assets by metric
        sorted_assets = sorted(
            asset_data_map.items(),
            key=lambda x: getattr(x[1], metric, 0),
            reverse=(direction == 'descending')
        )
        
        # Keep only top N
        ranked_assets = dict(sorted_assets[:limit])
        
        result.execution_logs.append(
            f"Ranking: Selected top {len(ranked_assets)} of {len(asset_data_map)} assets"
        )
        
        return ranked_assets
    
    def _execute_weighting_step(
        self, step: Dict, asset_data_map: Dict[str, AssetData], result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Calculate portfolio weights for assets"""
        method = step.get('method', 'equal')
        
        if method == 'equal':
            weight = Decimal('1') / Decimal(str(len(asset_data_map)))
            for asset_data in asset_data_map.values():
                asset_data.weight = weight
                
        elif method == 'market_cap':
            total_cap = sum(
                a.market_cap for a in asset_data_map.values() 
                if a.market_cap is not None
            )
            if total_cap > 0:
                for asset_data in asset_data_map.values():
                    if asset_data.market_cap is not None:
                        asset_data.weight = asset_data.market_cap / total_cap
                    else:
                        asset_data.weight = Decimal('0')
                        
        elif method == 'score':
            total_score = sum(a.score for a in asset_data_map.values())
            if total_score > 0:
                for asset_data in asset_data_map.values():
                    asset_data.weight = asset_data.score / total_score
                    
        elif method == 'inverse_volatility':
            # Calculate inverse volatility weights
            for asset_data in asset_data_map.values():
                if 'volatility' not in asset_data.indicators:
                    self._calculate_indicators(asset_data, ['volatility'])
                    
            total_inv_vol = sum(
                Decimal('1') / a.indicators.get('volatility', Decimal('1'))
                for a in asset_data_map.values()
            )
            
            if total_inv_vol > 0:
                for asset_data in asset_data_map.values():
                    vol = asset_data.indicators.get('volatility', Decimal('1'))
                    asset_data.weight = (Decimal('1') / vol) / total_inv_vol
                    
        elif method == 'custom':
            # Custom weights specified in step
            weights = step.get('weights', {})
            for symbol, asset_data in asset_data_map.items():
                asset_data.weight = Decimal(str(weights.get(symbol, 0)))
                
        # Apply constraints
        self._apply_weight_constraints(asset_data_map, step.get('constraints', {}))
        
        result.execution_logs.append(
            f"Weighting: Applied {method} weighting to {len(asset_data_map)} assets"
        )
        
        return asset_data_map
    
    def _apply_weight_constraints(
        self, asset_data_map: Dict[str, AssetData], constraints: Dict
    ):
        """Apply min/max weight constraints"""
        min_weight = Decimal(str(constraints.get('min_weight', 0)))
        max_weight = Decimal(str(constraints.get('max_weight', 1)))
        
        # First pass: apply constraints
        for asset_data in asset_data_map.values():
            asset_data.weight = max(min_weight, min(max_weight, asset_data.weight))
            
        # Normalize weights to sum to 1
        total_weight = sum(a.weight for a in asset_data_map.values())
        if total_weight > 0:
            for asset_data in asset_data_map.values():
                asset_data.weight = asset_data.weight / total_weight
    
    def _execute_filtering_step(
        self, step: Dict, asset_data_map: Dict[str, AssetData], result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Filter assets based on conditions"""
        conditions = step.get('conditions', [])
        filtered_assets = {}
        
        for symbol, asset_data in asset_data_map.items():
            if all(self._check_filter_condition(c, asset_data) for c in conditions):
                filtered_assets[symbol] = asset_data
            else:
                result.excluded_assets.append(symbol)
                
        result.execution_logs.append(
            f"Filtering: {len(filtered_assets)} of {len(asset_data_map)} assets passed"
        )
        
        return filtered_assets
    
    def _check_filter_condition(
        self, condition: Dict, asset_data: AssetData
    ) -> bool:
        """Check if asset meets filter condition"""
        # Similar to screening but can be more complex
        return self._check_screening_criterion(condition, asset_data)
    
    def _execute_asset_group_step(
        self, step: Dict, asset_data_map: Dict[str, AssetData], result: ExecutionResult
    ) -> Dict[str, AssetData]:
        """Group assets and apply group-level logic"""
        groups = step.get('groups', [])
        group_method = step.get('method', 'select_best')
        
        grouped_assets = {}
        
        for group in groups:
            group_name = group.get('name')
            symbols = group.get('symbols', [])
            
            # Get assets in this group
            group_assets = {
                s: asset_data_map[s] 
                for s in symbols 
                if s in asset_data_map
            }
            
            if not group_assets:
                continue
                
            if group_method == 'select_best':
                # Select best asset from group based on score
                best_symbol = max(group_assets.keys(), key=lambda s: group_assets[s].score)
                grouped_assets[best_symbol] = group_assets[best_symbol]
                
            elif group_method == 'weighted_average':
                # Keep all assets but adjust weights within group
                group_weight = Decimal(str(group.get('weight', 1.0 / len(groups))))
                for symbol, asset_data in group_assets.items():
                    asset_data.weight = asset_data.weight * group_weight
                    grouped_assets[symbol] = asset_data
                    
        result.execution_logs.append(
            f"Asset grouping: Processed {len(groups)} groups"
        )
        
        return grouped_assets
    
    def _calculate_indicators(
        self, asset_data: AssetData, indicators: List[str]
    ):
        """Calculate technical indicators for an asset"""
        prices = [float(p) for p in asset_data.historical_prices]
        
        for indicator in indicators:
            if indicator == 'rsi':
                value = self.technical_indicators.calculate_rsi(prices)
                asset_data.indicators['rsi'] = Decimal(str(value))
                
            elif indicator == 'volatility':
                value = self.technical_indicators.calculate_volatility(prices)
                asset_data.indicators['volatility'] = Decimal(str(value))
                
            elif indicator.startswith('sma_'):
                period = int(indicator.split('_')[1])
                value = self.technical_indicators.calculate_sma(prices, period)
                asset_data.indicators[indicator] = Decimal(str(value))
                
            elif indicator.startswith('ema_'):
                period = int(indicator.split('_')[1])
                value = self.technical_indicators.calculate_ema(prices, period)
                asset_data.indicators[indicator] = Decimal(str(value))
                
            elif indicator == 'macd':
                macd, signal, hist = self.technical_indicators.calculate_macd(prices)
                asset_data.indicators['macd'] = Decimal(str(macd))
                asset_data.indicators['macd_signal'] = Decimal(str(signal))
                asset_data.indicators['macd_histogram'] = Decimal(str(hist))
                
            elif indicator == 'bollinger_bands':
                upper, middle, lower = self.technical_indicators.calculate_bollinger_bands(prices)
                asset_data.indicators['bb_upper'] = Decimal(str(upper))
                asset_data.indicators['bb_middle'] = Decimal(str(middle))
                asset_data.indicators['bb_lower'] = Decimal(str(lower))
    
    def _get_value(
        self, value_spec: Union[Dict, str, float], asset_data_map: Dict[str, AssetData]
    ) -> Decimal:
        """Get a value from specification (literal, indicator, calculation)"""
        if isinstance(value_spec, (int, float)):
            return Decimal(str(value_spec))
            
        if isinstance(value_spec, str):
            # Try to parse as number
            try:
                return Decimal(value_spec)
            except:
                # Handle special values
                if value_spec == 'infinity':
                    return Decimal('999999999')
                return Decimal('0')
                
        if isinstance(value_spec, dict):
            value_type = value_spec.get('type')
            
            if value_type == 'literal':
                return Decimal(str(value_spec.get('value', 0)))
                
            elif value_type == 'indicator':
                symbol = value_spec.get('symbol')
                indicator = value_spec.get('indicator')
                
                if symbol in asset_data_map:
                    asset_data = asset_data_map[symbol]
                    if indicator not in asset_data.indicators:
                        self._calculate_indicators(asset_data, [indicator])
                    return asset_data.indicators.get(indicator, Decimal('0'))
                    
            elif value_type == 'aggregate':
                # Calculate aggregate values across assets
                agg_func = value_spec.get('function', 'avg')
                metric = value_spec.get('metric', 'score')
                
                values = []
                for asset_data in asset_data_map.values():
                    if hasattr(asset_data, metric):
                        values.append(getattr(asset_data, metric))
                    elif metric in asset_data.indicators:
                        values.append(asset_data.indicators[metric])
                        
                if not values:
                    return Decimal('0')
                    
                if agg_func == 'avg':
                    return sum(values) / len(values)
                elif agg_func == 'sum':
                    return sum(values)
                elif agg_func == 'max':
                    return max(values)
                elif agg_func == 'min':
                    return min(values)
                    
        return Decimal('0')
    
    def _generate_allocations(
        self, asset_data_map: Dict[str, AssetData], allocation_config: Dict
    ) -> Dict[str, Decimal]:
        """Generate final portfolio allocations from weighted assets"""
        allocations = {}
        
        # Apply any final allocation rules
        min_allocation = Decimal(str(allocation_config.get('min_allocation', 0)))
        max_allocation = Decimal(str(allocation_config.get('max_allocation', 1)))
        cash_buffer = Decimal(str(allocation_config.get('cash_buffer', 0)))
        
        # Calculate total investable weight (1 - cash buffer)
        investable_weight = Decimal('1') - cash_buffer
        
        # Generate allocations from weights
        for symbol, asset_data in asset_data_map.items():
            allocation = asset_data.weight * investable_weight
            
            # Apply min/max constraints
            if allocation < min_allocation:
                allocation = Decimal('0')  # Drop if below minimum
            elif allocation > max_allocation:
                allocation = max_allocation
                
            if allocation > 0:
                allocations[symbol] = allocation
                
        # Add cash allocation if specified
        if cash_buffer > 0:
            allocations['CASH'] = cash_buffer
            
        # Normalize allocations to sum to 1
        total_allocation = sum(allocations.values())
        if total_allocation > 0 and abs(total_allocation - Decimal('1')) > Decimal('0.001'):
            for symbol in allocations:
                allocations[symbol] = allocations[symbol] / total_allocation
                
        # Round allocations to reasonable precision
        for symbol in allocations:
            allocations[symbol] = allocations[symbol].quantize(Decimal('0.0001'))
            
        return allocations
