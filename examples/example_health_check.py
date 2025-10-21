#!/usr/bin/env python3
"""
Example: Health Check API

Demonstrates:
- Basic API connectivity
- Health endpoint (no authentication required)
- Service status verification
- Programmatic API access using httpx

Expected Output:
{
    "status": "healthy",
    "version": "1.0.0",
    "service": "fullon_master_api"
}
"""
import asyncio
import httpx
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.health_check")

API_BASE_URL = "http://localhost:8000"


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

            return health_data

        except httpx.ConnectError:
            logger.error("Cannot connect to API - is the server running?")
            print("\n❌ Connection Failed")
            print(f"   Make sure the server is running on {API_BASE_URL}")
            print("   Run: make run")
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


async def main():
    """Run all health checks."""
    print("=" * 60)
    print("Fullon Master API - Health Check Example")
    print("=" * 60)

    # Check health endpoint
    health = await check_health()

    if health and health["status"] == "healthy":
        # Check root endpoint for API info
        await check_root()
        print("\n✅ All checks passed!")
    else:
        print("\n❌ Health check failed - server may not be running")
        print(f"\nTo start the server:")
        print("  cd /home/ingmar/code/fullon_master_api")
        print("  make run")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
