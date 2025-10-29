#!/usr/bin/env python3
"""
Example Beta1 Server: OHLCV Collection Service

Starts and runs the Fullon Master API server with OHLCV collection service.
Server runs continuously until stopped with Ctrl-C.

Features:
- Uses fixed database names (fullon_beta1, fullon_beta1_ohlcv)
- Skips setup if databases already exist (fast restarts)
- Starts OHLCV collection service automatically using API key
- Runs FastAPI server on http://localhost:8000
- Graceful shutdown on Ctrl-C

Prerequisites:
    # Setup databases and create API key:
    python examples/demo_data_beta1.py --setup fullon_beta1

Usage:
    python examples/example_beta1_server.py

    # In another terminal, use the client:
    python examples/example_beta1_client.py

To reset databases:
    python examples/demo_data_beta1.py --cleanup fullon_beta1
"""

# 1. Standard library imports ONLY
import asyncio
import os
import signal
import subprocess
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
    install_demo_data,
)
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.examples.beta1.server")

# 9. Get server port from environment (default: 8000)
SERVER_PORT = int(os.getenv("PORT", "8000"))


def check_port_in_use(port: int = 8000) -> list[int]:
    """
    Check if a port is in use and return the PIDs using it.

    Args:
        port: Port number to check

    Returns:
        list[int]: List of PIDs using the port
    """
    try:
        # Use lsof to find processes using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            pids = [int(pid) for pid in result.stdout.strip().split("\n") if pid]
            return pids
        return []
    except subprocess.TimeoutExpired:
        logger.warning("Port check timed out", port=port)
        return []
    except FileNotFoundError:
        # lsof not available, try netstat
        try:
            result = subprocess.run(
                ["netstat", "-tulpn"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse netstat output for port
            pids = []
            for line in result.stdout.split("\n"):
                if f":{port}" in line and "LISTEN" in line:
                    # Extract PID from netstat output
                    parts = line.split()
                    for part in parts:
                        if "/" in part:
                            try:
                                pid = int(part.split("/")[0])
                                pids.append(pid)
                            except ValueError:
                                pass
            return pids
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("Could not check port status - lsof and netstat not available", port=port)
            return []
    except Exception as e:
        logger.error("Error checking port", port=port, error=str(e))
        return []


def kill_processes_on_port(port: int = 8000) -> bool:
    """
    Kill all processes using a specific port.

    Args:
        port: Port number to clear

    Returns:
        bool: True if processes were killed, False otherwise
    """
    pids = check_port_in_use(port)

    if not pids:
        return False

    print(f"\n⚠️  Port {port} is already in use by PIDs: {pids}")
    print(f"🔪 Killing processes to free port {port}...")

    killed = []
    for pid in pids:
        try:
            # Try graceful kill first (SIGTERM)
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
            logger.info("Sent SIGTERM to process", pid=pid, port=port)
        except ProcessLookupError:
            # Process already dead
            logger.debug("Process already terminated", pid=pid)
        except PermissionError:
            logger.error("Permission denied to kill process", pid=pid)
            print(f"   ❌ Cannot kill PID {pid} (permission denied)")
        except Exception as e:
            logger.error("Error killing process", pid=pid, error=str(e))
            print(f"   ❌ Error killing PID {pid}: {e}")

    if killed:
        # Wait a bit for graceful shutdown
        time.sleep(1)

        # Check if any processes are still alive, force kill them
        remaining = check_port_in_use(port)
        if remaining:
            print(f"⚠️  Some processes still alive, force killing: {remaining}")
            for pid in remaining:
                try:
                    os.kill(pid, signal.SIGKILL)
                    logger.info("Sent SIGKILL to process", pid=pid, port=port)
                except (ProcessLookupError, PermissionError):
                    pass

            time.sleep(0.5)

        # Final check
        final_check = check_port_in_use(port)
        if not final_check:
            print(f"   ✅ Port {port} is now free")
            logger.info("Port cleared successfully", port=port, killed_pids=killed)
            return True
        else:
            print(f"   ⚠️  Some processes could not be killed: {final_check}")
            logger.warning("Some processes remain on port", port=port, remaining_pids=final_check)
            return False

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


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=SERVER_PORT,
        log_level="info"
    )
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


async def start_ohlcv_service(api_key: str, base_url: str = "http://localhost:8000") -> bool:
    """
    Start the OHLCV collection service via API.

    Args:
        api_key: API key for authentication
        base_url: API base URL

    Returns:
        True if service started successfully, False otherwise
    """
    url = f"{base_url}/api/v1/services/ohlcv/start"

    headers = {"X-API-Key": api_key}

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


async def run_server_and_services():
    """
    Run server setup and start services.

    This function is called as a subprocess, so it can be killed immediately.
    """
    try:
        # Setup test environment
        await setup_test_environment()

        # Start embedded test server
        print(f"\n📡 Starting server on http://localhost:{SERVER_PORT}...")

        server = await start_test_server()
        server_task = asyncio.create_task(server.serve())

        # Wait for server to be ready (polls health endpoint)
        if not await wait_for_server(f"http://localhost:{SERVER_PORT}", timeout=10):
            raise RuntimeError("Server failed to start within 10 seconds")

        print("   ✅ Server started")

        # Read API key from file
        print("\n🔑 Reading API key...")
        api_key_file = Path(__file__).parent / ".beta1_api_key"
        if not api_key_file.exists():
            raise RuntimeError("API key file not found. Run: python examples/demo_data_beta1.py --setup fullon_beta1")

        api_key = api_key_file.read_text().strip()
        print(f"   ✅ API key loaded: {api_key[:20]}...")

        # Start OHLCV collection service
        print("\n📊 Starting OHLCV collection service...")
        if not await start_ohlcv_service(api_key, base_url=f"http://localhost:{SERVER_PORT}"):
            raise RuntimeError("Failed to start OHLCV service")

        print("\n" + "=" * 60)
        print("✅ SERVER RUNNING")
        print("=" * 60)
        print(f"\n📡 API available at: http://localhost:{SERVER_PORT}")
        print(f"📖 API docs at: http://localhost:{SERVER_PORT}/docs")
        print(f"💾 Using databases: {test_db_orm}, {test_db_ohlcv}")
        print(f"\n💡 Use example_beta1_client.py to query OHLCV data")
        print(f"🛑 Press Ctrl-C to stop the server\n")

        # Wait forever (server runs until killed)
        await server_task

    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback
        traceback.print_exc()
        logger.error("Server error", error=str(e))
        sys.exit(1)


def main():
    """
    Main entry point - starts server subprocess and handles Ctrl-C for immediate exit.
    """
    # Check if we're running as the subprocess (server mode)
    if os.environ.get("_FULLON_SERVER_SUBPROCESS") == "1":
        # Run the server directly
        asyncio.run(run_server_and_services())
        return

    # We're the main wrapper process
    print("=" * 60)
    print("Fullon Master API - OHLCV Collection Server (Beta1)")
    print("Server runs continuously until Ctrl-C")
    print("=" * 60)

    server_process = None

    def signal_handler(sig, frame):
        """Handle Ctrl-C by immediately killing the server subprocess."""
        print("\n💥 Ctrl-C received - killing server immediately!")

        # Kill subprocess if running
        if server_process and server_process.poll() is None:
            try:
                server_process.kill()  # SIGKILL for immediate termination
                server_process.wait(timeout=1)
            except:
                pass

        # Also kill any processes on the configured port
        try:
            subprocess.run(["sh", "-c", f"lsof -ti :{SERVER_PORT} | xargs kill -9 2>/dev/null || true"], timeout=2)
        except:
            pass

        print("   ✅ Server killed")
        print("\n" + "=" * 60)
        print("Database Persistence")
        print("=" * 60)
        print(f"📦 Databases preserved for reuse:")
        print(f"   ORM DB:   {test_db_orm}")
        print(f"   OHLCV DB: {test_db_ohlcv}")
        print("\n💡 Next run will skip installation and use existing data")
        print("=" * 60)

        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Check if configured port is already in use and kill if necessary
        print(f"\n🔍 Checking if port {SERVER_PORT} is available...")
        if check_port_in_use(SERVER_PORT):
            kill_processes_on_port(SERVER_PORT)
        else:
            print(f"   ✅ Port {SERVER_PORT} is available")

        # Run server in subprocess for immediate kill capability
        # Set environment variable to indicate subprocess mode
        env = os.environ.copy()
        env["_FULLON_SERVER_SUBPROCESS"] = "1"

        server_process = subprocess.Popen(
            [sys.executable, "-u", __file__],
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env
        )

        # Wait for subprocess to finish (or be killed by Ctrl-C)
        server_process.wait()

        print("\n   ✅ Server stopped")
        print("\n" + "=" * 60)
        print("Database Persistence")
        print("=" * 60)
        print(f"📦 Databases preserved for reuse:")
        print(f"   ORM DB:   {test_db_orm}")
        print(f"   OHLCV DB: {test_db_ohlcv}")
        print("\n💡 Next run will skip installation and use existing data")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        if server_process and server_process.poll() is None:
            server_process.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
