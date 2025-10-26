#!/usr/bin/env python3
"""
Example: Dashboard Views - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests dashboard views API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_dashboard_views.py

Demonstrates:
- Fetching bot dashboard data
- Getting trading overview
- Viewing performance metrics
- Accessing user summary
- Portfolio statistics
- Risk metrics analysis

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/views/bot-dashboard/{user_id}  - Bot dashboard data
- GET    /api/v1/orm/views/trading-overview         - Trading overview
- GET    /api/v1/orm/views/performance-metrics      - Performance metrics
- GET    /api/v1/orm/views/user-summary             - User summary dashboard
- GET    /api/v1/orm/views/portfolio-stats          - Portfolio statistics
- GET    /api/v1/orm/views/risk-metrics             - Risk analysis metrics
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
logger = get_component_logger("fullon.examples.dashboard_views")

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
            logger.info("Login successful for dashboard views example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for dashboard views example", error=str(e))
            return None


class DashboardViewsClient:
    """Client for dashboard views API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_bot_dashboard(self, user_id: int) -> Optional[dict]:
        """Get bot dashboard data for user."""
        url = f"{self.base_url}/api/v1/orm/views/bot-dashboard/{user_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get bot dashboard failed", status=e.response.status_code, user_id=user_id
                )
                return None

    async def get_trading_overview(self) -> Optional[dict]:
        """Get trading overview."""
        url = f"{self.base_url}/api/v1/orm/views/trading-overview"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trading overview failed", status=e.response.status_code)
                return None

    async def get_performance_metrics(self) -> Optional[dict]:
        """Get performance metrics."""
        url = f"{self.base_url}/api/v1/orm/views/performance-metrics"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get performance metrics failed", status=e.response.status_code)
                return None

    async def get_user_summary(self) -> Optional[dict]:
        """Get user summary dashboard."""
        url = f"{self.base_url}/api/v1/orm/views/user-summary"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get user summary failed", status=e.response.status_code)
                return None

    async def get_portfolio_stats(self) -> Optional[dict]:
        """Get portfolio statistics."""
        url = f"{self.base_url}/api/v1/orm/views/portfolio-stats"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get portfolio stats failed", status=e.response.status_code)
                return None

    async def get_risk_metrics(self) -> Optional[dict]:
        """Get risk analysis metrics."""
        url = f"{self.base_url}/api/v1/orm/views/risk-metrics"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get risk metrics failed", status=e.response.status_code)
                return None


async def example_dashboard_data_aggregation(token: str):
    """Demonstrate dashboard data aggregation."""
    print("\n" + "=" * 60)
    print("Example: Dashboard Data Aggregation (ORM API)")
    print("=" * 60)

    client = DashboardViewsClient(token=token)

    print("\n1️⃣  Getting bot dashboard data for user (ID: 1)...")
    bot_dashboard = await client.get_bot_dashboard(1)

    if bot_dashboard:
        print("   ✅ Bot dashboard data retrieved:")
        print(f"      Total bots: {bot_dashboard.get('total_bots', 'N/A')}")
        print(f"      Active bots: {bot_dashboard.get('active_bots', 'N/A')}")
        print(f"      Total trades: {bot_dashboard.get('total_trades', 'N/A')}")
    else:
        print("   ❌ Bot dashboard endpoint not yet implemented")

    print("\n2️⃣  Getting trading overview...")
    trading_overview = await client.get_trading_overview()

    if trading_overview:
        print("   ✅ Trading overview retrieved:")
        print(f"      Total volume: {trading_overview.get('total_volume', 'N/A')}")
        print(f"      Active pairs: {trading_overview.get('active_pairs', 'N/A')}")
        print(f"      Success rate: {trading_overview.get('success_rate', 'N/A')}")
    else:
        print("   ❌ Trading overview endpoint not yet implemented")

    print("\n3️⃣  Getting performance metrics...")
    performance = await client.get_performance_metrics()

    if performance:
        print("   ✅ Performance metrics retrieved:")
        print(f"      Win rate: {performance.get('win_rate', 'N/A')}")
        print(f"      Profit factor: {performance.get('profit_factor', 'N/A')}")
        print(f"      Sharpe ratio: {performance.get('sharpe_ratio', 'N/A')}")
    else:
        print("   ❌ Performance metrics endpoint not yet implemented")

    print("\n4️⃣  Getting user summary dashboard...")
    user_summary = await client.get_user_summary()

    if user_summary:
        print("   ✅ User summary retrieved:")
        print(f"      Account balance: {user_summary.get('account_balance', 'N/A')}")
        print(f"      Total value: {user_summary.get('total_value', 'N/A')}")
        print(f"      Daily P&L: {user_summary.get('daily_pnl', 'N/A')}")
    else:
        print("   ❌ User summary endpoint not yet implemented")

    print("\n5️⃣  Getting portfolio statistics...")
    portfolio_stats = await client.get_portfolio_stats()

    if portfolio_stats:
        print("   ✅ Portfolio statistics retrieved:")
        print(f"      Total assets: {portfolio_stats.get('total_assets', 'N/A')}")
        print(f"      Asset allocation: {portfolio_stats.get('asset_allocation', 'N/A')}")
        print(f"      Diversification: {portfolio_stats.get('diversification_score', 'N/A')}")
    else:
        print("   ❌ Portfolio stats endpoint not yet implemented")

    print("\n6️⃣  Getting risk analysis metrics...")
    risk_metrics = await client.get_risk_metrics()

    if risk_metrics:
        print("   ✅ Risk metrics retrieved:")
        print(f"      Value at risk: {risk_metrics.get('value_at_risk', 'N/A')}")
        print(f"      Max drawdown: {risk_metrics.get('max_drawdown', 'N/A')}")
        print(f"      Risk score: {risk_metrics.get('risk_score', 'N/A')}")
    else:
        print("   ❌ Risk metrics endpoint not yet implemented")


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


async def run_dashboard_views_examples():
    """Run all dashboard views API examples."""
    print("\n" + "=" * 60)
    print("Running Dashboard Views API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run dashboard views examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run dashboard data aggregation example
    await example_dashboard_data_aggregation(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Dashboard views provide aggregated business intelligence")
    print("   - Views combine data from multiple ORM entities")
    print("   - Optimized for frontend consumption")
    print("   - All operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Dashboard Views Example")
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
        await run_dashboard_views_examples()

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
