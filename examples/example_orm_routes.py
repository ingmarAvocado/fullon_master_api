#!/usr/bin/env python3
"""
Example: ORM API Routes (Composed from fullon_orm_api)

Demonstrates:
- User management endpoints
- Bot management endpoints
- Exchange management endpoints
- Order and trade operations
- Using ORM model instances (NOT dictionaries!)

Expected Endpoints (from fullon_orm_api):
- GET    /api/v1/users              - List users
- GET    /api/v1/users/me           - Current user info
- POST   /api/v1/users              - Create user
- GET    /api/v1/bots               - List bots
- POST   /api/v1/bots               - Create bot
- GET    /api/v1/exchanges          - List exchanges
- POST   /api/v1/orders             - Create order

Usage:
    python examples/example_orm_routes.py
"""
import asyncio
import httpx
from typing import Optional
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.orm_routes")

API_BASE_URL = "http://localhost:8000"


class ORMAPIClient:
    """Client for ORM API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_current_user(self) -> Optional[dict]:
        """Get current authenticated user info."""
        url = f"{self.base_url}/api/v1/users/me"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get current user failed", status=e.response.status_code)
                return None

    async def list_users(self) -> Optional[list]:
        """List all users (admin only)."""
        url = f"{self.base_url}/api/v1/users"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List users failed", status=e.response.status_code)
                return None

    async def create_user(self, user_data: dict) -> Optional[dict]:
        """
        Create new user.

        Args:
            user_data: User object data (will be converted to ORM model)
                {
                    "mail": "user@example.com",
                    "name": "John",
                    "password": "hashed_password",
                    "lastname": "Doe",
                    "f2a": "",
                    "phone": "",
                    "id_num": ""
                }
        """
        url = f"{self.base_url}/api/v1/users"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=user_data, headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Create user failed", status=e.response.status_code)
                return None

    async def list_bots(self) -> Optional[list]:
        """List all bots for current user."""
        url = f"{self.base_url}/api/v1/bots"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("List bots failed", status=e.response.status_code)
                return None

    async def create_bot(self, bot_data: dict) -> Optional[dict]:
        """
        Create new bot.

        Args:
            bot_data: Bot object data
                {
                    "name": "My Trading Bot",
                    "active": true,
                    "dry_run": true
                }
        """
        url = f"{self.base_url}/api/v1/bots"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=bot_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Create bot failed", status=e.response.status_code)
                return None

    async def create_order(self, order_data: dict) -> Optional[dict]:
        """
        Create new order.

        Args:
            order_data: Order object data (MUST use 'volume' not 'amount'!)
                {
                    "bot_id": 1,
                    "ex_id": 1,
                    "symbol": "BTC/USD",
                    "side": "buy",
                    "volume": 1.0,
                    "order_type": "market",
                    "status": "New"
                }
        """
        url = f"{self.base_url}/api/v1/orders"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=order_data, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Create order failed", status=e.response.status_code)
                return None


async def example_user_management():
    """Demonstrate user management endpoints."""
    print("\n" + "=" * 60)
    print("Example: User Management (ORM API)")
    print("=" * 60)

    # This would normally have a JWT token from login
    client = ORMAPIClient()

    print("\n1️⃣  Getting current user info...")
    user = await client.get_current_user()

    if user:
        print("   ✅ Current user:")
        print(f"      User ID: {user.get('uid')}")
        print(f"      Email: {user.get('mail')}")
        print(f"      Name: {user.get('name')}")
    else:
        print("   ❌ Endpoint not yet implemented")

    print("\n2️⃣  Listing all users (admin only)...")
    users = await client.list_users()

    if users:
        print(f"   ✅ Found {len(users)} users")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_bot_management():
    """Demonstrate bot management endpoints."""
    print("\n" + "=" * 60)
    print("Example: Bot Management (ORM API)")
    print("=" * 60)

    client = ORMAPIClient()

    print("\n1️⃣  Listing user's bots...")
    bots = await client.list_bots()

    if bots:
        print(f"   ✅ Found {len(bots)} bots")
        for bot in bots[:3]:
            print(f"      - {bot.get('name')} (ID: {bot.get('bot_id')})")
    else:
        print("   ❌ Endpoint not yet implemented")

    print("\n2️⃣  Creating new bot...")
    new_bot = {
        "name": "Example Trading Bot",
        "active": True,
        "dry_run": True,
    }

    bot = await client.create_bot(new_bot)

    if bot:
        print("   ✅ Bot created:")
        print(f"      Bot ID: {bot.get('bot_id')}")
        print(f"      Name: {bot.get('name')}")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_order_creation():
    """Demonstrate order creation (CRITICAL: use 'volume' not 'amount')."""
    print("\n" + "=" * 60)
    print("Example: Order Creation (ORM API)")
    print("=" * 60)

    client = ORMAPIClient()

    print("\n1️⃣  Creating market order...")
    print("   ⚠️  IMPORTANT: ORM uses 'volume' field, NOT 'amount'!")

    # ✅ CORRECT - uses 'volume'
    order_data = {
        "bot_id": 1,
        "ex_id": 1,
        "symbol": "BTC/USD",
        "side": "buy",
        "volume": 1.0,  # ✅ CORRECT field name
        "order_type": "market",
        "status": "New",
    }

    order = await client.create_order(order_data)

    if order:
        print("   ✅ Order created:")
        print(f"      Order ID: {order.get('order_id')}")
        print(f"      Symbol: {order.get('symbol')}")
        print(f"      Volume: {order.get('volume')}")
    else:
        print("   ❌ Endpoint not yet implemented")


async def main():
    """Run all ORM API examples."""
    print("=" * 60)
    print("Fullon Master API - ORM Routes Example")
    print("=" * 60)

    # Example 1: User management
    await example_user_management()

    # Example 2: Bot management
    await example_bot_management()

    # Example 3: Order creation
    await example_order_creation()

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - ORM endpoints use model instances (converted from JSON)")
    print("   - ALWAYS use 'volume' field for orders (NOT 'amount')")
    print("   - All write operations require authentication")
    print("   - These routes are COMPOSED from fullon_orm_api")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
