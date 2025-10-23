# Redis Isolation Fixtures - Quick Start Guide

## TL;DR

Redis isolation fixtures are ready to use for cache API integration tests. Just use the fixtures and everything is automatically isolated and cleaned up.

## Basic Usage

### Simple Cache Test

```python
import pytest

@pytest.mark.asyncio
async def test_my_cache(clean_redis, redis_db):
    """Test cache operations with automatic isolation and cleanup."""
    from fullon_cache import TickCache

    cache = TickCache()  # Uses REDIS_DB from environment
    # Your test code here
    # Automatically cleaned up after test
```

### Database + Cache Test

```python
import pytest

@pytest.mark.asyncio
async def test_database_and_cache(db_context, clean_redis, redis_db):
    """Test with both PostgreSQL and Redis."""
    # Database operations
    user = await db_context.users.get_by_id(1)

    # Cache operations
    from fullon_cache import AccountCache
    cache = AccountCache()
    # Both automatically isolated and cleaned up
```

## Available Fixtures

### Must Use For Cache Tests

1. **`clean_redis`** - Aggressive Redis cleanup (always use this)
2. **`redis_db`** - Unique Redis database per test

### Optional

3. **`test_isolation_prefix`** - Ultra-unique key prefix
4. **`redis_db_per_module`** - Auto-applied to all modules

## Running Tests

```bash
# Single test
poetry run pytest tests/integration/test_cache.py::test_my_cache -xvs

# All tests in file
poetry run pytest tests/integration/test_cache.py -xvs

# Parallel execution (4 workers)
poetry run pytest tests/integration/test_cache.py -n 4 -xvs
```

## What You Get

- **Isolation**: Each test gets its own Redis database
- **Cleanup**: Database flushed before and after each test
- **Safety**: Never uses Redis DB 0 (production)
- **Parallel**: Works with pytest-xdist (multiple workers)
- **Debug**: See which DB is allocated: `[REDIS DB SELECT] Worker master using Redis DB 5`

## Worker Isolation

Each worker gets its own Redis DB range:

```
Worker 0 (master): DBs 1-4
Worker 1 (gw0):    DBs 5-8
Worker 2 (gw1):    DBs 9-12
Worker 3 (gw2):    DBs 13-16
```

## Example Test File

See complete examples in:
```
tests/integration/test_redis_isolation_example.py
```

## Common Patterns

### Pattern 1: Cache Only
```python
@pytest.mark.asyncio
async def test_cache_only(clean_redis, redis_db):
    from fullon_cache import TickCache
    cache = TickCache()
    # Test operations
```

### Pattern 2: Database + Cache
```python
@pytest.mark.asyncio
async def test_db_and_cache(db_context, clean_redis, redis_db):
    user = await db_context.users.get_by_id(1)
    cache = AccountCache()
    # Test operations
```

### Pattern 3: Full Integration
```python
@pytest.mark.asyncio
async def test_full_stack(dual_test_databases, clean_redis, redis_db):
    orm_db = dual_test_databases["orm_db"]
    ohlcv_db = dual_test_databases["ohlcv_db"]
    cache = OHLCVCache()
    # Test operations
```

## Requirements

1. Redis server running: `redis-server`
2. fullon_cache installed (optional - fixtures degrade gracefully)
3. Environment variables set in `.env` (already configured)

## Troubleshooting

### Redis not running?
```bash
redis-server
# or
sudo systemctl start redis
```

### Tests interfering?
Make sure you use `clean_redis` fixture:
```python
async def test_my_test(clean_redis, redis_db):  # ← clean_redis is required
    # Test code
```

### Keys persisting?
Check that `clean_redis` is in your test signature and Redis is running.

## More Information

- Full documentation: `tests/REDIS_ISOLATION.md`
- Implementation summary: `REDIS_ISOLATION_SUMMARY.md`
- Example tests: `tests/integration/test_redis_isolation_example.py`

## Quick Reference Card

```python
# Imports
import pytest

# Basic test structure
@pytest.mark.asyncio
async def test_name(clean_redis, redis_db):
    from fullon_cache import SomeCache
    cache = SomeCache()
    # Test code here
    # Automatic cleanup by fixtures

# With database
@pytest.mark.asyncio
async def test_name(db_context, clean_redis, redis_db):
    # Both PostgreSQL and Redis available

# Run tests
poetry run pytest tests/integration/test_file.py -xvs

# Run in parallel
poetry run pytest tests/integration/test_file.py -n 4 -xvs
```

---

**That's it!** Just use `clean_redis` and `redis_db` in your test signatures and you get automatic isolation and cleanup.
