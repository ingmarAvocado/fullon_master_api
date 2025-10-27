#!/usr/bin/env python3
"""
Example: Strategy Management - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests strategy management API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_strategy_management.py

Demonstrates:
- Browsing strategy catalog
- Viewing strategy parameters
- Attaching strategies to bots
- Configuring strategy settings
- Managing bot strategy lifecycle
- Getting strategy details and performance

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/strategies/bot-strategies              - List bot strategies
- GET    /api/v1/orm/strategies/catalog                     - Available strategy catalog
- GET    /api/v1/orm/strategies/catalog/{cat_str_id}/params - Strategy parameters
- POST   /api/v1/orm/strategies/bot-strategies             - Add strategy to bot
- PUT    /api/v1/orm/strategies/bot-strategies/{str_id}   - Update bot strategy
- DELETE /api/v1/orm/strategies/bot-strategies/{str_id}  - Remove bot strategy
- GET    /api/v1/orm/strategies/bot-strategies/{str_id}   - Get strategy details
- GET    /api/v1/orm/strategies/catalog/{cat_str_id}      - Get catalog strategy details
- GET    /api/v1/orm/strategies/user-strategies           - Get user strategies
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
logger = get_component_logger("fullon.examples.strategy_management")

API_BASE_URL = "http://localhost:8000"


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    return server, task


async def wait_for_server(url: str, timeout: int = 30, interval: float = 0.5) -> bool:
    """
    Poll server health endpoint until ready or timeout.

    Args:
        url: Base URL of the server (e.g., "http://localhost:8000")
        timeout: Maximum seconds to wait for server
        interval: Seconds between polling attempts

    Returns:
        True if server is ready, False if timeout
    """
    start_time = asyncio.get_event_loop().time()

    async with httpx.AsyncClient() as client:
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                response = await client.get(f"{url}/health", timeout=1.0)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                # Server not ready yet, continue polling
                pass

            await asyncio.sleep(interval)

    return False


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
            logger.info("Login successful for strategy management example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for strategy management example", error=str(e))
            return None


class StrategyManagementClient:
    """Client for strategy management API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def list_bot_strategies(self, bot_id: int) -> Optional[list]:
        """List strategies attached to a bot."""
        url = f"{self.base_url}/api/v1/orm/strategies/bot-strategies?bot_id={bot_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "List bot strategies failed", status=e.response.status_code, bot_id=bot_id
                )
                return None

    async def list_strategy_catalog(self) -> Optional[list]:
        """List available strategies in catalog."""
        url = f"{self.base_url}/api/v1/orm/strategies/catalog"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List strategy catalog failed", status=e.response.status_code)
                return None

    async def get_strategy_params(self, cat_str_id: int) -> Optional[dict]:
        """Get strategy parameters."""
        url = f"{self.base_url}/api/v1/orm/strategies/catalog/{cat_str_id}/params"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get strategy params failed",
                    status=e.response.status_code,
                    cat_str_id=cat_str_id,
                )
                return None

    async def add_bot_strategy(self, bot_id: int, strategy_config: dict) -> Optional[dict]:
        """Add strategy to bot."""
        url = f"{self.base_url}/api/v1/orm/strategies/bot-strategies"

        # Include bot_id in the payload
        payload = {"bot_id": bot_id, **strategy_config}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Add bot strategy failed", status=e.response.status_code, bot_id=bot_id
                )
                return None

    async def update_bot_strategy(self, str_id: int, updates: dict) -> Optional[dict]:
        """Update bot strategy configuration."""
        url = f"{self.base_url}/api/v1/orm/strategies/bot-strategies/{str_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=updates, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Update bot strategy failed", status=e.response.status_code, str_id=str_id
                )
                return None

    async def remove_bot_strategy(self, str_id: int) -> bool:
        """Remove strategy from bot."""
        url = f"{self.base_url}/api/v1/orm/strategies/bot-strategies/{str_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=self._get_headers())
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Remove bot strategy failed", status=e.response.status_code, str_id=str_id
                )
                return False

    async def get_strategy_details(self, str_id: int) -> Optional[dict]:
        """Get strategy configuration details."""
        url = f"{self.base_url}/api/v1/orm/strategies/bot-strategies/{str_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get strategy details failed", status=e.response.status_code, str_id=str_id
                )
                return None

    async def get_catalog_strategy_details(self, cat_str_id: int) -> Optional[dict]:
        """Get catalog strategy details."""
        url = f"{self.base_url}/api/v1/orm/strategies/catalog/{cat_str_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get catalog strategy details failed",
                    status=e.response.status_code,
                    cat_str_id=cat_str_id,
                )
                return None

    async def get_user_strategies(self) -> Optional[list]:
        """Get user's strategies."""
        url = f"{self.base_url}/api/v1/orm/strategies/user-strategies"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get user strategies failed", status=e.response.status_code)
                return None


async def example_strategy_configuration_and_management(token: str):
    """Demonstrate strategy configuration and management."""
    print("\n" + "=" * 60)
    print("Example: Strategy Configuration & Management (ORM API)")
    print("=" * 60)

    client = StrategyManagementClient(token=token)

    print("\n1️⃣  Browsing available strategy catalog...")
    strategy_catalog = await client.list_strategy_catalog()

    if strategy_catalog:
        print(f"   ✅ Found {len(strategy_catalog)} available strategies")
        for strategy in strategy_catalog[:3]:  # Show first 3
            print(f"      - {strategy.get('name')} (ID: {strategy.get('cat_str_id')})")
        # Get first strategy for further operations
        first_strategy = strategy_catalog[0] if strategy_catalog else None
        cat_str_id = first_strategy.get("cat_str_id") if first_strategy else None
    else:
        print("   ❌ Strategy catalog endpoint not yet implemented")
        cat_str_id = None

    if cat_str_id:
        print(f"\n2️⃣  Getting parameters for strategy (ID: {cat_str_id})...")
        params = await client.get_strategy_params(cat_str_id)

        if params:
            print("   ✅ Strategy parameters retrieved:")
            print(f"      Params: {params}")
        else:
            print("   ❌ Strategy params endpoint not yet implemented")

    print("\n3️⃣  Listing strategies for bot (ID: 1)...")
    bot_strategies = await client.list_bot_strategies(1)

    if bot_strategies is not None:
        print(f"   ✅ Found {len(bot_strategies)} strategies attached to bot")
        for strategy in bot_strategies[:2]:  # Show first 2
            print(f"      - Strategy {strategy.get('str_id')}: {strategy.get('name')}")
    else:
        print("   ❌ Bot strategies endpoint not yet implemented")

    print("\n4️⃣  Adding strategy to bot...")
    if cat_str_id:
        strategy_config = {
            "cat_str_id": cat_str_id,
            "name": "My RSI Strategy",
            "parameters": {
                "rsi_period": 14,
                "overbought_level": 70,
                "oversold_level": 30,
            },
            "active": True,
        }

        added_strategy = await client.add_bot_strategy(1, strategy_config)

        if added_strategy and added_strategy.get("str_id"):
            print("   ✅ Strategy added to bot successfully:")
            print(f"      Strategy ID: {added_strategy.get('str_id')}")
            print(f"      Name: {added_strategy.get('name')}")
            str_id = added_strategy.get("str_id")
        else:
            print("   ❌ Failed to add strategy to bot - endpoint may not be implemented")
            str_id = None
    else:
        print("   ❌ Cannot add strategy - no catalog strategy available")
        str_id = None

    if str_id:
        print(f"\n5️⃣  Updating bot strategy configuration (ID: {str_id})...")
        updates = {
            "name": "Updated RSI Strategy",
            "parameters": {
                "rsi_period": 21,
                "overbought_level": 75,
                "oversold_level": 25,
            },
            "active": False,
        }

        updated_strategy = await client.update_bot_strategy(str_id, updates)

        if updated_strategy:
            print("   ✅ Bot strategy updated successfully:")
            print(f"      New name: {updated_strategy.get('name')}")
            print(f"      Active: {updated_strategy.get('active')}")
        else:
            print("   ❌ Update bot strategy endpoint not yet implemented")

        print(f"\n6️⃣  Removing strategy from bot (ID: {str_id})...")
        removed = await client.remove_bot_strategy(str_id)

        if removed:
            print("   ✅ Strategy removed from bot successfully")
        else:
            print("   ❌ Remove bot strategy endpoint not yet implemented")

    # Demonstrate additional strategy configuration routes
    print("\n7️⃣  Getting strategy configuration details...")
    if str_id:
        strategy_details = await client.get_strategy_details(str_id)

        if strategy_details:
            print("   ✅ Strategy details retrieved:")
            print(f"      Configuration: {strategy_details}")
        else:
            print("   ❌ Strategy details endpoint not yet implemented")

    print("\n8️⃣  Getting catalog strategy details...")
    if cat_str_id:
        catalog_details = await client.get_catalog_strategy_details(cat_str_id)

        if catalog_details:
            print("   ✅ Catalog strategy details retrieved:")
            print(f"      Details: {catalog_details}")
        else:
            print("   ❌ Catalog strategy details endpoint not yet implemented")

    print("\n9️⃣  Getting user strategies...")
    user_strategies = await client.get_user_strategies()

    if user_strategies is not None:
        print(f"   ✅ Found {len(user_strategies)} user strategies")
        for strategy in user_strategies[:2]:  # Show first 2
            print(f"      - Strategy {strategy.get('str_id')}: {strategy.get('name')}")
    else:
        print("   ❌ User strategies endpoint not yet implemented")


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


async def run_strategy_management_examples():
    """Run all strategy management API examples."""
    print("\n" + "=" * 60)
    print("Running Strategy Management API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run strategy management examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run strategy configuration and management example
    await example_strategy_configuration_and_management(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Strategy management handles bot trading logic")
    print("   - Separate catalog and bot-specific strategy management")
    print("   - Parameter configuration is strategy-specific")
    print("   - All operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Strategy Management Example")
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

        # Wait for server to be ready (polls health endpoint)
        if not await wait_for_server("http://localhost:8000", timeout=10):
            raise RuntimeError("Server failed to start within 10 seconds")

        print("   ✅ Server started")

        # Run examples
        await run_strategy_management_examples()

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
