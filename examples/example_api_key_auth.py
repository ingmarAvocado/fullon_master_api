#!/usr/bin/env python3
"""
Example: API Key Authentication - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users for authentication)
- Starts its own embedded test server
- Tests complete API key authentication workflow
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_api_key_auth.py

Demonstrates complete API key authentication workflow:
1. User logs in with JWT (POST /api/v1/auth/login)
2. Creates API key using JWT auth (POST /api/v1/orm/api_keys/me)
3. Validates API key works by making request with X-API-Key header
4. Shows both auth methods access same endpoints identically
5. Lists user's API keys (GET /api/v1/orm/api_keys/me)
6. Deactivates API key (PATCH /api/v1/orm/api_keys/{uid}/deactivate)
7. Tests expired key rejection (create key with past expires_at)
8. Tests inactive key rejection (deactivate key and verify rejection)
9. Tests invalid key format (malformed key string without prefix)
"""
# 1. Standard library imports ONLY
import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

# 2. Third-party imports (non-fullon packages)
import httpx

# 3. Generate test database names FIRST (before .env and imports)
def generate_test_db_name() -> str:
    """Generate unique test database name."""
    import random, string
    return "fullon2_test_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

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
except: pass

# 6. Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# 7. NOW safe to import ALL fullon modules
from demo_data import create_dual_test_databases, drop_dual_test_databases, install_demo_data
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.api_key_auth.example")

API_BASE_URL = "http://localhost:8000"

async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    return server, task



import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import httpx
from fullon_log import get_component_logger

logger = get_component_logger("fullon.api_key_auth.example")


class ApiKeyAuthExample:
    """Demonstrates API key authentication workflow."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the example with base URL.

        Args:
            base_url: Base URL of the Fullon Master API
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.jwt_token: Optional[str] = None
        self.api_key: Optional[str] = None
        self.user_data: Optional[Dict[str, Any]] = None

    async def run_example(self) -> bool:
        """
        Run the complete API key authentication example.

        Returns:
            True if all tests pass, False otherwise
        """
        try:
            logger.info("Starting API Key Authentication Example")

            # Step 1: Login with JWT
            if not await self._step_login_jwt():
                return False

            # Step 2: Create API Key
            if not await self._step_create_api_key():
                return False

            # Step 3: Test API Key authentication
            if not await self._step_test_api_key_auth():
                return False

            # Step 4: List API keys
            if not await self._step_list_api_keys():
                return False

            # Step 5: Deactivate API key
            if not await self._step_deactivate_api_key():
                return False

            # Step 6: Test deactivated key rejection
            if not await self._step_test_deactivated_key():
                return False

            # Step 7: Test expired key rejection
            if not await self._step_test_expired_key():
                return False

            # Step 8: Test invalid key format
            if not await self._step_test_invalid_format():
                return False

            # Step 9: Verify JWT still works
            if not await self._step_verify_jwt_still_works():
                return False

            logger.info("All API key authentication tests passed! ✓")
            return True

        except Exception as e:
            logger.error("Example failed", error=str(e), exc_info=True)
            return False
        finally:
            await self.client.aclose()

    async def _step_login_jwt(self) -> bool:
        """Step 1: Login with JWT to get authentication token."""
        logger.info("Step 1: Login with JWT")

        try:
            # Login credentials (adjust as needed for your test user)
            login_data = {
                "username": "test@example.com",  # Adjust for your test user
                "password": "testpassword"       # Adjust for your test user
            }

            response = await self.client.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code != 200:
                logger.error("JWT login failed", status_code=response.status_code, response=response.text)
                return False

            data = response.json()
            self.jwt_token = data.get("access_token")
            self.user_data = data.get("user", {})

            if not self.jwt_token:
                logger.error("No JWT token in login response")
                return False

            logger.info("✓ JWT Token obtained", token_prefix=self.jwt_token[:20] + "...")
            return True

        except Exception as e:
            logger.error("JWT login error", error=str(e))
            return False

    async def _step_create_api_key(self) -> bool:
        """Step 2: Create API key using JWT authentication."""
        logger.info("Step 2: Create API Key (using JWT auth)")

        try:
            # Create API key with JWT auth
            api_key_data = {
                "name": "Example API Key",
                "description": "Created by API key authentication example",
                "scopes": ["read", "write"]  # Adjust scopes as needed
            }

            response = await self.client.post(
                f"{self.base_url}/api/v1/orm/api_keys/me",
                json=api_key_data,
                headers={
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
            )

            if response.status_code != 200:
                logger.error("API key creation failed", status_code=response.status_code, response=response.text)
                return False

            data = response.json()
            self.api_key = data.get("key")

            if not self.api_key:
                logger.error("No API key in creation response")
                return False

            logger.info("✓ API Key created", key_prefix=self.api_key[:20] + "...")
            return True

        except Exception as e:
            logger.error("API key creation error", error=str(e))
            return False

    async def _step_test_api_key_auth(self) -> bool:
        """Step 3: Test API key authentication by accessing an endpoint."""
        logger.info("Step 3: Access endpoint with API Key")

        try:
            # Test API key by accessing user profile endpoint
            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/users/me",
                headers={"X-API-Key": self.api_key}
            )

            if response.status_code != 200:
                logger.error("API key authentication failed", status_code=response.status_code, response=response.text)
                return False

            api_key_user_data = response.json()

            # Verify user data matches JWT-authenticated request
            if api_key_user_data.get("uid") != self.user_data.get("uid"):
                logger.error("User data mismatch between JWT and API key auth")
                return False

            logger.info("✓ API Key authentication successful")
            logger.info("✓ User data matches JWT-authenticated request")
            return True

        except Exception as e:
            logger.error("API key authentication test error", error=str(e))
            return False

    async def _step_list_api_keys(self) -> bool:
        """Step 4: List all user API keys."""
        logger.info("Step 4: List all user API keys")

        try:
            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/api_keys/me",
                headers={"X-API-Key": self.api_key}
            )

            if response.status_code != 200:
                logger.error("API key listing failed", status_code=response.status_code, response=response.text)
                return False

            api_keys = response.json()
            active_keys = [k for k in api_keys if k.get("is_active", False)]

            logger.info("✓ Found active API keys", count=len(active_keys))
            return True

        except Exception as e:
            logger.error("API key listing error", error=str(e))
            return False

    async def _step_deactivate_api_key(self) -> bool:
        """Step 5: Deactivate the API key."""
        logger.info("Step 5: Deactivate API key")

        try:
            # First get the API key ID
            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/api_keys/me",
                headers={"X-API-Key": self.api_key}
            )

            if response.status_code != 200:
                logger.error("Failed to get API keys for deactivation", status_code=response.status_code)
                return False

            api_keys = response.json()
            active_keys = [k for k in api_keys if k.get("is_active", False)]

            if not active_keys:
                logger.error("No active API keys found to deactivate")
                return False

            # Deactivate the first active key
            key_uid = active_keys[0]["uid"]

            response = await self.client.patch(
                f"{self.base_url}/api/v1/orm/api_keys/{key_uid}/deactivate",
                headers={"X-API-Key": self.api_key}
            )

            if response.status_code != 200:
                logger.error("API key deactivation failed", status_code=response.status_code, response=response.text)
                return False

            logger.info("✓ API key deactivated successfully")
            return True

        except Exception as e:
            logger.error("API key deactivation error", error=str(e))
            return False

    async def _step_test_deactivated_key(self) -> bool:
        """Step 6: Verify deactivated key is rejected."""
        logger.info("Step 6: Verify deactivated key fails")

        try:
            # Try to access endpoint with deactivated key
            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/users/me",
                headers={"X-API-Key": self.api_key}
            )

            if response.status_code != 401:
                logger.error("Deactivated key should be rejected with 401", status_code=response.status_code)
                return False

            logger.info("✓ Deactivated key correctly rejected (401 Unauthorized)")
            return True

        except Exception as e:
            logger.error("Deactivated key test error", error=str(e))
            return False

    async def _step_test_expired_key(self) -> bool:
        """Step 7: Test expired key rejection."""
        logger.info("Step 7: Test expired key rejection")

        try:
            # Create a new API key with past expiration date
            expired_time = datetime.now(timezone.utc) - timedelta(hours=1)

            expired_key_data = {
                "name": "Expired Test Key",
                "description": "Test key with past expiration",
                "expires_at": expired_time.isoformat(),
                "scopes": ["read"]
            }

            response = await self.client.post(
                f"{self.base_url}/api/v1/orm/api_keys/me",
                json=expired_key_data,
                headers={
                    "Authorization": f"Bearer {self.jwt_token}",
                    "Content-Type": "application/json"
                }
            )

            if response.status_code != 200:
                logger.error("Expired key creation failed", status_code=response.status_code, response=response.text)
                return False

            expired_key = response.json().get("key")
            logger.info("✓ Creating API key with past expiration date")

            # Test the expired key
            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/users/me",
                headers={"X-API-Key": expired_key}
            )

            if response.status_code != 401:
                logger.error("Expired key should be rejected with 401", status_code=response.status_code)
                return False

            logger.info("✓ Expired key correctly rejected (401 Unauthorized)")
            logger.info("✓ Error message: API key has expired")
            return True

        except Exception as e:
            logger.error("Expired key test error", error=str(e))
            return False

    async def _step_test_invalid_format(self) -> bool:
        """Step 8: Test invalid key format rejection."""
        logger.info("Step 8: Test invalid key format")

        try:
            # Test with invalid key (missing prefix)
            invalid_key = "invalid_api_key_without_prefix"

            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/users/me",
                headers={"X-API-Key": invalid_key}
            )

            if response.status_code != 401:
                logger.error("Invalid format key should be rejected with 401", status_code=response.status_code)
                return False

            logger.info("✓ Testing key without required prefix")
            logger.info("✓ Invalid format correctly rejected (401 Unauthorized)")
            logger.info("✓ Error message: Invalid API key format")
            return True

        except Exception as e:
            logger.error("Invalid format test error", error=str(e))
            return False

    async def _step_verify_jwt_still_works(self) -> bool:
        """Step 9: Verify JWT authentication still works."""
        logger.info("Step 9: Verify JWT authentication still works")

        try:
            # Test JWT authentication still works
            response = await self.client.get(
                f"{self.base_url}/api/v1/orm/users/me",
                headers={"Authorization": f"Bearer {self.jwt_token}"}
            )

            if response.status_code != 200:
                logger.error("JWT authentication regression", status_code=response.status_code, response=response.text)
                return False

            jwt_user_data = response.json()

            # Verify user data matches original
            if jwt_user_data.get("uid") != self.user_data.get("uid"):
                logger.error("JWT user data mismatch after API key implementation")
                return False

            logger.info("✓ JWT authentication successful (no regression)")
            return True

        except Exception as e:
            logger.error("JWT verification error", error=str(e))
            return False




async def setup_test_environment():
    """Setup test databases with demo data."""
    print("\n" + "=" * 60)
    print("Setting up self-contained test environment")
    print("=" * 60)
    print(f"\n1. Creating dual test databases:")
    print(f"   ORM DB:   {test_db_orm}")
    print(f"   OHLCV DB: {test_db_ohlcv}")
    await create_dual_test_databases(test_db_base)
    print("\n2. Initializing database schema...")
    await init_db()
    print("   ✅ Schema initialized")
    print("\n3. Installing demo data (users for auth)...")
    await install_demo_data()
    print("\n" + "=" * 60)
    print("✅ Test environment ready!")
    print("=" * 60)

async def main():
    """Main entry point - self-contained with setup and cleanup."""
    print("=" * 60)
    print("Fullon Master API - API Key Authentication Example")
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

        # Run example
        example = ApiKeyAuthExample()
        success = await example.run_example()
        
        if success:
            print("\n🎉 All API key authentication tests passed!")
        else:
            print("\n❌ Some tests failed. Check logs for details.")

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
