#!/usr/bin/env python3
"""
Example: Service Control (Admin-Only)

Demonstrates:
- Admin authentication (user must match ADMIN_MAIL from .env)
- Starting/stopping/restarting services
- Checking service status
- Service lifecycle management
- Proper error handling for non-admin users

Services:
- ticker: Real-time ticker data collection (fullon_ticker_service)
- ohlcv: Historic + live OHLCV/trade collection (fullon_ohlcv_service)
- account: Adaptive account monitoring (fullon_account_service)

Expected Endpoints:
- POST   /api/v1/services/{service_name}/start   - Start service (admin only)
- POST   /api/v1/services/{service_name}/stop    - Stop service (admin only)
- POST   /api/v1/services/{service_name}/restart - Restart service (admin only)
- GET    /api/v1/services/{service_name}/status  - Get service status (admin only)
- GET    /api/v1/services                        - Get all services status (admin only)

Usage:
    # Run full lifecycle demo (admin user)
    python examples/example_service_control.py --username admin --password admin

    # Start specific service
    python examples/example_service_control.py --action start --service ticker

    # Check status
    python examples/example_service_control.py --action status

    # Test non-admin access (should fail with 403)
    python examples/example_service_control.py --username user --password user --action start
"""
import argparse
import asyncio
from typing import Optional

import httpx
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.service_control")

API_BASE_URL = "http://localhost:8000"


async def login_and_get_token(username: str = "admin", password: str = "admin") -> Optional[str]:
    """
    Login and get JWT token for authenticated requests.

    IMPORTANT: For service control, user's email MUST match ADMIN_MAIL from .env
    (default: admin@fullon)

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
            logger.info("Login successful for service control", username=username)
            return token_data["access_token"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Login failed - invalid credentials")
                print("❌ Login failed: Invalid credentials")
            else:
                logger.error("Login failed", status_code=e.response.status_code)
                print(f"❌ Login failed: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error("Login error", error=str(e))
            print(f"❌ Connection error: {e}")
            return None


class ServiceControlClient:
    """Client for admin-only service control endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with JWT authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def start_service(self, service_name: str) -> Optional[dict]:
        """
        Start a service (admin only).

        Args:
            service_name: Service to start ('ticker', 'ohlcv', 'account')

        Returns:
            dict with status or None if failed
        """
        url = f"{self.base_url}/api/v1/services/{service_name}/start"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error("Access denied - admin required", service=service_name)
                    print(f"   ❌ 403 Forbidden: Admin access required")
                    print(f"      User email must match ADMIN_MAIL from .env")
                elif e.response.status_code == 400:
                    error = e.response.json()
                    logger.error("Start failed", service=service_name, error=error)
                    print(f"   ❌ {error.get('detail', 'Service already running or invalid')}")
                else:
                    logger.error("Start failed", status=e.response.status_code)
                    print(f"   ❌ HTTP {e.response.status_code}")
                return None

    async def stop_service(self, service_name: str) -> Optional[dict]:
        """
        Stop a service (admin only).

        Args:
            service_name: Service to stop ('ticker', 'ohlcv', 'account')

        Returns:
            dict with status or None if failed
        """
        url = f"{self.base_url}/api/v1/services/{service_name}/stop"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error("Access denied - admin required", service=service_name)
                    print(f"   ❌ 403 Forbidden: Admin access required")
                elif e.response.status_code == 400:
                    error = e.response.json()
                    logger.error("Stop failed", service=service_name, error=error)
                    print(f"   ❌ {error.get('detail', 'Service not running or invalid')}")
                else:
                    logger.error("Stop failed", status=e.response.status_code)
                    print(f"   ❌ HTTP {e.response.status_code}")
                return None

    async def restart_service(self, service_name: str) -> Optional[dict]:
        """
        Restart a service (admin only).

        Args:
            service_name: Service to restart ('ticker', 'ohlcv', 'account')

        Returns:
            dict with status or None if failed
        """
        url = f"{self.base_url}/api/v1/services/{service_name}/restart"

        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for restart
            try:
                response = await client.post(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error("Access denied - admin required", service=service_name)
                    print(f"   ❌ 403 Forbidden: Admin access required")
                else:
                    logger.error("Restart failed", status=e.response.status_code)
                    print(f"   ❌ HTTP {e.response.status_code}")
                return None

    async def get_service_status(self, service_name: str) -> Optional[dict]:
        """
        Get status of a specific service (admin only).

        Args:
            service_name: Service to check ('ticker', 'ohlcv', 'account')

        Returns:
            dict with service status or None if failed
        """
        url = f"{self.base_url}/api/v1/services/{service_name}/status"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error("Access denied - admin required")
                    print(f"   ❌ 403 Forbidden: Admin access required")
                else:
                    logger.error("Status check failed", status=e.response.status_code)
                    print(f"   ❌ HTTP {e.response.status_code}")
                return None

    async def get_all_services_status(self) -> Optional[dict]:
        """
        Get status of all services (admin only).

        Returns:
            dict with all services status or None if failed
        """
        url = f"{self.base_url}/api/v1/services"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    logger.error("Access denied - admin required")
                    print(f"   ❌ 403 Forbidden: Admin access required")
                else:
                    logger.error("Status check failed", status=e.response.status_code)
                    print(f"   ❌ HTTP {e.response.status_code}")
                return None


async def example_check_all_status(token: str):
    """Demonstrate checking status of all services."""
    print("\n" + "=" * 60)
    print("Example 1: Check All Services Status")
    print("=" * 60)

    client = ServiceControlClient(token=token)

    print("\n1️⃣  Checking all services status...")
    status = await client.get_all_services_status()

    if status:
        print("   ✅ Services status retrieved:")
        for service_name, service_info in status.get("services", {}).items():
            status_icon = "🟢" if service_info.get("status") == "running" else "🔴"
            print(f"      {status_icon} {service_name}: {service_info.get('status')}")
    else:
        print("   ❌ Endpoint not yet implemented or access denied")


async def example_start_service(token: str, service_name: str = "ticker"):
    """Demonstrate starting a service."""
    print("\n" + "=" * 60)
    print(f"Example 2: Start {service_name.capitalize()} Service")
    print("=" * 60)

    client = ServiceControlClient(token=token)

    print(f"\n1️⃣  Starting {service_name} service...")
    result = await client.start_service(service_name)

    if result:
        print(f"   ✅ {service_name} service started")
        print(f"      Status: {result.get('status')}")
    else:
        print(f"   ⚠️  Service may already be running or access denied")


async def example_check_service_status(token: str, service_name: str = "ticker"):
    """Demonstrate checking single service status."""
    print("\n" + "=" * 60)
    print(f"Example 3: Check {service_name.capitalize()} Service Status")
    print("=" * 60)

    client = ServiceControlClient(token=token)

    print(f"\n1️⃣  Checking {service_name} service status...")
    status = await client.get_service_status(service_name)

    if status:
        status_icon = "🟢" if status.get("status") == "running" else "🔴"
        print(f"   {status_icon} Service: {status.get('service')}")
        print(f"      Status: {status.get('status')}")
        print(f"      Is Running: {status.get('is_running')}")
    else:
        print("   ❌ Status check failed or access denied")


async def example_stop_service(token: str, service_name: str = "ticker"):
    """Demonstrate stopping a service."""
    print("\n" + "=" * 60)
    print(f"Example 4: Stop {service_name.capitalize()} Service")
    print("=" * 60)

    client = ServiceControlClient(token=token)

    print(f"\n1️⃣  Stopping {service_name} service...")
    result = await client.stop_service(service_name)

    if result:
        print(f"   ✅ {service_name} service stopped")
        print(f"      Status: {result.get('status')}")
    else:
        print(f"   ⚠️  Service may not be running or access denied")


async def example_restart_service(token: str, service_name: str = "ticker"):
    """Demonstrate restarting a service."""
    print("\n" + "=" * 60)
    print(f"Example 5: Restart {service_name.capitalize()} Service")
    print("=" * 60)

    client = ServiceControlClient(token=token)

    print(f"\n1️⃣  Restarting {service_name} service...")
    print("      (This may take a few seconds...)")
    result = await client.restart_service(service_name)

    if result:
        print(f"   ✅ {service_name} service restarted")
        print(f"      Status: {result.get('status')}")
    else:
        print(f"   ❌ Restart failed or access denied")


async def example_non_admin_access(username: str = "user", password: str = "user"):
    """Demonstrate that non-admin users cannot control services."""
    print("\n" + "=" * 60)
    print("Example 6: Non-Admin Access (Should Fail)")
    print("=" * 60)

    print(f"\n1️⃣  Logging in as non-admin user ('{username}')...")
    token = await login_and_get_token(username, password)

    if not token:
        print("   ⚠️  Non-admin user not configured for this test")
        print("   Skipping non-admin access test")
        return

    client = ServiceControlClient(token=token)

    print("\n2️⃣  Attempting to start ticker service (should fail)...")
    result = await client.start_service("ticker")

    if result:
        print("   ⚠️  UNEXPECTED: Non-admin user was able to start service!")
        print("      This indicates an access control issue")
    else:
        print("   ✅ Access correctly denied (expected behavior)")
        print("      Only users matching ADMIN_MAIL can control services")


async def run_full_lifecycle_demo(token: str, service_name: str = "ticker"):
    """
    Run complete service lifecycle demonstration.

    Flow:
    1. Check initial status
    2. Start service
    3. Verify running
    4. Stop service
    5. Verify stopped
    """
    print("\n" + "=" * 60)
    print(f"FULL LIFECYCLE DEMO: {service_name.capitalize()} Service")
    print("=" * 60)

    client = ServiceControlClient(token=token)

    # Step 1: Initial status
    print(f"\n📊 Step 1: Check initial status...")
    status = await client.get_service_status(service_name)
    if status:
        print(f"   Initial status: {status.get('status')}")
    else:
        print("   ❌ Cannot check status - aborting demo")
        return

    # Step 2: Start service (if stopped)
    if status.get("status") == "stopped":
        print(f"\n▶️  Step 2: Starting {service_name} service...")
        result = await client.start_service(service_name)
        if result:
            print(f"   ✅ Service started")
            await asyncio.sleep(2)  # Give service time to initialize
        else:
            print("   ❌ Start failed - aborting demo")
            return
    else:
        print(f"\n▶️  Step 2: Service already running, skipping start")

    # Step 3: Verify running
    print(f"\n✔️  Step 3: Verify service is running...")
    status = await client.get_service_status(service_name)
    if status and status.get("status") == "running":
        print(f"   ✅ Service confirmed running")
    else:
        print(f"   ⚠️  Service may not be running properly")

    # Step 4: Stop service
    print(f"\n⏹️  Step 4: Stopping {service_name} service...")
    result = await client.stop_service(service_name)
    if result:
        print(f"   ✅ Service stopped")
        await asyncio.sleep(1)
    else:
        print("   ❌ Stop failed")

    # Step 5: Verify stopped
    print(f"\n✔️  Step 5: Verify service is stopped...")
    status = await client.get_service_status(service_name)
    if status and status.get("status") == "stopped":
        print(f"   ✅ Service confirmed stopped")
    else:
        print(f"   ⚠️  Service may still be running")

    print("\n" + "=" * 60)
    print(f"✅ Lifecycle demo complete for {service_name}")
    print("=" * 60)


async def main(args):
    """Run service control examples based on arguments."""
    print("=" * 60)
    print("Fullon Master API - Service Control Example")
    print("=" * 60)
    print(f"\n⚠️  ADMIN ONLY: User email must match ADMIN_MAIL from .env")
    print(f"   (Default: admin@fullon)")

    # Step 1: Admin login
    print(f"\n🔐 Authenticating as '{args.username}'...")
    token = await login_and_get_token(args.username, args.password)

    if not token:
        print("❌ Authentication failed - cannot run service control examples")
        print("   Make sure:")
        print("   1. Server is running (make run)")
        print("   2. User exists in database")
        print("   3. User email matches ADMIN_MAIL from .env")
        return

    print("✅ Authentication successful")

    # Run examples based on action
    if args.action == "lifecycle":
        # Full lifecycle demo
        await run_full_lifecycle_demo(token, args.service)

    elif args.action == "start":
        # Start service
        await example_start_service(token, args.service)

    elif args.action == "stop":
        # Stop service
        await example_stop_service(token, args.service)

    elif args.action == "restart":
        # Restart service
        await example_restart_service(token, args.service)

    elif args.action == "status":
        # Check status
        if args.service == "all":
            await example_check_all_status(token)
        else:
            await example_check_service_status(token, args.service)

    elif args.action == "demo":
        # Run all examples
        await example_check_all_status(token)
        await example_start_service(token, "ticker")
        await example_check_service_status(token, "ticker")
        await example_stop_service(token, "ticker")
        await example_restart_service(token, "ticker")

        # Test non-admin access (if different user configured)
        if args.username != "user":
            await example_non_admin_access()

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - Service control requires admin authentication")
    print("   - Admin check: user.mail == ADMIN_MAIL from .env")
    print("   - Services run as async background tasks in master API")
    print("   - Non-admin users receive 403 Forbidden")
    print("   - Services: ticker, ohlcv, account")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Service Control Example")
    parser.add_argument(
        "--username",
        type=str,
        default="admin",
        help="Admin username for login (user email must match ADMIN_MAIL)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default="admin",
        help="Admin password for login",
    )
    parser.add_argument(
        "--action",
        type=str,
        default="demo",
        choices=["start", "stop", "restart", "status", "lifecycle", "demo"],
        help="Action to perform",
    )
    parser.add_argument(
        "--service",
        type=str,
        default="ticker",
        choices=["ticker", "ohlcv", "account", "all"],
        help="Service to control (or 'all' for status check)",
    )

    args = parser.parse_args()

    asyncio.run(main(args))
