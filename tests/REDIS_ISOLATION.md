# Redis Isolation Fixtures for fullon_master_api

This document describes the Redis isolation fixtures implemented for fullon_master_api integration tests. These fixtures follow the proven pattern from fullon_cache and provide complete isolation for parallel test execution.

## Overview

The Redis isolation system provides:

1. **Worker-level isolation**: Each pytest-xdist worker gets its own Redis database range
2. **Test-level isolation**: Each test can optionally get a unique Redis database
3. **Module-level isolation**: Each test module (file) gets a consistent Redis database per worker
4. **Aggressive cleanup**: Ultra-clean Redis state before and after each test
5. **Safety guarantees**: Never uses Redis DB 0 (production)

## Architecture

### Database Allocation Strategy

```
Redis DB 0: PRODUCTION (NEVER USED IN TESTS)

Worker 0 (master):  DBs 1-4   (per-test allocation)
Worker 1 (gw0):     DBs 5-8   (per-test allocation)
Worker 2 (gw1):     DBs 9-12  (per-test allocation)
Worker 3 (gw2):     DBs 13-16 (per-test allocation, wraps to 1-15)

Module-level:
Worker 0 (master):  DBs 1-5   (per-module allocation)
Worker 1 (gw0):     DBs 6-10  (per-module allocation)
Worker 2 (gw1):     DBs 11-15 (per-module allocation)
```

## Available Fixtures

### 1. `redis_db` (Function-scoped)

Allocates a unique Redis database per test with worker isolation.

**Signature:**
```python
@pytest.fixture(scope="function")
def redis_db(worker_id, request) -> int
```

**Returns:** Redis database number (1-15)

**Features:**
- Hash-based DB selection for uniqueness
- Nanosecond timestamp + process ID + test info for isolation
- Sets `REDIS_DB` environment variable
- Worker-aware allocation

**Usage:**
```python
def test_redis_allocation(redis_db):
    assert 1 <= redis_db <= 15
    assert os.getenv('REDIS_DB') == str(redis_db)
```

### 2. `redis_db_per_module` (Module-scoped, autouse=True)

Allocates a Redis database per test module (file) with worker isolation.

**Signature:**
```python
@pytest.fixture(scope="module", autouse=True)
def redis_db_per_module(request)
```

**Returns:** Redis database number (1-15)

**Features:**
- Automatic application to all test modules
- Worker-aware base DB ranges
- Hash-based offset for test files
- Resets ConnectionPool after module
- Prints DB allocation for debugging

**Usage:**
```python
# Automatically applied to all test modules
# No explicit usage required
```

**Output:**
```
[REDIS DB SELECT] Worker master using Redis DB 5 for test file test_cache.py
```

### 3. `clean_redis` (Async fixture, function-scoped)

Provides aggressive Redis cleanup before and after each test.

**Signature:**
```python
@pytest_asyncio.fixture
async def clean_redis(redis_db) -> AsyncGenerator[None, None]
```

**Features:**
- Flushes entire test database before test
- Multiple cleanup attempts with retries (3 attempts)
- Verifies database is empty (`dbsize() == 0`)
- Resets ConnectionPool before and after
- Ultra-aggressive post-test cleanup
- Graceful degradation if fullon_cache not installed

**Usage:**
```python
@pytest.mark.asyncio
async def test_cache_operations(clean_redis, redis_db):
    from fullon_cache import TickCache
    cache = TickCache()  # Uses REDIS_DB from environment

    # Database is completely clean at start
    # All operations automatically cleaned up after test
```

**Cleanup Process:**
```
1. Pre-test cleanup:
   - Reset ConnectionPool
   - Flush database (3 attempts)
   - Verify dbsize() == 0
   - Brief pause (0.05s)

2. Test execution

3. Post-test cleanup:
   - Reset ConnectionPool
   - Double flush database (3 attempts)
   - Brief pause (0.05s)
```

### 4. `test_isolation_prefix` (Function-scoped)

Generates ultra-unique prefixes for Redis keys to prevent cross-test contamination.

**Signature:**
```python
@pytest.fixture(scope="function")
def test_isolation_prefix(worker_id, request) -> str
```

**Returns:** Ultra-unique prefix in format `w{worker_num}_{hash}`

**Features:**
- SHA256 hash of: worker_id + test_file + test_name + timestamp_ns + process_id + uuid
- Nanosecond precision timestamp
- 16-character hash for reasonable key length
- Prevents key collisions even in same Redis DB

**Usage:**
```python
def test_with_prefix(test_isolation_prefix, clean_redis):
    from fullon_cache import BaseCache
    cache = BaseCache()

    # Use prefix for guaranteed unique keys
    key = f"{test_isolation_prefix}:user:123"
    # key example: "w0_a1b2c3d4e5f6a7b8:user:123"
```

## Integration Patterns

### Pattern 1: Cache API Only

For tests that only need Redis/cache operations:

```python
import pytest

@pytest.mark.asyncio
async def test_ticker_cache(clean_redis, redis_db):
    """Test ticker cache operations."""
    from fullon_cache import TickCache

    cache = TickCache()
    # Cache automatically uses REDIS_DB from environment

    # Test operations
    await cache.update_ticker("kraken", "BTC/USD", {...})
    ticker = await cache.get_ticker("kraken", "BTC/USD")

    # Automatic cleanup by clean_redis fixture
```

### Pattern 2: Database + Cache

For tests that need both PostgreSQL and Redis:

```python
import pytest

@pytest.mark.asyncio
async def test_user_with_cache(db_context, clean_redis, redis_db):
    """Test user operations with cache."""
    from fullon_cache import AccountCache

    # Database operations
    user = await db_context.users.get_by_id(1)

    # Cache operations
    cache = AccountCache()
    await cache.set_account(user.uid, account_data)

    # Both isolated and cleaned up automatically
```

### Pattern 3: Full Integration (Dual Database + Cache)

For tests that need ORM + OHLCV + Redis:

```python
import pytest

@pytest.mark.asyncio
async def test_full_integration(dual_test_databases, clean_redis, redis_db):
    """Test full integration with all databases."""
    orm_db = dual_test_databases["orm_db"]
    ohlcv_db = dual_test_databases["ohlcv_db"]

    # Both PostgreSQL databases available
    # Redis database available
    # Complete isolation in parallel execution

    from fullon_cache import OHLCVCache
    cache = OHLCVCache()
    # Test operations across all databases
```

### Pattern 4: Custom Key Prefixes

For tests requiring additional key namespace isolation:

```python
import pytest

@pytest.mark.asyncio
async def test_with_custom_prefix(clean_redis, redis_db, test_isolation_prefix):
    """Test with custom key prefix for extra isolation."""
    from fullon_cache import BaseCache

    cache = BaseCache()

    # Use prefix for guaranteed unique keys
    key = f"{test_isolation_prefix}:bot:strategy:123"
    # Example: "w0_a1b2c3d4e5f6a7b8:bot:strategy:123"

    # Guaranteed unique even if tests run in same Redis DB
```

## Safety Features

### Production Protection

1. **Never uses Redis DB 0**: All fixtures allocate DBs 1-15 only
2. **Environment variable override**: Tests set `REDIS_DB` explicitly
3. **Worker isolation**: Each worker has separate DB range
4. **Module-level safety**: Autouse fixture prevents accidental production access

### Cleanup Guarantees

1. **Pre-test cleanup**: Database flushed before each test
2. **Post-test cleanup**: Database flushed after each test
3. **Multiple attempts**: 3 retry attempts for cleanup operations
4. **Verification**: `dbsize()` check ensures database is empty
5. **ConnectionPool reset**: Prevents connection leaks

### Parallel Execution Safety

1. **Worker-aware allocation**: Each worker gets separate DB range
2. **Hash-based selection**: Unique DB per test within worker range
3. **Timestamp precision**: Nanosecond timestamps prevent collisions
4. **Process ID**: Additional uniqueness guarantee
5. **UUID inclusion**: Final uniqueness guarantee

## Configuration

### Environment Variables

The fixtures use these environment variables (set automatically):

```bash
# Set by redis_db and redis_db_per_module fixtures
REDIS_DB=<1-15>

# Used by fullon_cache (from .env)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# Event loop optimization
FULLON_CACHE_EVENT_LOOP=auto
FULLON_CACHE_AUTO_CONFIGURE=true
```

### .env Configuration

Add to your `.env` file:

```env
# Redis Configuration (fullon_cache)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# Redis event loop optimization
FULLON_CACHE_EVENT_LOOP=auto
FULLON_CACHE_AUTO_CONFIGURE=true

# Cache TTL settings (in seconds)
CACHE_TTL_EXCHANGE=86400
CACHE_TTL_SYMBOL=86400
CACHE_TTL_ORDER=3600
```

## Testing

### Running Tests

```bash
# Single-threaded execution
poetry run pytest tests/integration/test_cache.py -xvs

# Parallel execution (2 workers)
poetry run pytest tests/integration/test_cache.py -n 2 -xvs

# Parallel execution (4 workers)
poetry run pytest tests/integration/test_cache.py -n 4 -xvs

# All integration tests in parallel
poetry run pytest tests/integration/ -n auto -xvs
```

### Verifying Isolation

```bash
# Run with verbose output to see DB allocation
poetry run pytest tests/integration/test_redis_isolation_example.py -xvs

# Output shows:
# [REDIS DB SELECT] Worker master using Redis DB 5 for test file test_redis_isolation_example.py
```

### Debugging

Enable debug output to see fixture behavior:

```python
import pytest

def test_debug_redis(redis_db, test_isolation_prefix):
    print(f"\nRedis DB: {redis_db}")
    print(f"Isolation prefix: {test_isolation_prefix}")
    print(f"REDIS_DB env: {os.getenv('REDIS_DB')}")
```

## Advanced Usage

### Custom Cleanup Patterns

If you need custom cleanup beyond `clean_redis`:

```python
@pytest.mark.asyncio
async def test_custom_cleanup(clean_redis, redis_db):
    from fullon_cache import BaseCache

    cache = BaseCache()

    # Test operations
    await cache.set("key", "value")

    # Custom cleanup (in addition to automatic cleanup)
    async with cache._redis_context() as redis:
        await redis.delete("specific:key:pattern")

    # clean_redis still does final cleanup
```

### Mixing Test Scopes

You can use both function and module-scoped fixtures together:

```python
# redis_db_per_module is autouse=True (module-scoped)
# redis_db overrides it for this specific test (function-scoped)

@pytest.mark.asyncio
async def test_with_both_fixtures(clean_redis, redis_db):
    # Uses redis_db (function-scoped) for this test
    # Other tests in module use redis_db_per_module
    pass
```

## Implementation Details

### Hash-Based DB Selection

The fixtures use MD5 hashing for consistent DB selection:

```python
unique_string = f"{worker_id}_{test_file}_{test_name}_{timestamp}_{process_id}"
hash_value = int(hashlib.md5(unique_string.encode()).hexdigest()[:8], 16)
db_num = base_db + (hash_value % 4)
```

### Worker Range Calculation

```python
# Function-scoped (4 DBs per worker)
base_db = (worker_num * 4) + 1
db_offset = hash_value % 4
db_num = base_db + db_offset

# Module-scoped (5 DBs per worker)
base_db = (worker_num * 5) + 1
db_offset = hash(test_file) % 5
db_num = ((base_db + db_offset - 1) % 15) + 1
```

### Cleanup Retry Logic

```python
for attempt in range(3):
    try:
        await redis.flushdb()
        key_count = await redis.dbsize()
        if key_count == 0:
            break  # Success
    except Exception:
        if attempt == 2:  # Last attempt
            pass  # Continue anyway
        await asyncio.sleep(0.1)
```

## Troubleshooting

### Issue: Tests fail with "Redis connection refused"

**Solution:** Ensure Redis is running:
```bash
redis-server
# or
sudo systemctl start redis
```

### Issue: Tests interfere with each other

**Solution:** Use `clean_redis` fixture:
```python
@pytest.mark.asyncio
async def test_isolated(clean_redis, redis_db):
    # Guaranteed clean database
    pass
```

### Issue: Keys persist between tests

**Solution:** Verify `clean_redis` is used and check cleanup:
```python
@pytest.mark.asyncio
async def test_verify_cleanup(clean_redis, redis_db):
    from fullon_cache import BaseCache
    cache = BaseCache()

    async with cache._redis_context() as redis:
        size = await redis.dbsize()
        assert size == 0, f"Database not clean: {size} keys found"
```

### Issue: Parallel tests conflict

**Solution:** Verify worker isolation:
```bash
# Check which DBs are allocated
poetry run pytest tests/ -n 4 -xvs | grep "REDIS DB SELECT"
```

## Migration Guide

### From No Redis Isolation

Before:
```python
def test_cache():
    cache = SomeCache()
    # Tests might conflict
    # Manual cleanup required
```

After:
```python
@pytest.mark.asyncio
async def test_cache(clean_redis, redis_db):
    cache = SomeCache()
    # Automatic isolation and cleanup
```

### From Manual Cleanup

Before:
```python
@pytest.mark.asyncio
async def test_cache():
    cache = SomeCache()
    try:
        # Test operations
        pass
    finally:
        # Manual cleanup
        await cache.clear()
```

After:
```python
@pytest.mark.asyncio
async def test_cache(clean_redis, redis_db):
    cache = SomeCache()
    # Test operations
    # Automatic cleanup by fixture
```

## Future Enhancements

Planned improvements:

1. **Redis Cluster Support**: Multi-node Redis cluster testing
2. **Performance Metrics**: Track cleanup times and DB usage
3. **Custom Allocators**: Pluggable DB allocation strategies
4. **Snapshot/Restore**: Save/restore Redis state for debugging
5. **Mock Mode**: Optional mock Redis for unit tests

## References

- [fullon_cache conftest.py](../../fullon_cache/tests/conftest.py) - Reference implementation
- [pytest-xdist documentation](https://pytest-xdist.readthedocs.io/) - Parallel execution
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/) - Async fixtures
- [Redis documentation](https://redis.io/docs/) - Redis concepts

## License

This test infrastructure is part of fullon_master_api and follows the same license.

## Support

For issues or questions:
1. Check this documentation
2. Review example tests in `tests/integration/test_redis_isolation_example.py`
3. Check fullon_cache reference implementation
4. File an issue if you discover a bug

---

**Last Updated:** 2025-10-23
**Version:** 1.0.0
**Status:** Production Ready
