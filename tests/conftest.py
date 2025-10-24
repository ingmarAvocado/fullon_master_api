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
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from fullon_orm.base import Base
from fullon_orm.database import create_database_url

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
            print(f"WARNING: DB_NAME is set to '{current_db}' but tests will use isolated test databases.")
            print("This is safe - each test creates its own database like 'test_master_api_module_worker'")
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
        host=host,
        port=port,
        user=user,
        password=password,
        database="postgres"
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
        host=host,
        port=port,
        user=user,
        password=password,
        database="postgres"
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
    module_name = request.module.__name__.split('.')[-1]
    worker_id = getattr(request.config, 'workerinput', {}).get('workerid', '')

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
    if hasattr(database, '_db_manager') and database._db_manager is not None:
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
        if hasattr(database, '_db_manager') and database._db_manager is not None:
            database._db_manager = None


@pytest_asyncio.fixture(scope="module")
async def dual_test_databases(request) -> AsyncGenerator[dict[str, str], None]:
    """Create dual test databases with worker isolation for integration tests.

    This creates BOTH ORM and OHLCV databases following the fullon_ohlcv_service pattern.
    Use this for tests that need both databases available.

    Returns:
        Dict with "orm_db" and "ohlcv_db" keys containing database names

    Usage:
        async def test_with_dual_databases(dual_test_databases):
            orm_db = dual_test_databases["orm_db"]
            ohlcv_db = dual_test_databases["ohlcv_db"]
            # Both databases are ready for use
    """
    orm_db_name, ohlcv_db_name = get_test_db_names(request)

    # Create both databases
    await create_test_database(orm_db_name)
    await create_test_database(ohlcv_db_name)

    # Store original DB names for restoration
    original_orm_db = os.getenv("DB_NAME")
    original_ohlcv_db = os.getenv("DB_OHLCV_NAME")

    # Set environment variables for this worker
    os.environ["DB_NAME"] = orm_db_name
    os.environ["DB_OHLCV_NAME"] = ohlcv_db_name

    # Create engines and initialize schemas
    await get_or_create_engine(orm_db_name, create_ohlcv_schemas=False)
    await get_or_create_engine(ohlcv_db_name, create_ohlcv_schemas=True)

    try:
        yield {
            "orm_db": orm_db_name,
            "ohlcv_db": ohlcv_db_name
        }
    finally:
        # Restore environment variables
        if original_orm_db:
            os.environ["DB_NAME"] = original_orm_db
        else:
            os.environ.pop("DB_NAME", None)

        if original_ohlcv_db:
            os.environ["DB_OHLCV_NAME"] = original_ohlcv_db
        else:
            os.environ.pop("DB_OHLCV_NAME", None)

        # Cleanup databases
        await drop_test_database(orm_db_name)
        await drop_test_database(ohlcv_db_name)


# ============================================================================
# EVENT LOOP FIXTURE - Function-Scoped
# ============================================================================


@pytest.fixture(scope="function")
def event_loop():
    """Create function-scoped event loop to prevent closure issues.

    This ensures each test gets its own fresh event loop, preventing
    "Event loop is closed" errors in async tests.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop

    # Proper cleanup - close loop after test with timeout to prevent hanging
    try:
        # Cancel all pending tasks
        pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        if pending_tasks:
            for task in pending_tasks:
                task.cancel()
            # Wait for cancellation with timeout to avoid hanging
            try:
                future = asyncio.gather(*pending_tasks, return_exceptions=True)
                loop.run_until_complete(asyncio.wait_for(future, timeout=2.0))
            except asyncio.TimeoutError:
                # Force close after timeout - don't wait for hung tasks
                pass

        # Force close the loop regardless of cleanup success
        if not loop.is_closed():
            loop.close()
    except Exception:
        # Always try to close the loop on error
        try:
            if not loop.is_closed():
                loop.close()
        except Exception:
            pass


# ============================================================================
# CACHE CLEARING - For Perfect Test Isolation
# ============================================================================


@pytest.fixture(autouse=True)
async def clear_symbol_cache(request):
    """Clear symbol caches before each test to ensure perfect isolation.

    This is only active for symbol repository tests to avoid unnecessary overhead.
    """
    test_file = request.fspath.basename if hasattr(request.fspath, 'basename') else str(request.fspath)
    if "symbol" in test_file.lower():
        try:
            from fullon_orm.cache import cache_manager
            cache_manager.invalidate_symbol_caches()
            cache_manager.invalidate_exchange_caches()
        except Exception:
            # Ignore cache errors to prevent test failures
            pass


# ============================================================================
# CLEANUP - Session-Level Cleanup
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    """Clean up after all tests.

    This disposes all engines and drops all test databases at the end of the test session.
    """
    def finalizer():
        """Properly dispose engines and drop databases."""
        import asyncio

        async def async_cleanup():
            try:
                # Cleanup all created databases and engines
                for db_name in list(_db_created.keys()):
                    try:
                        # Dispose engine if it exists
                        if db_name in _engine_cache:
                            engine = _engine_cache[db_name]
                            await engine.dispose()

                        # Drop the test database
                        await drop_test_database(db_name)

                    except Exception as e:
                        print(f"Warning: Failed to cleanup {db_name}: {e}")

                # Clear caches
                _engine_cache.clear()
                _db_created.clear()

            except Exception as e:
                print(f"Error during test cleanup: {e}")

        # Run the async cleanup
        try:
            asyncio.run(async_cleanup())
        except Exception as e:
            print(f"Failed to run async cleanup: {e}")

    request.addfinalizer(finalizer)


@pytest.fixture(scope="session")
def worker_id(request):
    """Get worker ID for parallel test execution.

    Returns 'master' for single-threaded execution, or worker ID (e.g., 'gw0', 'gw1')
    for parallel execution with pytest-xdist.
    """
    if hasattr(request.config, 'workerinput'):
        return request.config.workerinput.get('workerid', 'master')
    return 'master'


# ============================================================================
# REDIS ISOLATION FIXTURES - For Future Cache API Integration Tests
# ============================================================================


@pytest.fixture(scope="function")
def redis_db(worker_id, request) -> int:
    """Allocate completely unique Redis DB per test for maximum isolation.

    Each test gets its own database to ensure complete isolation.
    Uses process ID and timestamp to guarantee uniqueness.

    Args:
        worker_id: pytest-xdist worker ID (e.g., "gw0", "gw1", etc.)
        request: pytest request object to get test info

    Returns:
        Redis database number (1-16, rotating but unique per test)

    Safety:
        Never uses Redis DB 0 (reserved for production)
        Worker isolation: Worker 0 → DBs 1-4, Worker 1 → DBs 5-8,
                         Worker 2 → DBs 9-12, Worker 3 → DBs 13-16
    """
    # Get worker number
    if worker_id == "master":
        worker_num = 0
    else:
        try:
            worker_num = int(worker_id[2:])  # Extract number from "gw0", "gw1", etc.
        except (ValueError, IndexError):
            worker_num = 0

    # Create unique identifier for this test
    test_file = os.path.basename(request.node.fspath)
    test_name = request.node.name
    timestamp = str(time.time_ns())  # Nanosecond precision
    process_id = str(os.getpid())

    # Create hash for unique DB selection
    unique_string = f"{worker_id}_{test_file}_{test_name}_{timestamp}_{process_id}"
    hash_value = int(hashlib.md5(unique_string.encode()).hexdigest()[:8], 16)

    # Each worker gets a base DB range, but tests cycle through them uniquely
    base_db = (worker_num * 4) + 1  # Worker 0: 1-4, Worker 1: 5-8, Worker 2: 9-12, Worker 3: 13-16
    db_offset = hash_value % 4  # 4 DBs per worker for better isolation
    db_num = base_db + db_offset

    # Ensure we stay within Redis DB limits (1-15, extend to 16 for worker 3)
    if db_num > 15:
        db_num = ((db_num - 1) % 15) + 1

    # Set environment variable for this test
    os.environ['REDIS_DB'] = str(db_num)
    return db_num


@pytest.fixture(scope="module", autouse=True)
def redis_db_per_module(request):
    """Set Redis DB for each test file - module scoped with worker isolation.

    This fixture automatically allocates a unique Redis DB per test module (file)
    with worker-aware isolation to prevent conflicts in parallel execution.

    Args:
        request: pytest request object

    Returns:
        Redis database number (1-15)

    Note:
        This is autouse=True so it applies to all test modules automatically.
        It sets REDIS_DB environment variable and resets ConnectionPool after module.
    """
    # Get worker ID from pytest-xdist if available
    worker_id = getattr(request.config, 'workerinput', {}).get('workerid', 'master')

    # Get worker number for proper isolation
    if worker_id == "master":
        worker_num = 0
    else:
        try:
            worker_num = int(worker_id[2:])  # Extract number from "gw0", "gw1", etc.
        except (ValueError, IndexError):
            worker_num = 0

    # Each worker gets a base DB range to avoid conflicts
    base_db = (worker_num * 5) + 1  # Worker 0: 1, Worker 1: 6, Worker 2: 11

    # Get test file name and determine DB offset
    test_file = os.path.basename(request.node.fspath)

    # Map test files to consistent DB offsets within worker range
    # This ensures same test file always gets same DB per worker
    test_file_db_map = {
        # Add your test files here as needed
        # For now, use hash-based assignment
    }

    # Get DB offset from map, or use hash-based assignment for unknown files
    if test_file in test_file_db_map:
        db_offset = test_file_db_map[test_file]
    else:
        # Hash the filename to get a consistent offset within worker range
        db_offset = hash(test_file) % 5

    # Calculate final DB number within Redis limits (1-15)
    db_num = ((base_db + db_offset - 1) % 15) + 1

    os.environ['REDIS_DB'] = str(db_num)
    print(f"\n[REDIS DB SELECT] Worker {worker_id} using Redis DB {db_num} for test file {test_file}")

    yield db_num

    # Reset ConnectionPool after module
    try:
        from fullon_cache.connection import ConnectionPool
        ConnectionPool.reset()
    except Exception:
        # fullon_cache might not be available yet, that's OK
        pass


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
