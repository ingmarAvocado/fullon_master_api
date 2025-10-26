#!/usr/bin/env python3
"""
Example: Bot Management - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests bot management API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_bot_management.py

Demonstrates:
- Complete bot lifecycle management
- Bot configuration and details
- Bot data feeds and strategies
- Bot performance statistics
- Bot action history and logs
- Bot exchange connections
- Bot configuration updates

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/bots/{bot_id}/details       - Bot configuration details
- GET    /api/v1/orm/bots/{bot_id}/feeds         - Bot data feeds
- GET    /api/v1/orm/bots/{bot_id}/strategies    - Bot trading strategies
- GET    /api/v1/orm/bots/{bot_id}/stats         - Bot performance statistics
- GET    /api/v1/orm/bots/{bot_id}/actions       - Bot action history
- GET    /api/v1/orm/bots/{bot_id}/exchanges     - Bot exchange connections
- GET    /api/v1/orm/bots/{bot_id}/last-log      - Bot recent logs
- PATCH  /api/v1/orm/bots/{bot_id}               - Update bot configuration
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
logger = get_component_logger("fullon.examples.bot_management")

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
            logger.info("Login successful for bot management example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for bot management example", error=str(e))
            return None


class BotManagementClient:
    """Client for bot management API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def create_bot(self, bot_data: dict) -> Optional[dict]:
        """
        Create new bot.

        Args:
            bot_data: Bot object data
                {
                    "name": "My Trading Bot",
                    "active": true,
                    "dry_run": true,
                    "uid": 1  # User ID (required)
                }
        """
        url = f"{self.base_url}/api/v1/orm/bots/"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=bot_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Create bot failed", status=e.response.status_code)
                return None

    async def get_bot_details(self, bot_id: int) -> Optional[dict]:
        """Get bot configuration details."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/details"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get bot details failed", status=e.response.status_code, bot_id=bot_id)
                return None

    async def get_bot_feeds(self, bot_id: int) -> Optional[list]:
        """Get bot data feeds."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/feeds"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get bot feeds failed", status=e.response.status_code, bot_id=bot_id)
                return None

    async def get_bot_strategies(self, bot_id: int) -> Optional[list]:
        """Get bot trading strategies."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/strategies"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get bot strategies failed", status=e.response.status_code, bot_id=bot_id
                )
                return None

    async def get_bot_stats(self, bot_id: int) -> Optional[dict]:
        """Get bot performance statistics."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/stats"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get bot stats failed", status=e.response.status_code, bot_id=bot_id)
                return None

    async def get_bot_actions(self, bot_id: int) -> Optional[list]:
        """Get bot action history."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/actions"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get bot actions failed", status=e.response.status_code, bot_id=bot_id)
                return None

    async def get_bot_exchanges(self, bot_id: int) -> Optional[list]:
        """Get bot exchange connections."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/exchanges"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get bot exchanges failed", status=e.response.status_code, bot_id=bot_id
                )
                return None

    async def get_bot_last_log(self, bot_id: int) -> Optional[dict]:
        """Get bot recent logs."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}/last-log"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get bot last log failed", status=e.response.status_code, bot_id=bot_id
                )
                return None

    async def update_bot(self, bot_id: int, updates: dict) -> Optional[dict]:
        """Update bot configuration."""
        url = f"{self.base_url}/api/v1/orm/bots/{bot_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(url, json=updates, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Update bot failed", status=e.response.status_code, bot_id=bot_id)
                return None


async def example_bot_lifecycle_management(token: str):
    """Demonstrate complete bot lifecycle management."""
    print("\n" + "=" * 60)
    print("Example: Bot Lifecycle Management (ORM API)")
    print("=" * 60)

    client = BotManagementClient(token=token)

    print("\n1️⃣  Creating new bot with full configuration...")
    new_bot = {
        "name": "Comprehensive Trading Bot",
        "active": True,
        "dry_run": True,
        "uid": 1,  # Admin user ID
    }

    bot = await client.create_bot(new_bot)

    if not bot:
        print("   ❌ Cannot create bot - aborting lifecycle demo")
        return

    bot_id = bot.get("bot_id")
    if not bot_id:
        print("   ❌ Bot creation failed - no bot_id returned")
        return

    print("   ✅ Bot created successfully:")
    print(f"      Bot ID: {bot_id}")
    print(f"      Name: {bot.get('name')}")
    print(f"      Active: {bot.get('active')}")
    print(f"      Dry Run: {bot.get('dry_run')}")

    print(f"\n2️⃣  Getting bot configuration details (ID: {bot_id})...")
    details = await client.get_bot_details(bot_id)

    if details:
        print("   ✅ Bot details retrieved:")
        print(f"      Configuration: {details}")
    else:
        print("   ❌ Bot details endpoint not yet implemented")

    print(f"\n3️⃣  Checking bot data feeds (ID: {bot_id})...")
    feeds = await client.get_bot_feeds(bot_id)

    if feeds is not None:
        print(f"   ✅ Found {len(feeds)} data feeds")
        for feed in feeds[:2]:  # Show first 2
            print(f"      - Feed: {feed}")
    else:
        print("   ❌ Bot feeds endpoint not yet implemented")

    print(f"\n4️⃣  Checking bot trading strategies (ID: {bot_id})...")
    strategies = await client.get_bot_strategies(bot_id)

    if strategies is not None:
        print(f"   ✅ Found {len(strategies)} strategies")
        for strategy in strategies[:2]:  # Show first 2
            print(f"      - Strategy: {strategy}")
    else:
        print("   ❌ Bot strategies endpoint not yet implemented")

    print(f"\n5️⃣  Getting bot performance statistics (ID: {bot_id})...")
    stats = await client.get_bot_stats(bot_id)

    if stats:
        print("   ✅ Bot statistics retrieved:")
        print(f"      Stats: {stats}")
    else:
        print("   ❌ Bot stats endpoint not yet implemented")

    print(f"\n6️⃣  Checking bot action history (ID: {bot_id})...")
    actions = await client.get_bot_actions(bot_id)

    if actions is not None:
        print(f"   ✅ Found {len(actions)} actions")
        for action in actions[:2]:  # Show first 2
            print(f"      - Action: {action}")
    else:
        print("   ❌ Bot actions endpoint not yet implemented")

    print(f"\n7️⃣  Checking bot exchange connections (ID: {bot_id})...")
    exchanges = await client.get_bot_exchanges(bot_id)

    if exchanges is not None:
        print(f"   ✅ Found {len(exchanges)} exchange connections")
        for exchange in exchanges[:2]:  # Show first 2
            print(f"      - Exchange: {exchange}")
    else:
        print("   ❌ Bot exchanges endpoint not yet implemented")

    print(f"\n8️⃣  Getting bot recent logs (ID: {bot_id})...")
    last_log = await client.get_bot_last_log(bot_id)

    if last_log:
        print("   ✅ Bot last log retrieved:")
        print(f"      Log: {last_log}")
    else:
        print("   ❌ Bot last log endpoint not yet implemented")

    print(f"\n9️⃣  Updating bot configuration (ID: {bot_id})...")
    updates = {
        "name": "Updated Comprehensive Trading Bot",
        "active": False,
    }

    updated_bot = await client.update_bot(bot_id, updates)

    if updated_bot:
        print("   ✅ Bot updated successfully:")
        print(f"      New name: {updated_bot.get('name')}")
        print(f"      Active: {updated_bot.get('active')}")
    else:
        print("   ❌ Bot update endpoint not yet implemented")


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


async def run_bot_management_examples():
    """Run all bot management API examples."""
    print("\n" + "=" * 60)
    print("Running Bot Management API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run bot management examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run bot lifecycle management example
    await example_bot_lifecycle_management(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Bot management covers the complete bot lifecycle")
    print("   - All operations require authentication")
    print("   - Endpoints provide detailed bot monitoring and control")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Bot Management Example")
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
        await run_bot_management_examples()

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
