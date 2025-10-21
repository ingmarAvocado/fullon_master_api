#!/usr/bin/env python3
"""
Example: OHLCV API Routes (Composed from fullon_ohlcv_api)

Demonstrates:
- Fetching OHLCV (candlestick) data
- Querying trade data
- Time-series data retrieval
- Different timeframes (1m, 5m, 1h, 1d)

Expected Endpoints (from fullon_ohlcv_api):
- GET /api/v1/ohlcv/{exchange}/{symbol}        - Get OHLCV data
- GET /api/v1/trades/{exchange}/{symbol}       - Get trade data
- GET /api/v1/timeseries/{exchange}/{symbol}   - Get time-series data

Usage:
    python examples/example_ohlcv_routes.py
"""
import asyncio
import httpx
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.ohlcv_routes")

API_BASE_URL = "http://localhost:8000"


class OHLCVAPIClient:
    """Client for OHLCV API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, token: Optional[str] = None):
        self.base_url = base_url
        self.token = token

    def _get_headers(self) -> dict:
        """Get headers with optional authorization."""
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[List[list]]:
        """
        Get OHLCV candlestick data.

        Args:
            exchange: Exchange name (e.g., "binance")
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (1m, 5m, 15m, 1h, 1d)
            limit: Maximum number of candles
            start_time: Start datetime (UTC)
            end_time: End datetime (UTC)

        Returns:
            List of OHLCV arrays: [[timestamp, open, high, low, close, volume], ...]
        """
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
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get OHLCV failed", status=e.response.status_code)
                return None

    async def get_trades(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
        start_time: Optional[datetime] = None,
    ) -> Optional[List[dict]]:
        """
        Get raw trade data.

        Args:
            exchange: Exchange name
            symbol: Trading pair
            limit: Maximum number of trades
            start_time: Start datetime (UTC)

        Returns:
            List of trade objects
        """
        url = f"{self.base_url}/api/v1/trades/{exchange}/{symbol}"

        params = {"limit": limit}
        if start_time:
            params["start_time"] = start_time.isoformat()

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get trades failed", status=e.response.status_code)
                return None

    async def get_latest_ohlcv(
        self, exchange: str, symbol: str, timeframe: str = "1m"
    ) -> Optional[dict]:
        """
        Get latest OHLCV candle.

        Args:
            exchange: Exchange name
            symbol: Trading pair
            timeframe: Candle timeframe

        Returns:
            Latest OHLCV candle data
        """
        url = f"{self.base_url}/api/v1/ohlcv/{exchange}/{symbol}/latest"

        params = {"timeframe": timeframe}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self._get_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error("Get latest OHLCV failed", status=e.response.status_code)
                return None


async def example_ohlcv_data():
    """Demonstrate OHLCV data retrieval."""
    print("\n" + "=" * 60)
    print("Example: OHLCV Data Retrieval")
    print("=" * 60)

    client = OHLCVAPIClient()

    # Use demo data symbol (kraken BTC/USDC)
    print("\n1️⃣  Fetching 1-minute OHLCV data for BTC/USDC (Kraken)...")
    ohlcv = await client.get_ohlcv(
        exchange="kraken", symbol="BTC/USDC", timeframe="1m", limit=10
    )

    if ohlcv:
        print(f"   ✅ Retrieved {len(ohlcv)} candles")
        print("   Latest candle:")
        latest = ohlcv[-1] if ohlcv else None
        if latest:
            print(f"      Timestamp: {datetime.fromtimestamp(latest[0]/1000, tz=timezone.utc)}")
            print(f"      Open:      ${latest[1]:,.2f}")
            print(f"      High:      ${latest[2]:,.2f}")
            print(f"      Low:       ${latest[3]:,.2f}")
            print(f"      Close:     ${latest[4]:,.2f}")
            print(f"      Volume:    {latest[5]:,.4f}")
    else:
        print("   ❌ Endpoint not yet implemented")

    print("\n2️⃣  Fetching 1-hour OHLCV data...")
    ohlcv_1h = await client.get_ohlcv(
        exchange="kraken", symbol="BTC/USDC", timeframe="1h", limit=24
    )

    if ohlcv_1h:
        print(f"   ✅ Retrieved {len(ohlcv_1h)} hourly candles (last 24 hours)")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_trade_data():
    """Demonstrate trade data retrieval."""
    print("\n" + "=" * 60)
    print("Example: Raw Trade Data Retrieval")
    print("=" * 60)

    client = OHLCVAPIClient()

    print("\n1️⃣  Fetching recent trades for BTC/USDC (Kraken)...")
    trades = await client.get_trades(exchange="kraken", symbol="BTC/USDC", limit=10)

    if trades:
        print(f"   ✅ Retrieved {len(trades)} trades")
        print("   Most recent trade:")
        recent = trades[-1] if trades else None
        if recent:
            print(f"      Time:   {recent.get('timestamp')}")
            print(f"      Price:  ${recent.get('price'):,.2f}")
            print(f"      Volume: {recent.get('volume'):,.6f}")
            print(f"      Side:   {recent.get('side')}")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_time_range_query():
    """Demonstrate time-range queries."""
    print("\n" + "=" * 60)
    print("Example: Time-Range Queries")
    print("=" * 60)

    client = OHLCVAPIClient()

    # Get data for last hour
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    print(f"\n1️⃣  Fetching OHLCV for last hour (Kraken BTC/USDC)...")
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

        if ohlcv:
            first = ohlcv[0]
            last = ohlcv[-1]
            print(f"   First candle: {datetime.fromtimestamp(first[0]/1000, tz=timezone.utc)}")
            print(f"   Last candle:  {datetime.fromtimestamp(last[0]/1000, tz=timezone.utc)}")
    else:
        print("   ❌ Endpoint not yet implemented")


async def example_multiple_timeframes():
    """Demonstrate fetching multiple timeframes."""
    print("\n" + "=" * 60)
    print("Example: Multiple Timeframes")
    print("=" * 60)

    client = OHLCVAPIClient()

    timeframes = ["1m", "5m", "15m", "1h", "1d"]

    for tf in timeframes:
        print(f"\n⏱️  Fetching {tf} candles (Kraken BTC/USDC)...")
        ohlcv = await client.get_ohlcv(
            exchange="kraken", symbol="BTC/USDC", timeframe=tf, limit=5
        )

        if ohlcv:
            print(f"   ✅ Got {len(ohlcv)} {tf} candles")
        else:
            print(f"   ❌ {tf} endpoint not yet available")


async def main():
    """Run all OHLCV API examples."""
    print("=" * 60)
    print("Fullon Master API - OHLCV Routes Example")
    print("=" * 60)

    # Example 1: Basic OHLCV data
    await example_ohlcv_data()

    # Example 2: Trade data
    await example_trade_data()

    # Example 3: Time-range queries
    await example_time_range_query()

    # Example 4: Multiple timeframes
    await example_multiple_timeframes()

    print("\n" + "=" * 60)
    print("💡 Key Points:")
    print("   - OHLCV data format: [timestamp, open, high, low, close, volume]")
    print("   - Timestamps are in milliseconds (UTC)")
    print("   - Supported timeframes: 1m, 5m, 15m, 1h, 1d")
    print("   - These routes are COMPOSED from fullon_ohlcv_api")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
