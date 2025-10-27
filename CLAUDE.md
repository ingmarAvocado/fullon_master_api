# Fullon Master API - AI Agent Guide

**Updated**: 2025-10-27 | **For**: AI Agents | **Project**: Unified API Gateway

---

## Contents

1. [Overview](#1-overview)
2. [EDD](#2-edd)
3. [Test Isolation](#3-test-isolation)
4. [GitHub Workflow](#4-github-workflow)
5. [Code Style](#5-code-style)
6. [Testing](#6-testing)
7. [Architecture](#7-architecture)
8. [Workflow](#8-workflow)
9. [Tasks](#9-tasks)
10. [Troubleshooting](#10-troubleshooting)
11. [Reference](#11-reference)

---

## 1. Overview

**Fullon Master API**: Unified gateway composing `fullon_orm_api`, `fullon_ohlcv_api`, `fullon_cache_api` with JWT auth.

**Core Principle**: **Compose, Don't Duplicate** - Router composition only, no direct library access.

**LRRS**: Little, Responsible, Reusable, Separate architecture.

**URLs**:
```
/api/v1/auth/login           # JWT auth
/api/v1/orm/*               # DB operations
/api/v1/ohlcv/*             # Candlestick data
/api/v1/cache/ws/*          # WebSocket streams
/api/v1/services/*/start|stop|restart|status  # Admin service control
/health                     # System health status
/health/services            # Service status only
/health/monitor             # HealthMonitor details
/health/check               # Trigger health check
```

**Key Patterns**:
- Router composition (NOT direct imports)
- JWT middleware → `request.state.user`
- ServiceManager for async background tasks (with HealthMonitor)
- Examples-Driven Development (EDD)

---

## 2. EDD

**Examples define WHAT, Tests define HOW, Implementation makes it PASS.**

**Workflow**: Example → Issue → Test → Implement → Pass

**Critical**: NEVER implement without example.

**Why**: Eliminates ambiguity, prevents hallucination, enables TDD.

**Example Structure**:
```python
import os, uuid, asyncio, httpx
from demo_data import create_test_data, cleanup_test_database

os.environ["DB_NAME"] = f"test_example_{uuid.uuid4()[:8]}"

async def main():
    try:
        await create_test_data()
        async with httpx.AsyncClient() as client:
            # Login + API calls
            response = await client.get("/api/v1/endpoint", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200
    finally:
        await cleanup_test_database(os.environ["DB_NAME"])
```

**Key Examples**: `example_jwt_login.py`, `example_orm_routes.py`, `example_service_control.py`

**Run**: `python examples/run_all_examples.py`

**Issues**: Reference examples in descriptions.

---

## 3. Test Isolation

**Pattern**: Database-per-worker with savepoint rollback for parallel execution.

**Architecture**: Each pytest-xdist worker gets isolated PostgreSQL DB + Redis DBs.

**Key Fixtures**:

**Admin User** (with IntegrityError handling):
```python
@pytest_asyncio.fixture(scope="function")
async def test_admin_user(self, db_context):
    user = User(mail=settings.admin_mail, name="Admin", lastname="User",
        password=hash_password("adminpass123"), f2a="", phone="", id_num="")
    try:
        return await db_context.users.add_user(user)
    except IntegrityError:
        return await db_context.users.get_by_email(settings.admin_mail)
```

**Regular User** (UUID-based):
```python
@pytest_asyncio.fixture(scope="function")
async def test_regular_user(self, db_context):
    unique_id = str(uuid.uuid4())[:8]
    user = User(mail=f"user_{unique_id}@example.com", name="Regular", lastname="User",
        password=hash_password("userpass123"), f2a="", phone="", id_num="")
    return await db_context.users.add_user(user)
```

**Test Client**:
```python
@pytest.fixture(scope="function")
def admin_client(self, gateway, admin_token):
    client = TestClient(gateway.get_app())
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client
```

**Rules**:
- Function scope only
- UUID for unique emails
- Handle IntegrityError for admin
- Never share TestClient
- Add cleanup fixtures for async services

**Redis**: Worker 0 → DBs 1-4, Worker 1 → DBs 5-8, etc. (never DB 0).

**Service Cleanup**: Use autouse fixtures to stop services after tests:
```python
@pytest.fixture(autouse=True, scope="function")
async def cleanup_services(self, test_app):
    yield
    service_manager = test_app.state.service_manager
    await service_manager.stop_all()
```

**Safety**: Production DB access blocked, async task cleanup prevents warnings.

---

## 4. GitHub Workflow

**Pattern**: masterplan.md → Issues → Test stubs → TDD → Passing tests

**Issue Structure**:
```markdown
# Issue #42: Brief Title

**Example**: examples/example_file.py
**Depends On**: #38, #39

## Description
What to implement.

## Acceptance Criteria
- [ ] Feature 1
- [ ] Feature 2
- [ ] Tests pass
```

**Labels**: `phase-N-*`, `auth`, `orm`, `ohlcv`, `service-control`, `testing`

**TDD Workflow**:
```bash
gh issue view 42
# Write failing test
pytest tests/file.py::test_feature -v  # ❌ FAIL
# Implement
pytest tests/file.py::test_feature -v  # ✅ PASS
git commit -m "Issue #42: Summary\n\n- Changes\n\nCloses #42"
```

**Dependencies**: Complete dependencies first, reference in commits.

---

## 5. Code Style

**Tools**: Python 3.13+, Poetry, Ruff + MyPy, Black, 100 char lines.

**Imports**: stdlib → third-party → local (alphabetical).

**Naming**: snake_case (functions), PascalCase (classes), UPPER_CASE (constants).

**Type Hints**: Required everywhere.

**Docstrings**: Google style (Summary, Args, Returns, Raises).

**Error Handling**:
```python
# 401: No auth
if not token: raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})

# 403: Insufficient permissions
if user.mail != settings.admin_mail: raise HTTPException(403, "Admin access required")

# 404: Not found
if not resource: raise HTTPException(404, f"Resource {id} not found")

# 400: Bad request
if invalid_input: raise HTTPException(400, "Invalid input")

# 500: Server error
try: await operation()
except Exception as e:
    logger.error("Failed", error=str(e))
    raise HTTPException(500, "Internal server error")
```

**Logging**: Structured key-value pairs, not string interpolation.

**Comments**: Explain WHY, reference ADRs, avoid obvious comments.

---

## 6. Testing

**Organization**:
```
tests/
├── unit/           # Fast, mocked (JWT, dependencies)
├── integration/    # Real DB, async fixtures (API endpoints)
├── e2e/           # Full stack, real server (workflows)
├── conftest.py    # DB/Redis isolation fixtures
```

**Unit Tests**: Fast, isolated, mocked dependencies.

**Integration Tests**: Real PostgreSQL/Redis, async fixtures, TestClient.

**E2E Tests**: Run example scripts as subprocesses to validate complete workflows.

**Commands**:
```bash
make test              # All tests
make test-cov          # With coverage
pytest tests/ -n 4     # Parallel (4 workers)
pytest tests/ -k "pattern"  # Filter by pattern
pytest tests/unit/     # Unit only
pytest tests/integration/  # Integration only
```

**Coverage**: Unit 80%+, Integration all endpoints, E2E critical workflows.

### E2E Testing Pattern

**Purpose**: Validate complete workflows by running actual example scripts.

**Pattern**: E2E tests execute example scripts as subprocesses:

```python
def test_example_orm_routes():
    """Test example_orm_routes.py runs successfully."""
    script = Path("examples/example_orm_routes.py")

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        timeout=60
    )

    assert result.returncode == 0
```

**Why**: Examples already have perfect isolation, cleanup, and validation.

**Characteristics**: Real server, real database (isolated), complete workflow, validates examples are production-ready.

---

## 7. Architecture

**1. Router Composition**: Mount existing API routers, never bypass them.
```python
from fullon_orm_api import get_all_routers
orm_routers = get_all_routers()
for router in orm_routers:
    app.include_router(router, prefix="/api/v1/orm", dependencies=[Depends(get_current_user)])
```

**2. JWT Middleware**: Validate once, inject `request.state.user`.
```python
class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            payload = jwt_handler.decode_token(token)
            user = await db.users.get_by_id(payload["user_id"])
            request.state.user = user
        return await call_next(request)
```

**3. ServiceManager**: Asyncio.Task for background services with HealthMonitor.
```python
class ServiceManager:
    async def start_service(self, service_name):
        if self.tasks[service_name] is not None: raise ValueError("Already running")
        daemon = self.daemons[service_name]
        self.tasks[service_name] = asyncio.create_task(daemon.start())
        return {"service": service_name, "status": "started"}

    # HealthMonitor integration
    async def perform_health_check_and_recovery(self):
        # Service health, ProcessCache, database, Redis checks
        # Auto-restart failed services
        pass
```

**4. Dependency Injection**: FastAPI Depends() for shared logic.

**5. Structured Logging**: Key-value pairs, not string interpolation.

**6. Error Handling**: Consistent HTTP status codes (401/403/404/400/500).

**7. WebSocket Proxying**: Mount cache API for WebSocket streams.

---

## 8. Workflow

**Setup**:
```bash
git clone https://github.com/ingmarAvocado/fullon_master_api.git
cd fullon_master_api
make setup  # Install deps
cp .env.example .env  # Configure
make test  # Verify
make run   # Development server
```

**Development Cycle**:
1. Pick Issue → 2. Write Test → 3. Fail → 4. Implement → 5. Pass → 6. Commit

**Example**:
```bash
gh issue view 43
# Write failing test
pytest tests/integration/test_feature.py -v  # ❌ FAIL
# Implement feature
pytest tests/integration/test_feature.py -v  # ✅ PASS
make lint
git commit -m "Issue #43: Feature summary\n\n- Changes\n\nCloses #43"
```

**Git Commits**: `Issue #N: Summary\n\n- Details\n\nCloses #N`

**Server**:
```bash
make run      # Dev (auto-reload)
make run-prod # Prod (workers)
make daemon-start/stop/status  # Background
```

**Quality**: `make lint` (format + type-check + lint)

---

## 9. Tasks

**1. Add Endpoint**:
```bash
# 1. Write example FIRST
vim examples/example_feature.py

# 2. Create issue with example reference
gh issue create --title "Add feature" --body "**Example**: examples/example_feature.py"

# 3. Write failing test
vim tests/integration/test_feature.py

# 4. Implement router
vim src/fullon_master_api/routers/feature.py

# 5. Mount in gateway.py
app.include_router(feature_router, prefix="/api/v1/feature")

# 6. Test passes
pytest tests/integration/test_feature.py -v  # ✅ PASS

# 7. Run example
python examples/example_feature.py  # ✅ WORKS

# 8. Commit
git commit -m "Issue #N: Add feature\n\n- Implementation\n\nCloses #N"
```

**2. Admin Endpoint**: Use `Depends(get_admin_user)` instead of `get_current_user`.

**3. Add Service**: Update ServiceName enum and ServiceManager.__init__().

**4. Debug Tests**:
```bash
pytest tests/ -v -s --pdb  # Verbose + debug
pytest tests/ --durations=10  # Find slow tests
pytest tests/ --cov-report=term-missing  # Coverage gaps
```

---

## 10. Troubleshooting

**DB Isolation**: `UniqueViolationError` → Use `@pytest_asyncio.fixture(scope="function")` with IntegrityError handling.

**Event Loop Closed**: TestClient timing issue with async cleanup → Accept (works in production) or use AsyncClient.

**Pending Task Warnings**: "Task was destroyed but it is pending" → Add service cleanup fixtures, use asyncio.Event in MockDaemon.stop().

**Import Errors**: Check `__init__.py` exports, install missing deps, verify Python path.

**Auth Failures**: Check JWT secret, token expiry, user existence, admin email in `.env`.

**Redis Errors**: `redis-cli ping` (PONG?), start Redis service, check connection, verify `.env`.

**Fixture Not Found**: Check conftest.py location, fixture scope (`self.` in classes), dependencies.

---

## 11. Reference

**Make**:
```bash
make setup     # Install deps
make run       # Dev server
make test      # All tests
make lint      # Quality checks
```

**Pytest**:
```bash
pytest tests/ -n 4                    # Parallel tests
pytest tests/ -k "pattern"            # Filter
pytest tests/ --cov=src               # Coverage
```

**Git**:
```bash
git commit -m "Issue #N: Summary\n\n- Changes\n\nCloses #N"
```

**Structure**:
```
src/fullon_master_api/     # Core code
├── main.py, gateway.py, config.py
├── auth/, services/, routers/
tests/                     # Tests
examples/                  # Contracts
docs/                      # References
```

**Settings**:
```bash
DB_HOST=localhost DB_NAME=fullon DB_USER=postgres DB_PASSWORD=pass
REDIS_HOST=localhost REDIS_PORT=6379
JWT_SECRET_KEY=secret ADMIN_MAIL=admin@fullon
```

**Deps**: fullon_orm_api, fullon_ohlcv_api, fullon_cache_api (required) + services (optional)

**Latest**: ServiceManager-Gateway integration (#44), HealthMonitor with auto-restart, pending task warning fixes

---

**Key Rules**:
- ✅ Examples BEFORE implementation
- ✅ Async fixtures with IntegrityError handling
- ✅ Router composition (no direct imports)
- ✅ Structured logging (key-value pairs)
- ✅ Service cleanup fixtures (prevent pending task warnings)
- ✅ One GitHub issue per function
- ✅ Test before committing

**Resources**: `masterplan.md`, `AGENTS.md`, `examples/`, `README.md`
