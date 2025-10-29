#!/usr/bin/env python3
"""
Example Beta1: OHLCV Collection Test with Bitmex Data

This example demonstrates end-to-end OHLCV data collection testing:

1. Uses fixed database names (fullon_beta1, fullon_beta1_ohlcv)
2. Skips setup if databases already exist (fast subsequent runs)
3. Starts FastAPI server with proper health checking
4. Initiates OHLCV collection service via API
5. Polls OHLCV API for daily candles for 2 minutes
6. Succeeds if candles are found, fails with exit code 1 if timeout
7. Preserves databases for reuse across runs

Database Persistence:
- First run: Creates databases and installs Bitmex demo data
- Subsequent runs: Uses existing databases (much faster!)
- To reset: Manually drop databases or use demo_data_beta1.py cleanup
"""

# 1. Standard library imports ONLY
import asyncio
import os
import sys
import time
from pathlib import Path

# 2. Load .env file FIRST before ANY other imports (critical for env var caching)
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env", override=True)  # Load .env first
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")


# 3. Use fixed database names for persistence across runs
test_db_orm = "fullon_beta1"
test_db_ohlcv = "fullon_beta1_ohlcv"

# 4. Override database environment variables AFTER loading .env (so they take precedence)
os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv
# CRITICAL: Also override DB_TEST_NAME to prevent test mode from using wrong database
os.environ["DB_TEST_NAME"] = test_db_orm

# Disable service auto-start for examples (we only need the API, not background services)
os.environ["SERVICE_AUTO_START_ENABLED"] = "false"
os.environ["HEALTH_MONITOR_ENABLED"] = "false"

# 5. Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# 6. Third-party imports (non-fullon packages)
import httpx

# 7. NOW safe to import ALL fullon modules (env vars set, .env loaded)
from demo_data_beta1 import (
    create_dual_test_databases,
    database_exists,
    drop_dual_test_databases,
    install_demo_data,
)
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.examples.beta1")

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


async def login(username: str, password: str) -> str | None:
    """
    Authenticate user and get JWT token.

    Args:
        username: User's username/email
        password: User's password

    Returns:
        str: JWT access token
        None: If login failed
    """
    login_url = f"{API_BASE_URL}/api/v1/auth/login"

    # Login payload (form-data for OAuth2 compatibility)
    login_data = {
        "username": username,
        "password": password,
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info("Attempting login", username=username)

            response = await client.post(
                login_url,
                data=login_data,  # OAuth2 uses form data
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            token_data = response.json()
            logger.info("Login successful", token_type=token_data.get("token_type"))

            print("✅ Login successful for OHLCV service start")
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed", error=str(e))
            print(f"❌ Login failed: {e}")
            return None


async def start_ohlcv_service(token: str) -> bool:
    """
    Start the OHLCV collection service via API.

    Args:
        token: JWT access token for authentication

    Returns:
        True if service started successfully, False otherwise
    """
    url = f"{API_BASE_URL}/api/v1/services/ohlcv/start"

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            result = response.json()

            if result.get("status") == "started":
                logger.info("OHLCV service started successfully")
                print("✅ OHLCV service started")
                return True
            else:
                logger.error("Failed to start OHLCV service", result=result)
                print("❌ Failed to start OHLCV service")
                return False

        except Exception as e:
            logger.error("Error starting OHLCV service", error=str(e))
            print(f"❌ Error starting OHLCV service: {e}")
            return False


async def poll_daily_candles(token: str, timeout_minutes: int = 2) -> bool:
    """
    Poll for daily OHLCV candles for specified minutes.

    Args:
        token: JWT access token for authentication
        timeout_minutes: Maximum time to poll for candles

    Returns:
        True if candles found, False if timeout
    """
    # URL format: /api/v1/ohlcv/{exchange}/{symbol}/{timeframe}
    # Symbol must match what was created in demo_data_beta1.py: BTC/USD:BTC
    # Need to URL-encode the symbol (BTC/USD:BTC -> BTC%2FUSD%3ABTC)
    from urllib.parse import quote

    symbol = "BTC/USD:BTC"
    encoded_symbol = quote(symbol, safe="")
    url = f"{API_BASE_URL}/api/v1/ohlcv/bitmex/{encoded_symbol}/1d"

    # Add JWT token to headers
    headers = {"Authorization": f"Bearer {token}"}

    start_time = time.time()
    timeout_seconds = timeout_minutes * 60

    print(f"🔍 Polling for daily candles (timeout: {timeout_minutes} minutes)...")
    print(f"   URL: {url}")

    async with httpx.AsyncClient() as client:
        while (time.time() - start_time) < timeout_seconds:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data and len(data) > 0:
                    logger.info("Daily candles found", count=len(data))
                    print(f"✅ Found {len(data)} daily candles!")
                    return True
                else:
                    elapsed = int(time.time() - start_time)
                    print(f"⏳ No daily candles yet ({elapsed}s elapsed)")

            except Exception as e:
                elapsed = int(time.time() - start_time)
                print(f"⏳ API not ready yet ({elapsed}s elapsed): {str(e)[:50]}...")

            await asyncio.sleep(5)  # Check every 5 seconds

    logger.error("Timeout waiting for daily candles")
    print(f"❌ No daily candles found within {timeout_minutes} minutes - OHLCV collection failed!")
    return False


async def setup_test_environment():
    """
    Setup test databases with Bitmex demo data.

    Uses fixed database names (fullon_beta1, fullon_beta1_ohlcv).
    If databases already exist, skips creation and installation.
    """
    print("\n" + "=" * 60)
    print("Setting up Bitmex test environment")
    print("=" * 60)

    # Check if databases already exist
    print(f"\n1. Checking if databases exist:")
    print(f"   ORM DB:   {test_db_orm}")
    print(f"   OHLCV DB: {test_db_ohlcv}")

    orm_exists = await database_exists(test_db_orm)
    ohlcv_exists = await database_exists(test_db_ohlcv)

    if orm_exists and ohlcv_exists:
        print("   ✅ Databases already exist - skipping creation and installation")
        logger.info("Using existing databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)
        print("\n" + "=" * 60)
        print("✅ Bitmex test environment ready!")
        print("=" * 60)
        return

    # If either database doesn't exist, create both
    if orm_exists or ohlcv_exists:
        print("   ⚠️  Only some databases exist - recreating both for consistency")
        logger.warning("Partial database setup detected - recreating", orm_exists=orm_exists, ohlcv_exists=ohlcv_exists)
        # Drop any existing ones to start fresh
        if orm_exists:
            await drop_dual_test_databases(test_db_orm, test_db_ohlcv)
        else:
            await drop_dual_test_databases(test_db_orm, test_db_ohlcv)

    # Create both databases
    print(f"\n2. Creating dual test databases:")
    logger.info("Creating test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)

    # Use test_db_orm as base name (create_dual_test_databases will add _ohlcv suffix)
    orm_db_name, ohlcv_db_name = await create_dual_test_databases(test_db_orm)
    logger.info("Test databases created", orm_db=orm_db_name, ohlcv_db=ohlcv_db_name)

    # Initialize database schema
    print("\n3. Initializing database schema...")
    await init_db()
    print("   ✅ Schema initialized")

    # Install Bitmex demo data (no sample candles)
    print("\n4. Installing Bitmex demo data...")
    success = await install_demo_data()
    if not success:
        raise Exception("Failed to install demo data")

    print("\n" + "=" * 60)
    print("✅ Bitmex test environment ready!")
    print("=" * 60)


async def main():
    """
    Main entry point - self-contained OHLCV collection test.
    """
    print("=" * 60)
    print("Fullon Master API - OHLCV Collection Test (Beta1)")
    print("SELF-CONTAINED: Bitmex data + OHLCV collection")
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
        if not await wait_for_server(API_BASE_URL, timeout=10):
            raise RuntimeError("Server failed to start within 10 seconds")

        print("   ✅ Server started")

        # Login to get JWT token
        print("\n5. Authenticating admin user...")
        token = await login("admin@fullon", "password")
        if not token:
            raise RuntimeError("Authentication failed")

        # Start OHLCV collection service
        print("\n6. Starting OHLCV collection service...")
        if not await start_ohlcv_service(token):
            raise RuntimeError("Failed to start OHLCV service")

        # Poll for daily candles
        print("\n7. Monitoring OHLCV collection...")
        success = await poll_daily_candles(token, timeout_minutes=2)

        if success:
            print("\n🎉 OHLCV collection test PASSED!")
            print("   Daily candles were successfully collected and retrieved.")
        else:
            print("\n💥 OHLCV collection test FAILED!")
            print("   No daily candles were collected within the timeout period.")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback

        traceback.print_exc()
        logger.error("Example failed", error=str(e))
        sys.exit(1)

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

        # Preserve databases for reuse
        print("\n" + "=" * 60)
        print("Database Persistence")
        print("=" * 60)
        print(f"📦 Databases preserved for reuse:")
        print(f"   ORM DB:   {test_db_orm}")
        print(f"   OHLCV DB: {test_db_ohlcv}")
        print("\n💡 Next run will skip installation and use existing data")
        print("   To start fresh, manually drop databases:")
        print(f"   DROP DATABASE {test_db_orm};")
        print(f"   DROP DATABASE {test_db_ohlcv};")
        logger.info("Databases preserved for reuse", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
