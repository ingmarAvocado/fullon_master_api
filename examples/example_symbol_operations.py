#!/usr/bin/env python3
"""
Example: Symbol Operations - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests symbol operations API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_symbol_operations.py

Demonstrates:
- Searching for symbols
- Getting symbols by exchange
- Checking symbol decimal precision
- Adding new symbols
- Updating symbol information

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/symbols/by-exchange  - Symbols for an exchange
- GET    /api/v1/orm/symbols/search       - Search symbols by name
- GET    /api/v1/orm/symbols/decimals     - Get symbol decimal precision
- POST   /api/v1/orm/symbols             - Add new symbol
- PATCH  /api/v1/orm/symbols/{symbol_id} - Update symbol info
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
logger = get_component_logger("fullon.examples.symbol_operations")

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
            logger.info("Login successful for symbol operations example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for symbol operations example", error=str(e))
            return None


class SymbolOperationsClient:
    """Client for symbol operations API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_symbols_by_exchange(self, cat_ex_id: int) -> Optional[list]:
        """Get symbols for an exchange."""
        url = f"{self.base_url}/api/v1/orm/symbols/by-exchange?cat_ex_id={cat_ex_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get symbols by exchange failed",
                    status=e.response.status_code,
                    cat_ex_id=cat_ex_id,
                )
                return None

    async def search_symbols(self, query: str) -> Optional[list]:
        """Search symbols by name."""
        url = f"{self.base_url}/api/v1/orm/symbols/search?q={query}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Search symbols failed", status=e.response.status_code, query=query)
                return None

    async def get_symbol_decimals(self, symbol: str) -> Optional[dict]:
        """Get symbol decimal precision."""
        url = f"{self.base_url}/api/v1/orm/symbols/decimals?symbol={symbol}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get symbol decimals failed", status=e.response.status_code, symbol=symbol
                )
                return None

    async def add_symbol(self, symbol_data: dict) -> Optional[dict]:
        """Add new symbol."""
        url = f"{self.base_url}/api/v1/orm/symbols"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=symbol_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Add symbol failed", status=e.response.status_code)
                return None

    async def update_symbol(self, symbol_id: int, updates: dict) -> Optional[dict]:
        """Update symbol information."""
        url = f"{self.base_url}/api/v1/orm/symbols/{symbol_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(url, json=updates, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Update symbol failed", status=e.response.status_code, symbol_id=symbol_id
                )
                return None


async def example_symbol_discovery_and_management(token: str):
    """Demonstrate symbol discovery and management."""
    print("\n" + "=" * 60)
    print("Example: Symbol Discovery & Management (ORM API)")
    print("=" * 60)

    client = SymbolOperationsClient(token=token)

    print("\n1️⃣  Getting symbols for exchange (ID: 1)...")
    exchange_symbols = await client.get_symbols_by_exchange(1)

    if exchange_symbols is not None:
        print(f"   ✅ Found {len(exchange_symbols)} symbols for exchange")
        for symbol in exchange_symbols[:5]:  # Show first 5
            print(f"      - {symbol.get('symbol')} (ID: {symbol.get('symbol_id')})")
    else:
        print("   ❌ Symbols by exchange endpoint not yet implemented")

    print("\n2️⃣  Searching symbols by name (BTC)...")
    search_results = await client.search_symbols("BTC")

    if search_results is not None:
        print(f"   ✅ Found {len(search_results)} symbols matching 'BTC'")
        for symbol in search_results[:3]:  # Show first 3
            print(f"      - {symbol.get('symbol')}")
    else:
        print("   ❌ Symbol search endpoint not yet implemented")

    print("\n3️⃣  Getting decimal precision for BTC/USD...")
    decimals = await client.get_symbol_decimals("BTC/USD")

    if decimals:
        print("   ✅ Symbol decimals retrieved:")
        print(f"      Price decimals: {decimals.get('price_decimals')}")
        print(f"      Quantity decimals: {decimals.get('quantity_decimals')}")
    else:
        print("   ❌ Symbol decimals endpoint not yet implemented")

    print("\n4️⃣  Adding new symbol...")
    new_symbol = {
        "symbol": "SOL/USD",
        "base_asset": "SOL",
        "quote_asset": "USD",
        "cat_ex_id": 1,  # Binance
        "price_decimals": 2,
        "quantity_decimals": 8,
        "active": True,
    }

    added_symbol = await client.add_symbol(new_symbol)

    if added_symbol:
        print("   ✅ Symbol added successfully:")
        print(f"      Symbol ID: {added_symbol.get('symbol_id')}")
        print(f"      Symbol: {added_symbol.get('symbol')}")
        symbol_id = added_symbol.get("symbol_id")
    else:
        print("   ❌ Add symbol endpoint not yet implemented")
        symbol_id = None

    if symbol_id:
        print(f"\n5️⃣  Updating symbol information (ID: {symbol_id})...")
        updates = {
            "price_decimals": 3,
            "quantity_decimals": 6,
            "active": False,
        }

        updated_symbol = await client.update_symbol(symbol_id, updates)

        if updated_symbol:
            print("   ✅ Symbol updated successfully:")
            print(f"      New price decimals: {updated_symbol.get('price_decimals')}")
            print(f"      New quantity decimals: {updated_symbol.get('quantity_decimals')}")
            print(f"      Active: {updated_symbol.get('active')}")
        else:
            print("   ❌ Update symbol endpoint not yet implemented")


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


async def run_symbol_operations_examples():
    """Run all symbol operations API examples."""
    print("\n" + "=" * 60)
    print("Running Symbol Operations API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run symbol operations examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run symbol discovery and management example
    await example_symbol_discovery_and_management(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Symbol operations handle trading pair metadata")
    print("   - Decimal precision is critical for order accuracy")
    print("   - Symbols are tied to specific exchanges")
    print("   - All operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Symbol Operations Example")
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
        await run_symbol_operations_examples()

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
