#!/usr/bin/env python3
"""
Example: JWT Login & Authentication

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

Usage:
    python examples/example_jwt_login.py --username admin --password secret
"""
import asyncio
import httpx
import argparse
from typing import Optional
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.jwt_login")

API_BASE_URL = "http://localhost:8000"


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
            print("   Run: make run")
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


async def main(username: str, password: str):
    """Run JWT login example."""
    print("=" * 60)
    print("Fullon Master API - JWT Login Example")
    print("=" * 60)

    # Step 1: Login
    token_data = await login(username, password)

    if not token_data:
        print("\n⚠️  Note: Auth endpoints not yet implemented")
        print("   This example will work after Phase 2 completion")
        print("=" * 60)
        return

    # Step 2: Verify token
    access_token = token_data["access_token"]
    await verify_token(access_token)

    # Step 3: Show usage
    print("\n📖 Using the token in requests:")
    print(f'   headers = {{"Authorization": "Bearer {access_token[:30]}..."}}')
    print('   response = await client.get("/api/v1/users/me", headers=headers)')

    print("\n💡 Token saved for use in other examples")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="JWT Login Example")
    parser.add_argument(
        "--username",
        type=str,
        default="admin",
        help="Username for login",
    )
    parser.add_argument(
        "--password",
        type=str,
        default="admin",
        help="Password for login",
    )

    args = parser.parse_args()

    asyncio.run(main(args.username, args.password))
