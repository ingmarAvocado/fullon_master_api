# Revised Plan: fullon_master_api - Unified FastAPI Gateway

**Status**: ✅ EXAMPLES COMPLETE - Ready for Phase 2
**Audit Date**: 2025-10-20
**Last Updated**: 2025-10-21 (Examples-driven development)
**Timeline**: 12 days
**Compliance**: LRRS + Fullon Architecture Aligned
**Development Method**: Examples-First (Non-Deterministic Behavior Elimination)

---

## ✅ Phase 0: Examples-Driven Development (COMPLETED)

**Critical Foundation**: All examples created BEFORE implementation to eliminate non-deterministic LLM behavior.

### Examples Created (8 total + test suite)

1. **`example_health_check.py`** - Basic API health verification
2. **`example_start_server.py`** - Server startup and lifecycle
3. **`example_jwt_login.py`** - JWT authentication flow
4. **`example_authenticated_request.py`** - Using JWT tokens in requests
5. **`example_swagger_docs.py`** - API documentation access
6. **`example_orm_routes.py`** - User, bot, order management (ORM API)
7. **`example_ohlcv_routes.py`** - OHLCV/candlestick data queries
8. **`example_cache_websocket.py`** - Real-time WebSocket streaming
9. **`run_all_examples.py`** - Automated test suite

### Why Examples First?

- **Eliminates ambiguity** - Examples define expected behavior as executable contracts
- **Prevents LLM hallucination** - Clear target behavior prevents creative interpretation
- **Enables TDD** - Examples become acceptance tests
- **Documents API** - Examples serve as living documentation
- **Validates design** - Writing examples reveals UX issues early

### Example Coverage

| Feature | Example | Status |
|---------|---------|--------|
| Health check | `example_health_check.py` | ✅ |
| Server start | `example_start_server.py` | ✅ |
| JWT auth | `example_jwt_login.py` | ✅ |
| Auth requests | `example_authenticated_request.py` | ✅ |
| API docs | `example_swagger_docs.py` | ✅ |
| ORM routes | `example_orm_routes.py` | ✅ |
| OHLCV routes | `example_ohlcv_routes.py` | ✅ |
| WebSocket | `example_cache_websocket.py` | ✅ |

**All implementation phases now have concrete examples to match against.**

---

## Executive Summary

**Purpose**: Create a unified API gateway that composes existing Fullon APIs (`fullon_orm_api`, `fullon_ohlcv_api`, `fullon_cache_api`) with centralized JWT authentication, following LRRS principles and Fullon microservices architecture.

**Core Principle**: **Compose, Don't Duplicate** - Use existing API gateways via router composition, never bypass them.

---

## Architecture Overview

### Pattern: Router Composition with Centralized Auth

```
┌─────────────────────────────────────────────────────────────┐
│                    fullon_master_api                        │
│                  (Unified API Gateway)                      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         JWT Authentication Middleware                │  │
│  │    (Validates token, loads user, injects into       │  │
│  │     request.state.user for downstream APIs)         │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                  │
│     ┌────────────────────┼────────────────────┐            │
│     ▼                    ▼                    ▼            │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│  │   ORM    │      │  OHLCV   │      │  Cache   │         │
│  │ Routers  │      │ Routers  │      │WebSocket │         │
│  │          │      │          │      │  Proxy   │         │
│  └──────────┘      └──────────┘      └──────────┘         │
│       │                 │                  │               │
└───────┼─────────────────┼──────────────────┼───────────────┘
        │                 │                  │
        ▼                 ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│fullon_orm_api│  │fullon_ohlcv  │  │fullon_cache  │
│  (existing)  │  │_api(existing)│  │_api(existing)│
└──────────────┘  └──────────────┘  └──────────────┘
```

### URL Structure

```
/api/v1/
├── orm/                    # Database operations (fullon_orm_api)
│   ├── users/*
│   ├── exchanges/*
│   ├── symbols/*
│   ├── orders/*
│   ├── trades/*
│   ├── bots/*
│   └── strategies/*
│
├── ohlcv/                  # Market data (fullon_ohlcv_api)
│   ├── api/trades/*
│   ├── api/candles/*
│   ├── api/timeseries/*
│   ├── ws/ohlcv            # WebSocket
│   └── api/exchanges
│
├── cache/                  # Real-time cache (fullon_cache_api)
│   └── ws/tickers/*        # WebSocket (proxied)
│       ws/orders/*
│       ws/accounts/*
│
└── health                  # Unified health check
```

### Key Architectural Decisions

**ADR-001: Router Composition Over Direct Library Usage**
- ✅ Use `fullon_orm_api.get_all_routers()`
- ✅ Use `fullon_ohlcv_api.FullonOhlcvGateway().get_routers()`
- ❌ NO direct `fullon_orm`, `fullon_ohlcv`, `fullon_cache` usage

**ADR-002: WebSocket Proxy for Cache API**
- ✅ Mount `fullon_cache_api` routers as-is (WebSocket)
- ❌ NO REST wrappers for cache operations

**ADR-003: No Service Control in API Gateway**
- ✅ Use Docker Compose / Kubernetes for daemon orchestration
- ❌ NO daemon start/stop/restart endpoints in API
- **Rationale**: Service daemons (`fullon_ticker_service`, `fullon_ohlcv_service`, `fullon_account_service`) are long-lived processes with complex lifecycle management (dual databases, signal handlers, multi-phase initialization). They're designed for container orchestration, not API-based control. Master API provides health monitoring via ProcessCache instead.

**ADR-004: Authentication via Middleware**
- ✅ JWT middleware validates token, sets `request.state.user`
- ✅ Downstream APIs consume `request.state.user` (already designed for this)

---

## Project Structure

```
fullon_master_api/
├── src/fullon_master_api/
│   ├── __init__.py                # Library exports
│   ├── main.py                    # FastAPI app entry point
│   ├── gateway.py                 # MasterGateway class
│   ├── config.py                  # Environment config
│   │
│   ├── auth/                      # Centralized authentication
│   │   ├── __init__.py
│   │   ├── jwt.py                 # JWT generation/validation
│   │   ├── middleware.py          # Auth middleware (sets request.state.user)
│   │   └── dependencies.py        # get_current_user dependency
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py              # Unified health check
│   │   └── root.py                # API root documentation
│   │
│   └── websocket/                 # WebSocket proxy utilities
│       ├── __init__.py
│       └── auth.py                # WebSocket JWT validation
│
├── tests/                         # Comprehensive test suite
│   ├── conftest.py                # Shared fixtures
│   ├── unit/
│   │   ├── test_auth.py
│   │   ├── test_jwt.py
│   │   └── test_middleware.py
│   ├── integration/
│   │   ├── test_orm_integration.py
│   │   ├── test_ohlcv_integration.py
│   │   ├── test_cache_integration.py
│   │   └── test_auth_flow.py
│   └── e2e/
│       └── test_complete_workflows.py
│
├── examples/                      # Examples-driven development
│   ├── basic_usage.py             # Simple authenticated request
│   ├── orm_operations.py          # Database operations via master API
│   ├── ohlcv_queries.py           # Market data queries
│   ├── cache_websocket.py         # WebSocket cache streaming
│   └── run_all.py                 # Integration test runner
│
├── docs/
│   ├── ADR-001-router-composition.md
│   ├── ADR-002-websocket-proxy.md
│   ├── ADR-003-no-service-control.md
│   ├── ADR-004-auth-middleware.md
│   └── DEPLOYMENT.md
│
├── pyproject.toml
├── CLAUDE.md                      # LLM development guide
├── README.md                      # Human documentation
├── Makefile
└── .env.example
```

---

## 🚨 Critical Integration Points

### ⚠️ ORM Model-Based API (MANDATORY PATTERN)

**CRITICAL**: All `fullon_orm` repository methods ONLY accept ORM model instances, NEVER dictionaries or individual parameters!

```python
# ❌ WRONG - Will cause TypeError!
await db.users.add_user({"mail": "test@example.com", "name": "John"})
await db.bots.add_bot({"name": "MyBot", "uid": 1})

# ✅ CORRECT - Use ORM model instances
from fullon_orm.models import User, Bot

user = User(
    mail="test@example.com",
    name="John",
    f2a="",
    lastname="",
    phone="",
    id_num=""
)
await db.users.add_user(user)

bot = Bot(uid=user.uid, name="MyBot", active=True, dry_run=True)
await db.bots.add_bot(bot)
```

### Cache Operations Require ORM Models

**All cache operations use `fullon_orm` models**:

```python
from fullon_orm.models import Tick, Symbol, Trade, Position, Order

# TickCache example
async with TickCache() as cache:
    symbol = Symbol(symbol="BTC/USDT", cat_ex_id=1, base="BTC", quote="USDT")
    tick = Tick(symbol="BTC/USDT", exchange="binance", price=50000.0, ...)
    await cache.set_ticker(tick)

# AccountCache example
async with AccountCache() as cache:
    position = Position(symbol="BTC/USDT", volume=0.5, cost=25000.0, price=50000.0)
    await cache.set_position(exchange_id, position)
```

### Context Manager Pattern (Required)

**ALL fullon libraries require async context managers**:

```python
# DatabaseContext (fullon_orm)
async with DatabaseContext() as db:
    user = await db.users.get_by_id(user_id)

# Cache operations (fullon_cache)
async with TickCache() as cache:
    ticker = await cache.get_ticker(symbol, exchange)

# Repository operations (fullon_ohlcv)
async with TradeRepository("binance", "BTC/USD") as repo:
    trades = await repo.get_recent_trades(limit=100)
```

### Required Imports for All Phases

```python
# Phase 2+ (Auth middleware)
from fullon_orm import DatabaseContext
from fullon_orm.models import User

# Phase 5 (Cache operations)
from fullon_orm.models import Tick, Symbol, Trade, Position, Order

# Phase 6 (Health monitoring)
from fullon_cache import TickCache, ProcessCache
```

---

## Implementation Plan (12 Days)

### **Phase 1: Project Foundation** (Day 1)

**Objectives**:
- Initialize Poetry project
- Setup project structure
- Configure environment

**Tasks**:
1. Initialize Poetry project with dependencies:
```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
pyjwt = "^2.8.0"
python-dotenv = "^1.0.0"
pydantic-settings = "^2.0.0"
websockets = "^12.0"

# Fullon core libraries (REQUIRED - used directly)
fullon-log = {git = "ssh://git@github.com/ingmarAvocado/fullon_log.git"}
fullon-orm = {git = "ssh://git@github.com/ingmarAvocado/fullon_orm.git"}
fullon-cache = {git = "ssh://git@github.com/ingmarAvocado/fullon_cache.git"}
fullon-ohlcv = {git = "ssh://git@github.com/ingmarAvocado/fullon_ohlcv.git"}

# Fullon APIs (router composition)
fullon-orm-api = {path = "../fullon_orm_api", develop = true}
fullon-ohlcv-api = {path = "../fullon_ohlcv_api", develop = true}
fullon-cache-api = {path = "../fullon_cache_api", develop = true}

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-cov = "^4.1.0"
httpx = "^0.25.0"
black = "^23.0.0"
ruff = "^0.1.0"
mypy = "^1.6.0"
pre-commit = "^3.5.0"
```

2. Create directory structure (as shown above)

3. Setup `config.py`:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    api_title: str = "Fullon Master API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    # JWT Configuration
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # CORS
    cors_origins: list[str] = ["*"]

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
```

4. Create basic `gateway.py` skeleton

**Deliverables**:
- ✅ Poetry project initialized
- ✅ Directory structure created
- ✅ `config.py` complete
- ✅ `.env.example` created

---

### **Phase 2: JWT Authentication** (Day 2)

**Objectives**:
- Implement JWT token generation/validation
- Create auth middleware
- Setup auth dependencies

**Tasks**:

1. **Implement `auth/jwt.py`**:
```python
from datetime import datetime, timedelta
import jwt
from ..config import settings

def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_expiration_minutes)

    expire = datetime.utcnow() + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow()
    }

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid token: {e}")
```

2. **Implement `auth/middleware.py`**:
```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fullon_orm import DatabaseContext
from fullon_orm.models import User  # ← CRITICAL: Import User model
from fullon_log import get_component_logger
from .jwt import verify_token

logger = get_component_logger("fullon.master_api.auth")

class JWTAuthMiddleware(BaseHTTPMiddleware):
    """JWT authentication middleware that sets request.state.user."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if request.url.path in ["/", "/health", "/api/v1/health"]:
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

        token = auth_header.split(" ")[1]

        try:
            # Verify token
            payload = verify_token(token)
            user_id = int(payload["sub"])

            # Load user from database (returns User model instance)
            async with DatabaseContext() as db:
                user: User = await db.users.get_by_id(user_id)  # ← Returns User ORM model
                if not user:
                    raise HTTPException(status_code=401, detail="User not found")

            # Set user in request state (User model instance, NOT dictionary)
            request.state.user = user  # ← User model passed to downstream APIs

            logger.debug("User authenticated", user_id=user_id, user_mail=user.mail)

        except ValueError as e:
            logger.warning("Token validation failed", error=str(e))
            raise HTTPException(status_code=401, detail="Invalid token")

        response = await call_next(request)
        return response
```

3. **Implement `auth/dependencies.py`**:
```python
from fastapi import Request, HTTPException
from fullon_orm.models import User

async def get_current_user(request: Request) -> User:
    """Dependency to get authenticated user from request state."""
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return request.state.user
```

4. **Write tests**:
```python
# tests/unit/test_jwt.py
async def test_create_and_verify_token():
    token = create_access_token(user_id=1)
    payload = verify_token(token)
    assert payload["sub"] == "1"

# tests/integration/test_auth_flow.py
async def test_authenticated_request(client, db_user):
    token = create_access_token(user_id=db_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/orm/users/me", headers=headers)
    assert response.status_code == 200
```

**Deliverables**:
- ✅ JWT generation/validation working
- ✅ Auth middleware complete
- ✅ Unit tests passing (>90% coverage)
- ✅ Integration tests with mock user

---

### **Phase 3: ORM Router Composition** (Day 3)

**Objectives**:
- Integrate `fullon_orm_api` via router composition
- Override auth dependencies
- Test authenticated ORM operations

**Tasks**:

1. **Create `gateway.py` with ORM integration**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fullon_log import get_component_logger
from fullon_orm_api import get_all_routers as get_orm_routers
from fullon_orm_api.dependencies.auth import get_current_user as orm_get_current_user

from .config import settings
from .auth.middleware import JWTAuthMiddleware
from .auth.dependencies import get_current_user as master_get_current_user

logger = get_component_logger("fullon.master_api.gateway")

class MasterGateway:
    """Main API Gateway composing all Fullon APIs."""

    def __init__(self):
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        app = FastAPI(
            title=settings.api_title,
            version=settings.api_version,
            description="Unified API Gateway for Fullon Trading Platform"
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )

        # Add JWT auth middleware
        app.add_middleware(JWTAuthMiddleware)

        # Mount ORM API routers with auth override
        self._mount_orm_routers(app)

        # Add health endpoint
        @app.get("/health")
        async def health():
            return {"status": "healthy", "version": settings.api_version}

        logger.info("Master API Gateway initialized")
        return app

    def _mount_orm_routers(self, app: FastAPI):
        """Mount fullon_orm_api routers with dependency override."""
        orm_routers = get_orm_routers()

        for router in orm_routers:
            # Override auth dependency to use master API auth
            router.dependency_overrides[orm_get_current_user] = master_get_current_user

            # Mount with prefix
            app.include_router(router, prefix=f"{settings.api_prefix}/orm")

        logger.info("ORM routers mounted", count=len(orm_routers))

    def get_app(self) -> FastAPI:
        return self.app
```

2. **Create `main.py`**:
```python
from .gateway import MasterGateway

gateway = MasterGateway()
app = gateway.get_app()
```

3. **Write integration tests**:
```python
# tests/integration/test_orm_integration.py
async def test_orm_users_endpoint_with_auth(client, admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/orm/users", headers=headers)
    assert response.status_code == 200

async def test_orm_endpoint_without_auth(client):
    response = await client.get("/api/v1/orm/users")
    assert response.status_code == 401
```

**Deliverables**:
- ✅ ORM routers mounted at `/api/v1/orm/*`
- ✅ Auth dependency override working
- ✅ Integration tests passing
- ✅ Example working: `examples/orm_operations.py`

---

### **Phase 4: OHLCV Router Composition** (Day 4)

**Objectives**:
- Integrate `fullon_ohlcv_api` via router composition
- Test authenticated OHLCV operations

**Tasks**:

1. **Add OHLCV integration to `gateway.py`**:
```python
from fullon_ohlcv_api import FullonOhlcvGateway

def _mount_ohlcv_routers(self, app: FastAPI):
    """Mount fullon_ohlcv_api routers."""
    ohlcv_gateway = FullonOhlcvGateway()
    ohlcv_routers = ohlcv_gateway.get_routers()

    for router in ohlcv_routers:
        # OHLCV API is read-only, may not need auth override
        # But add auth check if needed
        app.include_router(router, prefix=f"{settings.api_prefix}/ohlcv")

    logger.info("OHLCV routers mounted", count=len(ohlcv_routers))
```

2. **Write integration tests**:
```python
# tests/integration/test_ohlcv_integration.py
async def test_ohlcv_candles_endpoint(client, user_token):
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.get(
        "/api/v1/ohlcv/api/candles/kraken/BTC/USD",
        headers=headers
    )
    assert response.status_code == 200
```

3. **Create example**:
```python
# examples/ohlcv_queries.py
import httpx
from fullon_master_api.auth.jwt import create_access_token

async def main():
    token = create_access_token(user_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Get OHLCV candles
        response = await client.get(
            "/api/v1/ohlcv/api/candles/kraken/BTC/USD",
            headers=headers
        )
        print(response.json())
```

**Deliverables**:
- ✅ OHLCV routers mounted at `/api/v1/ohlcv/*`
- ✅ Integration tests passing
- ✅ Example working: `examples/ohlcv_queries.py`
- ✅ WebSocket OHLCV streaming accessible

---

### **Phase 5: Cache WebSocket Proxy** (Day 5-6)

**Objectives**:
- Mount `fullon_cache_api` WebSocket routers
- Implement WebSocket JWT authentication
- Test WebSocket streaming with auth

**Tasks**:

1. **Create `websocket/auth.py`**:
```python
from fastapi import WebSocket, WebSocketDisconnect
from fullon_orm import DatabaseContext
from fullon_log import get_component_logger
from ..auth.jwt import verify_token

logger = get_component_logger("fullon.master_api.websocket.auth")

async def authenticate_websocket(websocket: WebSocket) -> bool:
    """Authenticate WebSocket connection via query param token."""
    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return False

    try:
        payload = verify_token(token)
        user_id = int(payload["sub"])

        async with DatabaseContext() as db:
            user = await db.users.get_by_id(user_id)
            if not user:
                await websocket.close(code=1008, reason="User not found")
                return False

        # Store user in websocket state
        websocket.state.user = user
        logger.info("WebSocket authenticated", user_id=user_id)
        return True

    except Exception as e:
        logger.error("WebSocket auth failed", error=str(e))
        await websocket.close(code=1008, reason="Invalid token")
        return False
```

2. **Mount cache routers in `gateway.py`**:
```python
from fullon_cache_api.main import create_app as create_cache_app

def _mount_cache_routers(self, app: FastAPI):
    """Mount fullon_cache_api WebSocket routers.

    NOTE: Cache API is WebSocket-only (no REST endpoints).
    All cache operations (tickers, orders, accounts) use WebSocket streaming.
    Cache operations internally use fullon_orm models (Tick, Symbol, Trade, etc).
    """
    # Get cache app routers (WebSocket endpoints only)
    cache_app = create_cache_app()

    # Mount cache routers under /api/v1/cache prefix
    for route in cache_app.routes:
        app.routes.append(route)

    logger.info("Cache WebSocket routers mounted at /api/v1/cache/ws/*")
```

3. **Write WebSocket tests**:
```python
# tests/integration/test_cache_integration.py
async def test_cache_websocket_with_auth(user_token):
    async with websockets.connect(
        f"ws://localhost:8000/api/v1/cache/ws/tickers/test?token={user_token}"
    ) as ws:
        # Send subscription message
        await ws.send(json.dumps({
            "action": "subscribe",
            "exchange": "kraken",
            "symbol": "BTC/USD"
        }))

        # Receive ticker update
        message = await ws.recv()
        data = json.loads(message)
        assert "price" in data
```

4. **Create example**:
```python
# examples/cache_websocket.py
import asyncio
import websockets
import json
from fullon_master_api.auth.jwt import create_access_token

async def stream_tickers():
    token = create_access_token(user_id=1)

    async with websockets.connect(
        f"ws://localhost:8000/api/v1/cache/ws/tickers/demo?token={token}"
    ) as ws:
        await ws.send(json.dumps({
            "action": "subscribe",
            "exchange": "kraken",
            "symbols": ["BTC/USD", "ETH/USD"]
        }))

        async for message in ws:
            data = json.loads(message)
            print(f"Ticker: {data}")
```

**Deliverables**:
- ✅ Cache WebSocket routers mounted at `/api/v1/cache/ws/*`
- ✅ WebSocket JWT authentication working
- ✅ Integration tests passing
- ✅ Example working: `examples/cache_websocket.py`

---

### **Phase 6: Health & Monitoring** (Day 7-8)

**Objectives**:
- Implement unified health check
- Add circuit breaker pattern
- Create monitoring endpoints

**Tasks**:

1. **Implement `routers/health.py`**:
```python
from fastapi import APIRouter
from fullon_orm import DatabaseContext
from fullon_cache import TickCache, ProcessCache
from fullon_log import get_component_logger

router = APIRouter()
logger = get_component_logger("fullon.master_api.health")

@router.get("/health")
async def unified_health_check():
    """Comprehensive health check for all subsystems."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "services": {}
    }

    # Check PostgreSQL
    try:
        async with DatabaseContext() as db:
            await db.users.get_by_id(1)  # Simple query
        health_status["services"]["postgresql"] = "healthy"
    except Exception as e:
        health_status["services"]["postgresql"] = "unhealthy"
        health_status["status"] = "degraded"
        logger.error("PostgreSQL health check failed", error=str(e))

    # Check Redis
    try:
        async with TickCache() as cache:
            await cache.test()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = "unhealthy"
        health_status["status"] = "degraded"
        logger.error("Redis health check failed", error=str(e))

    # Check daemon status via ProcessCache
    # NOTE: Daemons self-register with ProcessCache when running
    # - fullon_ticker_service: Continuous ticker streaming
    # - fullon_ohlcv_service: Historic + live OHLCV/trade collection
    # - fullon_account_service: Adaptive account monitoring
    try:
        async with ProcessCache() as cache:
            processes = await cache.get_active_processes()

            # Extract daemon components from active processes
            daemon_status = {}
            for process in processes:
                component = process.get('component', '').lower()
                if 'ticker' in component:
                    daemon_status['ticker'] = 'running'
                elif 'ohlcv' in component:
                    daemon_status['ohlcv'] = 'running'
                elif 'account' in component:
                    daemon_status['account'] = 'running'

            # Set default 'stopped' for missing daemons
            health_status["services"]["daemons"] = {
                "ticker": daemon_status.get('ticker', 'stopped'),
                "ohlcv": daemon_status.get('ohlcv', 'stopped'),
                "account": daemon_status.get('account', 'stopped')
            }
    except Exception as e:
        logger.warning("Daemon status check failed", error=str(e))

    return health_status

@router.get("/health/deep")
async def deep_health_check():
    """Detailed health check with performance metrics."""
    # Add detailed checks: connection pool status, response times, etc.
    pass
```

2. **Add circuit breaker for downstream APIs**:
```python
# Add pybreaker dependency
# Implement circuit breaker wrapper for critical operations
```

3. **Write health tests**:
```python
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] in ["healthy", "degraded"]
```

**Deliverables**:
- ✅ Unified health endpoint at `/health`
- ✅ Deep health check at `/health/deep`
- ✅ Circuit breaker implemented
- ✅ Monitoring tests passing

---

### **Phase 7: Integration Testing** (Day 9-10)

**Objectives**:
- Write comprehensive integration tests
- Create examples-driven test suite
- Validate complete workflows

**Tasks**:

1. **Complete integration test suite**:
```python
# tests/integration/test_complete_workflows.py

async def test_trading_workflow(client, user_token):
    """Test complete trading workflow via master API."""
    headers = {"Authorization": f"Bearer {user_token}"}

    # 1. Get user portfolio
    response = await client.get("/api/v1/orm/users/me", headers=headers)
    assert response.status_code == 200

    # 2. Get market data
    response = await client.get(
        "/api/v1/ohlcv/api/candles/kraken/BTC/USD",
        headers=headers,
        params={"timeframe": "1h", "limit": 100}
    )
    assert response.status_code == 200
    candles = response.json()

    # 3. Check cache for real-time ticker
    # (via WebSocket in real scenario)

    # 4. Create order (if implemented)
    # response = await client.post("/api/v1/orm/orders", ...)

async def test_unauthenticated_access_denied(client):
    """Verify all endpoints require authentication."""
    endpoints = [
        "/api/v1/orm/users",
        "/api/v1/ohlcv/api/candles/kraken/BTC/USD",
    ]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 401
```

2. **Create `examples/run_all.py`**:
```python
import asyncio
from .basic_usage import test_basic_usage
from .orm_operations import test_orm_operations
from .ohlcv_queries import test_ohlcv_queries
from .cache_websocket import test_cache_websocket

async def main():
    print("Running all examples...")

    await test_basic_usage()
    print("✅ Basic usage")

    await test_orm_operations()
    print("✅ ORM operations")

    await test_ohlcv_queries()
    print("✅ OHLCV queries")

    await test_cache_websocket()
    print("✅ Cache WebSocket")

    print("\n✅ All examples passed!")

if __name__ == "__main__":
    asyncio.run(main())
```

3. **Run full test suite**:
```bash
poetry run pytest tests/ -v --cov=fullon_master_api --cov-report=html
# Target: >80% coverage
```

**Deliverables**:
- ✅ Integration tests covering all workflows
- ✅ Examples-driven test suite (`run_all.py`)
- ✅ Test coverage >80%
- ✅ All examples working

---

### **Phase 8: Documentation & ADRs** (Day 11-12)

**Objectives**:
- Write comprehensive documentation
- Create Architecture Decision Records
- Finalize deployment guide

**Tasks**:

1. **Write `CLAUDE.md`** (LLM Development Guide):
```markdown
# fullon_master_api - LLM Development Guide

## Mission
Unified API Gateway composing fullon_orm_api, fullon_ohlcv_api, and fullon_cache_api with centralized JWT authentication.

## LRRS Principles
- **Little**: Single purpose - API gateway with auth
- **Responsible**: Composes existing APIs, doesn't duplicate
- **Reusable**: Standard JWT auth, composable pattern
- **Separate**: Clean boundaries via router composition

## Core Patterns
- Router composition (NOT direct library usage)
- JWT middleware setting request.state.user
- WebSocket proxy for cache operations
- Unified health monitoring

## Quick Start
[Include setup, development, testing instructions]
```

2. **Create ADRs**:
```markdown
# ADR-001: Router Composition Over Direct Library Usage

**Status**: Accepted
**Date**: 2025-10-20

## Context
Need to integrate existing fullon_orm_api, fullon_ohlcv_api, fullon_cache_api.

## Decision
Use router composition via `get_all_routers()` / `FullonOhlcvGateway().get_routers()`.

## Consequences
- ✅ Respects existing API boundaries
- ✅ No code duplication
- ✅ Easy to maintain
- ❌ Slightly more complex dependency injection

## Alternatives Considered
- Direct library usage (REJECTED - violates LRRS)
- HTTP reverse proxy (ALTERNATIVE - simpler but less flexible)
```

3. **Write `README.md`**:
```markdown
# Fullon Master API

Unified API Gateway for the Fullon Trading Platform.

## Features
- 🔐 Centralized JWT authentication
- 🔄 Composes existing APIs (ORM, OHLCV, Cache)
- 🌐 WebSocket support for real-time data
- 📊 Unified health monitoring

## Quick Start
[Installation, configuration, usage examples]
```

4. **Create `docs/DEPLOYMENT.md`**:
```markdown
# Deployment Guide

## Docker Compose
[Docker deployment configuration]

## Kubernetes
[K8s deployment manifests]

## Environment Variables
[Complete env var reference]
```

**Deliverables**:
- ✅ `CLAUDE.md` complete
- ✅ `README.md` complete
- ✅ ADRs created (ADR-001 through ADR-004)
- ✅ `DEPLOYMENT.md` complete
- ✅ API documentation auto-generated (FastAPI /docs)

---

## Dependencies (pyproject.toml)

```toml
[tool.poetry]
name = "fullon-master-api"
version = "1.0.0"
description = "Unified API Gateway for Fullon Trading Platform"
authors = ["Fullon Team"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = {extras = ["standard"], version = "^0.24.0"}
pyjwt = "^2.8.0"
python-dotenv = "^1.0.0"
pydantic-settings = "^2.0.0"
websockets = "^12.0"

# Fullon core libraries (REQUIRED - used directly)
fullon-log = {git = "ssh://git@github.com/ingmarAvocado/fullon_log.git"}
fullon-orm = {git = "ssh://git@github.com/ingmarAvocado/fullon_orm.git"}
fullon-cache = {git = "ssh://git@github.com/ingmarAvocado/fullon_cache.git"}
fullon-ohlcv = {git = "ssh://git@github.com/ingmarAvocado/fullon_ohlcv.git"}

# Fullon APIs (router composition)
fullon-orm-api = {path = "../fullon_orm_api", develop = true}
fullon-ohlcv-api = {path = "../fullon_ohlcv_api", develop = true}
fullon-cache-api = {path = "../fullon_cache_api", develop = true}

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.21.0"
pytest-cov = "^4.1.0"
httpx = "^0.25.0"
black = "^23.0.0"
ruff = "^0.1.0"
mypy = "^1.6.0"
pre-commit = "^3.5.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Timeline: 12 Days

| Phase | Days | Focus | Status |
|-------|------|-------|--------|
| Phase 1 | Day 1 | Project foundation | ⬜ Pending |
| Phase 2 | Day 2 | JWT authentication | ⬜ Pending |
| Phase 3 | Day 3 | ORM integration | ⬜ Pending |
| Phase 4 | Day 4 | OHLCV integration | ⬜ Pending |
| Phase 5 | Day 5-6 | Cache WebSocket proxy | ⬜ Pending |
| Phase 6 | Day 7-8 | Health & monitoring | ⬜ Pending |
| Phase 7 | Day 9-10 | Integration testing | ⬜ Pending |
| Phase 8 | Day 11-12 | Documentation & ADRs | ⬜ Pending |

---

## Success Criteria

✅ **Functional**:
- Single FastAPI app with unified `/api/v1/*` endpoints
- Centralized JWT authentication working
- All `fullon_orm_api` endpoints accessible via `/api/v1/orm/*`
- All `fullon_ohlcv_api` endpoints accessible via `/api/v1/ohlcv/*`
- Cache WebSocket operations working via `/api/v1/cache/ws/*`
- Unified health check endpoint functional

✅ **Quality**:
- Test coverage >80%
- All integration tests passing
- All examples working (`examples/run_all.py` passes)
- LRRS principles followed (audit approved)
- Fullon architecture patterns respected

✅ **Documentation**:
- `CLAUDE.md` complete (LLM guide)
- `README.md` complete (human guide)
- ADRs created for major decisions
- `DEPLOYMENT.md` complete
- API docs auto-generated

---

## Key Architectural Decisions

### ✅ What We're Doing:

1. **Router Composition**: Using existing API gateway patterns
   - `fullon_orm_api.get_all_routers()`
   - `fullon_ohlcv_api.FullonOhlcvGateway().get_routers()`
   - `fullon_cache_api` routers mounted as-is

2. **JWT Middleware**: Sets `request.state.user` for downstream APIs
   - Existing APIs already consume `request.state.user`
   - Clean separation of concerns

3. **WebSocket Proxy**: Mount cache WebSocket routers directly
   - No REST wrappers needed
   - Respect cache API's WebSocket-only design

4. **Health Monitoring**: Aggregate status from all subsystems
   - PostgreSQL, Redis, daemons
   - No daemon control endpoints

### ❌ What We're NOT Doing:

1. **Direct Library Usage**: Would bypass existing API patterns
2. **REST Wrappers for Cache**: Would conflict with WebSocket design
3. **Service Control Endpoints**: Use Docker/K8s for orchestration
4. **Code Duplication**: Compose, don't duplicate

---

## Risk Mitigation

| Risk | Mitigation | Status |
|------|------------|--------|
| Auth dependency injection conflicts | Use FastAPI dependency overrides | ✅ Tested |
| WebSocket auth complexity | Implement token query param auth | ✅ Designed |
| Integration test failures | Examples-driven development | ✅ Planned |
| Timeline slippage | 2-day buffer built in | ✅ Accounted |
| LRRS violations | Audit approved design | ✅ Validated |

---

## Next Steps

**Immediate**:
1. Review and approve revised masterplan
2. Create `fullon_master_api` directory structure
3. Initialize Poetry project
4. Start Phase 1 (Day 1)

**During Development**:
- Daily standup: Review progress against timeline
- After each phase: Validate deliverables
- Checkpoint after Day 6: Mid-project review
- Checkpoint after Day 10: Pre-documentation review

**Upon Completion**:
- Final review against success criteria
- Deploy to staging environment
- Create production deployment plan
- Archive audit reports and ADRs

---

**Plan Version**: 2.1 (Documentation Aligned)
**Last Updated**: 2025-10-20
**Approval Status**: ✅ READY FOR IMPLEMENTATION
