# Fullon Master API - Examples

**Comprehensive examples demonstrating all API functionality.**

## 📋 Available Examples

### Basic Operations
- **`example_health_check.py`** - Verify API is running and healthy
- **`example_start_server.py`** - Start the API server programmatically
- **`example_swagger_docs.py`** - Access and explore API documentation

### Authentication
- **`example_jwt_login.py`** - Login and get JWT token
- **`example_authenticated_request.py`** - Make authenticated API calls with JWT

### API Routes (Composed)
- **`example_orm_routes.py`** - User, bot, exchange, order management (from fullon_orm_api)
- **`example_ohlcv_routes.py`** - OHLCV/candlestick data, trades (from fullon_ohlcv_api)
- **`example_cache_websocket.py`** - Real-time WebSocket streaming (from fullon_cache_api)

### Test Suite
- **`run_all_examples.py`** - Run all examples in sequence
- **`run_example_pipeline.py`** - Full integration test (database setup + server + examples)
- **`demo_data.py`** - Database setup utilities for isolated testing

## 🚀 Quick Start

### Option 1: Full Automated Pipeline (Recommended)

```bash
# Complete integration test with isolated database
python examples/run_example_pipeline.py

# Skip WebSocket tests for faster execution
python examples/run_example_pipeline.py --skip-websocket
```

**What it does:**
- Creates isolated test databases (ORM + OHLCV)
- Installs demo data (users, exchanges, symbols, bots)
- Starts API server automatically
- Runs all examples
- Cleans up everything

### Option 2: Manual Server Testing

### Run Individual Example

```bash
# Check if API is running
python examples/example_health_check.py

# View API documentation
python examples/example_swagger_docs.py --open-browser

# Test JWT authentication
python examples/example_jwt_login.py --username admin --password admin

# Test WebSocket streaming
python examples/example_cache_websocket.py --stream tickers --duration 10
```

### Run All Examples

```bash
# Make sure server is running first
make run

# In another terminal:
python examples/run_all_examples.py

# Skip long-running WebSocket test
python examples/run_all_examples.py --skip-websocket
```

## 📖 Example Details

### 1. Health Check
```bash
python examples/example_health_check.py
```
**What it does:**
- Verifies server is running
- Checks `/health` endpoint
- Shows API version and status

**Expected output:**
```
✅ API Health Check:
   Status: healthy
   Version: 1.0.0
   Service: fullon_master_api
```

---

### 2. Start Server
```bash
python examples/example_start_server.py

# With custom options
python examples/example_start_server.py --port 8080 --reload
```
**What it does:**
- Starts uvicorn server programmatically
- Shows server configuration
- Displays documentation URLs

---

### 3. Swagger Documentation
```bash
python examples/example_swagger_docs.py

# Open browser automatically
python examples/example_swagger_docs.py --open-browser
```
**What it does:**
- Fetches OpenAPI schema
- Lists all available endpoints
- Shows API categories and tags
- Optionally opens browser to Swagger UI

---

### 4. JWT Login
```bash
python examples/example_jwt_login.py

# With custom credentials
python examples/example_jwt_login.py --username user --password pass
```
**What it does:**
- Authenticates user credentials
- Receives JWT access token
- Verifies token validity
- Shows token usage pattern

---

### 5. Authenticated Requests
```bash
python examples/example_authenticated_request.py
```
**What it does:**
- Demonstrates APIClient class
- Shows proper token management
- Makes authenticated requests
- Handles 401 errors

**Demonstrates:**
- User info endpoints
- Bot management
- Error handling patterns

---

### 6. ORM Routes
```bash
python examples/example_orm_routes.py
```
**What it does:**
- User management (list, create)
- Bot management (list, create)
- Order creation (⚠️ uses 'volume' not 'amount')

**Key Points:**
- ORM endpoints accept JSON (converted to ORM models)
- ALWAYS use `volume` field for orders
- All write operations require authentication

---

### 7. OHLCV Routes
```bash
python examples/example_ohlcv_routes.py
```
**What it does:**
- Fetches OHLCV candlestick data
- Retrieves raw trade data
- Time-range queries
- Multiple timeframes (1m, 5m, 1h, 1d)

**Data format:**
```python
[timestamp, open, high, low, close, volume]
```

---

### 8. Cache WebSocket
```bash
# Ticker stream
python examples/example_cache_websocket.py --stream tickers --duration 10

# Trade stream
python examples/example_cache_websocket.py --stream trades --symbol BTC/USDT

# Order queue
python examples/example_cache_websocket.py --stream orders --exchange binance

# Balance updates
python examples/example_cache_websocket.py --stream balances --exchange-id 1
```
**What it does:**
- Real-time ticker data streaming
- Live trade updates
- Order queue monitoring
- Account balance updates

**WebSocket URLs:**
- `ws://localhost:8000/ws/tickers/{exchange}/{symbol}`
- `ws://localhost:8000/ws/trades/{exchange}/{symbol}`
- `ws://localhost:8000/ws/orders/{exchange}`
- `ws://localhost:8000/ws/balances/{exchange_id}`

---

## 🧪 Database Setup for Testing

### Isolated Test Environment

The examples support running with isolated test databases, following the same pattern as `fullon_ohlcv_service`:

```bash
# Setup test database with demo data
python examples/demo_data.py --setup

# Run examples against test database
python examples/run_all_examples.py

# Cleanup test database
python examples/demo_data.py --cleanup <database_name>
```

### Demo Data Includes:
- **Admin user** - `admin@fullon` / `password`
- **3 exchanges** - Kraken, BitMEX, Hyperliquid
- **3 symbols** - BTC/USDC, BTC/USD:BTC, BTC/USDC:USDC
- **3 bots** - RSI Long, RSI Short, LLM Trader
- **Strategies & Feeds** - Complete bot configuration

### Environment Variables:
```bash
# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=fullon_orm              # Main ORM database
DB_OHLCV_NAME=fullon_ohlcv      # OHLCV timeseries database

# Admin user
ADMIN_MAIL=admin@fullon

# Redis cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## 🔧 Development Workflow

### Option A: Automated Testing (Recommended)
```bash
# Full pipeline with isolated databases
python examples/run_example_pipeline.py
```

### Option B: Manual Testing
```bash
# 1. Start Server
make run

# 2. Verify Health
python examples/example_health_check.py

# 3. Explore API
python examples/example_swagger_docs.py --open-browser

# 4. Test Functionality
python examples/run_all_examples.py
```

## 💡 Tips

- **Use automated pipeline** - `run_example_pipeline.py` handles everything
- **Isolated testing** - Each test run uses fresh database
- **Always check health first** - Ensure server is running
- **Use Swagger UI** - Interactive API testing at `/docs`
- **Check logs** - Examples use fullon_log for detailed logging
- **Examples are self-contained** - Each can run independently
- **Expected failures** - Some endpoints return 404 during development
- **Demo data** - Pre-configured users, bots, exchanges for testing

## ⚠️ Common Issues

### Connection Refused
```
❌ Connection Failed
   Server not running on http://localhost:8000
```
**Solution:** Start the server with `make run`

### 404 Not Found
```
❌ Login endpoint not found (not implemented yet)
   Expected endpoint: POST /api/v1/auth/login
```
**This is normal!** - Endpoints are implemented progressively across phases

### Import Errors
```
ModuleNotFoundError: No module named 'fullon_log'
```
**Solution:** Install dependencies with `poetry install`

## 📚 Next Steps

After running examples:
1. Review Swagger UI at http://localhost:8000/docs
2. Check API logs for detailed request/response info
3. Modify examples to test custom scenarios
4. Use examples as templates for your own code

## 🤝 Contributing

When adding new functionality:
1. **Create example FIRST** (examples-driven development)
2. Ensure example demonstrates all new endpoints
3. Update this README with usage instructions
4. Add example to `run_all_examples.py`

---

**Examples demonstrate expected behavior - use them as contracts for implementation!**
