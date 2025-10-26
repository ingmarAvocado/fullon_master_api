#!/usr/bin/env python3
"""
Example: Exchange Catalog - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users, bots, exchanges, symbols)
- Starts its own embedded test server
- Tests exchange catalog API endpoints
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_exchange_catalog.py

Demonstrates:
- Browsing available exchanges
- Viewing exchange parameters and symbols
- Adding user exchange connections
- Managing user exchange configurations
- Getting exchange metadata

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/orm/exchanges/catalog                      - List available exchanges
- GET    /api/v1/orm/exchanges/catalog/{cat_ex_id}/params   - Exchange parameters
- GET    /api/v1/orm/exchanges/catalog/{cat_ex_id}/symbols  - Exchange available symbols
- GET    /api/v1/orm/exchanges/user-exchanges               - User's configured exchanges
- GET    /api/v1/orm/exchanges/id-by-name                   - Get exchange ID by name
- GET    /api/v1/orm/exchanges/catalog-id                   - Get catalog exchange ID
- POST   /api/v1/orm/exchanges/user-exchanges              - Add user exchange
- PATCH  /api/v1/orm/exchanges/user-exchanges/{ex_id}     - Update user exchange
- DELETE /api/v1/orm/exchanges/user-exchanges/{ex_id}     - Remove user exchange
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
logger = get_component_logger("fullon.examples.exchange_catalog")

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
            logger.info("Login successful for exchange catalog example", username=username)
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed for exchange catalog example", error=str(e))
            return None


class ExchangeCatalogClient:
    """Client for exchange catalog API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def list_available_exchanges(self) -> Optional[list]:
        """List available exchanges in catalog."""
        url = f"{self.base_url}/api/v1/orm/exchanges/catalog"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List available exchanges failed", status=e.response.status_code)
                return None

    async def get_exchange_params(self, cat_ex_id: int) -> Optional[dict]:
        """Get exchange parameters."""
        url = f"{self.base_url}/api/v1/orm/exchanges/catalog/{cat_ex_id}/params"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get exchange params failed", status=e.response.status_code, cat_ex_id=cat_ex_id
                )
                return None

    async def get_exchange_symbols(self, cat_ex_id: int) -> Optional[list]:
        """Get exchange available symbols."""
        url = f"{self.base_url}/api/v1/orm/exchanges/catalog/{cat_ex_id}/symbols"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get exchange symbols failed",
                    status=e.response.status_code,
                    cat_ex_id=cat_ex_id,
                )
                return None

    async def list_user_exchanges(self) -> Optional[list]:
        """List user's configured exchanges."""
        url = f"{self.base_url}/api/v1/orm/exchanges/user-exchanges"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List user exchanges failed", status=e.response.status_code)
                return None

    async def get_exchange_id_by_name(self, name: str) -> Optional[int]:
        """Get exchange ID by name."""
        url = f"{self.base_url}/api/v1/orm/exchanges/id-by-name?name={name}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()
                return result.get("exchange_id")
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get exchange ID by name failed", status=e.response.status_code, name=name
                )
                return None

    async def get_catalog_exchange_id(self, exchange_name: str) -> Optional[int]:
        """Get catalog exchange ID."""
        url = f"{self.base_url}/api/v1/orm/exchanges/catalog-id?exchange_name={exchange_name}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()
                return result.get("cat_ex_id")
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get catalog exchange ID failed",
                    status=e.response.status_code,
                    exchange_name=exchange_name,
                )
                return None

    async def add_user_exchange(self, exchange_config: dict) -> Optional[dict]:
        """Add user exchange connection."""
        url = f"{self.base_url}/api/v1/orm/exchanges/user-exchanges"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=exchange_config, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Add user exchange failed", status=e.response.status_code)
                return None

    async def update_user_exchange(self, ex_id: int, updates: dict) -> Optional[dict]:
        """Update user exchange configuration."""
        url = f"{self.base_url}/api/v1/orm/exchanges/user-exchanges/{ex_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(url, json=updates, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Update user exchange failed", status=e.response.status_code, ex_id=ex_id
                )
                return None

    async def remove_user_exchange(self, ex_id: int) -> bool:
        """Remove user exchange connection."""
        url = f"{self.base_url}/api/v1/orm/exchanges/user-exchanges/{ex_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=self._get_headers())
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Remove user exchange failed", status=e.response.status_code, ex_id=ex_id
                )
                return False


async def example_exchange_discovery_and_management(token: str):
    """Demonstrate exchange discovery and management."""
    print("\n" + "=" * 60)
    print("Example: Exchange Discovery & Management (ORM API)")
    print("=" * 60)

    client = ExchangeCatalogClient(token=token)

    print("\n1️⃣  Browsing available exchanges in catalog...")
    available_exchanges = await client.list_available_exchanges()

    if available_exchanges:
        print(f"   ✅ Found {len(available_exchanges)} available exchanges")
        for exchange in available_exchanges[:3]:  # Show first 3
            print(f"      - {exchange.get('name')} (ID: {exchange.get('cat_ex_id')})")
        # Get first exchange for further operations
        first_exchange = available_exchanges[0] if available_exchanges else None
        cat_ex_id = first_exchange.get("cat_ex_id") if first_exchange else None
    else:
        print("   ❌ Available exchanges endpoint not yet implemented")
        cat_ex_id = None

    if cat_ex_id:
        print(f"\n2️⃣  Getting parameters for exchange (ID: {cat_ex_id})...")
        params = await client.get_exchange_params(cat_ex_id)

        if params:
            print("   ✅ Exchange parameters retrieved:")
            print(f"      Params: {params}")
        else:
            print("   ❌ Exchange params endpoint not yet implemented")

        print(f"\n3️⃣  Getting available symbols for exchange (ID: {cat_ex_id})...")
        symbols = await client.get_exchange_symbols(cat_ex_id)

        if symbols is not None:
            print(f"   ✅ Found {len(symbols)} symbols for exchange")
            for symbol in symbols[:5]:  # Show first 5
                print(f"      - {symbol.get('symbol')}")
        else:
            print("   ❌ Exchange symbols endpoint not yet implemented")

    print("\n4️⃣  Listing user's configured exchanges...")
    user_exchanges = await client.list_user_exchanges()

    if user_exchanges is not None:
        print(f"   ✅ Found {len(user_exchanges)} user-configured exchanges")
        for exchange in user_exchanges[:2]:  # Show first 2
            print(f"      - {exchange.get('name')} (ID: {exchange.get('ex_id')})")
    else:
        print("   ❌ User exchanges endpoint not yet implemented")

    print("\n5️⃣  Getting exchange ID by name (Binance)...")
    exchange_id = await client.get_exchange_id_by_name("Binance")

    if exchange_id:
        print(f"   ✅ Exchange ID for Binance: {exchange_id}")
    else:
        print("   ❌ Exchange ID by name endpoint not yet implemented")

    print("\n6️⃣  Getting catalog exchange ID for Binance...")
    catalog_id = await client.get_catalog_exchange_id("Binance")

    if catalog_id:
        print(f"   ✅ Catalog exchange ID for Binance: {catalog_id}")
    else:
        print("   ❌ Catalog exchange ID endpoint not yet implemented")

    print("\n7️⃣  Adding new user exchange connection...")
    new_exchange_config = {
        "cat_ex_id": 1,  # Binance
        "name": "My Binance Account",
        "api_key": "test_api_key_123",
        "api_secret": "test_api_secret_456",
        "is_testnet": True,
    }

    added_exchange = await client.add_user_exchange(new_exchange_config)

    if added_exchange:
        print("   ✅ User exchange added successfully:")
        print(f"      Exchange ID: {added_exchange.get('ex_id')}")
        print(f"      Name: {added_exchange.get('name')}")
        ex_id = added_exchange.get("ex_id")
    else:
        print("   ❌ Add user exchange endpoint not yet implemented")
        ex_id = None

    if ex_id:
        print(f"\n8️⃣  Updating user exchange configuration (ID: {ex_id})...")
        updates = {
            "name": "Updated Binance Account",
            "is_testnet": False,
        }

        updated_exchange = await client.update_user_exchange(ex_id, updates)

        if updated_exchange:
            print("   ✅ User exchange updated successfully:")
            print(f"      New name: {updated_exchange.get('name')}")
            print(f"      Testnet: {updated_exchange.get('is_testnet')}")
        else:
            print("   ❌ Update user exchange endpoint not yet implemented")

        print(f"\n9️⃣  Removing user exchange connection (ID: {ex_id})...")
        removed = await client.remove_user_exchange(ex_id)

        if removed:
            print("   ✅ User exchange removed successfully")
        else:
            print("   ❌ Remove user exchange endpoint not yet implemented")


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


async def run_exchange_catalog_examples():
    """Run all exchange catalog API examples."""
    print("\n" + "=" * 60)
    print("Running Exchange Catalog API Examples")
    print("=" * 60)

    # Step 1: Login and get JWT token
    print("\n🔐 Authenticating...")
    token = await login_and_get_token()

    if not token:
        print("❌ Authentication failed - cannot run exchange catalog examples")
        print("   Auth endpoint may not be fully implemented")
        return

    print("✅ Authentication successful")

    # Run exchange discovery and management example
    await example_exchange_discovery_and_management(token)

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Exchange catalog provides discovery and configuration")
    print("   - Separate catalog and user-specific exchange management")
    print("   - Secure API key handling required")
    print("   - All operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Exchange Catalog Example")
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
        await run_exchange_catalog_examples()

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
