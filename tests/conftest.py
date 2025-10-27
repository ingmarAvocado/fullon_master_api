"""Test configuration with database-per-worker isolation for fullon_master_api.

This implements the dual-database pattern from fullon_ohlcv_service, adapted for master API:
- Database per worker for parallel test execution (pytest-xdist)
- Dual database support (ORM + OHLCV)
- Redis isolation for cache API integration tests
- Savepoint-based test isolation (flush + rollback)
- Real database integration instead of mocks
- Worker-aware naming: test_master_api_{module}_{worker_id} + test_master_api_{module}_{worker_id}_ohlcv

Architecture:
- Each test module gets its own database pair per worker
- Each test module gets its own Redis DB per worker
- Databases cached at module level for performance
- Tests use savepoints for perfect isolation
- All changes rolled back after each test
- Comprehensive safety checks prevent production database access

Redis Isolation:
- Never uses Redis DB 0 (production)
- Worker isolation: Worker 0 → DBs 1-4, Worker 1 → DBs 5-8, Worker 2 → DBs 9-12, Worker 3 → DBs 13-16
- Aggressive cleanup before and after each test
- Ultra-unique key prefixes for additional isolation
"""

import asyncio
import hashlib
import os
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Dict

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from fullon_master_api.auth.jwt import JWTHandler
from fullon_master_api.config import settings
from fullon_master_api.gateway import MasterGateway
from fullon_orm.base import Base
from fullon_orm.database import create_database_url
from fullon_orm.models import User

# Load environment variables
load_dotenv()

# ============================================================================
# SAFETY CHECKS - Prevent Production Database Access
# ============================================================================


def _validate_test_environment():
    """Validate that we're in a test environment and not accidentally using production database."""
    import sys

    is_pytest = "pytest" in sys.modules or (sys.argv and "pytest" in sys.argv[0])

    if is_pytest:
        production_db_names = {"fullon", "fullon2", "production", "prod"}
        current_db = os.getenv("DB_NAME", "").lower()

        if current_db in production_db_names:
            print(
                f"WARNING: DB_NAME is set to '{current_db}' but tests will use isolated test databases."
            )
            print(
                "This is safe - each test creates its own database like 'test_master_api_module_worker'"
            )
        return

    # Non-test context: strict validation
    production_db_names = {"fullon", "fullon2", "production", "prod"}
    current_db = os.getenv("DB_NAME", "").lower()

    if current_db in production_db_names:
        raise RuntimeError(
            f"SAFETY CHECK FAILED: Cannot run against production database '{current_db}' outside of tests. "
            f"Please set DB_NAME to a development database name."
        )

    host = os.getenv("DB_HOST", "localhost").lower()
    if any(prod_pattern in host for prod_pattern in ["prod", "production", "live"]):
        raise RuntimeError(
            f"SAFETY CHECK FAILED: Database host '{host}' appears to be a production host. "
            f"Use localhost or development hosts only."
        )


# Run safety check on import
_validate_test_environment()

# ============================================================================
# DATABASE PER WORKER PATTERN - Module-Level Caches
# ============================================================================

# Cache for engines per database to reuse across tests
_engine_cache: Dict[str, AsyncEngine] = {}
_db_created: Dict[str, bool] = {}


async def create_test_database(db_name: str) -> None:
    """Create a test database if it doesn't exist."""
    # Safety check: ensure database name looks like a test database
    if not db_name.startswith("test_"):
        raise RuntimeError(
            f"SAFETY CHECK FAILED: Database name '{db_name}' does not start with 'test_'. "
            f"Only test databases should be created/dropped during testing."
        )

    if db_name in _db_created:
        return

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "password")

    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database="postgres"
    )

    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        _db_created[db_name] = True
    finally:
        await conn.close()


async def drop_test_database(db_name: str) -> None:
    """Drop a test database."""
    # Safety check: ensure database name looks like a test database
    if not db_name.startswith("test_"):
        raise RuntimeError(
            f"SAFETY CHECK FAILED: Refusing to drop database '{db_name}' that doesn't start with 'test_'. "
            f"This safety check prevents accidental deletion of production databases."
        )

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "password")

    conn = await asyncpg.connect(
        host=host, port=port, user=user, password=password, database="postgres"
    )

    try:
        # Terminate all connections
        await conn.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = $1
            AND pid <> pg_backend_pid()
        """,
            db_name,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        _db_created.pop(db_name, None)
    finally:
        await conn.close()


def get_test_db_names(request) -> tuple[str, str]:
    """Generate worker-aware database names for BOTH ORM and OHLCV databases.

    This follows the fullon_ohlcv_service pattern for dual database support.

    Args:
        request: Pytest request fixture

    Returns:
        Tuple of (orm_db_name, ohlcv_db_name)

    Examples:
        Single-threaded: ("test_master_api_module", "test_master_api_module_ohlcv")
        Worker gw0: ("test_master_api_module_gw0", "test_master_api_module_gw0_ohlcv")
        Worker gw1: ("test_master_api_module_gw1", "test_master_api_module_gw1_ohlcv")
    """
    module_name = request.module.__name__.split(".")[-1]
    worker_id = getattr(request.config, "workerinput", {}).get("workerid", "")

    if worker_id:
        orm_db = f"test_master_api_{module_name}_{worker_id}"
        ohlcv_db = f"test_master_api_{module_name}_{worker_id}_ohlcv"
    else:
        orm_db = f"test_master_api_{module_name}"
        ohlcv_db = f"test_master_api_{module_name}_ohlcv"

    return orm_db, ohlcv_db


async def get_or_create_engine(db_name: str, create_ohlcv_schemas: bool = False) -> AsyncEngine:
    """Get or create an engine for the database.

    Args:
        db_name: Database name
        create_ohlcv_schemas: If True, create exchange schemas for OHLCV data

    Returns:
        AsyncEngine for the database
    """
    if db_name not in _engine_cache:
        # Create database if needed
        await create_test_database(db_name)

        # Create engine with NullPool to avoid connection pool issues
        database_url = create_database_url(database=db_name)
        engine = create_async_engine(
            database_url,
            echo=False,
            poolclass=NullPool,  # Use NullPool to avoid event loop issues
        )

        # Create ORM tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Create OHLCV schemas if requested
            if create_ohlcv_schemas:
                # Try to create TimescaleDB extension if available
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
                except Exception:
                    # TimescaleDB not available, continue without it
                    pass

                # Create schemas for test exchanges
                test_exchanges = ["test", "binance", "kraken"]
                for exchange in test_exchanges:
                    try:
                        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{exchange}"'))
                    except Exception:
                        # Schema creation failed, continue without it
                        pass

        _engine_cache[db_name] = engine

    return _engine_cache[db_name]


# ============================================================================
# TEST DATABASE CONTEXT - Rollback-Based Isolation
# ============================================================================


class DatabaseTestContext:
    """DatabaseContext wrapper for testing with perfect isolation.

    This mimics fullon_orm's DatabaseContext pattern but uses savepoints for test isolation:
    - Never commits - always rollbacks to avoid event loop cleanup issues
    - Uses savepoints for nested transaction support
    - Provides same repository interface as real DatabaseContext
    - All changes automatically rolled back after each test

    Repository Properties:
        - api_keys: ApiKeyRepository
        - users: UserRepository
        - exchanges: ExchangeRepository
        - symbols: SymbolRepository
        - bots: BotRepository
        - strategies: StrategyRepository
        - orders: OrderRepository
        - trades: TradeRepository
    """

    def __init__(self, session: AsyncSession):
        """Initialize with an async session."""
        self.session = session
        # Repository instances (lazy loaded)
        self._api_key_repo = None
        self._user_repo = None
        self._exchange_repo = None
        self._symbol_repo = None
        self._bot_repo = None
        self._strategy_repo = None
        self._order_repo = None
        self._trade_repo = None

    @property
    def api_keys(self):
        """Get ApiKeyRepository with current session."""
        if self._api_key_repo is None:
            from fullon_orm.repositories import ApiKeyRepository

            self._api_key_repo = ApiKeyRepository(self.session)
        return self._api_key_repo

    @property
    def users(self):
        """Get UserRepository with current session."""
        if self._user_repo is None:
            from fullon_orm.repositories import UserRepository

            self._user_repo = UserRepository(self.session)
        return self._user_repo

    @property
    def exchanges(self):
        """Get ExchangeRepository with current session."""
        if self._exchange_repo is None:
            from fullon_orm.repositories import ExchangeRepository

            self._exchange_repo = ExchangeRepository(self.session)
        return self._exchange_repo

    @property
    def symbols(self):
        """Get SymbolRepository with current session."""
        if self._symbol_repo is None:
            from fullon_orm.repositories import SymbolRepository

            self._symbol_repo = SymbolRepository(self.session)
        return self._symbol_repo

    @property
    def bots(self):
        """Get BotRepository with current session."""
        if self._bot_repo is None:
            from fullon_orm.repositories import BotRepository

            self._bot_repo = BotRepository(self.session)
        return self._bot_repo

    @property
    def strategies(self):
        """Get StrategyRepository with current session."""
        if self._strategy_repo is None:
            from fullon_orm.repositories import StrategyRepository

            self._strategy_repo = StrategyRepository(self.session)
        return self._strategy_repo

    @property
    def orders(self):
        """Get OrderRepository with current session."""
        if self._order_repo is None:
            from fullon_orm.repositories import OrderRepository

            self._order_repo = OrderRepository(self.session)
        return self._order_repo

    @property
    def trades(self):
        """Get TradeRepository with current session."""
        if self._trade_repo is None:
            from fullon_orm.repositories import TradeRepository

            self._trade_repo = TradeRepository(self.session)
        return self._trade_repo

    async def commit(self):
        """Commit current transaction (for compatibility)."""
        await self.session.commit()

    async def rollback(self):
        """Rollback current transaction."""
        await self.session.rollback()

    async def flush(self):
        """Flush current session."""
        await self.session.flush()


@pytest_asyncio.fixture
async def test_users(db_context, request):
    """Create test users in database for authentication tests.

    Creates:
    - Admin user with email matching settings.admin_mail
    - Regular user with different email

    Returns:
        Dict with 'admin' and 'user' keys containing User ORM objects
    """
    from fullon_master_api.auth.jwt import hash_password
    from fullon_master_api.config import settings
    import uuid

    # Use unique user email to avoid conflicts between tests
    test_id = str(uuid.uuid4())[:8]
    user_email = f"user_{test_id}@example.com"

    # Try to delete existing admin user first (ignore errors)
    try:
        existing_admin = await db_context.users.get_user_by_email(settings.admin_mail)
        if existing_admin:
            await db_context.users.delete_user(existing_admin.uid)
    except Exception:
        pass  # Ignore errors if user doesn't exist

    # Create admin user with the correct admin email
    admin_user = User(
        mail=settings.admin_mail,  # Must match settings.admin_mail for admin access
        name="Admin",
        lastname="User",
        password=hash_password("adminpass123"),
        f2a="",  # Two-factor auth disabled
        phone="",
        id_num="",
        note=None,
        manager=None,
        external_id=None,
        active=True,
    )
    created_admin = await db_context.users.add_user(admin_user)

    # Try to delete existing regular user first (ignore errors)
    try:
        existing_user = await db_context.users.get_user_by_email(user_email)
        if existing_user:
            await db_context.users.delete_user(existing_user.uid)
    except Exception:
        pass  # Ignore errors if user doesn't exist

    # Create regular user
    regular_user = User(
        mail=user_email,
        name="Regular",
        lastname="User",
        password=hash_password("userpass123"),
        f2a="",  # Two-factor auth disabled
        phone="",
        id_num="",
        note=None,
        manager=None,
        external_id=None,
        active=True,
    )
    created_user = await db_context.users.add_user(regular_user)

    return {"admin": created_admin, "user": created_user}


@pytest_asyncio.fixture
async def clean_redis(redis_db) -> AsyncGenerator[None, None]:
    """Ensure Redis is ultra-clean for each test with aggressive cleanup.

    This fixture provides aggressive Redis cleanup before and after each test:
    - Flushes entire test database before test
    - Multiple cleanup attempts with retries
    - Verifies database is empty (dbsize() == 0)
    - Resets ConnectionPool
    - Ultra-aggressive post-test cleanup

    Args:
        redis_db: Redis database number from redis_db fixture

    Yields:
        None

    Note:
        Requires fullon_cache to be installed. If not available, fixture
        passes silently (for tests that don't need Redis yet).

    Safety:
        Never touches Redis DB 0 (production)
        Only cleans the isolated test database
    """
    # Reset connection pool and completely flush database before test
    try:
        from fullon_cache.connection import ConnectionPool
        from fullon_cache import BaseCache

        await ConnectionPool.reset_async()

        # Clear all data in the test database with multiple attempts
        for attempt in range(3):
            try:
                cache = BaseCache()
                async with cache._redis_context() as redis:
                    # Force flush the entire test database
                    await redis.flushdb()
                    # Verify it's actually empty
                    key_count = await redis.dbsize()
                    if key_count == 0:
                        break
                await cache.close()
            except Exception:
                if attempt == 2:  # Last attempt
                    pass  # Continue anyway
                await asyncio.sleep(0.1)

        # Brief pause to ensure cleanup is complete
        await asyncio.sleep(0.05)

    except ImportError:
        # fullon_cache not available yet, skip Redis cleanup
        pass

    yield

    # Ultra-aggressive cleanup after each test
    try:
        from fullon_cache.connection import ConnectionPool
        from fullon_cache import BaseCache

        for attempt in range(3):
            try:
                await ConnectionPool.reset_async()
                cache = BaseCache()
                async with cache._redis_context() as redis:
                    # Force flush entire database
                    await redis.flushdb()
                    # Double-check it's clean
                    await redis.flushdb()
                await cache.close()
                break
            except Exception:
                if attempt == 2:
                    pass  # Give up after 3 attempts
                await asyncio.sleep(0.1)

        # Final pause to ensure all cleanup is complete
        await asyncio.sleep(0.05)

    except ImportError:
        # fullon_cache not available yet, skip Redis cleanup
        pass


@pytest.fixture(scope="function")
def redis_db(worker_id, request) -> int:
    """Allocate a unique Redis database per test with worker isolation.

    This fixture provides database-per-test isolation for Redis operations.
    Worker 0 gets DBs 1-4, Worker 1 gets DBs 5-8, etc.

    Returns:
        Redis database number (1-15, never 0 for production safety)
    """
    import hashlib
    import time
    import os

    # Get worker number
    if worker_id == "master":
        worker_num = 0
    else:
        try:
            worker_num = int(worker_id[2:])
        except (ValueError, IndexError):
            worker_num = 0

    # Base DB for this worker (4 DBs per worker)
    base_db = (worker_num * 4) + 1

    # Get test info for hash-based selection
    test_file = os.path.basename(request.node.fspath)
    test_name = request.node.name
    timestamp_ns = time.time_ns()
    process_id = os.getpid()

    # Create unique identifier for this test
    unique_string = f"{worker_id}_{test_file}_{test_name}_{timestamp_ns}_{process_id}"

    # Hash to get consistent but unique DB selection
    hash_value = int(hashlib.md5(unique_string.encode()).hexdigest()[:8], 16)
    db_offset = hash_value % 4
    db_num = base_db + db_offset

    # Ensure we don't exceed DB 15
    if db_num > 15:
        db_num = ((db_num - 1) % 15) + 1

    # Set environment variable for fullon_cache
    os.environ["REDIS_DB"] = str(db_num)

    return db_num


@pytest.fixture(scope="module", autouse=True)
def redis_db_per_module(request, worker_id):
    """Allocate a Redis database per test module with worker isolation.

    This fixture automatically sets REDIS_DB for all tests in a module.
    Worker 0 gets DBs 1-5, Worker 1 gets DBs 6-10, etc.
    """
    import hashlib
    import os

    # Get worker number
    if worker_id == "master":
        worker_num = 0
    else:
        try:
            worker_num = int(worker_id[2:])
        except (ValueError, IndexError):
            worker_num = 0

    # Base DB for this worker (5 DBs per worker for module scope)
    base_db = (worker_num * 5) + 1

    # Get module info
    module_name = os.path.basename(request.node.fspath)

    # Hash module name for consistent DB selection
    hash_value = int(hashlib.md5(module_name.encode()).hexdigest()[:8], 16)
    db_offset = hash_value % 5
    db_num = base_db + db_offset

    # Ensure we don't exceed DB 15
    if db_num > 15:
        db_num = ((db_num - 1) % 15) + 1

    # Set environment variable
    os.environ["REDIS_DB"] = str(db_num)

    # Print allocation for debugging
    print(
        f"[REDIS DB SELECT] Worker {worker_id} using Redis DB {db_num} for test file {module_name}"
    )


@pytest.fixture(scope="function")
def test_isolation_prefix(worker_id, request) -> str:
    """Generate ultra-unique prefix for test data to prevent cross-test contamination.

    This ensures that even within the same Redis DB, different tests and workers
    use completely isolated key spaces with nanosecond precision.

    Args:
        worker_id: pytest-xdist worker ID
        request: pytest request object

    Returns:
        Ultra-unique prefix in format: w{worker_num}_{hash}

    Format:
        The hash is SHA256 of:
        - worker_id
        - test_file
        - test_name
        - timestamp_ns (nanosecond precision)
        - process_id
        - uuid (12 chars)

    Example:
        "w0_a1b2c3d4e5f6a7b8"  # Worker 0, 16-char hash
    """
    # Get worker number
    if worker_id == "master":
        worker_num = 0
    else:
        try:
            worker_num = int(worker_id[2:])
        except (ValueError, IndexError):
            worker_num = 0

    # Get test info
    test_file = os.path.basename(request.node.fspath)
    test_name = request.node.name

    # Create ultra-unique prefix with maximum separation
    timestamp_ns = time.time_ns()  # Nanosecond precision
    process_id = os.getpid()
    unique_id = uuid.uuid4().hex[:12]  # Longer unique ID

    # Create a hash to keep key length reasonable
    full_identifier = f"{worker_id}_{test_file}_{test_name}_{timestamp_ns}_{process_id}_{unique_id}"
    prefix_hash = hashlib.sha256(full_identifier.encode()).hexdigest()[:16]

    # Final prefix: worker + hash for maximum uniqueness and reasonable length
    prefix = f"w{worker_num}_{prefix_hash}"

    return prefix


# ============================================================================
# AUTHENTICATION TEST FIXTURES - For Integration Tests
# ============================================================================


@pytest_asyncio.fixture
async def db_context(request):
    """Create a DatabaseContext-like wrapper for testing with proper isolation.

    This provides:
    - Per-test database isolation via savepoints
    - Automatic rollback after each test
    - Same interface as fullon_orm.DatabaseContext
    - Access to all repositories (users, bots, orders, etc.)
    - Sets DB_NAME environment variable so middleware uses test database

    Usage:
        async def test_user_creation(db_context):
            user = User(mail="test@example.com", name="Test", ...)
            created_user = await db_context.users.add_user(user)
            assert created_user.uid is not None
            # Automatically rolled back after test
    """
    # Get ORM database name for this module
    orm_db_name, _ = get_test_db_names(request)

    # Store original DB_NAME for restoration
    original_db_name = os.getenv("DB_NAME")

    # CRITICAL: Set environment variable so middleware uses test database
    os.environ["DB_NAME"] = orm_db_name

    # Clear cached database managers so middleware uses test DB
    from fullon_orm import database

    if hasattr(database, "_db_manager") and database._db_manager is not None:
        database._db_manager = None

    try:
        # Get or create engine
        engine = await get_or_create_engine(orm_db_name)

        # Create session maker
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create a session WITHOUT context manager to have full control
        session = async_session_maker()

        try:
            # Begin transaction explicitly for proper rollback
            await session.begin()

            # Create test database context wrapper
            db = DatabaseTestContext(session)

            yield db
        finally:
            # Always rollback - this ensures no data persists
            await session.rollback()
            await session.close()
    finally:
        # Restore original DB_NAME
        if original_db_name:
            os.environ["DB_NAME"] = original_db_name
        else:
            os.environ.pop("DB_NAME", None)

        # Clear cache again so next test/module gets fresh connection
        from fullon_orm import database

        if hasattr(database, "_db_manager") and database._db_manager is not None:
            database._db_manager = None


@pytest.fixture(scope="function")
def jwt_handler():
    """Create JWT handler for token generation in tests."""
    return JWTHandler(settings.jwt_secret_key, settings.jwt_algorithm)


@pytest.fixture(scope="function")
def admin_token(test_users, jwt_handler):
    """Generate JWT token for admin user."""
    admin_user = test_users["admin"]
    return jwt_handler.generate_token(
        user_id=admin_user.uid,
        username=admin_user.mail,  # Use email as username
        email=admin_user.mail,
    )


@pytest.fixture(scope="function")
def user_token(test_users, jwt_handler):
    """Generate JWT token for regular user."""
    regular_user = test_users["user"]
    return jwt_handler.generate_token(
        user_id=regular_user.uid,
        username=regular_user.mail,  # Use email as username
        email=regular_user.mail,
    )


@pytest.fixture(scope="function")
def test_app():
    """Create FastAPI test application instance."""
    gateway = MasterGateway()
    return gateway.get_app()


@pytest.fixture(scope="function")
def admin_client(test_app, admin_token):
    """Create TestClient with admin authentication."""
    client = TestClient(test_app)
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client


@pytest.fixture(scope="function")
def user_client(test_app, user_token):
    """Create TestClient with regular user authentication."""
    client = TestClient(test_app)
    client.headers.update({"Authorization": f"Bearer {user_token}"})
    return client
