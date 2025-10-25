#!/usr/bin/env python3
"""
Example: JWT Login & Authentication - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (users for authentication)
- Starts its own embedded test server
- Tests JWT login and authentication
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_jwt_login.py
    python examples/example_jwt_login.py --username admin --password password

Demonstrates:
- User login with username/password
- JWT token generation
- Token storage and reuse
- Token validation
- Refresh token flow (if implemented)

Expected Flow:
1. POST /api/v1/auth/login with credentials
2. Receive JWT access token
3. Use token in Authorization header for authenticated requests

Expected Response:
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600
}
"""
# 1. Standard library imports ONLY
import asyncio
import os
import sys
from pathlib import Path
import argparse
from typing import Optional

# 2. Third-party imports (non-fullon packages)
import httpx

# 3. Generate test database names FIRST (before .env and imports)
def generate_test_db_name() -> str:
    """Generate unique test database name (copied from demo_data.py to avoid imports)."""
    import random
    import string
    return "fullon2_test_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

test_db_base = generate_test_db_name()
test_db_orm = test_db_base
test_db_ohlcv = f"{test_db_base}_ohlcv"

# 4. Set ALL database environment variables BEFORE loading .env (so they won't be overridden)
os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv
# CRITICAL: Also override DB_TEST_NAME to prevent test mode from using wrong database
os.environ["DB_TEST_NAME"] = test_db_orm

# 5. NOW load .env file (won't override existing env vars)
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env", override=False)  # Don't override our test DB settings
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# 6. Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# 7. NOW safe to import ALL fullon modules (env vars set, .env loaded)
from demo_data import (
    create_dual_test_databases,
    drop_dual_test_databases,
    install_demo_data
)
from fullon_log import get_component_logger
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.examples.jwt_login")

API_BASE_URL = "http://localhost:8000"


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    return server, task


async def login(username: str, password: str) -> Optional[dict]:
    """
    Authenticate user and get JWT token.

    Args:
        username: User's username/email
        password: User's password

    Returns:
        dict: Token data with 'access_token', 'token_type', 'expires_in'
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

            print("\n✅ Login Successful!")
            print(f"   Access Token: {token_data['access_token'][:50]}...")
            print(f"   Token Type: {token_data['token_type']}")
            print(f"   Expires In: {token_data['expires_in']} seconds")

            return token_data

        except httpx.ConnectError:
            logger.error("Cannot connect to API")
            print("\n❌ Connection Failed")
            print(f"   Server not running on {API_BASE_URL}")
            return None

        except httpx.HTTPStatusError as e:
            logger.error("Login failed", status_code=e.response.status_code)

            if e.response.status_code == 401:
                print("\n❌ Login Failed: Invalid credentials")
            elif e.response.status_code == 404:
                print("\n❌ Login endpoint not found (not implemented yet)")
                print("   Expected endpoint: POST /api/v1/auth/login")
            else:
                print(f"\n❌ Login failed with status {e.response.status_code}")

            try:
                error_detail = e.response.json()
                print(f"   Details: {error_detail}")
            except:
                pass

            return None


async def verify_token(token: str) -> bool:
    """
    Verify JWT token validity.

    Args:
        token: JWT access token

    Returns:
        bool: True if token is valid
    """
    verify_url = f"{API_BASE_URL}/api/v1/auth/verify"

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(verify_url, headers=headers)
            response.raise_for_status()

            user_data = response.json()
            logger.info("Token verified", user_id=user_data.get("user_id"))

            print("\n✅ Token Verified!")
            print(f"   User ID: {user_data.get('user_id')}")
            print(f"   Username: {user_data.get('username')}")
            print(f"   Email: {user_data.get('email')}")

            return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Token invalid or expired")
                print("\n❌ Token Invalid/Expired")
            else:
                logger.error("Token verification failed", status_code=e.response.status_code)
                print(f"\n❌ Verification failed: {e.response.status_code}")

            return False


async def setup_test_environment():
    """
    Setup test databases with demo data.

    Steps:
    1. Create dual test databases (ORM + OHLCV)
    2. Install ORM metadata (exchanges, symbols, users)
    3. No OHLCV data needed for auth examples
    """
    print("\n" + "=" * 60)
    print("Setting up self-contained test environment")
    print("=" * 60)

    logger.info("Creating test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)

    # Step 1: Create dual test databases
    print(f"\n1. Creating dual test databases:")
    print(f"   ORM DB:   {test_db_orm}")
    print(f"   OHLCV DB: {test_db_ohlcv}")

    orm_db_name, ohlcv_db_name = await create_dual_test_databases(test_db_base)
    logger.info("Test databases created", orm_db=orm_db_name, ohlcv_db=ohlcv_db_name)

    # Step 2: Initialize database schema
    print("\n2. Initializing database schema...")
    await init_db()
    print("   ✅ Schema initialized")

    # Step 3: Install demo data (includes users for auth)
    print("\n3. Installing demo data (users for auth)...")
    success = await install_demo_data()
    if not success:
        raise Exception("Failed to install demo data")

    print("\n" + "=" * 60)
    print("✅ Test environment ready!")
    print("=" * 60)


async def run_examples(username: str, password: str):
    """Run JWT login examples."""
    print("\n" + "=" * 60)
    print("Running JWT Login Examples")
    print("=" * 60)

    # Step 1: Login
    token_data = await login(username, password)

    if not token_data:
        print("\n⚠️  Note: Login failed - check credentials")
        print(f"   Demo credentials: username=admin@fullon, password=password")
        return

    # Step 2: Verify token
    access_token = token_data["access_token"]
    await verify_token(access_token)

    # Step 3: Show usage
    print("\n📖 Using the token in requests:")
    print(f'   headers = {{"Authorization": "Bearer {access_token[:30]}..."}}')
    print('   response = await client.get("/api/v1/users/me", headers=headers)')

    print("\n💡 Token saved for use in other examples")


async def main(username: str, password: str):
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - JWT Login Example")
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
        await asyncio.sleep(2)  # Wait for server to start
        print("   ✅ Server started")

        # Run examples
        await run_examples(username, password)

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
    parser = argparse.ArgumentParser(description="JWT Login Example")
    parser.add_argument(
        "--username",
        type=str,
        default="admin@fullon",
        help="Username for login",
    )
    parser.add_argument(
        "--password",
        type=str,
        default="password",
        help="Password for login",
    )

    args = parser.parse_args()

    asyncio.run(main(args.username, args.password))
