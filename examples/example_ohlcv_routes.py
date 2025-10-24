#!/usr/bin/env python3
"""
Example: OHLCV API Routes (Composed from fullon_ohlcv_api)

Demonstrates:
- Fetching OHLCV (candlestick) data with JWT authentication
- Getting latest candle data
- Different timeframes (1m, 5m, 15m, 1h, 1d)
- Time range queries

Available Endpoints (mounted in fullon_master_api):
- GET /api/v1/ohlcv/{exchange}/{symbol}        - Get OHLCV data
- GET /api/v1/ohlcv/{exchange}/{symbol}/latest - Get latest candle

Note: All endpoints require JWT authentication via Bearer token.

Usage:
    python examples/example_ohlcv_routes.py

Prerequisites:
- Server running on localhost:8000
- Valid user in database (user_id=1 for demo)
- OHLCV database tables initialized (if using real data)
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fullon_log import get_component_logger

# Import JWT handler for authentication
try:
    from fullon_master_api.auth.jwt import JWTHandler
    from fullon_master_api.config import settings
except ImportError:
    # Fallback for when running outside the project
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    from fullon_master_api.auth.jwt import JWTHandler
    from fullon_master_api.config import settings

logger = get_component_logger("fullon.examples.ohlcv_routes")

API_BASE_URL = "http://localhost:8000"


class OHLCVAPIClient:
    """Client for OHLCV API endpoints with JWT authentication."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token
        self.jwt_handler = JWTHandler(settings.jwt_secret_key, settings.jwt_algorithm)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with JWT authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def create_demo_token(self, user_id: int = 1) -> str:
        """Create a demo JWT token for testing."""
        return self.jwt_handler.create_token({
            "sub": str(user_id),
            "user_id": user_id,
            "scopes": ["read", "write"]
        })

    async def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[List[List[float]]]:
        """
        Get OHLCV candlestick data.

        Args:
            exchange: Exchange name (e.g., "kraken")
            symbol: Trading pair (e.g., "BTC/USDC")
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 1d)
            limit: Maximum number of candles
            start_time: Start datetime (UTC)
            end_time: End datetime (UTC)

        Returns:
            List of OHLCV arrays: [[timestamp, open, high, low, close, volume], ...]
        """
        # Use the mounted endpoint path
        url = f"{self.base_url}/api/v1/ohlcv/{exchange}/{symbol}"

        params = {"timeframe": timeframe, "limit": limit}

        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "OHLCV data retrieved",
                    exchange=exchange,
                    symbol=symbol,
                    count=len(data) if data else 0,
                )
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get OHLCV failed",
                    status=e.response.status_code,
                    exchange=exchange,
                    symbol=symbol,
                )
                return None

    async def get_trades(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get raw trade data.

        Note: This endpoint may not be available in all versions of fullon_ohlcv_api.

        Args:
            exchange: Exchange name
            symbol: Trading pair
            limit: Maximum number of trades
            start_time: Start datetime (UTC)

        Returns:
            List of trade objects, or None if endpoint not available
        """
        url = f"{self.base_url}/api/v1/trades/{exchange}/{symbol}"

        params = {"limit": limit}
        if start_time:
            params["start_time"] = start_time.isoformat()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Trade data retrieved",
                    exchange=exchange,
                    symbol=symbol,
                    count=len(data) if data else 0,
                )
                return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(
                        "Trades endpoint not available",
                        exchange=exchange,
                        symbol=symbol,
                    )
                else:
                    logger.error(
                        "Get trades failed",
                        status=e.response.status_code,
                        exchange=exchange,
                        symbol=symbol,
                    )
                return None

    async def get_latest_ohlcv(
        self, exchange: str, symbol: str, timeframe: str = "1m"
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest OHLCV candle.

        Args:
            exchange: Exchange name
            symbol: Trading pair
            timeframe: Candle timeframe

        Returns:
            Latest OHLCV candle data as dict
        """
        url = f"{self.base_url}/api/v1/ohlcv/{exchange}/{symbol}/latest"

        params = {"timeframe": timeframe}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Latest OHLCV retrieved",
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                )
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Get latest OHLCV failed",
                    status=e.response.status_code,
                    exchange=exchange,
                    symbol=symbol,
                )
                return None


async def example_ohlcv_data():
    """Demonstrate OHLCV data retrieval with JWT authentication."""
    print("\n" + "=" * 60)
    print("Example: OHLCV Data Retrieval (with JWT Auth)")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)  # Demo user
    client.token = token

    print("🔐 Using JWT token for user_id=1")

    # Use demo data symbol (kraken BTC/USDC)
    print("\n1️⃣  Fetching 1-minute OHLCV data for BTC/USDC (Kraken)...")
    ohlcv = await client.get_ohlcv(
        exchange="kraken", symbol="BTC/USDC", timeframe="1m", limit=10
    )

    if ohlcv:
        print(f"   ✅ Retrieved {len(ohlcv)} candles")
        print("   Latest candle:")
        latest = ohlcv[-1] if ohlcv else None
        if latest and len(latest) >= 6:
            print(f"      Timestamp: {datetime.fromtimestamp(latest[0]/1000, tz=timezone.utc)}")
            print(f"      Open:      ${latest[1]:,.2f}")
            print(f"      High:      ${latest[2]:,.2f}")
            print(f"      Low:       ${latest[3]:,.2f}")
            print(f"      Close:     ${latest[4]:,.2f}")
            print(f"      Volume:    {latest[5]:,.4f}")
    else:
        print("   ❌ Failed to retrieve OHLCV data (may be due to missing database)")

    print("\n2️⃣  Fetching 1-hour OHLCV data...")
    ohlcv_1h = await client.get_ohlcv(
        exchange="kraken", symbol="BTC/USDC", timeframe="1h", limit=24
    )

    if ohlcv_1h:
        print(f"   ✅ Retrieved {len(ohlcv_1h)} hourly candles (last 24 hours)")
    else:
        print("   ❌ Failed to retrieve 1h OHLCV data (may be due to missing database)")


async def example_trade_data():
    """Demonstrate trade data retrieval (if available)."""
    print("\n" + "=" * 60)
    print("Example: Raw Trade Data Retrieval")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)
    client.token = token

    print("\n1️⃣  Fetching recent trades for BTC/USDC (Kraken)...")
    trades = await client.get_trades(exchange="kraken", symbol="BTC/USDC", limit=10)

    if trades:
        print(f"   ✅ Retrieved {len(trades)} trades")
        print("   Most recent trade:")
        recent = trades[-1] if trades else None
        if recent:
            print(f"      Time:   {recent.get('timestamp', 'N/A')}")
            print(f"      Price:  ${recent.get('price', 0):,.2f}")
            print(f"      Volume: {recent.get('volume', 0):,.6f}")
            print(f"      Side:   {recent.get('side', 'N/A')}")
    else:
        print(
            "   ❌ Trade data not available "
            "(endpoint may not be implemented or database not set up)"
        )


async def example_time_range_query():
    """Demonstrate time-range queries."""
    print("\n" + "=" * 60)
    print("Example: Time-Range Queries")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)
    client.token = token

    # Get data for last hour
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    print("\n1️⃣  Fetching OHLCV for last hour (Kraken BTC/USDC)...")
    print(f"   Start: {start_time.isoformat()}")
    print(f"   End:   {end_time.isoformat()}")

    ohlcv = await client.get_ohlcv(
        exchange="kraken",
        symbol="BTC/USDC",
        timeframe="1m",
        start_time=start_time,
        end_time=end_time,
    )

    if ohlcv:
        print(f"   ✅ Retrieved {len(ohlcv)} candles for specified time range")

        if len(ohlcv) > 0:
            first = ohlcv[0]
            last = ohlcv[-1]
            if len(first) >= 1 and len(last) >= 1:
                print(f"   First candle: {datetime.fromtimestamp(first[0]/1000, tz=timezone.utc)}")
                print(f"   Last candle:  {datetime.fromtimestamp(last[0]/1000, tz=timezone.utc)}")
    else:
        print("   ❌ Failed to retrieve time-range data (may be due to missing database)")


async def example_multiple_timeframes():
    """Demonstrate fetching multiple timeframes."""
    print("\n" + "=" * 60)
    print("Example: Multiple Timeframes")
    print("=" * 60)

    # Create client with JWT token
    client = OHLCVAPIClient()
    token = client.create_demo_token(user_id=1)
    client.token = token

    timeframes = ["1m", "5m", "15m", "1h", "1d"]

    for tf in timeframes:
        print(f"\n⏱️  Fetching {tf} candles (Kraken BTC/USDC)...")
        ohlcv = await client.get_ohlcv(
            exchange="kraken", symbol="BTC/USDC", timeframe=tf, limit=5
        )

        if ohlcv:
            print(f"   ✅ Got {len(ohlcv)} {tf} candles")
        else:
            print(f"   ❌ Failed to get {tf} candles (may be due to missing database)")


async def main():
    """Run all OHLCV API examples with JWT authentication."""
    print("=" * 60)
    print("Fullon Master API - OHLCV Routes Example")
    print("=" * 60)
    print("🔐 All endpoints require JWT authentication")
    print("📊 Using demo user (user_id=1) with read/write scopes")

    try:
        # Example 1: Basic OHLCV data
        await example_ohlcv_data()

        # Example 2: Trade data (may not be available)
        await example_trade_data()

        # Example 3: Time-range queries
        await example_time_range_query()

        # Example 4: Multiple timeframes
        await example_multiple_timeframes()

        print("\n" + "=" * 60)
        print("✅ Examples completed!")
        print("💡 Key Points:")
        print("   - All endpoints require Bearer JWT tokens")
        print("   - OHLCV data format: [timestamp, open, high, low, close, volume]")
        print("   - Timestamps are in milliseconds (UTC)")
        print("   - Supported timeframes: 1m, 5m, 15m, 1h, 1d")
        print("   - Routes are COMPOSED from fullon_ohlcv_api with auth overrides")
        print("   - Database setup required for actual data retrieval")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        print("Make sure the server is running on localhost:8000")
        print("and the OHLCV database is properly configured.")


if __name__ == "__main__":
    asyncio.run(main())
