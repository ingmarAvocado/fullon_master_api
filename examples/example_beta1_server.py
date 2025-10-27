#!/usr/bin/env python3
"""
Example Beta1 Server: OHLCV Collection Service

Starts and runs the Fullon Master API server with OHLCV collection service.
Server runs continuously until stopped with Ctrl-C.

Features:
- Uses fixed database names (fullon_beta1, fullon_beta1_ohlcv)
- Skips setup if databases already exist (fast restarts)
- Starts OHLCV collection service automatically
- Runs FastAPI server on http://localhost:8000
- Graceful shutdown on Ctrl-C

Usage:
    python examples/example_beta1_server.py

    # In another terminal, use the client:
    python examples/example_beta1_client.py

To reset databases:
    DROP DATABASE fullon_beta1;
    DROP DATABASE fullon_beta1_ohlcv;
"""

# 1. Standard library imports ONLY
import asyncio
import os
import signal
import sys
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
    install_demo_data,
)
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.examples.beta1.server")


async def setup_test_environment():
    """
    Setup test databases with Hyperliquid demo data.

    Uses fixed database names (fullon_beta1, fullon_beta1_ohlcv).
    If databases already exist, skips creation and installation.
    """
    print("\n" + "=" * 60)
    print("Setting up Hyperliquid test environment")
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
        print("✅ Hyperliquid test environment ready!")
        print("=" * 60)
        return

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

    # Install Hyperliquid demo data (no sample candles)
    print("\n4. Installing Hyperliquid demo data...")
    success = await install_demo_data()
    if not success:
        raise Exception("Failed to install demo data")

    print("\n" + "=" * 60)
    print("✅ Hyperliquid test environment ready!")
    print("=" * 60)


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)

    return server


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


async def login(username: str, password: str, base_url: str = "http://localhost:8000") -> str | None:
    """
    Authenticate user and get JWT token.

    Args:
        username: User's username/email
        password: User's password
        base_url: API base URL

    Returns:
        str: JWT access token
        None: If login failed
    """
    login_url = f"{base_url}/api/v1/auth/login"

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

            print("✅ Login successful")
            return token_data["access_token"]

        except Exception as e:
            logger.error("Login failed", error=str(e))
            print(f"❌ Login failed: {e}")
            return None


async def start_ohlcv_service(token: str, base_url: str = "http://localhost:8000") -> bool:
    """
    Start the OHLCV collection service via API.

    Args:
        token: JWT access token for authentication
        base_url: API base URL

    Returns:
        True if service started successfully, False otherwise
    """
    url = f"{base_url}/api/v1/services/ohlcv/start"

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


async def main():
    """
    Main entry point - starts server and runs until Ctrl-C.
    """
    print("=" * 60)
    print("Fullon Master API - OHLCV Collection Server (Beta1)")
    print("Server runs continuously until Ctrl-C")
    print("=" * 60)

    server = None
    server_task = None

    # Setup signal handlers for graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print("\n🛑 Shutdown signal received...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Setup test environment
        await setup_test_environment()

        # Start embedded test server
        print("\n📡 Starting server on http://localhost:8000...")

        server = await start_test_server()
        server_task = asyncio.create_task(server.serve())

        # Wait for server to be ready (polls health endpoint)
        if not await wait_for_server("http://localhost:8000", timeout=10):
            raise RuntimeError("Server failed to start within 10 seconds")

        print("   ✅ Server started")

        # Login to get JWT token
        print("\n🔐 Authenticating admin user...")
        token = await login("admin@fullon", "password")
        if not token:
            raise RuntimeError("Authentication failed")

        # Start OHLCV collection service
        print("\n📊 Starting OHLCV collection service...")
        if not await start_ohlcv_service(token):
            raise RuntimeError("Failed to start OHLCV service")

        print("\n" + "=" * 60)
        print("✅ SERVER RUNNING")
        print("=" * 60)
        print(f"\n📡 API available at: http://localhost:8000")
        print(f"📖 API docs at: http://localhost:8000/docs")
        print(f"💾 Using databases: {test_db_orm}, {test_db_ohlcv}")
        print(f"\n💡 Use example_beta1_client.py to query OHLCV data")
        print(f"🛑 Press Ctrl-C to stop the server\n")

        # Wait for shutdown signal
        await shutdown_event.wait()

    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received...")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback

        traceback.print_exc()
        logger.error("Server error", error=str(e))
        sys.exit(1)

    finally:
        # Stop test server
        if server:
            print("\n🔄 Stopping server...")
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
        logger.info("Databases preserved for reuse", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
