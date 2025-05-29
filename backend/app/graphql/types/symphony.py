"""Symphony GraphQL types with algorithm complexity support."""

from typing import List, Optional, Dict, Any
from datetime import datetime
import strawberry
from strawberry.types import Info
import json

from app.graphql.context import GraphQLContext
from app.graphql.types.user import User
from app.models.symphony import Symphony as SymphonyModel
from app.parsers.schemas import RebalanceFrequency, AssetClass


@strawberry.type
class SymphonyComplexity:
    """Symphony complexity metrics."""
    
    total_steps: int
    max_depth: int
    unique_assets: int
    if_conditions: int
    filters: int
    groups: int
    weighting_strategies: int


@strawberry.type
class SymphonyAsset:
    """Asset referenced in a symphony."""
    
    ticker: str
    exchange: str
    name: str


@strawberry.type
class Symphony:
    """GraphQL Symphony type."""
    
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    rebalance_frequency: str
    algorithm: Dict[str, Any]  # Full algorithm JSON
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_executed_at: Optional[datetime] = None
    execution_count: int = 0
    
    @strawberry.field
    def user(self, info: Info[GraphQLContext]) -> Optional[User]:
        """Get the symphony owner."""
        from app.models.user import User as UserModel
        
        user = info.context.db.query(UserModel).filter(
            UserModel.id == self.user_id
        ).first()
        
        if user:
            return User.from_model(user)
        return None
    
    @strawberry.field
    def complexity(self) -> SymphonyComplexity:
        """Get symphony complexity metrics."""
        from app.parsers.symphony_parser import symphony_parser
        
        try:
            symphony_schema = symphony_parser.parse_dict(self.algorithm)
            metrics = symphony_parser.get_complexity_metrics(symphony_schema)
            
            return SymphonyComplexity(
                total_steps=metrics["total_steps"],
                max_depth=metrics["max_depth"],
                unique_assets=metrics["unique_assets"],
                if_conditions=metrics["if_conditions"],
                filters=metrics["filters"],
                groups=metrics["groups"],
                weighting_strategies=metrics["weighting_strategies"]
            )
        except:
            # Return zeros if parsing fails
            return SymphonyComplexity(
                total_steps=0,
                max_depth=0,
                unique_assets=0,
                if_conditions=0,
                filters=0,
                groups=0,
                weighting_strategies=0
            )
    
    @strawberry.field
    def assets(self) -> List[SymphonyAsset]:
        """Get list of assets used in the symphony."""
        from app.parsers.symphony_parser import symphony_parser
        from app.parsers.schemas import AssetStep
        
        assets_list = []
        
        try:
            symphony_schema = symphony_parser.parse_dict(self.algorithm)
            
            # Extract all asset steps
            def extract_asset_steps(step):
                if hasattr(step, 'step') and step.step == 'asset':
                    assets_list.append(SymphonyAsset(
                        ticker=step.ticker,
                        exchange=step.exchange,
                        name=step.name
                    ))
                
                if hasattr(step, 'children'):
                    for child in step.children:
                        extract_asset_steps(child)
            
            root = symphony_schema.to_root_step()
            for child in root.children:
                extract_asset_steps(child)
            
            # Remove duplicates
            seen = set()
            unique_assets = []
            for asset in assets_list:
                if asset.ticker not in seen:
                    seen.add(asset.ticker)
                    unique_assets.append(asset)
            
            return unique_assets
            
        except:
            return []
    
    @strawberry.field
    def algorithm_json(self) -> str:
        """Get algorithm as JSON string."""
        return json.dumps(self.algorithm, indent=2)
    
    @strawberry.field
    def validation_warnings(self) -> List[str]:
        """Get validation warnings for the symphony."""
        from app.parsers.symphony_parser import symphony_parser
        from app.parsers.validator import symphony_validator
        
        try:
            symphony_schema = symphony_parser.parse_dict(self.algorithm)
            warnings = symphony_validator.validate(symphony_schema)
            return warnings
        except Exception as e:
            return [f"Validation error: {str(e)}"]
    
    @classmethod
    def from_model(cls, symphony: SymphonyModel) -> 'Symphony':
        """Convert SQLAlchemy model to GraphQL type."""
        return cls(
            id=symphony.id,
            user_id=symphony.user_id,
            name=symphony.name,
            description=symphony.description,
            rebalance_frequency=symphony.rebalance_frequency,
            algorithm=symphony.algorithm,
            is_active=symphony.is_active,
            created_at=symphony.created_at,
            updated_at=symphony.updated_at,
            last_executed_at=symphony.last_executed_at,
            execution_count=symphony.execution_count
        )


@strawberry.type
class SymphonyConnection:
    """Paginated symphonies connection."""
    
    nodes: List[Symphony]
    total_count: int
    has_next_page: bool
    has_previous_page: bool


@strawberry.type
class SymphonyValidationResult:
    """Result of symphony validation."""
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    complexity: SymphonyComplexity
    assets: List[SymphonyAsset]


@strawberry.type
class SymphonyUploadResult:
    """Result of symphony upload."""
    
    success: bool
    symphony: Optional[Symphony] = None
    error: Optional[str] = None
    validation: Optional[SymphonyValidationResult] = None


@strawberry.type
class SymphonyExecutionStatus:
    """Status of a symphony execution."""
    
    symphony_id: int
    is_executing: bool
    last_executed_at: Optional[datetime] = None
    next_execution_at: Optional[datetime] = None
    last_error: Optional[str] = None
    execution_count: int = 0
