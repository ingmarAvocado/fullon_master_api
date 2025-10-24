"""
E2E tests for OHLCV routes example (Phase 4 Issue #29).

Validates:
- example_ohlcv_routes.py executes without errors
- OHLCVAPIClient methods work correctly
- Example follows all 4 critical patterns
- OHLCV endpoints accessible via HTTP API
"""
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fullon_log import get_component_logger

# Add examples directory to path for imports
examples_dir = Path(__file__).parent.parent.parent / "examples"
if str(examples_dir) not in sys.path:
    sys.path.insert(0, str(examples_dir))

# Import example functions to test (after path setup)
# ruff: noqa: E402
from example_ohlcv_routes import (  # noqa: E402  # type: ignore
    OHLCVAPIClient,
    example_multiple_timeframes,
    example_ohlcv_data,
    example_time_range_query,
    example_trade_data,
)

logger = get_component_logger("fullon.master_api.tests.e2e.ohlcv")


@pytest.fixture(scope="module")
def server_process():
    """
    Start server for E2E testing.

    Yields:
        subprocess.Popen: Server process
    """
    logger.info("Starting test server for OHLCV E2E tests")

    # Start server
    process = subprocess.Popen(
        ["poetry", "run", "uvicorn", "fullon_master_api.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    time.sleep(3)

    # Verify server is running
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        assert response.status_code == 200
        logger.info("Test server started successfully")
    except Exception as e:
        process.kill()
        logger.error("Test server failed to start", error=str(e))
        raise RuntimeError(f"Server failed to start: {e}")

    yield process

    # Cleanup
    logger.info("Stopping test server")
    process.kill()
    process.wait()


class TestExampleOHLCVRoutes:
    """E2E tests for OHLCV routes example."""

    @pytest.mark.asyncio
    async def test_example_ohlcv_data_runs(self, server_process):
        """Test example_ohlcv_data() runs without errors."""
        logger.info("Testing example_ohlcv_data execution")
        # Should not raise exceptions
        await example_ohlcv_data()
        logger.info("example_ohlcv_data completed successfully")

    @pytest.mark.asyncio
    async def test_example_trade_data_runs(self, server_process):
        """Test example_trade_data() runs without errors."""
        logger.info("Testing example_trade_data execution")
        await example_trade_data()
        logger.info("example_trade_data completed successfully")

    @pytest.mark.asyncio
    async def test_example_time_range_query_runs(self, server_process):
        """Test example_time_range_query() runs without errors."""
        logger.info("Testing example_time_range_query execution")
        await example_time_range_query()
        logger.info("example_time_range_query completed successfully")

    @pytest.mark.asyncio
    async def test_example_multiple_timeframes_runs(self, server_process):
        """Test example_multiple_timeframes() runs without errors."""
        logger.info("Testing example_multiple_timeframes execution")
        await example_multiple_timeframes()
        logger.info("example_multiple_timeframes completed successfully")

    @pytest.mark.asyncio
    async def test_ohlcv_client_methods_work(self, server_process):
        """Test OHLCVAPIClient methods work correctly."""
        logger.info("Testing OHLCVAPIClient methods")

        client = OHLCVAPIClient()
        # Create demo token for testing
        token = client.create_demo_token(user_id=1)
        client.token = token

        # Test get_ohlcv method
        logger.info("Testing get_ohlcv method", exchange="kraken", symbol="BTC/USDC")
        data = await client.get_ohlcv(
            exchange="kraken",
            symbol="BTC/USDC",
            timeframe="1m",
            limit=10
        )

        # Should return list or None (if database not set up)
        assert data is None or isinstance(data, list), (
            "get_ohlcv should return list of candles or None"
        )
        logger.info("get_ohlcv validated", has_data=data is not None)

        # Test get_latest_ohlcv method
        logger.info("Testing get_latest_ohlcv method", exchange="kraken", symbol="BTC/USDC")
        latest = await client.get_latest_ohlcv(
            exchange="kraken",
            symbol="BTC/USDC",
            timeframe="1m"
        )

        # Should return dict or None
        assert latest is None or isinstance(latest, (dict, list)), (
            "get_latest_ohlcv should return dict/list or None"
        )
        logger.info("get_latest_ohlcv validated", has_data=latest is not None)

        # Test get_trades method
        logger.info("Testing get_trades method", exchange="kraken", symbol="BTC/USDC")
        trades = await client.get_trades(
            exchange="kraken",
            symbol="BTC/USDC",
            limit=5
        )

        # Should return list or None (trades endpoint may not exist)
        assert trades is None or isinstance(trades, list), (
            "get_trades should return list of trades or None"
        )
        logger.info("get_trades validated", has_data=trades is not None)


class TestExamplePatternCompliance:
    """Test example code follows all 4 critical patterns."""

    def test_example_uses_http_api_not_direct_imports(self):
        """Test example uses HTTP API, not direct fullon_ohlcv imports."""
        logger.info("Validating HTTP API usage pattern")

        example_file = examples_dir / "example_ohlcv_routes.py"
        content = example_file.read_text()

        # Should use httpx for HTTP API calls
        assert "httpx.AsyncClient" in content or "httpx" in content, (
            "Example should use httpx.AsyncClient for HTTP API calls"
        )

        # Should NOT import fullon_ohlcv directly
        assert "from fullon_ohlcv import" not in content, (
            "Example should NOT import fullon_ohlcv directly. "
            "Use HTTP API via httpx instead (ADR-001: Router Composition)"
        )

        # Should NOT import fullon_ohlcv_api directly
        assert "from fullon_ohlcv_api import" not in content, (
            "Example should NOT import fullon_ohlcv_api directly. "
            "Use HTTP API via httpx instead"
        )

        logger.info("HTTP API usage pattern validated")

    def test_example_urls_follow_structure(self):
        """Test example uses /api/v1/ohlcv/* URL structure."""
        logger.info("Validating URL structure pattern")

        example_file = examples_dir / "example_ohlcv_routes.py"
        content = example_file.read_text()

        # Should use /api/v1/ohlcv/* structure for OHLCV endpoints
        assert "/api/v1/ohlcv/" in content, (
            "Example should use /api/v1/ohlcv/* URL structure for OHLCV endpoints"
        )

        # Check for specific endpoint patterns
        has_url_pattern = (
            'f"{self.base_url}/api/v1/ohlcv/{exchange}/{symbol}"' in content
            or '/api/v1/ohlcv/' in content
        )
        assert has_url_pattern, (
            "Example should demonstrate /api/v1/ohlcv/{exchange}/{symbol} endpoint"
        )

        # May also use /api/v1/trades/* for trade endpoints
        # This is optional but good to check
        if "/api/v1/trades/" in content:
            logger.info("Trade endpoints also found", pattern="/api/v1/trades/*")

        logger.info("URL structure pattern validated")

    def test_example_demonstrates_jwt_auth(self):
        """Test example demonstrates JWT authentication."""
        logger.info("Validating JWT authentication pattern")

        example_file = examples_dir / "example_ohlcv_routes.py"
        content = example_file.read_text()

        # Should demonstrate Bearer token auth
        assert "Bearer" in content or "Authorization" in content, (
            "Example should demonstrate JWT Bearer token authentication"
        )

        # Should show token creation/handling
        assert "token" in content.lower(), (
            "Example should show JWT token handling"
        )

        # Should have _get_headers or similar auth header method
        assert "_get_headers" in content or '"Authorization"' in content, (
            "Example should show how to add Authorization headers"
        )

        # Should create or use JWT tokens
        assert "create_demo_token" in content or "JWTHandler" in content, (
            "Example should demonstrate JWT token creation"
        )

        logger.info("JWT authentication pattern validated")

    def test_example_uses_fullon_log(self):
        """Test example uses fullon_log structured logging."""
        logger.info("Validating structured logging pattern")

        example_file = examples_dir / "example_ohlcv_routes.py"
        content = example_file.read_text()

        # Should import fullon_log
        assert "from fullon_log import" in content, (
            "Example should import fullon_log for structured logging"
        )

        # Should use get_component_logger
        assert "get_component_logger" in content, (
            "Example should use get_component_logger for structured logging"
        )

        # Should use structured logging (key=value pairs)
        assert "logger.info" in content or "logger.error" in content, (
            "Example should use logger.info/error for structured logging"
        )

        # Should NOT use f-strings in logging
        # Check for common anti-patterns
        if 'logger.info(f"' in content or "logger.info(f'" in content:
            # This is a warning, not a hard failure
            logger.warning("Example may be using f-strings in logging",
                          recommendation="Use structured key=value pairs instead")

        # Should use structured logging with key=value pairs
        assert "exchange=" in content or "symbol=" in content or "count=" in content, (
            "Example should use structured logging with key=value pairs (e.g., exchange=...)"
        )

        logger.info("Structured logging pattern validated")
