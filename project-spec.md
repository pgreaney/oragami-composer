# Oragami Composer

A cloud-hosted, multi-tenant paper trading application that executes Composer.trade algorithmic strategies using Alpaca's paper trading API with real-time performance tracking and backtesting capabilities.

## Target Audience

Power users and algorithmic traders who want to test Composer.trade symphonies with real market data without risking actual capital, while having the ability to compare live performance against backtested results.

## Desired Features

### User Management
- [ ] Multi-tenant architecture supporting multiple users
- [ ] User registration and secure authentication
- [ ] Alpaca OAuth 2.0 integration for seamless paper trading account connection
- [ ] User-specific symphony and performance data isolation

### Symphony Management
- [ ] JSON file upload system for Composer.trade symphonies
- [ ] Symphony validation and parsing engine
- [ ] Symphony library for storing inactive strategies (initial limit: 40 per user)
- [ ] Start/stop controls for active symphonies
- [ ] Symphony status tracking (active, inactive, stopped)
- [ ] Read-only symphony display (no modifications allowed)

### Paper Trading Engine
- [ ] Alpaca paper trading API integration for execution only (no live trading)
- [ ] Automated trade execution based on symphony algorithms
- [ ] Daily evaluation window at 15:50-16:00 EST with sophisticated rebalancing logic:
  - [ ] Time-based rebalancing: Execute trades on schedule (daily, weekly, monthly, quarterly, yearly)
  - [ ] Threshold-based rebalancing: Execute trades only when portfolio drift exceeds configured corridor width (e.g., 7.5%)
- [ ] Real-time position tracking and updates
- [ ] Support for equities and ETFs (no options)
- [ ] Multiple symphonies per user account management (up to 40)
- [ ] Portfolio drift calculation engine for threshold-based symphonies
- [ ] Error handling with automatic liquidation to cash on algorithm failures

### Performance Analytics
- [ ] Real-time portfolio positions by symphony
- [ ] Cumulative returns and daily P&L tracking
- [ ] Standard quantstats metrics (Sharpe Ratio, Maximum Drawdown, Volatility, Win Rate, Sortino Ratio, Calmar Ratio)
- [ ] Historical performance data storage and retrieval
- [ ] Live vs. Backtest performance comparisons

### Backtesting Capabilities
- [ ] Historical market data integration for algorithm simulation (2007-present)
- [ ] Backtest execution engine for complex algorithmic symphonies with full conditional logic
- [ ] Performance comparison tools (live vs. backtest) with statistical analysis
- [ ] Historical data visualization and technical indicator backtesting
- [ ] Algorithm decision tree replay for understanding historical execution paths

## Design Requests

### Technical Architecture
- [ ] Cloud-native architecture optimized for cost efficiency and horizontal scaling
- [ ] Container-based deployment for easy scaling
- [ ] Auto-scaling capabilities based on user load (supporting 40 users × 40 symphonies = 1,600 daily executions)

### User Interface & Experience
- [ ] Responsive web interface optimized for desktop and mobile
- [ ] Real-time updating charts and performance metrics without page refreshes
- [ ] Clean, professional trading dashboard aesthetic with dark/light mode support
- [ ] Intuitive symphony upload and management workflow with drag-and-drop
- [ ] Fast loading times and smooth interactions (sub-second response times)
- [ ] Clear visual hierarchy for complex financial data presentation
- [ ] Interactive charts with zoom, pan, and time-range selection
- [ ] Status indicators and progress feedback for all user actions
- [ ] Error states with helpful guidance and recovery options (including liquidation notifications)
- [ ] Accessible design following WCAG 2.1 guidelines

## Other Notes

- Sample Composer.trade symphony JSON files will be provided during development showing full algorithmic complexity
- Symphony evaluation occurs daily within the 15:50-16:00 EST window (closer to end time is better)
- Actual rebalancing is determined by each symphony's configuration:
  - Time-based: Rebalance on fixed schedule (daily, weekly, monthly, quarterly, yearly)
  - Threshold-based: Rebalance only when portfolio drift exceeds configured percentage
- No modification of symphonies allowed - users must edit in Composer.trade to preserve algorithmic integrity
- Symphonies contain complex conditional logic, technical indicators, and asset selection algorithms that must be executed precisely
- Emphasis on reliable daily execution within the specified time window
- Integration with GitHub for version control and CI/CD
- Python FastAPI + Strawberry GraphQL backend for quantitative computing power
- Market data budget: $100/month (Alpha Vantage Premium + EOD Historical Data)
- Users provide their own Alpaca paper trading account credentials
- No alerts/notifications for significant changes required (except liquidation events)
- Secure API key management for user Alpaca accounts required
- Rate limiting and API quota management needed
- Historical data requirement: Back to at least 2007 (BIL ETF inception)
- Error handling strategy: Algorithm failures result in immediate liquidation to cash positions
