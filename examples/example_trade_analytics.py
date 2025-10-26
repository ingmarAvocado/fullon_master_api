#!/usr/bin/env python3
"""
Example: Trade Analytics - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests trade analytics API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_trade_analytics.py

Demonstrates:
- Creating dry-run and live trades
- Querying trade history and performance
- Analyzing trades by bot and symbol
- Viewing trade statistics and summaries
- Updating and deleting trades

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/trades/bot                  - Get bot trades
- GET    /api/v1/orm/trades/by-bot               - Trades grouped by bot
- GET    /api/v1/orm/trades/by-symbol            - Trades grouped by symbol
- GET    /api/v1/orm/trades/history              - Trade history query
- GET    /api/v1/orm/trades/live                 - Active live trades
- GET    /api/v1/orm/trades/performance          - Trade performance metrics
- GET    /api/v1/orm/trades/stats                - Trade statistics
- GET    /api/v1/orm/trades/stats/overall        - Overall trading statistics
- GET    /api/v1/orm/trades/summary              - Trade summary report
- GET    /api/v1/orm/trades/symbol-performance   - Per-symbol performance
- POST   /api/v1/orm/trades/bot                  - Create bot trade
- POST   /api/v1/orm/trades/dry                  - Create dry-run trade
- POST   /api/v1/orm/trades/live                 - Create live trade
- PATCH  /api/v1/orm/trades/{trade_id}           - Update trade
- DELETE /api/v1/orm/trades/{trade_id}           - Delete trade
"""
# 1. Standard library imports ONLY
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# 2. Third-party imports (non-fullon packages)
import httpx


# 3. Generate test database names FIRST (before .env and imports)
def generate_test_db_name() -> str:
    """Generate unique test database name (copied from demo_data.py to avoid imports)."""
    import random
    import string

    return "fullon2_test_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


test_db_base = generate_test_db_name()
test_db_orm = test_db_base
test_db_ohlcv = f"{test_db_base}_ohlcv"

# 4. Set ALL database environment variables BEFORE loading .env
os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv
os.environ["DB_TEST_NAME"] = test_db_orm

# 5. NOW load .env file
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env", override=False)
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# 6. Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# 7. NOW safe to import ALL fullon modules
from demo_data import create_dual_test_databases, drop_dual_test_databases, install_demo_data
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.examples.trade_analytics")

API_BASE_URL = "http://localhost:8000"


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    return server, task


async def login_and_get_token(
    username: str = "admin@fullon", password: str = "password"
) -> Optional[str]:
    """
    Login and get JWT token for authenticated requests.

    Args:
        username: Login username
        password: Login password

    Returns:
        JWT token string or None if login failed
    """
    login_url = f"{API_BASE_URL}/api/v1/auth/login"

    login_data = {
        "username": username,
        "password": password,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                login_url,
                data=login_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            token_data = response.json()
            logger.info("Login successful for trade analytics example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for trade analytics example", error=str(e))
            return None


class TradeAnalyticsClient:
    """Client for trade analytics API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def create_dry_trade(self, trade_data: dict) -> Optional[dict]:
        """Create dry-run trade."""
        url = f"{self.base_url}/api/v1/orm/trades/dry"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=trade_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Create dry trade failed", status=e.response.status_code)
                return None

    async def create_live_trade(self, trade_data: dict) -> Optional[dict]:
        """Create live trade."""
        url = f"{self.base_url}/api/v1/orm/trades/live"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=trade_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Create live trade failed", status=e.response.status_code)
                return None

    async def get_bot_trades(self, bot_id: int) -> Optional[list]:
        """Get trades for specific bot."""
        url = f"{self.base_url}/api/v1/orm/trades/bot?bot_id={bot_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get bot trades failed", status=e.response.status_code, bot_id=bot_id)
                return None

    async def get_trades_by_bot(self) -> Optional[dict]:
        """Get trades grouped by bot."""
        url = f"{self.base_url}/api/v1/orm/trades/by-bot"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trades by bot failed", status=e.response.status_code)
                return None

    async def get_trades_by_symbol(self) -> Optional[dict]:
        """Get trades grouped by symbol."""
        url = f"{self.base_url}/api/v1/orm/trades/by-symbol"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trades by symbol failed", status=e.response.status_code)
                return None

    async def get_trade_history(self, filters: Optional[dict] = None) -> Optional[list]:
        """Get trade history with optional filters."""
        url = f"{self.base_url}/api/v1/orm/trades/history"
        if filters:
            # Add query parameters
            params = "&".join([f"{k}={v}" for k, v in filters.items()])
            url += f"?{params}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trade history failed", status=e.response.status_code)
                return None

    async def get_live_trades(self) -> Optional[list]:
        """Get active live trades."""
        url = f"{self.base_url}/api/v1/orm/trades/live"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get live trades failed", status=e.response.status_code)
                return None

    async def get_trade_performance(self) -> Optional[dict]:
        """Get trade performance metrics."""
        url = f"{self.base_url}/api/v1/orm/trades/performance"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trade performance failed", status=e.response.status_code)
                return None

    async def get_trade_stats(self) -> Optional[dict]:
        """Get trade statistics."""
        url = f"{self.base_url}/api/v1/orm/trades/stats"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trade stats failed", status=e.response.status_code)
                return None

    async def get_overall_stats(self) -> Optional[dict]:
        """Get overall trading statistics."""
        url = f"{self.base_url}/api/v1/orm/trades/stats/overall"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get overall stats failed", status=e.response.status_code)
                return None

    async def get_trade_summary(self) -> Optional[dict]:
        """Get trade summary report."""
        url = f"{self.base_url}/api/v1/orm/trades/summary"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trade summary failed", status=e.response.status_code)
                return None

    async def get_symbol_performance(self) -> Optional[dict]:
        """Get per-symbol performance."""
        url = f"{self.base_url}/api/v1/orm/trades/symbol-performance"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get symbol performance failed", status=e.response.status_code)
                return None

    async def update_trade(self, trade_id: int, updates: dict) -> Optional[dict]:
        """Update trade."""
        url = f"{self.base_url}/api/v1/orm/trades/{trade_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(url, json=updates, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Update trade failed", status=e.response.status_code, trade_id=trade_id
                )
                return None

    async def delete_trade(self, trade_id: int) -> bool:
        """Delete trade."""
        url = f"{self.base_url}/api/v1/orm/trades/{trade_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=self._get_headers())
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Delete trade failed", status=e.response.status_code, trade_id=trade_id
                )
                return False


async def example_trade_operations_and_analytics(token: str):
    """Demonstrate trade operations and analytics."""
    print("\n" + "=" * 60)
    print("Example: Trade Operations & Analytics (ORM API)")
    print("=" * 60)

    client = TradeAnalyticsClient(token=token)

    print("\n1️⃣  Creating dry-run trade for testing...")
    dry_trade_data = {
        "bot_id": 1,
        "symbol": "BTC/USD",
        "side": "buy",
        "volume": 0.1,
        "price": 50000.0,
        "order_type": "market",
    }

    dry_trade = await client.create_dry_trade(dry_trade_data)

    if dry_trade:
        print("   ✅ Dry-run trade created:")
        print(f"      Trade ID: {dry_trade.get('trade_id')}")
        print(f"      Symbol: {dry_trade.get('symbol')}")
        print(f"      Volume: {dry_trade.get('volume')}")
        trade_id = dry_trade.get("trade_id")
    else:
        print("   ❌ Dry-run trade creation failed")
        trade_id = None

    print("\n2️⃣  Creating live trade...")
    live_trade_data = {
        "bot_id": 1,
        "symbol": "ETH/USD",
        "side": "sell",
        "volume": 1.0,
        "price": 3000.0,
        "order_type": "limit",
    }

    live_trade = await client.create_live_trade(live_trade_data)

    if live_trade:
        print("   ✅ Live trade created:")
        print(f"      Trade ID: {live_trade.get('trade_id')}")
        print(f"      Symbol: {live_trade.get('symbol')}")
        print(f"      Volume: {live_trade.get('volume')}")
    else:
        print("   ❌ Live trade creation failed")

    print("\n3️⃣  Getting trades for bot (ID: 1)...")
    bot_trades = await client.get_bot_trades(1)

    if bot_trades is not None:
        print(f"   ✅ Found {len(bot_trades)} trades for bot")
        for trade in bot_trades[:2]:  # Show first 2
            print(
                f"      - Trade {trade.get('trade_id')}: {trade.get('symbol')} {trade.get('side')}"
            )
    else:
        print("   ❌ Bot trades endpoint not yet implemented")

    print("\n4️⃣  Getting trades grouped by bot...")
    trades_by_bot = await client.get_trades_by_bot()

    if trades_by_bot:
        print("   ✅ Trades grouped by bot:")
        print(f"      Groups: {list(trades_by_bot.keys())[:3]}...")  # Show first 3 bot IDs
    else:
        print("   ❌ Trades by bot endpoint not yet implemented")

    print("\n5️⃣  Getting trades grouped by symbol...")
    trades_by_symbol = await client.get_trades_by_symbol()

    if trades_by_symbol:
        print("   ✅ Trades grouped by symbol:")
        print(f"      Symbols: {list(trades_by_symbol.keys())[:3]}...")  # Show first 3 symbols
    else:
        print("   ❌ Trades by symbol endpoint not yet implemented")

    print("\n6️⃣  Querying trade history...")
    history = await client.get_trade_history()

    if history is not None:
        print(f"   ✅ Found {len(history)} trades in history")
        for trade in history[:2]:  # Show first 2
            print(f"      - {trade.get('symbol')} {trade.get('side')} {trade.get('volume')}")
    else:
        print("   ❌ Trade history endpoint not yet implemented")

    print("\n7️⃣  Getting active live trades...")
    live_trades = await client.get_live_trades()

    if live_trades is not None:
        print(f"   ✅ Found {len(live_trades)} active live trades")
    else:
        print("   ❌ Live trades endpoint not yet implemented")

    print("\n8️⃣  Getting trade performance metrics...")
    performance = await client.get_trade_performance()

    if performance:
        print("   ✅ Trade performance metrics:")
        print(f"      Metrics: {performance}")
    else:
        print("   ❌ Trade performance endpoint not yet implemented")

    print("\n9️⃣  Getting trade statistics...")
    stats = await client.get_trade_stats()

    if stats:
        print("   ✅ Trade statistics:")
        print(f"      Stats: {stats}")
    else:
        print("   ❌ Trade stats endpoint not yet implemented")

    print("\n🔟  Getting overall trading statistics...")
    overall_stats = await client.get_overall_stats()

    if overall_stats:
        print("   ✅ Overall trading statistics:")
        print(f"      Overall: {overall_stats}")
    else:
        print("   ❌ Overall stats endpoint not yet implemented")

    print("\n1️⃣1️⃣  Getting trade summary report...")
    summary = await client.get_trade_summary()

    if summary:
        print("   ✅ Trade summary report:")
        print(f"      Summary: {summary}")
    else:
        print("   ❌ Trade summary endpoint not yet implemented")

    print("\n1️⃣2️⃣  Getting per-symbol performance...")
    symbol_perf = await client.get_symbol_performance()

    if symbol_perf:
        print("   ✅ Per-symbol performance:")
        print(f"      Symbols: {list(symbol_perf.keys())[:3]}...")  # Show first 3 symbols
    else:
        print("   ❌ Symbol performance endpoint not yet implemented")

    # Update and delete operations (if we have a trade_id)
    if trade_id:
        print(f"\n1️⃣3️⃣  Updating trade (ID: {trade_id})...")
        updates = {"status": "completed"}
        updated_trade = await client.update_trade(trade_id, updates)

        if updated_trade:
            print("   ✅ Trade updated successfully")
        else:
            print("   ❌ Trade update endpoint not yet implemented")

        print(f"\n1️⃣4️⃣  Deleting trade (ID: {trade_id})...")
        deleted = await client.delete_trade(trade_id)

        if deleted:
            print("   ✅ Trade deleted successfully")
        else:
            print("   ❌ Trade delete endpoint not yet implemented")


async def setup_test_environment():
    """Setup test databases with demo data."""
    print("\n" + "=" * 60)
    print("Setting up self-contained test environment")
    print("=" * 60)

    logger.info("Creating test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)

    print(f"\n1. Creating dual test databases:")
    print(f"   ORM DB:   {test_db_orm}")
    print(f"   OHLCV DB: {test_db_ohlcv}")

    orm_db_name, ohlcv_db_name = await create_dual_test_databases(test_db_base)
    logger.info("Test databases created", orm_db=orm_db_name, ohlcv_db=ohlcv_db_name)

    print("\n2. Initializing database schema...")
    await init_db()
    print("   ✅ Schema initialized")

    print("\n3. Installing demo data (users, bots, exchanges)...")
    success = await install_demo_data()
    if not success:
        raise Exception("Failed to install demo data")

    print("\n" + "=" * 60)
    print("✅ Test environment ready!")
    print("=" * 60)


async def run_trade_analytics_examples():
    """Run all trade analytics API examples."""
    print("\n" + "=" * 60)
    print("Running Trade Analytics API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run trade analytics examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run trade operations and analytics example
    await example_trade_operations_and_analytics(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Trade analytics covers creation, querying, and analysis")
    print("   - Both dry-run and live trades are supported")
    print("   - Rich filtering and grouping capabilities")
    print("   - All operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Trade Analytics Example")
    print("SELF-CONTAINED: Creates, tests, and cleans up databases")
    print("=" * 60)

    server = None
    server_task = None
    try:
        # Setup test environment
        await setup_test_environment()

        # Start embedded test server
        print("\n4. Starting test server on localhost:8000...")
        server, server_task = await start_test_server()
        await asyncio.sleep(2)
        print("   ✅ Server started")

        # Run examples
        await run_trade_analytics_examples()

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

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
