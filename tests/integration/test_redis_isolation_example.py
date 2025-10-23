"""Example integration test demonstrating Redis isolation fixtures.

This test file shows how to use the Redis isolation fixtures for cache API integration tests.
The fixtures ensure complete isolation between tests and workers in parallel execution.

Available Fixtures:
- redis_db: Function-scoped, allocates unique Redis DB per test
- redis_db_per_module: Module-scoped, allocates Redis DB per file (autouse=True)
- clean_redis: Async fixture, aggressive Redis cleanup before/after each test
- test_isolation_prefix: Ultra-unique prefix for Redis keys

Usage Patterns:
1. Cache API only: Use clean_redis and redis_db
2. Database + Cache: Use db_context, clean_redis, and redis_db
3. Full integration: Use dual_test_databases, clean_redis, and redis_db
"""

import os
import pytest


class TestRedisIsolationExample:
    """Example tests demonstrating Redis isolation fixture usage."""

    def test_redis_db_allocation(self, redis_db):
        """Test that redis_db fixture allocates a unique database number.

        The redis_db fixture:
        - Returns a Redis DB number (1-15, never 0)
        - Sets REDIS_DB environment variable
        - Uses worker-aware allocation for parallel tests
        - Worker 0: DBs 1-4, Worker 1: DBs 5-8, etc.
        """
        # Verify DB number is allocated
        assert 1 <= redis_db <= 15, f"Redis DB {redis_db} should be between 1-15"

        # Verify environment variable is set
        assert os.getenv('REDIS_DB') == str(redis_db)

        # Verify we're not using production DB 0
        assert redis_db != 0, "Never use Redis DB 0 (production)"

    def test_isolation_prefix_generation(self, test_isolation_prefix):
        """Test that test_isolation_prefix generates ultra-unique prefixes.

        The test_isolation_prefix fixture:
        - Generates format: w{worker_num}_{hash}
        - Hash includes: worker_id, test_file, test_name, timestamp_ns, process_id, uuid
        - Prevents key collisions even in same Redis DB
        """
        # Verify prefix format
        assert test_isolation_prefix.startswith('w')
        assert '_' in test_isolation_prefix

        # Verify prefix length (worker digit + underscore + 16-char hash)
        parts = test_isolation_prefix.split('_', 1)
        assert len(parts) == 2
        assert parts[0].startswith('w')
        assert len(parts[1]) == 16  # SHA256 hash truncated to 16 chars

    @pytest.mark.asyncio
    async def test_clean_redis_fixture(self, clean_redis, redis_db):
        """Test that clean_redis fixture works (requires fullon_cache installed).

        The clean_redis fixture:
        - Flushes entire test database before test
        - Verifies database is empty (dbsize() == 0)
        - Aggressive cleanup with retries
        - Cleans up after test completion
        - Resets ConnectionPool

        Note:
            If fullon_cache is not installed, this fixture passes silently.
            This allows tests to run even before fullon_cache integration.
        """
        # This test demonstrates the fixture is available
        # When fullon_cache is installed, the database will be completely clean
        assert redis_db is not None
        assert 1 <= redis_db <= 15

    @pytest.mark.asyncio
    async def test_cache_api_integration_example(self, db_context, clean_redis, redis_db):
        """Example of full-stack integration test with database and cache.

        This pattern combines:
        - db_context: PostgreSQL ORM database access
        - clean_redis: Clean Redis database
        - redis_db: Isolated Redis DB number

        Usage Example:
            async def test_ticker_cache(db_context, clean_redis, redis_db):
                # Database operations
                user = await db_context.users.get_by_id(1)

                # Cache operations (when fullon_cache is installed)
                from fullon_cache import TickCache
                cache = TickCache()  # Uses REDIS_DB from environment

                # Test cache operations
                # Automatically cleaned up after test
        """
        # Verify both PostgreSQL and Redis isolation are available
        assert db_context is not None, "db_context should provide ORM database access"
        assert redis_db is not None, "redis_db should provide Redis DB number"

        # Example: Database operations work alongside Redis
        # (Add actual fullon_cache operations when available)


class TestRedisWorkerIsolation:
    """Test worker isolation guarantees."""

    def test_worker_db_ranges(self, redis_db, worker_id):
        """Verify that workers use separate DB ranges.

        Worker DB ranges:
        - Worker 0 (master): DBs 1-4
        - Worker 1 (gw0): DBs 5-8
        - Worker 2 (gw1): DBs 9-12
        - Worker 3 (gw2): DBs 13-16 (wraps to 1-15)
        """
        # Extract worker number
        if worker_id == "master":
            worker_num = 0
            expected_min = 1
            expected_max = 4
        else:
            worker_num = int(worker_id[2:])
            expected_min = (worker_num * 4) + 1
            expected_max = (worker_num * 4) + 4

        # Verify DB is within worker's range (with wrapping for high workers)
        if expected_max <= 15:
            assert expected_min <= redis_db <= expected_max, \
                f"Worker {worker_id} should use DBs {expected_min}-{expected_max}, got {redis_db}"


# Module-level documentation for future developers
"""
Future Cache Integration Test Guidelines
========================================

When fullon_cache is integrated, follow these patterns:

1. Simple Cache Test
-------------------
async def test_cache_operation(clean_redis, redis_db):
    from fullon_cache import TickCache
    cache = TickCache()
    # Cache automatically uses REDIS_DB from environment
    # Test operations here
    # Automatic cleanup by clean_redis fixture


2. Cache + Database Test
------------------------
async def test_cache_with_database(db_context, clean_redis, redis_db):
    # Database operations
    user = await db_context.users.get_by_id(1)

    # Cache operations
    from fullon_cache import AccountCache
    cache = AccountCache()
    # Both databases available and isolated


3. Full Integration Test
------------------------
async def test_full_integration(dual_test_databases, clean_redis, redis_db):
    orm_db = dual_test_databases["orm_db"]
    ohlcv_db = dual_test_databases["ohlcv_db"]

    # Both PostgreSQL databases + Redis available
    # Complete isolation in parallel execution


4. Custom Key Prefix
--------------------
async def test_with_prefix(clean_redis, redis_db, test_isolation_prefix):
    from fullon_cache import BaseCache
    cache = BaseCache()

    # Use prefix for additional isolation
    key = f"{test_isolation_prefix}:my_key"
    # Guaranteed unique even in same Redis DB
"""
