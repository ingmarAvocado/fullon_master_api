#!/usr/bin/env python3
"""
Example: Daemon Control

Demonstrates:
- Starting the API as a background daemon
- Stopping the daemon
- Checking daemon status
- Viewing daemon logs
- Programmatic daemon management

Usage:
    python examples/example_daemon_control.py --action start
    python examples/example_daemon_control.py --action status
    python examples/example_daemon_control.py --action logs
    python examples/example_daemon_control.py --action stop
"""
import asyncio
import subprocess
import argparse
import time
from pathlib import Path
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.daemon_control")

PROJECT_ROOT = Path(__file__).parent.parent
DAEMON_SCRIPT = PROJECT_ROOT / "start_fullon.py"


async def start_daemon():
    """Start the daemon."""
    print("\n" + "=" * 60)
    print("Starting Fullon Master API Daemon")
    print("=" * 60)

    result = subprocess.run(
        [str(DAEMON_SCRIPT), "start"],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        logger.info("Daemon started successfully")

        # Wait a moment for daemon to initialize
        print("\n⏳ Waiting for daemon to initialize...")
        await asyncio.sleep(3)

        # Check status
        await check_status()
    else:
        logger.error("Failed to start daemon", returncode=result.returncode)

    return result.returncode


async def stop_daemon():
    """Stop the daemon."""
    print("\n" + "=" * 60)
    print("Stopping Fullon Master API Daemon")
    print("=" * 60)

    result = subprocess.run(
        [str(DAEMON_SCRIPT), "stop"],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        logger.info("Daemon stopped successfully")
    else:
        logger.error("Failed to stop daemon", returncode=result.returncode)

    return result.returncode


async def restart_daemon():
    """Restart the daemon."""
    print("\n" + "=" * 60)
    print("Restarting Fullon Master API Daemon")
    print("=" * 60)

    result = subprocess.run(
        [str(DAEMON_SCRIPT), "restart"],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        logger.info("Daemon restarted successfully")
        await asyncio.sleep(3)
        await check_status()
    else:
        logger.error("Failed to restart daemon", returncode=result.returncode)

    return result.returncode


async def check_status():
    """Check daemon status."""
    print("\n" + "=" * 60)
    print("Checking Daemon Status")
    print("=" * 60)

    result = subprocess.run(
        [str(DAEMON_SCRIPT), "status"],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0:
        logger.info("Daemon is running")

        # Try to connect to API
        print("\n⏳ Testing API connectivity...")
        await test_api_connection()
    else:
        logger.info("Daemon is not running")

    return result.returncode


async def view_logs(lines: int = 20):
    """View daemon logs."""
    print("\n" + "=" * 60)
    print(f"Daemon Logs (last {lines} lines)")
    print("=" * 60)

    result = subprocess.run(
        [str(DAEMON_SCRIPT), "logs", "--no-follow", "--lines", str(lines)],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    print("\n💡 Tip: Use './start_fullon.py logs' to tail logs in real-time")

    return result.returncode


async def test_api_connection():
    """Test if API is responding."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/health")

            if response.status_code == 200:
                data = response.json()
                print("   ✅ API is responding")
                print(f"      Status: {data.get('status')}")
                print(f"      Version: {data.get('version')}")
                logger.info("API health check successful", **data)
            else:
                print(f"   ⚠️  API returned status {response.status_code}")

    except httpx.ConnectError:
        print("   ❌ Cannot connect to API")
        print("      Daemon may still be starting...")
    except Exception as e:
        print(f"   ❌ Error: {e}")


async def full_lifecycle_example():
    """Demonstrate full daemon lifecycle."""
    print("\n" + "=" * 60)
    print("Full Daemon Lifecycle Example")
    print("=" * 60)
    print("\nThis example will:")
    print("  1. Start the daemon")
    print("  2. Check status")
    print("  3. View logs")
    print("  4. Restart daemon")
    print("  5. Stop daemon")

    input("\nPress ENTER to continue...")

    # 1. Start
    print("\n\n📍 Step 1: Starting daemon...")
    await start_daemon()
    await asyncio.sleep(2)

    # 2. Status
    print("\n\n📍 Step 2: Checking status...")
    await check_status()
    await asyncio.sleep(2)

    # 3. Logs
    print("\n\n📍 Step 3: Viewing logs...")
    await view_logs(lines=10)
    await asyncio.sleep(2)

    # 4. Restart
    print("\n\n📍 Step 4: Restarting daemon...")
    await restart_daemon()
    await asyncio.sleep(2)

    # 5. Stop
    print("\n\n📍 Step 5: Stopping daemon...")
    await stop_daemon()

    print("\n" + "=" * 60)
    print("✅ Full lifecycle example complete!")
    print("=" * 60)


async def main(action: str, lines: int = 20):
    """Run daemon control example."""
    if action == "start":
        return await start_daemon()
    elif action == "stop":
        return await stop_daemon()
    elif action == "restart":
        return await restart_daemon()
    elif action == "status":
        return await check_status()
    elif action == "logs":
        return await view_logs(lines)
    elif action == "lifecycle":
        return await full_lifecycle_example()
    else:
        print(f"Unknown action: {action}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daemon Control Example")
    parser.add_argument(
        "--action",
        type=str,
        default="status",
        choices=["start", "stop", "restart", "status", "logs", "lifecycle"],
        help="Action to perform",
    )
    parser.add_argument(
        "--lines",
        type=int,
        default=20,
        help="Number of log lines to show (for logs action)",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(main(args.action, args.lines))
    exit(exit_code)
