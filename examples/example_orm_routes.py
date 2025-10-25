#!/usr/bin/env python3
"""
Example: ORM API Routes - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests ORM API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_orm_routes.py

Demonstrates:
- User management endpoints
- Bot management endpoints
- Exchange management endpoints
- Order and trade operations
- Using ORM model instances (NOT dictionaries!)

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/users          - List users
- GET    /api/v1/orm/users/me       - Current user info
- POST   /api/v1/orm/users          - Create user
- GET    /api/v1/orm/bots           - List bots
- POST   /api/v1/orm/bots           - Create bot
- GET    /api/v1/orm/exchanges      - List exchanges
- POST   /api/v1/orm/orders         - Create order
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
logger = get_component_logger("fullon.examples.orm_routes")

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
            logger.info("Login successful for ORM example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for ORM example", error=str(e))
            return None


class ORMAPIClient:
    """Client for ORM API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_current_user(self) -> Optional[dict]:
        """Get current authenticated user info."""
        url = f"{self.base_url}/api/v1/orm/users/me"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get current user failed", status=e.response.status_code)
                return None

    async def list_users(self) -> Optional[list]:
        """List all users (admin only)."""
        url = f"{self.base_url}/api/v1/orm/users"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List users failed", status=e.response.status_code)
                return None

    async def list_bots(self, user_id: int) -> Optional[list]:
        """List all bots for current user."""
        url = f"{self.base_url}/api/v1/orm/bots/by-user?user_id={user_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List bots failed", status=e.response.status_code, user_id=user_id)
                return None

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

    async def create_order(self, order_data: dict) -> Optional[dict]:
        """
        Create new order.

        Args:
            order_data: Order object data (MUST use 'volume' not 'amount'!)
                {
                    "bot_id": 1,
                    "cat_ex_id": 1,
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "volume": 1.0,
                    "order_type": "market",
                    "status": "New"
                }
        """
        url = f"{self.base_url}/api/v1/orm/orders/"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=order_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_detail = e.response.text if e.response else "Unknown error"
                logger.error("Create order failed", status=e.response.status_code, detail=error_detail[:200])
                return None


async def example_user_management(token: str):
    """Demonstrate user management endpoints."""
    print("\n" + "=" * 60)
    print("Example: User Management (ORM API)")
    print("=" * 60)

    client = ORMAPIClient(token=token)

    print("\n1️⃣  Getting current user info...")
    user = await client.get_current_user()

    if user:
        print("   ✅ Current user:")
        print(f"      User ID: {user.get('uid')}")
        print(f"      Email: {user.get('mail')}")
        print(f"      Name: {user.get('name')}")
    else:
        print("   ❌ Endpoint not yet implemented")

    print("\n2️⃣  Listing all users (admin only)...")
    users = await client.list_users()

    if users:
        print(f"   ✅ Found {len(users)} users")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_bot_management(token: str):
    """Demonstrate bot management endpoints."""
    print("\n" + "=" * 60)
    print("Example: Bot Management (ORM API)")
    print("=" * 60)

    client = ORMAPIClient(token=token)

    print("\n1️⃣  Getting current user info...")
    user = await client.get_current_user()

    if not user:
        print("   ❌ Cannot get user info - aborting bot management")
        return

    user_id = user.get("uid")
    print(f"   ✅ User ID: {user_id}")

    print("\n2️⃣  Listing user's bots...")
    bots = await client.list_bots(user_id=user_id)

    if bots:
        print(f"   ✅ Found {len(bots)} bots")
        for bot in bots[:3]:
            print(f"      - {bot.get('name')} (ID: {bot.get('bot_id')})")
    else:
        print("   ❌ Endpoint not yet implemented")

    print("\n3️⃣  Creating new bot...")
    new_bot = {
        "name": "Example Trading Bot",
        "active": True,
        "dry_run": True,
        "uid": user_id,  # Include user ID for bot creation
    }

    bot = await client.create_bot(new_bot)

    if bot:
        print("   ✅ Bot created:")
        print(f"      Bot ID: {bot.get('bot_id')}")
        print(f"      Name: {bot.get('name')}")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_order_creation(token: str):
    """Demonstrate order creation (CRITICAL: use 'volume' not 'amount')."""
    print("\n" + "=" * 60)
    print("Example: Order Creation (ORM API)")
    print("=" * 60)

    client = ORMAPIClient(token=token)

    print("\n1️⃣  Creating market order...")
    print("   ⚠️  IMPORTANT: ORM uses 'volume' field, NOT 'amount'!")

    # ✅ CORRECT - uses 'volume'
    order_data = {
        "bot_id": 1,
        "cat_ex_id": 1,  # Category exchange ID
        "symbol": "BTC/USD",
        "side": "buy",
        "volume": 1.0,  # ✅ CORRECT field name
        "order_type": "market",
        "status": "New",
    }

    order = await client.create_order(order_data)

    if order:
        print("   ✅ Order created:")
        print(f"      Order ID: {order.get('order_id')}")
        print(f"      Symbol: {order.get('symbol')}")
        print(f"      Volume: {order.get('volume')}")
    else:
        print("   ❌ Endpoint not yet implemented")


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


async def run_orm_examples():
    """Run all ORM API examples."""
    print("\n" + "=" * 60)
    print("Running ORM API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run ORM examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Example 1: User management
    await example_user_management(token)

    # Example 2: Bot management
    await example_bot_management(token)

    # Example 3: Order creation
    await example_order_creation(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - ORM endpoints use model instances (converted from JSON)")
    print("   - ALWAYS use 'volume' field for orders (NOT 'amount')")
    print("   - All write operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - ORM Routes Example")
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
        await run_orm_examples()

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
