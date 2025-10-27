#!/usr/bin/env python3
"""
Example: Health Check API - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Starts its own embedded test server
- Tests the health check endpoints
- Stops the server when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_health_check.py

Demonstrates:
- Basic API connectivity
- Enhanced health endpoint with ProcessCache monitoring
- Self-healing capabilities with auto-restart
- Service status monitoring
- Process health tracking
- Programmatic API access using httpx

Expected Output (Enhanced):
{
    "status": "healthy|degraded|recovering",
    "version": "1.0.0",
    "service": "fullon_master_api",
    "services": {
        "ticker": {"service": "ticker", "status": "running|stopped", "is_running": true|false},
        "ohlcv": {"service": "ohlcv", "status": "running|stopped", "is_running": true|false},
        "account": {"service": "account", "status": "running|stopped", "is_running": true|false}
    },
    "processes": {
        "system_health": {...},
        "active_count": 0,
        "active_processes": [...]
    },
    "issues": [...],
    "auto_restarts": 0
}
"""
import asyncio
import httpx
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.health_check")

API_BASE_URL = "http://localhost:8000"


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    return server, task


async def check_health():
    """Check API health status."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            response.raise_for_status()

            health_data = response.json()
            logger.info("Health check successful", **health_data)

            print("\n✅ API Health Check:")
            print(f"   Status: {health_data['status']}")
            print(f"   Version: {health_data['version']}")
            print(f"   Service: {health_data['service']}")

            # Show enhanced health features
            if "services" in health_data:
                print(f"   Services monitored: {len(health_data['services'])}")
                for service_name, service_info in health_data["services"].items():
                    status = service_info.get("status", "unknown")
                    running = "✅" if service_info.get("is_running", False) else "❌"
                    print(f"     {service_name}: {status} {running}")

            if "processes" in health_data:
                active_count = health_data["processes"].get("active_count", 0)
                print(f"   Active processes: {active_count}")

            if "auto_restarts" in health_data and health_data["auto_restarts"] > 0:
                print(f"   Auto-restarts performed: {health_data['auto_restarts']}")

            if "issues" in health_data and health_data["issues"]:
                print(f"   Issues detected: {len(health_data['issues'])}")
                for issue in health_data["issues"][:3]:  # Show first 3 issues
                    print(f"     - {issue}")
                if len(health_data["issues"]) > 3:
                    print(f"     ... and {len(health_data['issues']) - 3} more")

            return health_data

        except httpx.ConnectError:
            logger.error("Cannot connect to API - is the server running?")
            print("\n❌ Connection Failed")
            print(f"   Make sure the server is running on {API_BASE_URL}")
            return None

        except httpx.HTTPStatusError as e:
            logger.error("Health check failed", status_code=e.response.status_code)
            print(f"\n❌ Health check failed with status {e.response.status_code}")
            return None


async def check_root():
    """Check API root endpoint."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/")
            response.raise_for_status()

            root_data = response.json()
            logger.info("Root endpoint successful", **root_data)

            print("\n📋 API Information:")
            print(f"   Service: {root_data['service']}")
            print(f"   Version: {root_data['version']}")
            print(f"   Docs: {API_BASE_URL}{root_data['docs']}")
            print(f"   Health: {API_BASE_URL}{root_data['health']}")
            print(f"   API: {API_BASE_URL}{root_data['api']}")

            return root_data

        except Exception as e:
            logger.error("Root endpoint check failed", error=str(e))
            return None


async def run_examples():
    """Run all health check examples."""
    print("\n" + "=" * 60)
    print("Running Health Check Examples")
    print("=" * 60)

    # Check health endpoint
    health = await check_health()

    if health and health["status"] == "healthy":
        # Check root endpoint for API info
        await check_root()
        print("\n✅ All checks passed!")
        return True
    else:
        print("\n❌ Health check failed")
        return False


async def main():
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Health Check Example")
    print("SELF-CONTAINED: Starts, tests, and stops server automatically")
    print("=" * 60)

    server = None
    server_task = None
    try:
        # Start embedded test server
        print("\n1. Starting test server on localhost:8000...")
        server, server_task = await start_test_server()
        await asyncio.sleep(2)  # Wait for server to start
        print("   ✅ Server started")

        # Run examples
        success = await run_examples()

        if not success:
            logger.error("Health check examples failed")

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

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
