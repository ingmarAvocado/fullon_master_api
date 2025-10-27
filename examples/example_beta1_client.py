#!/usr/bin/env python3
"""
Example Beta1 Client: OHLCV Data Query Client

Queries OHLCV data from the running Fullon Master API server.

Assumes example_beta1_server.py is already running on http://localhost:8000

Features:
- Authenticates with admin credentials
- Queries OHLCV candles for specified symbol and timeframe
- Displays candles in a formatted table
- Supports multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d, etc.)

Usage:
    # Get daily candles (default)
    python examples/example_beta1_client.py

    # Get 1-hour candles
    python examples/example_beta1_client.py --timeframe 1h

    # Get 5-minute candles, limit to 20
    python examples/example_beta1_client.py --timeframe 5m --limit 20

    # Query different symbol
    python examples/example_beta1_client.py --symbol ETH/USDC:USDC --timeframe 1d

Prerequisites:
    1. Start the server first: python examples/example_beta1_server.py
    2. Wait for "SERVER RUNNING" message
    3. Run this client
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# Third-party imports
import httpx

API_BASE_URL = "http://localhost:8000"


async def check_server_running(url: str = API_BASE_URL, timeout: float = 2.0) -> bool:
    """
    Check if server is running and healthy.

    Args:
        url: Base URL of the server
        timeout: Timeout for health check

    Returns:
        True if server is running, False otherwise
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{url}/health", timeout=timeout)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
            return False


async def login(username: str, password: str, base_url: str = API_BASE_URL) -> str | None:
    """
    Authenticate user and get JWT token.

    Args:
        username: User's username/email
        password: User's password
        base_url: API base URL

    Returns:
        str: JWT access token
        None: If login failed
    """
    login_url = f"{base_url}/api/v1/auth/login"

    # Login payload (form-data for OAuth2 compatibility)
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
            return token_data["access_token"]

        except Exception as e:
            print(f"❌ Login failed: {e}")
            return None


async def get_ohlcv_candles(
    token: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    limit: int = 100,
    base_url: str = API_BASE_URL,
) -> list:
    """
    Get OHLCV candles from the API.

    Args:
        token: JWT access token
        exchange: Exchange name (e.g., "hyperliquid")
        symbol: Trading pair symbol (e.g., "BTC/USDC:USDC")
        timeframe: Timeframe (e.g., "1m", "1h", "1d")
        limit: Maximum number of candles to retrieve
        base_url: API base URL

    Returns:
        list: List of OHLCV candles
    """
    # URL encode the symbol
    encoded_symbol = quote(symbol, safe="")
    url = f"{base_url}/api/v1/ohlcv/{exchange}/{encoded_symbol}/{timeframe}"

    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": limit}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            # API returns {"success": true, "candles": [...], "count": N}
            if isinstance(data, dict) and "candles" in data:
                return data["candles"]
            elif isinstance(data, list):
                # Fallback if API changes to return list directly
                return data
            else:
                print(f"⚠️  Unexpected response format: {type(data)}")
                return []

        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP error: {e.response.status_code} - {e.response.text}")
            return []
        except Exception as e:
            print(f"❌ Error fetching candles: {e}")
            return []


def format_timestamp(ts) -> str:
    """Format timestamp for display."""
    if isinstance(ts, str):
        # Parse ISO format timestamp
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def display_candles(candles: list, symbol: str, timeframe: str):
    """Display candles in a formatted table."""
    if not candles:
        print("📊 No candles found")
        return

    print(f"\n📊 OHLCV Candles: {symbol} ({timeframe})")
    print("=" * 100)
    print(f"{'Timestamp':<20} {'Open':<12} {'High':<12} {'Low':<12} {'Close':<12} {'Volume':<12}")
    print("-" * 100)

    for candle in candles:
        # Handle both dict and array formats
        if isinstance(candle, dict):
            timestamp = format_timestamp(candle["timestamp"])
            open_price = f"{float(candle['open']):,.2f}"
            high_price = f"{float(candle['high']):,.2f}"
            low_price = f"{float(candle['low']):,.2f}"
            close_price = f"{float(candle['close']):,.2f}"
            volume = f"{float(candle['vol']):,.2f}"
        else:
            # Array format [timestamp, open, high, low, close, volume]
            timestamp = format_timestamp(candle[0])
            open_price = f"{float(candle[1]):,.2f}"
            high_price = f"{float(candle[2]):,.2f}"
            low_price = f"{float(candle[3]):,.2f}"
            close_price = f"{float(candle[4]):,.2f}"
            volume = f"{float(candle[5]):,.2f}"

        print(f"{timestamp:<20} {open_price:<12} {high_price:<12} {low_price:<12} {close_price:<12} {volume:<12}")

    print("=" * 100)
    print(f"✅ Total candles: {len(candles)}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Query OHLCV data from Fullon Master API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get daily candles (default)
  %(prog)s

  # Get 1-hour candles
  %(prog)s --timeframe 1h

  # Get 5-minute candles, limit to 20
  %(prog)s --timeframe 5m --limit 20

  # Query different symbol
  %(prog)s --symbol ETH/USDC:USDC --timeframe 1d
        """,
    )

    parser.add_argument(
        "--exchange",
        default="hyperliquid",
        help="Exchange name (default: hyperliquid)",
    )
    parser.add_argument(
        "--symbol",
        default="BTC/USDC:USDC",
        help="Trading pair symbol (default: BTC/USDC:USDC)",
    )
    parser.add_argument(
        "--timeframe",
        default="1d",
        help="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d, etc. (default: 1d)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of candles to retrieve (default: 100)",
    )
    parser.add_argument(
        "--username",
        default="admin@fullon",
        help="Username for authentication (default: admin@fullon)",
    )
    parser.add_argument(
        "--password",
        default="password",
        help="Password for authentication (default: password)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Fullon Master API - OHLCV Data Query Client")
    print("=" * 60)

    # Check if server is running
    print(f"\n🔍 Checking if server is running at {API_BASE_URL}...")
    if not await check_server_running():
        print(f"❌ Server is not running at {API_BASE_URL}")
        print("\n💡 Start the server first:")
        print("   python examples/example_beta1_server.py")
        sys.exit(1)

    print("   ✅ Server is running")

    # Login
    print(f"\n🔐 Authenticating as {args.username}...")
    token = await login(args.username, args.password)
    if not token:
        print("❌ Authentication failed")
        sys.exit(1)

    print("   ✅ Authentication successful")

    # Get OHLCV candles
    print(f"\n📊 Fetching {args.timeframe} candles for {args.symbol} ({args.exchange})...")
    candles = await get_ohlcv_candles(
        token=token,
        exchange=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe,
        limit=args.limit,
    )

    # Display results
    display_candles(candles, args.symbol, args.timeframe)

    if candles:
        print("✅ Query completed successfully")
    else:
        print("⚠️  No data available (collection may still be in progress)")
        print("   Try again in a few moments or check server logs")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
