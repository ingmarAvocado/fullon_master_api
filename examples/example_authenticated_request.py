#!/usr/bin/env python3
"""
Example: Making Authenticated Requests

Demonstrates:
- Getting JWT token via login
- Adding Authorization header to requests
- Making authenticated API calls
- Handling 401 Unauthorized errors
- Token refresh pattern

Expected Flow:
1. Login to get JWT token
2. Add token to Authorization header
3. Make authenticated requests to protected endpoints
4. Handle token expiration

Usage:
    python examples/example_authenticated_request.py
"""
import asyncio
import httpx
from typing import Optional
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.authenticated_request")

API_BASE_URL = "http://localhost:8000"


class APIClient:
    """Authenticated API client with automatic token management."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.token: Optional[str] = None
        self.token_type: str = "bearer"

    async def login(self, username: str, password: str) -> bool:
        """
        Login and store JWT token.

        Args:
            username: User's username
            password: User's password

        Returns:
            bool: True if login successful
        """
        login_url = f"{self.base_url}/api/v1/auth/login"
        login_data = {"username": username, "password": password}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    login_url,
                    data=login_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()

                token_data = response.json()
                self.token = token_data["access_token"]
                self.token_type = token_data.get("token_type", "bearer")

                logger.info("Login successful")
                return True

            except Exception as e:
                logger.error("Login failed", error=str(e))
                return False

    def _get_headers(self) -> dict:
        """Get headers with authorization token."""
        if not self.token:
            raise ValueError("Not authenticated - call login() first")

        return {"Authorization": f"{self.token_type.capitalize()} {self.token}"}

    async def get(self, endpoint: str) -> Optional[dict]:
        """
        Make authenticated GET request.

        Args:
            endpoint: API endpoint (e.g., "/api/v1/users/me")

        Returns:
            dict: Response data
            None: If request failed
        """
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    logger.error("Unauthorized - token may be expired")
                else:
                    logger.error("Request failed", status_code=e.response.status_code)
                return None

    async def post(self, endpoint: str, data: dict) -> Optional[dict]:
        """
        Make authenticated POST request.

        Args:
            endpoint: API endpoint
            data: Request payload

        Returns:
            dict: Response data
            None: If request failed
        """
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error("Request failed", status_code=e.response.status_code)
                return None


async def example_user_endpoints():
    """Demonstrate authenticated user endpoints."""
    print("\n" + "=" * 60)
    print("Example: User Endpoints (Authenticated)")
    print("=" * 60)

    client = APIClient()

    # Login
    print("\n1️⃣  Logging in...")
    success = await client.login("admin", "admin")

    if not success:
        print("   ❌ Login failed - endpoint not yet implemented")
        return

    print("   ✅ Logged in successfully")

    # Get current user info
    print("\n2️⃣  Getting current user info...")
    user_data = await client.get("/api/v1/users/me")

    if user_data:
        print("   ✅ User data retrieved:")
        print(f"      User ID: {user_data.get('user_id')}")
        print(f"      Username: {user_data.get('username')}")
        print(f"      Email: {user_data.get('email')}")
    else:
        print("   ❌ Endpoint not yet implemented")

    # List all users (admin only)
    print("\n3️⃣  Listing all users (admin)...")
    users = await client.get("/api/v1/users")

    if users:
        print(f"   ✅ Found {len(users)} users")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_bot_endpoints():
    """Demonstrate authenticated bot management endpoints."""
    print("\n" + "=" * 60)
    print("Example: Bot Management Endpoints (Authenticated)")
    print("=" * 60)

    client = APIClient()

    # Login
    print("\n1️⃣  Logging in...")
    success = await client.login("admin", "admin")

    if not success:
        print("   ❌ Login failed - endpoint not yet implemented")
        return

    print("   ✅ Logged in successfully")

    # List bots
    print("\n2️⃣  Listing user's bots...")
    bots = await client.get("/api/v1/bots")

    if bots:
        print(f"   ✅ Found {len(bots)} bots")
        for bot in bots[:3]:  # Show first 3
            print(f"      - {bot.get('name')} (ID: {bot.get('bot_id')})")
    else:
        print("   ❌ Endpoint not yet implemented")

    # Create new bot
    print("\n3️⃣  Creating new bot...")
    new_bot_data = {
        "name": "Example Trading Bot",
        "active": True,
        "dry_run": True,
    }

    bot = await client.post("/api/v1/bots", new_bot_data)

    if bot:
        print("   ✅ Bot created:")
        print(f"      Bot ID: {bot.get('bot_id')}")
        print(f"      Name: {bot.get('name')}")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_error_handling():
    """Demonstrate error handling patterns."""
    print("\n" + "=" * 60)
    print("Example: Error Handling")
    print("=" * 60)

    client = APIClient()

    # Attempt request without login
    print("\n1️⃣  Attempting request without authentication...")
    try:
        await client.get("/api/v1/users/me")
        print("   ❌ Should have raised error")
    except ValueError as e:
        print(f"   ✅ Correctly raised error: {e}")

    # Login with invalid credentials
    print("\n2️⃣  Attempting login with invalid credentials...")
    success = await client.login("invalid", "wrongpassword")

    if not success:
        print("   ✅ Login correctly rejected invalid credentials")
    else:
        print("   ❌ Should have rejected invalid credentials")


async def main():
    """Run all authenticated request examples."""
    print("=" * 60)
    print("Fullon Master API - Authenticated Requests Example")
    print("=" * 60)

    # Example 1: User endpoints
    await example_user_endpoints()

    # Example 2: Bot management
    await example_bot_endpoints()

    # Example 3: Error handling
    await example_error_handling()

    print("\n" + "=" * 60)
    print("💡 Key Takeaways:")
    print("   - Always login first to get JWT token")
    print("   - Add Authorization header to protected endpoints")
    print("   - Handle 401 errors (expired/invalid tokens)")
    print("   - Use APIClient class for clean token management")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
