# Oragami Composer Technical Specification (New Project)

## 1. System Overview
- **Core Purpose & Goals**: Multi-tenant paper trading platform that executes Composer.trade algorithmic strategies via Alpaca API with real-time performance tracking and backtesting capabilities
- **Primary Use Cases**: 
  - Upload and manage Composer.trade symphonies
  - Execute automated paper trades based on symphony algorithms
  - Track real-time performance with quantstats metrics
  - Compare live vs. backtested performance
  - Manage multiple symphonies per user account
- **High-Level Architecture**: 
  - Frontend (React SPA with Apollo Client) ↔ GraphQL API (Strawberry) ↔ FastAPI Services ↔ PostgreSQL/TimescaleDB
  - Background Job Queue (Celery/Redis) for algorithmic execution
  - Alpaca API integration for paper trading
  - GraphQL Subscriptions for sophisticated real-time updates
  - Quantitative computing layer (pandas, numpy, TA-Lib) for algorithm execution and backtesting

## 2. Technology & Tools
- **Languages & Frameworks**: Python 3.11+, FastAPI, GraphQL (Strawberry), React 18+ with TypeScript
- **Libraries & Dependencies**: 
  - Backend: SQLAlchemy ORM, Celery, pandas, numpy, TA-Lib, alpaca-py, strawberry-graphql, uvicorn
  - Frontend: Apollo Client, React Router, Recharts, Material-UI, @apollo/client
- **Quantitative Computing**: pandas for data manipulation, numpy for numerical computing, TA-Lib for technical indicators, scipy for statistical analysis
- **Database & ORM**: PostgreSQL 14+ with TimescaleDB extension, SQLAlchemy ORM with asyncio support
- **Background Processing**: Celery with Redis broker for distributed task execution
- **Real-time**: GraphQL subscriptions with Strawberry for sophisticated real-time updates
- **DevOps & Hosting**: Docker, Kubernetes, GitHub Actions, AWS/GCP
- **CI/CD Pipeline**: GitHub Actions with automated testing, Docker builds, and K8s deployment

## 3. Project Structure
- **Folder Organization**: 
  ```
  /
  ├── backend/
  │   ├── app/                 # FastAPI application
  │   ├── tests/               # Python tests
  │   └── alembic/             # Database migrations
  ├── frontend/
  │   ├── src/                 # React application
  │   └── tests/               # Frontend tests
  ├── docker/                  # Docker configurations
  └── k8s/                     # Kubernetes manifests
  ```
- **Naming Conventions**: 
  - Python files: snake_case (user_service.py)
  - React components: PascalCase (SymphonyDashboard.tsx)
  - GraphQL types: PascalCase (Symphony, User)
  - API routes: kebab-case (/api/symphonies)
- **Key Modules**: 
  - Auth module (JWT-based authentication)
  - Symphony module (parsing, validation, execution)
  - Trading module (Alpaca integration)
  - Analytics module (quantstats calculations)
  - Backtesting module (historical data processing)

## 4. Feature Specification

### 4.1 User Authentication & Alpaca OAuth Integration
- **User Story & Requirements**: Users register with our app and seamlessly connect their Alpaca accounts via OAuth 2.0 without sharing API credentials
- **Implementation Details**: 
  - JWT-based authentication for our app sessions
  - OAuth 2.0 flow with Alpaca for secure account connection
  - Secure storage of OAuth access tokens per user
  - Multi-tenant data isolation using user_id foreign keys
- **Edge Cases & Error Handling**: OAuth authorization denied, token expiration, Alpaca account suspension, network failures during OAuth flow
- **UI/UX Considerations**: Clean login/register forms, "Connect Alpaca Account" button, OAuth authorization status indicators

### 4.2 Symphony Upload & Management
- **User Story & Requirements**: Users upload Composer.trade JSON files, view symphony details, and manage active/inactive status
- **Implementation Details**: 
  - File upload with JSON validation using Zod schemas
  - Symphony parsing to extract rebalancing schedules and allocations
  - Database storage with status tracking (active/inactive/stopped)
- **Edge Cases & Error Handling**: Invalid JSON format, missing required fields, large file uploads
- **UI/UX Considerations**: Drag-and-drop upload, symphony library grid view, status indicators

### 4.3 Paper Trading Engine
- **User Story & Requirements**: Automated execution of trades based on symphony algorithms with daily rebalancing at 15:50-16:00 EST
- **Implementation Details**: 
  - Celery Beat scheduler for precise 15:50 EST daily execution
  - Alpaca paper trading API integration (no live trading)
  - Daily rebalancing within 10-minute window before market close
  - Support for up to 1,600 daily executions (40 users × 40 symphonies)
- **Edge Cases & Error Handling**: API rate limits, failed orders, market closures, insufficient buying power, algorithm failures trigger liquidation to cash
- **UI/UX Considerations**: Real-time position updates, trade history, execution status indicators, liquidation notifications

### 4.4 Performance Analytics
- **User Story & Requirements**: Real-time tracking of portfolio performance with standard quantstats metrics
- **Implementation Details**: 
  - Time-series data storage using TimescaleDB
  - Automated calculation of Sharpe ratio, max drawdown, volatility, win rate, Sortino ratio, Calmar ratio
  - Real-time metric updates via WebSocket connections
- **Edge Cases & Error Handling**: Missing price data, calculation errors, data inconsistencies
- **UI/UX Considerations**: Interactive charts, metric dashboards, performance comparisons

### 4.5 Backtesting Engine
- **User Story & Requirements**: Execute complex algorithmic symphony strategies against historical data from 2007-present with full conditional logic simulation and compare with live performance
- **Implementation Details**: 
  - Historical market data integration using Alpha Vantage Premium + EOD Historical Data ($100/month budget)
  - Data coverage from 2007 (BIL inception) to present
  - Sophisticated backtest execution engine that simulates the complete algorithm decision tree
  - Technical indicator calculation on historical data (RSI, moving averages, volatility measures)
  - Conditional logic evaluation with historical market conditions
  - Asset filtering and selection replay based on historical metrics
  - Daily rebalancing simulation respecting 15:50-16:00 EST timing
  - Performance comparison tools with statistical analysis and decision path visualization
- **Edge Cases & Error Handling**: Missing historical data, data quality issues, algorithm execution timeouts, circular logic dependencies, invalid technical indicator calculations
- **UI/UX Considerations**: Backtest configuration forms with algorithm parameter display, progress indicators for complex simulations, results visualization with decision tree replay, side-by-side live vs. backtest comparison charts

### 4.6 User Experience Flows
- **User Story & Requirements**: Seamless user journeys from onboarding to active trading with clear navigation and feedback
- **Implementation Details**: 
  - **Onboarding Flow**: Account creation → Email verification → Alpaca OAuth connection → Dashboard tour
  - **Symphony Management Flow**: Upload JSON → Validation feedback → Configuration → Activate/Deactivate
  - **Performance Monitoring Flow**: Real-time dashboard → Drill-down analytics → Historical comparisons → Export data
  - **Error Recovery Flow**: Clear error messages → Suggested actions → Alternative paths → Support contact
- **Edge Cases & Error Handling**: Network disconnections, OAuth token expiration, file upload failures, data loading errors
- **UI/UX Considerations**: 
  - Progressive disclosure of complex information
  - Contextual help and tooltips for financial metrics
  - Keyboard shortcuts for power users
  - Mobile-optimized touch interactions
  - Loading states that maintain context
- **User Story & Requirements**: Execute symphony strategies against historical data and compare with live performance
- **Implementation Details**: 
  - Historical market data integration (Alpha Vantage or similar)
  - Backtest execution engine that simulates symphony logic
  - Performance comparison tools with statistical analysis
- **Edge Cases & Error Handling**: Missing historical data, data quality issues, computation timeouts
- **UI/UX Considerations**: Backtest configuration forms, progress indicators, results visualization

## 5. Database Schema

### 5.1 Tables / Collections
- **users**: id (UUID), email, password_hash, alpaca_oauth_token, alpaca_token_scope, oauth_connected_at, created_at, updated_at
- **symphonies**: id (UUID), user_id (FK), name, description, json_data (JSONB), status (enum), uploaded_at, last_executed_at
- **positions**: id (UUID), symphony_id (FK), symbol, quantity, market_value, timestamp (TimescaleDB hypertable)
- **trades**: id (UUID), symphony_id (FK), symbol, side, quantity, price, executed_at (TimescaleDB hypertable)
- **performance_metrics**: id (UUID), symphony_id (FK), metric_type, value, calculated_at (TimescaleDB hypertable)
- **backtests**: id (UUID), symphony_id (FK), start_date, end_date, results (JSONB), algorithm_decisions (JSONB), created_at

### 5.2 Relationships
- users → symphonies (one-to-many)
- symphonies → positions (one-to-many)
- symphonies → trades (one-to-many)
- symphonies → performance_metrics (one-to-many)
- symphonies → backtests (one-to-many)

### 5.3 Indexes
- user_id indexes on all user-scoped tables
- TimescaleDB time-based indexes on timestamp columns
- Composite indexes on (symphony_id, timestamp) for performance queries

## 6. GraphQL API Design & Schema

### 6.1 Why GraphQL with Strawberry
- **Type Safety**: Automatic TypeScript generation from Python schema
- **Flexible Queries**: Clients request exactly what they need
- **Real-time Subscriptions**: Built-in support for live updates
- **Single Endpoint**: All operations through one GraphQL endpoint
- **Rich Ecosystem**: Apollo Client, GraphQL Code Generator, excellent tooling
- **Python Native**: Strawberry provides pythonic GraphQL development

### 6.2 Core GraphQL Schema
```python
import strawberry
from strawberry.types import Info
from typing import List, Optional
import datetime

# Enums
@strawberry.enum
class SymphonyStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    STOPPED = "stopped"

@strawberry.enum
class RebalanceFrequency:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

# Complex Symphony Step Types
@strawberry.type
class SymphonyStep:
    id: str
    step: str  # 'root', 'asset', 'group', 'if', 'if-child', 'filter', etc.
    name: Optional[str] = None
    description: Optional[str] = None
    rebalance: Optional[RebalanceFrequency] = None
    children: Optional[List['SymphonyStep']] = None
    
    # Asset-specific fields
    ticker: Optional[str] = None
    exchange: Optional[str] = None
    
    # Weighting fields
    weight: Optional[dict] = None  # {"num": 60, "den": 100}
    
    # Conditional logic fields
    lhs_fn: Optional[str] = None
    lhs_val: Optional[str] = None
    lhs_fn_params: Optional[dict] = None
    rhs_fn: Optional[str] = None
    rhs_val: Optional[str] = None
    rhs_fn_params: Optional[dict] = None
    comparator: Optional[str] = None  # 'gt', 'lt', 'gte', 'lte', 'eq'
    is_else_condition: Optional[bool] = None
    
    # Filter/sort fields
    sort_by_fn: Optional[str] = None
    sort_by_fn_params: Optional[dict] = None
    select_fn: Optional[str] = None  # 'top', 'bottom'
    select_n: Optional[str] = None

# Core Types
@strawberry.type
class User:
    id: strawberry.ID
    email: str
    alpaca_connected: bool
    created_at: datetime.datetime
    symphonies_count: int
    
    @strawberry.field
    async def symphonies(self, info: Info) -> List['Symphony']:
        return await info.context.symphony_service.get_user_symphonies(self.id)

@strawberry.type
class Symphony:
    id: strawberry.ID
    name: str
    description: Optional[str]
    status: SymphonyStatus
    algorithm: SymphonyStep
    uploaded_at: datetime.datetime
    last_executed_at: Optional[datetime.datetime]
    
    @strawberry.field
    async def current_positions(self, info: Info) -> List['Position']:
        return await info.context.trading_service.get_symphony_positions(self.id)
    
    @strawberry.field
    async def performance_metrics(self, info: Info) -> 'PerformanceMetrics':
        return await info.context.analytics_service.get_symphony_metrics(self.id)

@strawberry.type
class Position:
    id: strawberry.ID
    symphony_id: strawberry.ID
    symbol: str
    quantity: float
    market_value: float
    cost_basis: float
    unrealized_pnl: float
    timestamp: datetime.datetime

@strawberry.type
class Trade:
    id: strawberry.ID
    symphony_id: strawberry.ID
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    executed_at: datetime.datetime
    algorithm_decision: Optional[dict]  # Store decision path

@strawberry.type
class PerformanceMetrics:
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    win_rate: float
    sortino_ratio: float
    calmar_ratio: float
    total_return: float
    daily_pnl: float

@strawberry.type
class Backtest:
    id: strawberry.ID
    symphony_id: strawberry.ID
    start_date: datetime.date
    end_date: datetime.date
    performance_metrics: PerformanceMetrics
    algorithm_decisions: List[dict]  # Historical decision paths
    created_at: datetime.datetime

# Input Types
@strawberry.input
class SymphonyUploadInput:
    name: str
    description: Optional[str] = None
    algorithm_json: str  # JSON string of the algorithm

@strawberry.input
class BacktestInput:
    symphony_id: strawberry.ID
    start_date: datetime.date
    end_date: datetime.date
    include_decision_tree: bool = True
    include_technical_indicators: bool = True

# Mutations
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def upload_symphony(self, info: Info, input: SymphonyUploadInput) -> Symphony:
        """Upload and validate a new symphony (max 40 per user)"""
        user_id = info.context.user.id
        return await info.context.symphony_service.upload_symphony(user_id, input)
    
    @strawberry.mutation
    async def toggle_symphony_status(self, info: Info, symphony_id: strawberry.ID) -> Symphony:
        """Activate or deactivate a symphony"""
        return await info.context.symphony_service.toggle_status(symphony_id)
    
    @strawberry.mutation
    async def run_backtest(self, info: Info, input: BacktestInput) -> Backtest:
        """Run a backtest for a symphony with historical data from 2007+"""
        return await info.context.backtest_service.run_backtest(input)
    
    @strawberry.mutation
    async def connect_alpaca(self, info: Info, auth_code: str) -> User:
        """Complete Alpaca OAuth flow for paper trading"""
        return await info.context.alpaca_service.complete_oauth(info.context.user.id, auth_code)

# Queries
@strawberry.type
class Query:
    @strawberry.field
    async def me(self, info: Info) -> User:
        """Get current user information"""
        return await info.context.user_service.get_user(info.context.user.id)
    
    @strawberry.field
    async def symphony(self, info: Info, id: strawberry.ID) -> Optional[Symphony]:
        """Get a specific symphony by ID"""
        return await info.context.symphony_service.get_symphony(id)
    
    @strawberry.field
    async def my_symphonies(self, info: Info, status: Optional[SymphonyStatus] = None) -> List[Symphony]:
        """Get all user symphonies, optionally filtered by status"""
        return await info.context.symphony_service.get_user_symphonies(
            info.context.user.id, status
        )
    
    @strawberry.field
    async def backtest_results(self, info: Info, backtest_id: strawberry.ID) -> Backtest:
        """Get detailed backtest results including decision history"""
        return await info.context.backtest_service.get_results(backtest_id)
    
    @strawberry.field
    async def compare_performance(
        self, info: Info, symphony_id: strawberry.ID, backtest_id: strawberry.ID
    ) -> dict:
        """Compare live vs backtest performance"""
        return await info.context.analytics_service.compare_performance(
            symphony_id, backtest_id
        )

# Subscriptions
@strawberry.type
class Subscription:
    @strawberry.subscription
    async def position_updates(self, info: Info, symphony_id: strawberry.ID) -> Position:
        """Subscribe to real-time position updates for a symphony"""
        async for position in info.context.subscription_manager.position_updates(symphony_id):
            yield position
    
    @strawberry.subscription
    async def trade_executions(self, info: Info, symphony_id: strawberry.ID) -> Trade:
        """Subscribe to trade executions for a symphony"""
        async for trade in info.context.subscription_manager.trade_executions(symphony_id):
            yield trade
    
    @strawberry.subscription
    async def performance_updates(self, info: Info, symphony_id: strawberry.ID) -> PerformanceMetrics:
        """Subscribe to performance metric updates"""
        async for metrics in info.context.subscription_manager.performance_updates(symphony_id):
            yield metrics

# Schema Assembly
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription
)
```

### 6.3 GraphQL Context & Authentication
```python
from fastapi import Depends, HTTPException
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

class GraphQLContext:
    def __init__(self, user, db_session, services):
        self.user = user
        self.db = db_session
        self.user_service = services['user']
        self.symphony_service = services['symphony']
        self.trading_service = services['trading']
        self.analytics_service = services['analytics']
        self.backtest_service = services['backtest']
        self.alpaca_service = services['alpaca']
        self.subscription_manager = services['subscription_manager']

async def get_context(
    user=Depends(get_current_user),
    db=Depends(get_db),
    services=Depends(get_services)
) -> GraphQLContext:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return GraphQLContext(user, db, services)

# FastAPI Integration
from fastapi import FastAPI

app = FastAPI()

graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    subscription_protocols=["graphql-ws", "graphql-transport-ws"]
)

app.include_router(graphql_app, prefix="/graphql")
```

### 6.4 Frontend Usage with Apollo Client
```typescript
// Auto-generated types from GraphQL schema
import { gql, useQuery, useMutation, useSubscription } from '@apollo/client';
import { Symphony, Position, PerformanceMetrics } from './generated/graphql';

// Query all symphonies
const GET_SYMPHONIES = gql`
  query GetMySymphonies($status: SymphonyStatus) {
    mySymphonies(status: $status) {
      id
      name
      status
      lastExecutedAt
      performanceMetrics {
        totalReturn
        sharpeRatio
        maxDrawdown
      }
    }
  }
`;

// Upload symphony mutation
const UPLOAD_SYMPHONY = gql`
  mutation UploadSymphony($input: SymphonyUploadInput!) {
    uploadSymphony(input: $input) {
      id
      name
      status
    }
  }
`;

// Real-time position updates
const POSITION_UPDATES = gql`
  subscription PositionUpdates($symphonyId: ID!) {
    positionUpdates(symphonyId: $symphonyId) {
      id
      symbol
      quantity
      marketValue
      unrealizedPnl
    }
  }
`;

// React component usage
function SymphonyDashboard() {
  const { data, loading } = useQuery(GET_SYMPHONIES, {
    variables: { status: 'ACTIVE' }
  });
  
  const [uploadSymphony] = useMutation(UPLOAD_SYMPHONY);
  
  const { data: positionData } = useSubscription(POSITION_UPDATES, {
    variables: { symphonyId: selectedSymphonyId }
  });
  
  // TypeScript knows exact types for all data
}
```

## 7. Server Architecture & Services

### 7.1 Python Services & Business Logic
- **FastAPI Routes**: RESTful endpoints with automatic OpenAPI documentation
- **Pydantic Models**: Runtime validation with auto-generated TypeScript types
- **SQLAlchemy ORM**: Async database operations with connection pooling
- **Celery Tasks**: Distributed background processing for algorithm execution
- **Algorithm Services**: Complex symphony parsing, validation, and execution

### 7.2 Core Services
- **UserService**: User management, OAuth token handling, authentication
- **AlpacaOAuthService**: OAuth 2.0 flow management, token refresh
- **SymphonyService**: Algorithm parsing, validation, execution orchestration
- **AlgorithmExecutor**: Core algorithm interpretation and technical indicator calculations
- **TradingService**: Alpaca API wrapper with OAuth authentication
- **MarketDataService**: Real-time and historical market data integration
- **BacktestService**: Historical algorithm simulation with full decision tree execution
- **AnalyticsService**: Performance metrics calculation using quantstats

### 7.3 Algorithm Execution Examples
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Symphony, User
from app.services.algorithm_executor import AlgorithmExecutor
import pandas as pd

class SymphonyService:
    def __init__(self, db: AsyncSession, market_data_service, alpaca_client):
        self.db = db
        self.executor = AlgorithmExecutor(market_data_service, alpaca_client)
    
    async def execute_symphony(self, symphony_id: str, user_id: str) -> Dict[str, Any]:
        """Execute complex symphony algorithm with real-time data"""
        
        # Get symphony from database
        symphony = await self.get_symphony(symphony_id, user_id)
        
        # Get current market data context
        market_context = await self._build_market_context(symphony)
        
        # Execute algorithm tree
        execution_result = await self.executor.execute_step(
            symphony.json_data, market_context
        )
        
        # Process trades and update positions
        trades = await self._process_execution_result(execution_result, symphony)
        
        return {
            "symphony_id": symphony_id,
            "execution_timestamp": datetime.now(),
            "trades": trades,
            "algorithm_decisions": execution_result.get("decisions", [])
        }
    
    async def _build_market_context(self, symphony: Symphony) -> Dict[str, Any]:
        """Build market data context for algorithm execution"""
        symbols = self._extract_symbols_from_symphony(symphony.json_data)
        
        market_data = {}
        for symbol in symbols:
            data = await self.market_data_service.get_current_data(symbol)
            market_data[symbol] = {
                "price": data.close,
                "volume": data.volume,
                "timestamp": data.timestamp
            }
        
        return {
            "market_data": market_data,
            "execution_time": datetime.now(),
            "symphony_id": symphony.id
        }

class BacktestService:
    def __init__(self, db: AsyncSession, historical_data_service):
        self.db = db
        self.historical_data = historical_data_service
    
    async def run_backtest(
        self, 
        symphony_id: str, 
        start_date: date, 
        end_date: date, 
        user_id: str
    ) -> Dict[str, Any]:
        """Run sophisticated algorithm backtest with full simulation"""
        
        symphony = await self.get_symphony(symphony_id, user_id)
        
        # Get historical data for all symphony symbols
        symbols = self._extract_symbols_from_symphony(symphony.json_data)
        historical_data = await self.historical_data.get_data(
            symbols, start_date, end_date
        )
        
        # Initialize backtest state
        portfolio_value = []
        trades = []
        algorithm_decisions = []
        
        # Simulate algorithm execution for each rebalance period
        current_date = start_date
        while current_date <= end_date:
            # Build historical market context for this date
            market_context = self._build_historical_context(
                historical_data, current_date
            )
            
            # Execute algorithm with historical data
            execution_result = await self.executor.execute_step(
                symphony.json_data, market_context
            )
            
            # Record decisions and trades
            algorithm_decisions.append({
                "date": current_date,
                "decisions": execution_result.get("decisions", []),
                "selected_assets": execution_result.get("assets", [])
            })
            
            # Calculate portfolio performance
            portfolio_performance = self._calculate_portfolio_performance(
                execution_result, historical_data, current_date
            )
            portfolio_value.append(portfolio_performance)
            
            # Move to next rebalance date
            current_date = self._get_next_rebalance_date(
                current_date, symphony.json_data.rebalance
            )
        
        # Calculate final performance metrics
        returns = pd.Series([pv["return"] for pv in portfolio_value])
        performance_metrics = self._calculate_performance_metrics(returns)
        
        return {
            "backtest_id": str(uuid4()),
            "symphony_id": symphony_id,
            "start_date": start_date,
            "end_date": end_date,
            "performance_metrics": performance_metrics,
            "algorithm_decisions": algorithm_decisions,
            "portfolio_value": portfolio_value
        }
```

### 7.4 Technical Indicators Service
```python
import talib
import pandas as pd
import numpy as np

class TechnicalIndicatorsService:
    """High-performance technical indicator calculations using TA-Lib"""
    
    async def calculate_indicator(
        self, 
        symbol: str, 
        indicator: str, 
        params: Dict[str, Any],
        market_data: Optional[pd.DataFrame] = None
    ) -> Union[float, np.ndarray]:
        """Calculate technical indicators with caching for performance"""
        
        if market_data is None:
            market_data = await self.market_data_service.get_data(symbol)
        
        window = params.get('window', 14)
        close_prices = market_data.close.values
        
        # Calculate indicators using TA-Lib for performance
        if indicator == "relative-strength-index":
            return talib.RSI(close_prices, timeperiod=window)
        
        elif indicator == "moving-average-price":
            return talib.SMA(close_prices, timeperiod=window)
        
        elif indicator == "exponential-moving-average-price":
            return talib.EMA(close_prices, timeperiod=window)
        
        elif indicator == "standard-deviation-price":
            return talib.STDDEV(close_prices, timeperiod=window)
        
        elif indicator == "standard-deviation-return":
            returns = market_data.close.pct_change().values
            return talib.STDDEV(returns[1:], timeperiod=window)  # Skip first NaN
        
        elif indicator == "max-drawdown":
            # Custom implementation for max drawdown
            rolling_max = market_data.close.rolling(window).max()
            drawdown = (market_data.close - rolling_max) / rolling_max
            return drawdown.rolling(window).min().values
        
        elif indicator == "cumulative-return":
            # Calculate cumulative return over window
            return ((close_prices[-1] / close_prices[-window]) - 1) * 100
        
        elif indicator == "current-price":
            return close_prices[-1]
        
        else:
            raise ValueError(f"Unsupported indicator: {indicator}")
    
    async def calculate_multiple_indicators(
        self, 
        symbols: List[str], 
        indicators: List[str],
        params: Dict[str, Any]
    ) -> Dict[str, Dict[str, Union[float, np.ndarray]]]:
        """Batch calculate indicators for multiple symbols efficiently"""
        
        results = {}
        for symbol in symbols:
            market_data = await self.market_data_service.get_data(symbol)
            results[symbol] = {}
            
            for indicator in indicators:
                results[symbol][indicator] = await self.calculate_indicator(
                    symbol, indicator, params, market_data
                )
        
        return results
```

### 7.5 Real-time Data Processing
```python
from celery import Celery
import asyncio

# Celery configuration for distributed processing
celery_app = Celery(
    "oragami_composer",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def execute_symphony_algorithm(symphony_id: str, user_id: str):
    """Background task for algorithm execution"""
    asyncio.run(_execute_symphony_async(symphony_id, user_id))

@celery_app.task
def calculate_performance_metrics(symphony_id: str):
    """Background task for performance calculation"""
    asyncio.run(_calculate_metrics_async(symphony_id))

@celery_app.task
def run_backtest_simulation(symphony_id: str, start_date: str, end_date: str, user_id: str):
    """Background task for backtesting"""
    asyncio.run(_run_backtest_async(symphony_id, start_date, end_date, user_id))

# WebSocket manager for real-time updates
class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def broadcast_position_update(self, user_id: str, positions: List[Dict]):
        """Broadcast position updates to user's connected clients"""
        if user_id in self.connections:
            message = {
                "type": "position_update",
                "data": positions,
                "timestamp": datetime.now().isoformat()
            }
            
            for connection in self.connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Remove disconnected clients
                    self.connections[user_id].remove(connection)
```

## 8. Design System

### 8.1 Visual Style
- **Branding & Theme**: Professional trading platform aesthetic with dark/light mode toggle, financial data-focused color scheme
- **Color Palette**: 
  - Primary: Deep blue (#1976d2) for actions and navigation
  - Success: Green (#4caf50) for gains and positive metrics
  - Warning: Orange (#ff9800) for alerts and neutral changes  
  - Error: Red (#f44336) for losses and critical states
  - Neutral: Gray scale for backgrounds and secondary text
- **Typography**: Monospace fonts for numerical data, sans-serif for UI text, clear hierarchy with appropriate font weights
- **Layout & Spacing**: Material Design spacing scale (8px grid), responsive breakpoints (mobile: 320px+, tablet: 768px+, desktop: 1024px+)
- **Data Visualization**: Consistent chart styling, color-coded performance indicators, clear legends and axis labels
- **Accessibility Considerations**: WCAG 2.1 AA compliance, 4.5:1 contrast ratios, keyboard navigation, screen reader support, focus indicators

### 8.2 UI Components
- **Trading Dashboard Elements**:
  - PerformanceCard: Metric display with sparkline charts, color-coded indicators
  - SymphonyStatusBadge: Visual status indicators (active/inactive/stopped)
  - PositionTable: Sortable, filterable data tables with real-time updates
  - ChartContainer: Interactive time-series charts with zoom/pan capabilities
- **Data Input & Management**:
  - FileUploader: Drag-and-drop zone with validation feedback
  - SymphonyLibrary: Grid/list view toggle with search and filtering
  - MetricsDashboard: Configurable widget layout for key performance indicators
- **Navigation & Layout**:
  - ResponsiveSidebar: Collapsible navigation with role-based menu items
  - HeaderBar: Account status, notifications, and quick actions
  - LoadingStates: Skeleton screens and progress indicators for data fetching
- **Interaction States**: 
  - Hover effects for interactive elements
  - Loading spinners with progress feedback
  - Error boundaries with retry actions
  - Success confirmations with clear messaging
- **Responsive Patterns**: 
  - Mobile-first design approach
  - Progressive disclosure for complex data
  - Touch-friendly targets and gestures
  - Adaptive layouts for different screen sizes

## 9. Component Architecture

### 9.1 Backend Components (Python + GraphQL)
- **Framework**: Strawberry GraphQL with FastAPI integration
- **Data Models**: SQLAlchemy models with Strawberry GraphQL type integration
- **Error Handling**: GraphQL error handling with custom error types and structured logging
- **Services**: 
  - AuthService: JWT management, OAuth token handling
  - AlpacaOAuthService: OAuth 2.0 flow management, token refresh
  - SymphonyService: Algorithm parsing, validation, execution orchestration
  - AlgorithmExecutor: Core algorithm interpretation and technical indicator calculations
  - TradingService: Alpaca API wrapper with OAuth authentication
  - MarketDataService: Real-time and historical market data integration
  - BacktestService: Historical algorithm simulation with decision tree execution
  - AnalyticsService: Performance metrics calculation using quantstats
- **GraphQL Integration**:
  - Schema-first approach with Strawberry decorators
  - Automatic TypeScript type generation
  - Real-time subscriptions with Redis pub/sub
  - Sophisticated query optimization and caching

### 9.2 Frontend Components (TypeScript + React + Apollo)
- **State Management**: Apollo Client for GraphQL state management with normalized cache
- **API Integration**: Apollo Client with automatic type generation from GraphQL schema
- **Routing**: React Router with protected routes, lazy loading for performance
- **Key UI Components**:
  - **SymphonyDashboard**: Uses comprehensive GraphQL query for all dashboard data
    ```typescript
    // Single efficient query instead of multiple REST calls
    const { data, loading } = useQuery(DASHBOARD_QUERY);
    
    // Real-time subscription for position updates
    useSubscription(POSITION_SUBSCRIPTION, {
      variables: { symphonyId },
      onData: ({ subscriptionData }) => {
        // Apollo automatically updates cache and re-renders components
      }
    });
    ```
  - **AlpacaOAuthConnect**: OAuth flow with GraphQL mutations for connection management
    ```typescript
    const [connectAlpaca] = useMutation(CONNECT_ALPACA_MUTATION, {
      onCompleted: () => client.refetchQueries({ include: ['DashboardData'] })
    });
    ```
  - **UploadSymphony**: File upload with GraphQL mutations and comprehensive validation feedback
  - **PerformanceAnalytics**: Interactive charts with GraphQL queries for flexible data fetching
  - **BacktestResults**: Side-by-side comparisons using GraphQL fragments for data consistency
  - **AlgorithmVisualization**: Decision tree and conditional logic visualization components
  - **TechnicalIndicatorCharts**: Real-time and historical indicator visualization with GraphQL subscriptions
- **Real-time Updates**: GraphQL subscriptions with Apollo Client for sophisticated live data management
- **Error Handling**: Apollo Error Link for global GraphQL error handling with user-friendly messages
- **Performance Optimization**: Apollo Client cache policies, query batching, subscription management, component memoization

### 9.3 GraphQL Type Safety & Code Generation
```python
# Strawberry automatically generates TypeScript types
# Using strawberry-graphql-codegen or graphql-code-generator

# Python GraphQL schema
@strawberry.type
class Symphony:
    id: strawberry.ID
    name: str
    status: str
    current_positions: List[Position]
    performance_metrics: List[PerformanceMetric]

# Auto-generated TypeScript interface
interface Symphony {
  __typename?: 'Symphony';
  id: string;
  name: string;
  status: string;
  currentPositions: Position[];
  performanceMetrics: PerformanceMetric[];
}

# Frontend usage with full type safety
const { data } = useQuery<DashboardDataQuery>(DASHBOARD_QUERY);
// TypeScript knows exact shape of data.user.symphonies
```

### 9.4 Real-time Architecture
```python
# Subscription manager with Redis pub/sub
class GraphQLSubscriptionManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.subscribers = {}
    
    async def publish_position_update(
        self, 
        user_id: str, 
        symphony_id: str, 
        positions: List[Position]
    ):
        """Publish position updates to GraphQL subscribers"""
        channel = f"positions_{user_id}_{symphony_id}"
        await self.redis.publish(channel, json.dumps({
            "type": "position_update",
            "data": [pos.dict() for pos in positions]
        }))
    
    async def subscribe_to_position_updates(
        self, 
        user_id: str, 
        symphony_id: str
    ) -> AsyncGenerator[List[Position], None]:
        """Subscribe to real-time position updates"""
        channel = f"positions_{user_id}_{symphony_id}"
        
        async with self.redis.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    yield [Position(**pos) for pos in data['data']]
```

## 10. Authentication & Authorization
- **Method**: JWT tokens for app sessions + OAuth 2.0 for Alpaca integration
- **OAuth Flow**: Standard OAuth 2.0 authorization code flow with Alpaca
- **Session Management**: 15-minute JWT access tokens, 7-day refresh tokens for app sessions
- **OAuth Token Security**: Encrypted storage of Alpaca OAuth access tokens, secure token refresh handling
- **Scopes**: `account:write trading` for paper trading access
- **FastAPI Authorization**: Dependency injection for route-level authorization, JWT token validation middleware

## 11. Data Flow
- **REST API Request/Response Lifecycle**: 
  1. Client HTTP request → FastAPI route → Pydantic validation → Service layer → SQLAlchemy → Database
  2. Background Celery tasks → Algorithm execution → Alpaca API → Database updates → WebSocket notifications
  3. WebSocket events → Connected clients → React Query cache updates → UI updates
- **State Management**: React Query for server state with automatic background refetching and caching
- **Real-Time Updates**: WebSocket connections with message filtering based on user context and symphony ownership
- **Type Safety**: Pydantic models auto-generate TypeScript interfaces for end-to-end type safety

## 11. Payment Integration
- **Not Applicable**: This is a paper trading platform with no real money transactions

## 12. Analytics Integration
- **Tracking Tools**: Custom analytics for user engagement and system performance
- **Event Naming**: user_symphony_upload, trade_executed, backtest_completed
- **Reporting**: Admin dashboard for system metrics and user activity

## 13. Security & Compliance
- **Encryption**: AES-256 for OAuth tokens, bcrypt for user passwords, TLS for transit
- **OAuth Security**: Secure client secret management, PKCE for additional security, token rotation
- **Compliance**: SOC 2 Type II for financial data handling, OAuth 2.0 security best practices
- **Threat Modeling**: SQL injection prevention, XSS protection, CSRF protection, OAuth token leakage prevention
- **Secrets Management**: Kubernetes secrets for OAuth client credentials, secure token storage

## 14. Environment Configuration & Deployment
- **Local Setup**: Docker Compose with PostgreSQL, Redis, and API services
- **Staging/Production**: Kubernetes with auto-scaling based on CPU/memory metrics
- **CI/CD**: GitHub Actions pipeline with testing, building, and deployment stages
- **Monitoring**: Prometheus metrics, Grafana dashboards, structured logging

## 15. Testing
- **Unit Testing**: Jest for business logic, 90% coverage target
- **Integration Testing**: Supertest for API endpoints, database transactions
- **End-to-End Testing**: Playwright for critical user flows
- **Performance Testing**: Artillery for load testing, Alpaca API rate limit validation

---

### Summary & Next Steps
- **Recap**: Modern Python FastAPI backend with quantitative computing power, providing efficient algorithmic execution, sophisticated backtesting, and real-time performance tracking. PostgreSQL with TimescaleDB for time-series performance data, TypeScript React frontend with comprehensive trading functionality, OAuth 2.0 integration with Alpaca, and consistent `.env` file configuration across all environments
- **Python Backend Benefits**: Native quantitative computing with pandas/numpy/TA-Lib, 150+ built-in technical indicators, high-performance backtesting with vectorized operations, scalable async architecture, automatic type generation for frontend, and cost-effective cloud resource utilization
- **Architecture Benefits**: Separation of concerns with Python handling complex computations and TypeScript providing excellent UX, automatic API documentation with FastAPI, type safety across the full stack, and horizontal scalability for 40+ concurrent users
- **Configuration Benefits**: Simplified deployment and consistent configuration management using `.env` files for development, staging, and production environments
- **Open Questions**: 
  - Historical data provider selection (Alpha Vantage vs. Polygon vs. Quandl)
  - Exact Composer.trade JSON schema validation edge cases (pending sample files analysis)
  - Cloud provider preference (AWS vs. GCP vs. Azure)
  - Alpaca OAuth app approval process for live trading (if needed beyond paper trading)
  - WebSocket connection management strategy for 40+ concurrent users
  - Celery worker scaling strategy for algorithm execution under load
- **Future Enhancements**: Machine learning integration for algorithm optimization, Advanced caching strategies with Redis, Mobile app with React Native, Social trading features with real-time collaboration, Algorithm marketplace with user-generated strategies
