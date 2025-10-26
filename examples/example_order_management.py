#!/usr/bin/env python3
"""
Example: Order Management - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests order management API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_order_management.py

Demonstrates:
- Creating orders for bots
- Querying open and historical orders
- Viewing order statistics
- Filtering orders by bot and symbol
- Updating order status

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/orders/by-bot      - Orders for specific bot
- GET    /api/v1/orm/orders/open        - Open/pending orders
- GET    /api/v1/orm/orders/history     - Order history
- GET    /api/v1/orm/orders/stats       - Order statistics
- GET    /api/v1/orm/orders/by-symbol   - Orders for specific symbol
- PATCH  /api/v1/orm/orders/{order_id}/status - Update order status
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
logger = get_component_logger("fullon.examples.order_management")

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
            logger.info("Login successful for order management example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for order management example", error=str(e))
            return None


class OrderManagementClient:
    """Client for order management API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

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
                logger.error(
                    "Create order failed", status=e.response.status_code, detail=error_detail[:200]
                )
                return None

    async def get_orders_by_bot(self, bot_id: int) -> Optional[list]:
        """Get orders for specific bot."""
        url = f"{self.base_url}/api/v1/orm/orders/by-bot?bot_id={bot_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get orders by bot failed", status=e.response.status_code, bot_id=bot_id
                )
                return None

    async def get_open_orders(self) -> Optional[list]:
        """Get open/pending orders."""
        url = f"{self.base_url}/api/v1/orm/orders/open"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get open orders failed", status=e.response.status_code)
                return None

    async def get_order_history(self) -> Optional[list]:
        """Get order history."""
        url = f"{self.base_url}/api/v1/orm/orders/history"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get order history failed", status=e.response.status_code)
                return None

    async def get_order_stats(self) -> Optional[dict]:
        """Get order statistics."""
        url = f"{self.base_url}/api/v1/orm/orders/stats"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get order stats failed", status=e.response.status_code)
                return None

    async def get_orders_by_symbol(self, symbol: str) -> Optional[list]:
        """Get orders for specific symbol."""
        url = f"{self.base_url}/api/v1/orm/orders/by-symbol?symbol={symbol}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get orders by symbol failed", status=e.response.status_code, symbol=symbol
                )
                return None

    async def update_order_status(self, order_id: int, status: str) -> Optional[dict]:
        """Update order status."""
        url = f"{self.base_url}/api/v1/orm/orders/{order_id}/status"

        update_data = {"status": status}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(url, json=update_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Update order status failed", status=e.response.status_code, order_id=order_id
                )
                return None


async def example_order_operations_and_monitoring(token: str):
    """Demonstrate order operations and monitoring."""
    print("\n" + "=" * 60)
    print("Example: Order Operations & Monitoring (ORM API)")
    print("=" * 60)

    client = OrderManagementClient(token=token)

    print("\n1️⃣  Creating test order...")
    print("   ⚠️  IMPORTANT: ORM uses 'volume' field, NOT 'amount'!")

    order_data = {
        "bot_id": 1,
        "cat_ex_id": 1,  # Category exchange ID
        "symbol": "BTC/USD",
        "side": "buy",
        "volume": 0.5,  # ✅ CORRECT field name
        "order_type": "limit",
        "status": "New",
    }

    order = await client.create_order(order_data)

    if order:
        print("   ✅ Order created:")
        print(f"      Order ID: {order.get('order_id')}")
        print(f"      Symbol: {order.get('symbol')}")
        print(f"      Volume: {order.get('volume')}")
        order_id = order.get("order_id")
    else:
        print("   ❌ Order creation failed")
        order_id = None

    print("\n2️⃣  Getting orders for bot (ID: 1)...")
    bot_orders = await client.get_orders_by_bot(1)

    if bot_orders is not None:
        print(f"   ✅ Found {len(bot_orders)} orders for bot")
        for order in bot_orders[:3]:  # Show first 3
            print(
                f"      - Order {order.get('order_id')}: {order.get('symbol')} {order.get('side')}"
            )
    else:
        print("   ❌ Orders by bot endpoint not yet implemented")

    print("\n3️⃣  Getting open/pending orders...")
    open_orders = await client.get_open_orders()

    if open_orders is not None:
        print(f"   ✅ Found {len(open_orders)} open orders")
        for order in open_orders[:2]:  # Show first 2
            print(f"      - Open order {order.get('order_id')}: {order.get('status')}")
    else:
        print("   ❌ Open orders endpoint not yet implemented")

    print("\n4️⃣  Getting order history...")
    history = await client.get_order_history()

    if history is not None:
        print(f"   ✅ Found {len(history)} orders in history")
        for order in history[:2]:  # Show first 2
            print(f"      - Historical order {order.get('order_id')}: {order.get('symbol')}")
    else:
        print("   ❌ Order history endpoint not yet implemented")

    print("\n5️⃣  Getting order statistics...")
    stats = await client.get_order_stats()

    if stats:
        print("   ✅ Order statistics:")
        print(f"      Stats: {stats}")
    else:
        print("   ❌ Order stats endpoint not yet implemented")

    print("\n6️⃣  Getting orders for symbol (BTC/USD)...")
    symbol_orders = await client.get_orders_by_symbol("BTC/USD")

    if symbol_orders is not None:
        print(f"   ✅ Found {len(symbol_orders)} orders for BTC/USD")
        for order in symbol_orders[:2]:  # Show first 2
            print(
                f"      - Symbol order {order.get('order_id')}: {order.get('side')} {order.get('volume')}"
            )
    else:
        print("   ❌ Orders by symbol endpoint not yet implemented")

    if order_id:
        print(f"\n7️⃣  Updating order status (ID: {order_id})...")
        updated_order = await client.update_order_status(order_id, "filled")

        if updated_order:
            print("   ✅ Order status updated successfully:")
            print(f"      New status: {updated_order.get('status')}")
        else:
            print("   ❌ Update order status endpoint not yet implemented")


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


async def run_order_management_examples():
    """Run all order management API examples."""
    print("\n" + "=" * 60)
    print("Running Order Management API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run order management examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run order operations and monitoring example
    await example_order_operations_and_monitoring(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Order management covers the complete order lifecycle")
    print("   - ALWAYS use 'volume' field for orders (NOT 'amount')")
    print("   - Rich querying capabilities by bot, symbol, and status")
    print("   - All operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Order Management Example")
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
        await run_order_management_examples()

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
