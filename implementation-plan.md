# Implementation Plan

## Reference Files & Context

**IMPORTANT**: The following reference files are available in your workspace and should be consulted throughout development:

### Required Reference Documents
- **`project-spec.md`**: Complete business requirements, user needs, and feature specifications for Oragami Composer
- **`technical-spec.md`**: Comprehensive technical architecture, Python + GraphQL backend design, database schemas, and component specifications
- **`docs/security-best-practices.md`**: Comprehensive security architecture and considerations
- **`sample-symphonies/sample-symphony.json`**: Critical reference showing the full complexity of Composer.trade algorithmic symphonies with all available functions, technical indicators, conditional logic, and step types

### Optional Workspace Files
- **`.cline/instructions.md`**: Workspace-specific instructions and development guidelines (create if needed)

### Key Points for Development
- **Algorithm Complexity**: The sample symphony demonstrates sophisticated decision trees with conditional logic, technical indicators (RSI, moving averages, volatility), asset filtering, and multiple weighting strategies
- **Architecture**: Python backend with FastAPI + Strawberry GraphQL, React frontend with Apollo Client, comprehensive testing (90%+ coverage)
- **Testing Requirements**: All algorithm calculations must be tested for accuracy, behavioral testing for user workflows, performance testing for 40 concurrent users
- **Configuration**: Use .env files for all environments, no environment variables during development
- **Execution Timing**: Daily rebalancing within 10 minutes of market close (15:50-16:00 EST), closer to end time is better
- **Error Handling**: Algorithm failures result in immediate liquidation to cash positions

### Workspace Setup Instructions
1. Ensure `project-spec.md` and `technical-spec.md` are in your workspace root
2. Create `sample-symphonies/` folder with `sample-symphony.json` file
3. Optionally create `.cline/instructions.md` for persistent workspace rules
4. Begin development with Step 1 below, referencing these files as needed

## Project Setup & Infrastructure

- [ ] Step 1: Initialize Python Project Structure and Development Environment
  - **Task**: Set up Python backend structure with FastAPI, Docker, and development tooling
  - **Files**: 
    - `backend/requirements.txt`: Python dependencies (fastapi, strawberry-graphql, sqlalchemy, celery, ta-lib, etc.)
    - `backend/requirements-dev.txt`: Development dependencies (pytest, black, flake8, etc.)
    - `backend/app/__init__.py`: Application package initialization
    - `backend/app/main.py`: FastAPI application entry point
    - `backend/app/config.py`: Configuration management using pydantic-settings
    - `frontend/package.json`: React + Apollo Client dependencies
    - `docker-compose.yml`: Local development services (PostgreSQL + TimescaleDB, Redis)
    - `docker/Dockerfile.backend`: Python backend container configuration
    - `docker/Dockerfile.frontend`: React frontend container configuration
    - `.env.example`: Development configuration template
    - `.env`: Local development configuration (gitignored)
    - `.env.production`: Production configuration template (gitignored)
    - `.env.staging`: Staging configuration template (gitignored)
    - `backend/pyproject.toml`: Python project configuration
    - `backend/.flake8`: Python linting rules
    - `backend/.black`: Python formatting rules
  - **Step Dependencies**: None
  - **User Instructions**: Run `cd backend && pip install -r requirements.txt`, copy `.env.example` to `.env`, and run `docker-compose up -d` to start development environment

- [ ] Step 2: Database Schema and SQLAlchemy Setup
  - **Task**: Create PostgreSQL schema with TimescaleDB, set up SQLAlchemy ORM, and create initial migrations
  - **Files**:
    - `backend/app/models/__init__.py`: SQLAlchemy model definitions
    - `backend/app/models/user.py`: User model with OAuth token storage
    - `backend/app/models/symphony.py`: Symphony model with JSON algorithm storage
    - `backend/app/models/position.py`: Position model for TimescaleDB hypertable
    - `backend/app/models/trade.py`: Trade model for TimescaleDB hypertable
    - `backend/app/models/performance.py`: Performance metrics model for TimescaleDB
    - `backend/app/models/backtest.py`: Backtest results model
    - `backend/alembic.ini`: Alembic configuration
    - `backend/alembic/env.py`: Alembic migration environment configuration
    - `backend/alembic/versions/001_initial_setup.py`: Initial database migration
    - `backend/app/database/connection.py`: Database connection and session management
    - `backend/app/database/init_db.py`: Database initialization and TimescaleDB setup
    - `docker/init-timescaledb.sql`: TimescaleDB extension and hypertable setup
  - **Step Dependencies**: Step 1
  - **User Instructions**: Run `cd backend && alembic upgrade head` to apply migrations and `python -m app.database.init_db` to set up TimescaleDB

## Authentication & User Management

- [ ] Step 3: JWT Authentication System
  - **Task**: Implement JWT-based authentication with user registration, login, and token management using FastAPI
  - **Files**:
    - `backend/app/auth/jwt.py`: JWT utilities and token management
    - `backend/app/auth/password.py`: Password hashing and validation using bcrypt
    - `backend/app/services/auth_service.py`: Authentication business logic
    - `backend/app/auth/dependencies.py`: FastAPI authentication dependencies
    - `backend/app/schemas/auth.py`: Pydantic models for authentication
    - `backend/app/api/routes/auth.py`: Authentication API endpoints
  - **Step Dependencies**: Step 2
  - **User Instructions**: Configure JWT_SECRET and TOKEN_EXPIRY in your `.env` file (defaults provided for development)

- [ ] Step 4: Alpaca OAuth 2.0 Integration (Paper Trading Only)
  - **Task**: Implement OAuth 2.0 flow for Alpaca paper trading account connection with secure token storage
  - **Files**:
    - `backend/app/services/alpaca_oauth_service.py`: OAuth flow implementation for paper trading
    - `backend/app/integrations/alpaca_client.py`: Alpaca paper trading API client with OAuth authentication
    - `backend/app/api/routes/oauth.py`: OAuth callback handling and endpoints
    - `backend/app/auth/oauth_utils.py`: OAuth utilities and token refresh
    - `backend/app/schemas/alpaca.py`: Alpaca API Pydantic models
    - `backend/app/config/settings.py`: Configuration management with pydantic-settings
  - **Step Dependencies**: Step 3
  - **User Instructions**: Register OAuth app in Alpaca dashboard (paper trading scope only) and add ALPACA_CLIENT_ID and ALPACA_CLIENT_SECRET to your `.env` file

- [ ] Step 5: GraphQL API Setup with Strawberry
  - **Task**: Initialize Strawberry GraphQL server with authentication, create user management schema and resolvers
  - **Files**:
    - `backend/app/graphql/__init__.py`: GraphQL module initialization
    - `backend/app/graphql/schema.py`: Main GraphQL schema assembly
    - `backend/app/graphql/types/user.py`: User GraphQL types and resolvers
    - `backend/app/graphql/types/auth.py`: Authentication GraphQL types
    - `backend/app/graphql/mutations/auth.py`: Authentication mutations
    - `backend/app/graphql/queries/user.py`: User query resolvers
    - `backend/app/graphql/context.py`: GraphQL context and authentication
    - `backend/app/main.py`: FastAPI application with GraphQL endpoint integration
    - `backend/tests/test_graphql_auth.py`: GraphQL authentication testing
  - **Step Dependencies**: Step 4
  - **User Instructions**: Reference `technical-spec.md` Section 6.2 for complete GraphQL schema design and `sample-symphonies/sample-symphony.json` for understanding the data structures that need to be supported in the GraphQL types.

## Algorithm Engine & Symphony Management

- [ ] Step 6: Symphony Algorithmic Management GraphQL API
  - **Task**: Create GraphQL schema and resolvers for complex symphony upload, validation, and algorithmic execution engine
  - **Files**:
    - `backend/app/graphql/types/symphony.py`: Symphony GraphQL types with algorithm complexity support
    - `backend/app/graphql/mutations/symphony.py`: Symphony management mutations
    - `backend/app/graphql/queries/symphony.py`: Symphony query resolvers
    - `backend/app/services/symphony_service.py`: Symphony business logic and algorithm interpreter
    - `backend/app/parsers/symphony_parser.py`: Composer.trade complex JSON validation and parsing
    - `backend/app/parsers/schemas.py`: Comprehensive Pydantic schemas for all symphony step types and functions
    - `backend/app/parsers/validator.py`: Algorithm validation and execution tree builder
    - `backend/app/algorithms/executor.py`: Algorithmic execution engine for conditional logic, technical indicators, and asset selection
    - `backend/app/algorithms/indicators.py`: Technical indicator calculation functions using TA-Lib
    - `backend/tests/test_symphony_algorithms.py`: Comprehensive algorithm execution testing
    - `backend/tests/test_symphony_graphql.py`: GraphQL symphony API testing
  - **Step Dependencies**: Step 5
  - **User Instructions**: **CRITICAL**: Reference the `sample-symphonies/sample-symphony.json` file for comprehensive algorithm structure validation and testing. This file shows all available functions, metrics, and step types that must be supported. Also reference `technical-spec.md` for detailed algorithm execution requirements and `project-spec.md` for business context. Note: Maximum 40 symphonies per user initially.

- [ ] Step 7: Market Data Integration Service
  - **Task**: Integrate market data provider with $100/month budget for real-time and historical data
  - **Files**:
    - `backend/app/services/market_data_service.py`: Market data service with Alpha Vantage + EOD Historical Data integration
    - `backend/app/services/data_cache_service.py`: Redis caching for market data optimization
    - `backend/app/integrations/alpha_vantage_client.py`: Alpha Vantage API client
    - `backend/app/integrations/eod_historical_client.py`: EOD Historical Data API client
    - `backend/app/schemas/market_data.py`: Market data Pydantic models
    - `backend/tests/test_market_data.py`: Market data service testing
  - **Step Dependencies**: Step 6
  - **User Instructions**: Add ALPHA_VANTAGE_API_KEY and EOD_HISTORICAL_API_KEY to your `.env` file. Historical data should go back to at least 2007 (BIL inception).

- [ ] Step 8: Trading Operations GraphQL API
  - **Task**: Implement GraphQL schema and resolvers for position tracking, trade history, and Alpaca paper trading integration
  - **Files**:
    - `backend/app/graphql/types/trading.py`: Trading GraphQL types (Position, Trade, PerformanceMetric)
    - `backend/app/graphql/queries/trading.py`: Trading query resolvers
    - `backend/app/graphql/subscriptions/trading.py`: Real-time GraphQL subscriptions for positions and trades
    - `backend/app/services/trading_service.py`: Trading business logic
    - `backend/app/services/alpaca_trading_service.py`: Alpaca paper trading API integration with algorithm execution
    - `backend/app/services/error_handler_service.py`: Error handling with automatic liquidation to cash
    - `backend/tests/test_trading_graphql.py`: Trading GraphQL API testing
  - **Step Dependencies**: Step 7
  - **User Instructions**: None

## Real-time Features & Background Processing

- [ ] Step 9: Daily Algorithmic Execution & Background Processing
  - **Task**: Set up Celery with Redis for algorithm execution at 15:50-16:00 EST daily window
  - **Files**:
    - `backend/app/celery_app.py`: Celery application configuration with Redis broker
    - `backend/app/tasks/algorithm_execution.py`: Complex algorithmic logic execution with conditional branching
    - `backend/app/tasks/technical_indicators.py`: Technical indicator calculations using TA-Lib
    - `backend/app/tasks/symphony_scheduler.py`: Daily rebalancing scheduler (15:50 EST execution)
    - `backend/app/tasks/error_tasks.py`: Error handling tasks with liquidation logic
    - `backend/app/services/task_service.py`: Task management service with algorithm execution tracking
    - `backend/app/workers/__init__.py`: Celery worker configuration and startup
    - `backend/app/services/pubsub_service.py`: Redis pub/sub service for GraphQL subscriptions
    - `backend/celery_worker.py`: Celery worker startup script
    - `backend/tests/test_algorithm_execution.py`: Comprehensive algorithm execution testing with real symphony data
    - `backend/tests/test_technical_indicators.py`: Technical indicator accuracy testing
    - `backend/tests/test_celery_tasks.py`: Background task testing
  - **Step Dependencies**: Step 8
  - **User Instructions**: Ensure Redis is running for Celery broker. Run `cd backend && celery -A app.celery_app worker --loglevel=info` to start workers. The algorithm execution engine must handle complex conditional logic, asset filtering, and technical analysis functions as shown in `sample-symphonies/sample-symphony.json`. Daily execution at 15:50 EST with completion by 15:58 EST.

- [ ] Step 10: Real-time GraphQL Subscriptions
  - **Task**: Implement GraphQL subscriptions for live position updates, metrics, and trade executions
  - **Files**:
    - `backend/app/graphql/subscriptions/__init__.py`: GraphQL subscriptions module
    - `backend/app/graphql/subscriptions/positions.py`: Position update subscriptions
    - `backend/app/graphql/subscriptions/metrics.py`: Performance metrics subscriptions
    - `backend/app/graphql/subscriptions/trades.py`: Trade execution subscriptions
    - `backend/app/services/subscription_manager.py`: GraphQL subscription management with Redis
    - `backend/app/graphql/schema.py`: Updated schema with subscription support
    - `backend/tests/test_graphql_subscriptions.py`: Real-time subscription testing
  - **Step Dependencies**: Step 9
  - **User Instructions**: None

## Frontend Development

- [ ] Step 11: React Frontend Setup and Apollo GraphQL Client
  - **Task**: Initialize React application with Apollo Client, routing, and authentication
  - **Files**:
    - `frontend/src/main.tsx`: React application entry point
    - `frontend/src/lib/apollo.ts`: Apollo GraphQL client configuration with subscriptions
    - `frontend/src/lib/auth.tsx`: Authentication context and hooks
    - `frontend/src/components/layout/Layout.tsx`: Main application layout
    - `frontend/src/pages/Login.tsx`: Login page component
    - `frontend/src/pages/Register.tsx`: Registration page component
    - `frontend/src/hooks/useAuth.ts`: Authentication hooks with GraphQL mutations
    - `frontend/src/utils/router.tsx`: React Router configuration
    - `frontend/src/generated/graphql.ts`: Auto-generated TypeScript types from GraphQL schema
    - `frontend/vite.config.ts`: Vite build configuration
    - `frontend/codegen.yml`: GraphQL code generation configuration
    - `frontend/src/__tests__/Auth.test.tsx`: Authentication component testing
  - **Step Dependencies**: Step 10
  - **User Instructions**: Run `cd frontend && npm run codegen` to generate TypeScript types from GraphQL schema

- [ ] Step 12: Dashboard and Symphony Algorithm Management UI
  - **Task**: Create main dashboard, symphony library (max 40 per user), upload components, and algorithm visualization
  - **Files**:
    - `frontend/src/pages/Dashboard.tsx`: Main trading dashboard with GraphQL queries
    - `frontend/src/components/symphony/SymphonyLibrary.tsx`: Symphony management with 40-symphony limit display
    - `frontend/src/components/symphony/UploadSymphony.tsx`: File upload with GraphQL mutations and limit checking
    - `frontend/src/components/symphony/SymphonyCard.tsx`: Individual symphony display with real-time subscriptions
    - `frontend/src/components/symphony/AlgorithmTree.tsx`: Visual representation of algorithm decision tree
    - `frontend/src/components/symphony/ConditionalLogicViewer.tsx`: Display conditional "if-then-else" logic flows
    - `frontend/src/components/ui/FileUploader.tsx`: Reusable file upload component
    - `frontend/src/components/ui/StatusBadge.tsx`: Status indicator component
    - `frontend/src/hooks/useSymphonies.ts`: Symphony management hooks with GraphQL operations
    - `frontend/src/graphql/queries/dashboard.graphql`: Dashboard GraphQL queries
    - `frontend/src/graphql/mutations/symphony.graphql`: Symphony GraphQL mutations
    - `frontend/src/__tests__/Dashboard.test.tsx`: Dashboard component behavioral testing
    - `frontend/src/__tests__/SymphonyUpload.test.tsx`: Symphony upload flow testing
  - **Step Dependencies**: Step 11
  - **User Instructions**: Algorithm visualization should show the complete decision tree structure, conditional logic branches, and technical indicator parameters from the sample symphony. Display symphony count (X/40) prominently.

- [ ] Step 13: Trading Interface and Real-time GraphQL Updates
  - **Task**: Build position tracking, trade history, error status display, and real-time GraphQL subscription components
  - **Files**:
    - `frontend/src/components/trading/PositionsTable.tsx`: Live positions with GraphQL subscriptions
    - `frontend/src/components/trading/TradeHistory.tsx`: Trade execution history
    - `frontend/src/components/trading/TradingDashboard.tsx`: Main trading interface with real-time data
    - `frontend/src/components/trading/ErrorStatus.tsx`: Display liquidation events and error states
    - `frontend/src/components/ui/DataTable.tsx`: Reusable data table component
    - `frontend/src/hooks/useRealtime.ts`: GraphQL subscription hooks
    - `frontend/src/hooks/usePositions.ts`: Position tracking hooks with GraphQL
    - `frontend/src/graphql/subscriptions/positions.graphql`: Position update subscriptions
    - `frontend/src/graphql/subscriptions/trades.graphql`: Trade execution subscriptions
    - `frontend/src/graphql/queries/trading.graphql`: Trading GraphQL queries
    - `frontend/src/__tests__/TradingInterface.test.tsx`: Trading interface behavioral testing
    - `frontend/cypress/e2e/trading-workflow.cy.ts`: End-to-end trading workflow testing
  - **Step Dependencies**: Step 12
  - **User Instructions**: None

## Advanced Features

- [ ] Step 14: Performance Analytics and Charts
  - **Task**: Implement performance metrics display with interactive charts and quantstats integration
  - **Files**:
    - `frontend/src/components/analytics/PerformanceCharts.tsx`: Interactive chart components
    - `frontend/src/components/analytics/MetricsDashboard.tsx`: Metrics overview with quantstats
    - `frontend/src/components/analytics/PerformanceCard.tsx`: Individual metric cards
    - `backend/app/services/analytics_service.py`: Performance calculation service using quantstats
    - `backend/app/graphql/types/analytics.py`: Analytics GraphQL types
    - `backend/app/graphql/queries/analytics.py`: Analytics GraphQL resolvers
    - `frontend/src/hooks/useAnalytics.ts`: Analytics data hooks with GraphQL
    - `frontend/src/graphql/queries/analytics.graphql`: Analytics GraphQL queries
    - `backend/requirements.txt`: Add quantstats, matplotlib for performance analysis
    - `backend/tests/test_analytics_service.py`: Performance calculation accuracy testing
    - `frontend/src/__tests__/PerformanceCharts.test.tsx`: Analytics component testing
  - **Step Dependencies**: Step 13
  - **User Instructions**: None

- [ ] Step 15: Complex Algorithmic Backtesting Engine
  - **Task**: Build sophisticated backtesting functionality with historical data integration back to 2007, algorithm simulation, and comparison tools
  - **Files**:
    - `backend/app/services/backtest_service.py`: Advanced backtesting engine with full algorithm simulation
    - `backend/app/services/historical_data_service.py`: Historical market data integration with pandas (2007-present)
    - `backend/app/algorithms/backtest_executor.py`: Algorithm execution engine for historical simulation
    - `backend/app/graphql/types/backtest.py`: Backtesting GraphQL types
    - `backend/app/graphql/mutations/backtest.py`: Backtesting GraphQL mutations
    - `frontend/src/components/backtest/BacktestForm.tsx`: Backtest configuration with algorithm parameter display
    - `frontend/src/components/backtest/BacktestResults.tsx`: Results comparison with decision tree visualization
    - `frontend/src/components/backtest/AlgorithmReplay.tsx`: Historical algorithm decision path visualization
    - `frontend/src/components/backtest/TechnicalIndicatorCharts.tsx`: Historical technical indicator visualization
    - `frontend/src/pages/Backtesting.tsx`: Comprehensive backtesting interface
    - `backend/app/tasks/backtest_tasks.py`: Background Celery tasks for backtesting
    - `frontend/src/graphql/mutations/backtest.graphql`: Backtesting GraphQL mutations
    - `backend/tests/test_backtest_engine.py`: Comprehensive backtesting accuracy testing with real symphonies
    - `frontend/cypress/e2e/backtesting-workflow.cy.ts`: End-to-end backtesting testing
  - **Step Dependencies**: Step 14
  - **User Instructions**: The backtesting engine must simulate the complete algorithmic decision tree shown in `sample-symphonies/sample-symphony.json`, including all conditional logic, technical indicators, and dynamic asset selection. Historical data should cover from BIL inception (2007) to present.

- [ ] Step 16: OAuth Connection Flow UI
  - **Task**: Implement Alpaca paper trading account connection interface with OAuth flow
  - **Files**:
    - `frontend/src/components/auth/AlpacaConnect.tsx`: OAuth connection component (paper trading only)
    - `frontend/src/components/auth/OAuthCallback.tsx`: OAuth callback handler
    - `frontend/src/pages/Settings.tsx`: User settings and account management
    - `frontend/src/hooks/useAlpacaAuth.ts`: Alpaca OAuth hooks with GraphQL
    - `frontend/src/graphql/mutations/alpaca-auth.graphql`: Alpaca OAuth GraphQL mutations
    - `frontend/src/__tests__/AlpacaOAuth.test.tsx`: OAuth flow behavioral testing
  - **Step Dependencies**: Step 15
  - **User Instructions**: None

## Testing & Deployment

- [ ] Step 17: Comprehensive Testing Suite
  - **Task**: Implement unit tests, integration tests, and E2E tests for core functionality
  - **Files**:
    - `backend/tests/test_auth.py`: Authentication tests with pytest
    - `backend/tests/test_symphony.py`: Symphony management and algorithm execution tests
    - `backend/tests/test_trading.py`: Trading operations tests
    - `backend/tests/test_algorithms.py`: Algorithm execution and technical indicator tests
    - `backend/tests/test_daily_execution.py`: Daily execution timing tests (15:50-16:00 EST)
    - `backend/tests/test_error_handling.py`: Liquidation on error tests
    - `frontend/src/__tests__/Dashboard.test.tsx`: Dashboard component tests
    - `frontend/src/__tests__/Symphony.test.tsx`: Symphony UI tests
    - `tests/e2e/trading-flow.spec.ts`: End-to-end trading tests with Playwright
    - `backend/pytest.ini`: Pytest configuration
    - `frontend/jest.config.js`: Jest testing configuration for frontend
    - `playwright.config.ts`: E2E testing configuration
    - `backend/conftest.py`: Pytest fixtures and test configuration
  - **Step Dependencies**: Step 16
  - **User Instructions**: Run `cd backend && pytest` for Python tests and `cd frontend && npm run test` for frontend tests

- [ ] Step 18: Production Deployment and Monitoring
  - **Task**: Set up Kubernetes deployment, monitoring, and CI/CD pipeline
  - **Files**:
    - `k8s/backend-deployment.yaml`: Python FastAPI Kubernetes deployment
    - `k8s/frontend-deployment.yaml`: React frontend Kubernetes deployment  
    - `k8s/database-statefulset.yaml`: PostgreSQL + TimescaleDB StatefulSet configuration
    - `k8s/redis-deployment.yaml`: Redis deployment for Celery tasks
    - `k8s/celery-worker-deployment.yaml`: Celery worker deployment (scaled for 1,600 daily executions)
    - `k8s/celery-beat-deployment.yaml`: Celery Beat scheduler for 15:50 EST daily execution
    - `k8s/ingress.yaml`: Load balancer and SSL configuration
    - `k8s/config-secret.yaml`: .env file mounting as Kubernetes secret
    - `.github/workflows/deploy.yml`: CI/CD pipeline configuration with Python testing
    - `docker/docker-compose.prod.yml`: Production Docker Compose with .env.production
    - `monitoring/prometheus.yml`: Metrics collection configuration
    - `monitoring/grafana-dashboard.json`: Performance monitoring dashboard
  - **Step Dependencies**: Step 17
  - **User Instructions**: Configure cloud provider access and copy `.env.production` template, then deploy to Kubernetes cluster

## Final Configuration & Launch

- [ ] Step 19: Environment Configuration and Launch Preparation
  - **Task**: Finalize production configurations, security settings, and launch checklist
  - **Files**:
    - `docs/deployment-guide.md`: Production deployment documentation
    - `docs/api-documentation.md`: GraphQL API documentation
    - `docs/user-guide.md`: End-user documentation
    - `docs/algorithm-guide.md`: Symphony algorithm complexity guide
    - `scripts/production-setup.sh`: Production environment setup script
    - `scripts/health-check.sh`: Application health monitoring script
    - `scripts/daily-execution-monitor.sh`: Daily execution window monitoring
  - **Step Dependencies**: Step 18
  - **User Instructions**: Review security checklist, configure production `.env.production` file with secure secrets, set up market data API keys, and perform final testing before launch

---

### Summary & Implementation Approach

This implementation plan provides a systematic approach to building Oragami Composer with 19 distinct steps, each focusing on a specific aspect of the application. The plan emphasizes:

**Key Implementation Strategy:**
- **Python-First Architecture**: FastAPI + Strawberry GraphQL for quantitative computing power
- **Daily Execution Window**: Precise timing at 15:50-16:00 EST for all symphonies
- **Error Resilience**: Automatic liquidation to cash on algorithm failures
- **Market Data Optimization**: $100/month budget with Alpha Vantage + EOD Historical Data
- **Symphony Limits**: Initial cap of 40 symphonies per user
- **Historical Depth**: Backtesting from 2007 (BIL inception) to present
- **Paper Trading Only**: No live trading capability, Alpaca paper trading API only

**Major Technical Milestones:**
1. **Steps 1-5**: Foundation (Python setup, database, authentication, GraphQL)
2. **Steps 6-8**: Core Algorithm Engine (symphony parsing, market data, trading)
3. **Steps 9-10**: Real-time capabilities (daily scheduler, subscriptions)
4. **Steps 11-13**: Frontend foundation (React UI, real-time integration)
5. **Steps 14-16**: Advanced features (analytics, backtesting, OAuth UI)
6. **Steps 17-19**: Production deployment (testing, monitoring, launch)

**Estimated Timeline**: 8 weeks for full implementation with dedicated development resources, with core trading functionality available after steps 1-13 (5-6 weeks).

**Daily Execution Architecture**: 
- 40 users × 40 symphonies = 1,600 potential daily executions
- 10-minute execution window (15:50-16:00 EST)
- Parallel processing with 8-12 Celery workers
- Pre-fetched market data for optimal performance
- Automatic error handling with cash liquidation

The plan maintains focus on reliability, scalability, and precise algorithmic execution while respecting the $100/month market data budget constraint.
