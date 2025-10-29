#!/usr/bin/env python3
"""
Example Beta1 Client: OHLCV Data Query Client

Queries OHLCV data from the running Fullon Master API server using API key authentication.

Assumes example_beta1_server.py is already running on http://localhost:8000

Features:
- Authenticates with API key (no password required)
- Queries OHLCV candles for specified symbol and timeframe
- Displays candles in a formatted table
- Supports multiple timeframes (1m, 5m, 15m, 1h, 4h, 1d, etc.)

Usage:
    # Get daily candles (default) - uses API key from .beta1_api_key file
    python examples/example_beta1_client.py

    # Provide API key via environment variable
    export FULLON_API_KEY=your_api_key_here
    python examples/example_beta1_client.py

    # Provide API key via command line
    python examples/example_beta1_client.py --api-key your_api_key_here

    # Get 1-hour candles
    python examples/example_beta1_client.py --timeframe 1h

    # Get 5-minute candles, limit to 20
    python examples/example_beta1_client.py --timeframe 5m --limit 20

    # Query different symbol
    python examples/example_beta1_client.py --symbol ETH/USDC:USDC --timeframe 1d

Prerequisites:
    1. Setup database with demo data: python examples/demo_data_beta1.py --setup fullon_beta1
    2. Start the server: python examples/example_beta1_server.py
    3. Wait for "SERVER RUNNING" message
    4. Run this client (API key will be read from .beta1_api_key file)
"""

import argparse
import asyncio
import os
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


def get_api_key(args_api_key: str | None = None) -> str | None:
    """
    Get API key from command line, environment variable, or .beta1_api_key file.

    Priority:
        1. Command line argument (--api-key)
        2. Environment variable (FULLON_API_KEY)
        3. File (.beta1_api_key in examples directory)

    Args:
        args_api_key: API key from command line argument

    Returns:
        str: API key if found
        None: If no API key found
    """
    # Priority 1: Command line argument
    if args_api_key:
        return args_api_key

    # Priority 2: Environment variable
    env_key = os.getenv("FULLON_API_KEY")
    if env_key:
        return env_key

    # Priority 3: File
    api_key_file = Path(__file__).parent / ".beta1_api_key"
    if api_key_file.exists():
        try:
            return api_key_file.read_text().strip()
        except Exception as e:
            print(f"⚠️  Could not read API key from {api_key_file}: {e}")

    return None


async def get_ohlcv_candles(
    api_key: str,
    exchange: str,
    symbol: str,
    timeframe: str,
    limit: int = 100,
    base_url: str = API_BASE_URL,
) -> list:
    """
    Get OHLCV candles from the API using API key authentication.

    Args:
        api_key: API key for authentication
        exchange: Exchange name (e.g., "bitmex")
        symbol: Trading pair symbol (e.g., "BTC/USD:BTC")
        timeframe: Timeframe (e.g., "1m", "1h", "1d")
        limit: Maximum number of candles to retrieve
        base_url: API base URL

    Returns:
        list: List of OHLCV candles
    """
    # URL encode the symbol
    encoded_symbol = quote(symbol, safe="")
    url = f"{base_url}/api/v1/ohlcv/{exchange}/{encoded_symbol}/{timeframe}"

    headers = {"X-API-Key": api_key}
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
        default="bitmex",
        help="Exchange name (default: bitmex)",
    )
    parser.add_argument(
        "--symbol",
        default="BTC/USD:BTC",
        help="Trading pair symbol (default: BTC/USD:BTC)",
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
        "--api-key",
        dest="api_key",
        help="API key for authentication (default: read from .beta1_api_key file or FULLON_API_KEY env var)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Fullon Master API - OHLCV Data Query Client")
    print("API Key Authentication")
    print("=" * 60)

    # Get API key
    print("\n🔑 Getting API key...")
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("❌ No API key found")
        print("\n💡 Provide API key via:")
        print("   1. Command line: --api-key YOUR_KEY")
        print("   2. Environment: export FULLON_API_KEY=YOUR_KEY")
        print("   3. File: examples/.beta1_api_key")
        print("\n💡 To create a new API key:")
        print("   python examples/demo_data_beta1.py --setup fullon_beta1")
        sys.exit(1)

    print(f"   ✅ API key found: {api_key[:20]}...")

    # Check if server is running
    print(f"\n🔍 Checking if server is running at {API_BASE_URL}...")
    if not await check_server_running():
        print(f"❌ Server is not running at {API_BASE_URL}")
        print("\n💡 Start the server first:")
        print("   python examples/example_beta1_server.py")
        sys.exit(1)

    print("   ✅ Server is running")

    # Get OHLCV candles
    print(f"\n📊 Fetching {args.timeframe} candles for {args.symbol} ({args.exchange})...")
    candles = await get_ohlcv_candles(
        api_key=api_key,
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
