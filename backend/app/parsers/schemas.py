"""Comprehensive Pydantic schemas for all symphony step types and functions."""

from typing import Dict, List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from enum import Enum


class RebalanceFrequency(str, Enum):
    """Rebalancing frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class StepType(str, Enum):
    """All possible step types in a symphony."""
    ROOT = "root"
    ASSET = "asset"
    GROUP = "group"
    IF = "if"
    IF_CHILD = "if-child"
    FILTER = "filter"
    WT_CASH_EQUAL = "wt-cash-equal"
    WT_CASH_SPECIFIED = "wt-cash-specified"
    WT_INVERSE_VOL = "wt-inverse-vol"
    WT_MARKET_CAP = "wt-market-cap"
    WT_RISK_PARITY = "wt-risk-parity"


class MetricFunction(str, Enum):
    """Available metric functions for conditions and sorting."""
    CURRENT_PRICE = "current-price"
    CUMULATIVE_RETURN = "cumulative-return"
    EXPONENTIAL_MOVING_AVERAGE_PRICE = "exponential-moving-average-price"
    MAX_DRAWDOWN = "max-drawdown"
    MOVING_AVERAGE_PRICE = "moving-average-price"
    MOVING_AVERAGE_RETURN = "moving-average-return"
    RELATIVE_STRENGTH_INDEX = "relative-strength-index"
    STANDARD_DEVIATION_PRICE = "standard-deviation-price"
    STANDARD_DEVIATION_RETURN = "standard-deviation-return"
    SHARPE_RATIO = "sharpe-ratio"
    VOLATILITY = "volatility"
    BETA = "beta"
    ALPHA = "alpha"
    CORRELATION = "correlation"


class Comparator(str, Enum):
    """Comparison operators for conditional logic."""
    GT = "gt"  # Greater than
    LT = "lt"  # Less than
    GTE = "gte"  # Greater than or equal
    LTE = "lte"  # Less than or equal
    EQ = "eq"  # Equal
    NEQ = "neq"  # Not equal


class SelectionFunction(str, Enum):
    """Selection functions for filters."""
    TOP = "top"
    BOTTOM = "bottom"
    ALL = "all"
    RANDOM = "random"


class AssetClass(str, Enum):
    """Asset class categories."""
    EQUITIES = "EQUITIES"
    BONDS = "BONDS"
    COMMODITIES = "COMMODITIES"
    CURRENCIES = "CURRENCIES"
    CRYPTO = "CRYPTO"
    REAL_ESTATE = "REAL_ESTATE"


class Weight(BaseModel):
    """Weight representation as numerator/denominator."""
    num: Union[int, str] = Field(..., description="Numerator")
    den: int = Field(..., description="Denominator")
    
    @validator('num')
    def validate_numerator(cls, v):
        """Ensure numerator is valid."""
        if isinstance(v, str):
            try:
                int(v)
            except ValueError:
                raise ValueError("Numerator must be a valid integer string")
        return v
    
    def to_decimal(self) -> Decimal:
        """Convert to decimal representation."""
        num_val = int(self.num) if isinstance(self.num, str) else self.num
        return Decimal(num_val) / Decimal(self.den)


class BaseStep(BaseModel):
    """Base class for all symphony steps."""
    id: str = Field(..., description="Unique identifier for the step")
    step: StepType = Field(..., description="Type of step")
    name: Optional[str] = Field(None, description="Optional name for the step")
    children: Optional[List['SymphonyStep']] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class AssetStep(BaseStep):
    """Individual asset/security step."""
    step: Literal[StepType.ASSET] = StepType.ASSET
    ticker: str = Field(..., description="Asset ticker symbol")
    exchange: str = Field(..., description="Exchange code")
    name: str = Field(..., description="Asset full name")
    weight: Optional[Weight] = Field(None, description="Optional weight for weighted strategies")


class GroupStep(BaseStep):
    """Group container step."""
    step: Literal[StepType.GROUP] = StepType.GROUP


class FilterStep(BaseStep):
    """Filter step for asset selection."""
    step: Literal[StepType.FILTER] = StepType.FILTER
    sort_by_fn: MetricFunction = Field(..., description="Function to sort by")
    sort_by_fn_params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for sort function")
    select_fn: SelectionFunction = Field(..., description="Selection function")
    select_n: Union[int, str] = Field(..., description="Number to select")
    
    @validator('select_n')
    def validate_select_n(cls, v):
        """Ensure select_n is valid."""
        if isinstance(v, str):
            try:
                int(v)
            except ValueError:
                raise ValueError("select_n must be a valid integer or 'all'")
        return v


class IfChildStep(BaseStep):
    """Child of an IF statement (then or else branch)."""
    step: Literal[StepType.IF_CHILD] = StepType.IF_CHILD
    is_else_condition: bool = Field(..., alias="is-else-condition?")
    
    # Condition parameters (only for non-else branches)
    lhs_fn: Optional[MetricFunction] = Field(None, alias="lhs-fn", description="Left-hand side function")
    lhs_fn_params: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="lhs-fn-params")
    lhs_val: Optional[str] = Field(None, alias="lhs-val", description="Left-hand side value/ticker")
    
    comparator: Optional[Comparator] = Field(None, description="Comparison operator")
    
    rhs_fn: Optional[MetricFunction] = Field(None, alias="rhs-fn", description="Right-hand side function")
    rhs_fn_params: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="rhs-fn-params")
    rhs_val: Optional[str] = Field(None, alias="rhs-val", description="Right-hand side value/ticker")
    rhs_fixed_value: Optional[bool] = Field(None, alias="rhs-fixed-value?", description="Is RHS a fixed value")


class IfStep(BaseStep):
    """Conditional logic step."""
    step: Literal[StepType.IF] = StepType.IF
    
    @validator('children')
    def validate_if_children(cls, v):
        """Ensure IF step has exactly 2 children (then and else)."""
        if len(v) != 2:
            raise ValueError("IF step must have exactly 2 children (then and else branches)")
        
        # Verify one is else and one is not
        else_count = sum(1 for child in v if getattr(child, 'is_else_condition', False))
        if else_count != 1:
            raise ValueError("IF step must have exactly one else branch")
        
        return v


class WeightingStep(BaseStep):
    """Base class for weighting strategies."""
    window_days: Optional[Union[int, str]] = Field(None, alias="window-days", description="Lookback window in days")


class WtCashEqualStep(WeightingStep):
    """Equal weight cash distribution step."""
    step: Literal[StepType.WT_CASH_EQUAL] = StepType.WT_CASH_EQUAL


class WtCashSpecifiedStep(WeightingStep):
    """Specified weight cash distribution step."""
    step: Literal[StepType.WT_CASH_SPECIFIED] = StepType.WT_CASH_SPECIFIED
    
    @validator('children')
    def validate_weights(cls, v):
        """Ensure all children have weights and they sum to 100%."""
        if not v:
            return v
            
        total_weight = Decimal('0')
        for child in v:
            if not hasattr(child, 'weight') or child.weight is None:
                raise ValueError("All children of wt-cash-specified must have weights")
            total_weight += child.weight.to_decimal()
        
        if abs(total_weight - Decimal('1')) > Decimal('0.001'):
            raise ValueError(f"Weights must sum to 100%, got {float(total_weight * 100)}%")
        
        return v


class WtInverseVolStep(WeightingStep):
    """Inverse volatility weighting step."""
    step: Literal[StepType.WT_INVERSE_VOL] = StepType.WT_INVERSE_VOL


class WtMarketCapStep(WeightingStep):
    """Market cap weighting step."""
    step: Literal[StepType.WT_MARKET_CAP] = StepType.WT_MARKET_CAP


class WtRiskParityStep(WeightingStep):
    """Risk parity weighting step."""
    step: Literal[StepType.WT_RISK_PARITY] = StepType.WT_RISK_PARITY


class RootStep(BaseStep):
    """Root symphony step with metadata."""
    step: Literal[StepType.ROOT] = StepType.ROOT
    description: Optional[str] = Field(None, description="Symphony description")
    rebalance: RebalanceFrequency = Field(..., description="Rebalancing frequency")
    asset_classes: Optional[List[AssetClass]] = Field(default_factory=list)
    asset_class: Optional[AssetClass] = None
    
    @validator('children')
    def validate_has_children(cls, v):
        """Ensure root has at least one child."""
        if not v:
            raise ValueError("Symphony must have at least one child step")
        return v


# Union type for all possible steps
SymphonyStep = Union[
    AssetStep,
    GroupStep,
    FilterStep,
    IfStep,
    IfChildStep,
    WtCashEqualStep,
    WtCashSpecifiedStep,
    WtInverseVolStep,
    WtMarketCapStep,
    WtRiskParityStep,
    RootStep
]

# Update forward references
for model in [
    BaseStep, AssetStep, GroupStep, FilterStep, IfStep, IfChildStep,
    WtCashEqualStep, WtCashSpecifiedStep, WtInverseVolStep,
    WtMarketCapStep, WtRiskParityStep, RootStep
]:
    model.update_forward_refs()


class SymphonySchema(BaseModel):
    """Complete symphony schema."""
    # Root level fields are spread into the schema
    id: str
    step: Literal["root"] = "root"
    name: str
    description: Optional[str] = None
    rebalance: RebalanceFrequency
    children: List[SymphonyStep]
    asset_classes: Optional[List[AssetClass]] = Field(default_factory=list)
    asset_class: Optional[AssetClass] = None
    
    @validator('children')
    def validate_has_children(cls, v):
        """Ensure symphony has at least one child."""
        if not v:
            raise ValueError("Symphony must have at least one child step")
        return v
    
    def to_root_step(self) -> RootStep:
        """Convert to RootStep model."""
        return RootStep(
            id=self.id,
            step=StepType.ROOT,
            name=self.name,
            description=self.description,
            rebalance=self.rebalance,
            children=self.children,
            asset_classes=self.asset_classes,
            asset_class=self.asset_class
        )
