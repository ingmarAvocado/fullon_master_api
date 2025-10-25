#!/usr/bin/env python3
"""
Example: OHLCV API Routes - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates realistic OHLCV data (30 days of 1m candles)
- Tests the API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_ohlcv_routes.py

Demonstrates:
- Fetching OHLCV (candlestick) data with JWT authentication
- Getting latest candle data
- Different timeframes (1m, 5m, 15m, 1h, 1d)
- Time range queries

Available Endpoints (mounted in fullon_master_api):
- GET /api/v1/ohlcv/{exchange}/{symbol}        - Get OHLCV data
- GET /api/v1/ohlcv/{exchange}/{symbol}/latest - Get latest candle

Note: All endpoints require JWT authentication via Bearer token.
"""

# 1. Standard library imports ONLY
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

# 2. Third-party imports (non-fullon packages)
import httpx

# 3. Generate test database names FIRST (before .env and imports)
def generate_test_db_name() -> str:
    """Generate unique test database name (copied from demo_data.py to avoid imports)."""
    import random
    import string
    return "fullon2_test_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

test_db_base = generate_test_db_name()
test_db_orm = test_db_base
test_db_ohlcv = f"{test_db_base}_ohlcv"

# 4. Set ALL database environment variables BEFORE loading .env (so they won't be overridden)
os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv
# CRITICAL: Also override DB_TEST_NAME to prevent test mode from using wrong database
os.environ["DB_TEST_NAME"] = test_db_orm

# 5. NOW load .env file (won't override existing env vars)
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env", override=False)  # Don't override our test DB settings
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# 6. Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# 7. NOW safe to import ALL fullon modules (env vars set, .env loaded)
from demo_data import (
    create_dual_test_databases,
    drop_dual_test_databases,
    install_demo_data
)
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Import JWT handler
# NOTE: We do NOT import settings at module level to avoid early caching
try:
    from fullon_master_api.auth.jwt import JWTHandler
except ImportError:
    # Fallback for when running outside the project
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from fullon_master_api.auth.jwt import JWTHandler

# 9. Initialize logger
logger = get_component_logger("fullon.examples.ohlcv_routes")

API_BASE_URL = "http://localhost:8000"


async def start_test_server():
    """Start uvicorn server as async background task.

    Runs in the same process with shared environment variables,
    ensuring fullon_ohlcv connects to the correct test database.
    """
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    return server, task


class OHLCVAPIClient:
    """Client for OHLCV API endpoints with JWT authentication."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        # Import settings here to avoid early caching of DB_NAME
        from fullon_master_api.config import settings

        self.base_url = base_url
        self.token = token
        self.jwt_handler = JWTHandler(settings.jwt_secret_key, settings.jwt_algorithm)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with JWT authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def create_demo_token(self, user_id: int = 1) -> str:
        """Create a demo JWT token for testing."""
        return self.jwt_handler.create_token({
            "sub": str(user_id),
            "user_id": user_id,
            "scopes": ["read", "write"]
        })

    async def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[List[List[float]]]:
        """
        Get OHLCV candlestick data.

        Args:
            exchange: Exchange name (e.g., "kraken")
            symbol: Trading pair (e.g., "BTC/USDC")
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 1d)
            limit: Maximum number of candles
            start_time: Start datetime (UTC)
            end_time: End datetime (UTC)

        Returns:
            List of OHLCV arrays: [[timestamp, open, high, low, close, volume], ...]
        """
        # Use the mounted endpoint path with timeframe in the path
        # URL-encode symbol to handle slashes (e.g., BTC/USDC -> BTC%2FUSDC)
        encoded_symbol = quote(symbol, safe='')
        url = f"{self.base_url}/api/v1/ohlcv/{exchange}/{encoded_symbol}/{timeframe}"

        params = {"limit": limit}

        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "OHLCV data retrieved",
                    exchange=exchange,
                    symbol=symbol,
                    count=len(data) if data else 0,
                )
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get OHLCV failed",
                    status=e.response.status_code,
                    exchange=exchange,
                    symbol=symbol,
                    response_body=e.response.text[:500],
                    url=url,
                )
                print(f"   DEBUG: HTTP {e.response.status_code} error")
                print(f"   DEBUG: URL: {url}")
                print(f"   DEBUG: Response: {e.response.text[:500]}")
                return None

    async def get_trades(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get raw trade data.

        Note: This endpoint may not be available in all versions of fullon_ohlcv_api.

        Args:
            exchange: Exchange name
            symbol: Trading pair
            limit: Maximum number of trades
            start_time: Start datetime (UTC)

        Returns:
            List of trade objects, or None if endpoint not available
        """
        # URL-encode symbol to handle slashes
        encoded_symbol = quote(symbol, safe='')
        url = f"{self.base_url}/api/v1/ohlcv/{exchange}/{encoded_symbol}"

        params = {"limit": limit}
        if start_time:
            params["start_time"] = start_time.isoformat()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Trade data retrieved",
                    exchange=exchange,
                    symbol=symbol,
                    count=len(data) if data else 0,
                )
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(
                        "Trades endpoint not available",
                        exchange=exchange,
                        symbol=symbol,
                    )
                else:
                    logger.error(
                        "Get trades failed",
                        status=e.response.status_code,
                        exchange=exchange,
                        symbol=symbol,
                    )
                return None

    async def get_latest_ohlcv(
        self, exchange: str, symbol: str, timeframe: str = "1m"
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest OHLCV candle.

        Args:
            exchange: Exchange name
            symbol: Trading pair
            timeframe: Candle timeframe

        Returns:
            Latest OHLCV candle data as dict
        """
        # URL-encode symbol to handle slashes
        encoded_symbol = quote(symbol, safe='')
        url = f"{self.base_url}/api/v1/ohlcv/{exchange}/{encoded_symbol}/latest"

        params = {"timeframe": timeframe}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Latest OHLCV retrieved",
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                )
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get latest OHLCV failed",
                    status=e.response.status_code,
                    exchange=exchange,
                    symbol=symbol,
                )
                return None


async def setup_realistic_ohlcv_data():
    """
    Setup test databases with realistic 30 days of 1m OHLCV data.

    Steps:
    1. Create dual test databases (ORM + OHLCV)
    2. Install ORM metadata (exchanges, symbols, users)
    3. Initialize OHLCV tables via init_symbol()
    4. Populate with 43,200 x 1m candles (30 days)
    """
    print("\n" + "=" * 60)
    print("Setting up self-contained test environment")
    print("=" * 60)

    logger.info("Creating test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)

    # Step 1: Create dual test databases
    print(f"\n1. Creating dual test databases:")
    print(f"   ORM DB:   {test_db_orm}")
    print(f"   OHLCV DB: {test_db_ohlcv}")

    orm_db_name, ohlcv_db_name = await create_dual_test_databases(test_db_base)
    logger.info("Test databases created", orm_db=orm_db_name, ohlcv_db=ohlcv_db_name)

    # Step 2: Initialize database schema
    print("\n2. Initializing database schema...")
    await init_db()
    print("   ✅ Schema initialized")

    # Step 3: Install demo data (includes OHLCV data via new install_ohlcv_sample_data)
    print("\n3. Installing demo data (users, exchanges, symbols, OHLCV)...")
    success = await install_demo_data()
    if not success:
        raise Exception("Failed to install demo data")

    print("\n" + "=" * 60)
    print("✅ Test environment ready!")
    print("=" * 60)


async def run_ohlcv_examples():
    """Run all OHLCV API examples (separated for clarity)."""
    print("\n" + "=" * 60)
    print("Running OHLCV API Examples")
    print("=" * 60)
    print("🔐 All endpoints require JWT authentication")
    print("📊 Using demo user (user_id=1) with read/write scopes")

    try:
        # Example 1: Basic OHLCV data
        await example_ohlcv_data()

        # Example 2: Trade data (may not be available)
        await example_trade_data()

        # Example 3: Time-range queries
        await example_time_range_query()

        # Example 4: Multiple timeframes
        await example_multiple_timeframes()

        print("\n" + "=" * 60)
        print("✅ Examples completed!")
        print("💡 Key Points:")
        print("   - All endpoints require Bearer JWT tokens")
        print("   - Response format: {'candles': [{'timestamp': '...', 'open': ..., ...}], ...}")
        print("   - Candle fields: timestamp (ISO), open, high, low, close, vol")
        print("   - Supported timeframes: 1m, 5m, 15m, 1h, 1d")
        print("   - Routes are COMPOSED from fullon_ohlcv_api with auth overrides")
        print("   - Database setup required for actual data retrieval")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("Make sure the server is running on localhost:8000")
        print("and the OHLCV database is properly configured.")


async def example_ohlcv_data():
    """Demonstrate OHLCV data retrieval with JWT authentication."""
    print("\n" + "=" * 60)
    print("Example: OHLCV Data Retrieval (with JWT Auth)")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)  # Demo user
    client.token = token

    print("🔐 Using JWT token for user_id=1")

    # Use demo data symbol (hyperliquid BTC/USDC)
    print("\n1️⃣  Fetching 1-minute OHLCV data for BTC/USDC (Hyperliquid)...")
    ohlcv = await client.get_ohlcv(
        exchange="hyperliquid", symbol="BTC/USDC", timeframe="1m", limit=10
    )

    if ohlcv and isinstance(ohlcv, dict) and ohlcv.get('candles'):
        candles = ohlcv['candles']
        print(f"   ✅ Retrieved {len(candles)} candles")
        print("   Latest candle:")
        latest = candles[-1] if candles else None
        if latest:
            print(f"      Timestamp: {latest['timestamp']}")
            print(f"      Open:      ${latest['open']:,.2f}")
            print(f"      High:      ${latest['high']:,.2f}")
            print(f"      Low:       ${latest['low']:,.2f}")
            print(f"      Close:     ${latest['close']:,.2f}")
            print(f"      Volume:    {latest['vol']:,.4f}")
    else:
        print("   ❌ Failed to retrieve OHLCV data (may be due to missing database)")

    print("\n2️⃣  Fetching 1-hour OHLCV data...")
    ohlcv_1h = await client.get_ohlcv(
        exchange="hyperliquid", symbol="BTC/USDC", timeframe="1h", limit=24
    )

    if ohlcv_1h and isinstance(ohlcv_1h, dict) and ohlcv_1h.get('candles'):
        print(f"   ✅ Retrieved {len(ohlcv_1h['candles'])} hourly candles (last 24 hours)")
    else:
        print("   ❌ Failed to retrieve 1h OHLCV data (may be due to missing database)")


async def example_trade_data():
    """Demonstrate trade data retrieval (if available)."""
    print("\n" + "=" * 60)
    print("Example: Raw Trade Data Retrieval")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)
    client.token = token

    print("\n1️⃣  Fetching recent trades for BTC/USDC (Hyperliquid)...")
    trades = await client.get_trades(exchange="hyperliquid", symbol="BTC/USDC", limit=10)

    if trades:
        print(f"   ✅ Retrieved {len(trades)} trades")
        print("   Most recent trade:")
        recent = trades[-1] if trades else None
        if recent:
            print(f"      Time:   {recent.get('timestamp', 'N/A')}")
            print(f"      Price:  ${recent.get('price', 0):,.2f}")
            print(f"      Volume: {recent.get('volume', 0):,.6f}")
            print(f"      Side:   {recent.get('side', 'N/A')}")
    else:
        print(
            "   ❌ Trade data not available "
            "(endpoint may not be implemented or database not set up)"
        )


async def example_time_range_query():
    """Demonstrate time-range queries."""
    print("\n" + "=" * 60)
    print("Example: Time-Range Queries")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)
    client.token = token

    # Get data for last hour
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    print("\n1️⃣  Fetching OHLCV for last hour (Hyperliquid BTC/USDC)...")
    print(f"   Start: {start_time.isoformat()}")
    print(f"   End:   {end_time.isoformat()}")

    ohlcv = await client.get_ohlcv(
        exchange="hyperliquid",
        symbol="BTC/USDC",
        timeframe="1m",
        start_time=start_time,
        end_time=end_time,
    )

    if ohlcv and isinstance(ohlcv, dict) and ohlcv.get('candles'):
        candles = ohlcv['candles']
        print(f"   ✅ Retrieved {len(candles)} candles for specified time range")

        if len(candles) > 0:
            first = candles[0]
            last = candles[-1]
            print(f"   First candle: {first['timestamp']}")
            print(f"   Last candle:  {last['timestamp']}")
    else:
        print("   ❌ Failed to retrieve time-range data (may be due to missing database)")


async def example_multiple_timeframes():
    """Demonstrate fetching multiple timeframes."""
    print("\n" + "=" * 60)
    print("Example: Multiple Timeframes")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)
    client.token = token

    timeframes = ["1m", "5m", "15m", "1h", "1d"]

    for tf in timeframes:
        print(f"\n⏱️  Fetching {tf} candles (Hyperliquid BTC/USDC)...")
        ohlcv = await client.get_ohlcv(
            exchange="hyperliquid", symbol="BTC/USDC", timeframe=tf, limit=5
        )

        if ohlcv and isinstance(ohlcv, dict) and ohlcv.get('candles'):
            print(f"   ✅ Got {len(ohlcv['candles'])} {tf} candles")
        else:
            print(f"   ❌ Failed to get {tf} candles (may be due to missing database)")


async def main():
    """
    Main entry point - self-contained with setup and cleanup.

    Pattern (from ohlcv_collection_example.py):
    1. Setup test databases and install data
    2. Run examples
    3. Always cleanup databases (even on failure)
    """
    print("=" * 60)
    print("Fullon Master API - OHLCV Routes Example")
    print("SELF-CONTAINED: Creates, tests, and cleans up databases")
    print("=" * 60)

    server = None
    server_task = None
    try:
        # Setup test environment
        await setup_realistic_ohlcv_data()

        # Start embedded test server as async background task
        print("\n4. Starting test server on localhost:8000...")
        server, server_task = await start_test_server()
        await asyncio.sleep(2)  # Wait for server to start
        print("   ✅ Server started")

        # Run examples
        await run_ohlcv_examples()

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()
        logger.error("Example failed", error=str(e))

    finally:
        # Stop test server
        if server:
            print("\n   Stopping test server...")
            server.should_exit = True
            if server_task:
                try:
                    await asyncio.wait_for(server_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Server shutdown timed out")
            print("   ✅ Server stopped")

        # Always cleanup test databases
        print("\n" + "=" * 60)
        print("Cleaning up test databases...")
        print("=" * 60)
        try:
            logger.info("Dropping test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)
            await drop_dual_test_databases(test_db_orm, test_db_ohlcv)
            print("✅ Test databases cleaned up successfully")
            logger.info("Cleanup complete")
        except Exception as cleanup_error:
            print(f"⚠️  Error during cleanup: {cleanup_error}")
            logger.warning("Cleanup error", error=str(cleanup_error))


if __name__ == "__main__":
    asyncio.run(main())
