# Origami Composer

A cloud-hosted, multi-tenant paper trading application that executes Composer.trade algorithmic strategies using Alpaca's paper trading API with real-time performance tracking and backtesting capabilities.

## 🚀 Project Overview

Origami Composer allows users to:
- Upload and manage Composer.trade symphony JSON files
- Execute automated paper trades based on algorithmic strategies
- Track real-time performance with quantstats metrics
- Compare live performance against backtested results
- Manage up to 40 symphonies per user account

## 🏗️ Architecture

- **Backend**: Python 3.11+ with FastAPI and Strawberry GraphQL
- **Frontend**: React 18+ with TypeScript and Apollo Client
- **Database**: PostgreSQL 14+ with TimescaleDB extension
- **Task Queue**: Celery with Redis for background processing
- **Trading**: Alpaca Paper Trading API (OAuth 2.0)
- **Deployment**: Docker containers with Kubernetes orchestration

## 📋 Prerequisites

- Python 3.11+
- Node.js 20+
- Docker and Docker Compose
- PostgreSQL 14+
- Redis 7+

## 🛠️ Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/pgreaney/oragami-composer.git
cd oragami-composer
```

### 2. Environment Configuration
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API credentials:
# - ALPACA_CLIENT_ID (from Alpaca OAuth app)
# - ALPACA_CLIENT_SECRET (from Alpaca OAuth app)
# - ALPHA_VANTAGE_API_KEY (for market data)
# - EOD_HISTORICAL_API_KEY (for historical data)
```

⚠️ **Security Note**: Never commit `.env` files with real credentials. See [Security Best Practices](docs/security-best-practices.md) for production deployment.

### 3. Start Development Environment
```bash
# Start all services with Docker Compose
docker-compose up -d

# Verify services are running
docker-compose ps
```

Services will be available at:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### 4. Install Dependencies (Optional for local development)

#### Backend
```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### Frontend
```bash
cd frontend
npm install
```

### 5. Initialize Database
```bash
# Run database migrations
cd backend
alembic upgrade head

# Initialize TimescaleDB extensions
python -m app.database.init_db
```

## 🏃‍♂️ Running the Application

### Using Docker (Recommended)
```bash
docker-compose up
```

### Local Development
```bash
# Terminal 1: Start backend
cd backend
uvicorn app.main:app --reload

# Terminal 2: Start Celery worker
cd backend
celery -A app.celery_app worker --loglevel=info

# Terminal 3: Start Celery beat scheduler
cd backend
celery -A app.celery_app beat --loglevel=info

# Terminal 4: Start frontend
cd frontend
npm run dev
```

## 📊 Key Features

### Symphony Management
- Upload Composer.trade JSON files
- Validate and parse complex algorithmic strategies
- Support for conditional logic, technical indicators, and asset filtering
- Manage up to 40 symphonies per user

### Paper Trading Engine
- Automated execution via Alpaca Paper Trading API
- Daily rebalancing at 15:50-16:00 EST
- Real-time position tracking
- Error handling with automatic liquidation to cash

### Performance Analytics
- Real-time portfolio tracking
- Quantstats metrics (Sharpe Ratio, Max Drawdown, etc.)
- Historical performance comparisons
- GraphQL subscriptions for live updates

### Backtesting
- Historical data from 2007 to present
- Full algorithm simulation with decision tree execution
- Side-by-side comparison with live performance
- Technical indicator calculations on historical data

## 🔌 API Access

### GraphQL Endpoint
- URL: `http://localhost:8000/graphql`
- GraphiQL UI: `http://localhost:8000/graphql` (development only)

### Authentication
- Register/Login via GraphQL mutations
- JWT tokens for API access
- Alpaca OAuth for paper trading connection

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# End-to-end tests
npm run e2e
```

## 📚 Documentation

- [Project Specification](project-spec.md)
- [Technical Specification](technical-spec.md)
- [Implementation Plan](implementation-plan.md)
- [Security Best Practices](docs/security-best-practices.md)
- [API Documentation](docs/api-documentation.md) (coming soon)
- [User Guide](docs/user-guide.md) (coming soon)

## 🔒 Security

- OAuth 2.0 integration with Alpaca
- JWT-based authentication
- Encrypted storage of OAuth tokens
- See [Security Best Practices](docs/security-best-practices.md) for production deployment

## 🤝 Contributing

1. Create a feature branch from `main`
2. Make your changes with descriptive commits
3. Ensure all tests pass
4. Submit a pull request with detailed description
5. Update README with relevant information

### Commit Guidelines
- Use descriptive commit messages
- Include extensive details in commit summaries
- Reference issue numbers when applicable

### Code Style
- Python: Black formatter, Flake8 linter
- TypeScript: ESLint with Prettier
- Document all functions with docstrings/comments

## 📝 License

[License information to be added]

## 🚧 Current Status

### ✅ Completed (Steps 1-8)
- [x] Step 1: Project structure and development environment setup
- [x] Step 2: Database schema and SQLAlchemy setup with TimescaleDB
- [x] Step 3: JWT authentication system
- [x] Step 4: Alpaca OAuth 2.0 integration (paper trading)
- [x] Step 5: GraphQL API setup with Strawberry
- [x] Step 6: Symphony algorithmic management with complex JSON parsing
- [x] Step 7: Market data integration (Alpha Vantage + EOD Historical)
- [x] Step 8: Trading operations GraphQL API with Alpaca integration

### 🔄 In Progress
- [ ] Step 9: Daily Algorithmic Execution & Background Processing
- [ ] Step 10: Real-time GraphQL Subscriptions

### 📅 Upcoming
- [ ] Step 11-19: Frontend development, analytics, backtesting, and deployment
- See [Implementation Plan](implementation-plan.md) for full roadmap

## 🏛️ Backend Architecture

### Core Components
- **Authentication**: JWT-based auth with secure password hashing
- **GraphQL API**: Type-safe API with Strawberry GraphQL
- **Symphony Parser**: Complex JSON parsing for Composer.trade algorithms
- **Market Data Service**: Dual-source integration with intelligent caching
- **Trading Service**: Position management and trade execution
- **Error Handler**: Automatic liquidation on algorithm failures

### Key Technologies
- **FastAPI**: High-performance async web framework
- **SQLAlchemy**: ORM with TimescaleDB support
- **Strawberry GraphQL**: Modern Python GraphQL library
- **Redis**: Caching and task queue broker
- **Celery**: Distributed task processing

## 📞 Support

[Support information to be added]

---

Built with ❤️ for algorithmic traders who want to test their strategies without risking capital.
