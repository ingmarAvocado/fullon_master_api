#!/usr/bin/env python3
"""
Example: Cache WebSocket Streaming - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Creates its own test databases (ORM + OHLCV)
- Populates demo data (exchanges, symbols for cache)
- Starts its own embedded test server
- Tests WebSocket streaming with JWT authentication
- Cleans up databases when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_cache_websocket.py
    python examples/example_cache_websocket.py --stream tickers --symbol BTC/USDT
    python examples/example_cache_websocket.py --auth-demo  # Show auth failure demo

Demonstrates:
- JWT-authenticated WebSocket connections to cache API
- Real-time ticker data streaming
- Real-time trade updates
- Account balance updates
- Order queue monitoring
- Authentication failure handling
- Proper WebSocket lifecycle management

Expected WebSocket Endpoints (JWT-authenticated, proxied from fullon_cache_api):
- ws://localhost:8000/api/v1/cache/ws/tickers/{exchange}/{symbol}?token=jwt_token
- ws://localhost:8000/api/v1/cache/ws/trades/{exchange}/{symbol}?token=jwt_token
- ws://localhost:8000/api/v1/cache/ws/orders/{exchange}?token=jwt_token
- ws://localhost:8000/api/v1/cache/ws/balances/{exchange_id}?token=jwt_token
"""
# 1. Standard library imports ONLY
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# 2. Third-party imports (non-fullon packages)
import websockets

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
from fullon_master_api.auth.jwt import JWTHandler
from fullon_master_api.config import settings
from fullon_orm import init_db

# 8. Initialize logger
logger = get_component_logger("fullon.examples.cache_websocket")

WS_BASE_URL = "ws://localhost:8000/api/v1/cache"

# JWT Handler for authentication
jwt_handler = JWTHandler(settings.jwt_secret_key)

async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    return server, task


import argparse
import asyncio
import json

import websockets
from fullon_log import get_component_logger
from fullon_master_api.auth.jwt import JWTHandler
from fullon_master_api.config import settings

logger = get_component_logger("fullon.examples.cache_websocket")

WS_BASE_URL = "ws://localhost:8000/api/v1/cache"

# JWT Handler for authentication
jwt_handler = JWTHandler(settings.jwt_secret_key)


def generate_demo_token() -> str:
    """
    Generate a demo JWT token for WebSocket authentication.

    Returns:
        JWT token string for demo user
    """
    # Demo user credentials (match demo_data.py - admin user)
    user_id = 1
    username = "admin@fullon"
    email = "admin@fullon"

    token = jwt_handler.generate_token(user_id=user_id, username=username, email=email)
    logger.info("Generated demo JWT token for WebSocket authentication", username=username)
    return token


async def stream_tickers(exchange: str, symbol: str, duration: int = 10):
    """
    Stream real-time ticker data.

    Args:
        exchange: Exchange name (e.g., "binance")
        symbol: Trading pair (e.g., "BTC/USDT")
        duration: How long to stream (seconds)
    """
    token = generate_demo_token()
    url = f"{WS_BASE_URL}/ws/tickers/{exchange}/{symbol}?token={token}"

    print(f"\n📊 Streaming ticker data: {exchange} {symbol}")
    print(f"   Duration: {duration} seconds")
    print("   Press Ctrl+C to stop early")
    print("-" * 60)

    try:
        async with websockets.connect(url) as websocket:
            logger.info("WebSocket connected", url=url)

            # Stream for specified duration
            end_time = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < end_time:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    # Display ticker data
                    print(f"⏰ {data.get('time', 'N/A')}")
                    print(f"   Price:  ${data.get('price', 0):,.2f}")
                    print(f"   Bid:    ${data.get('bid', 0):,.2f}")
                    print(f"   Ask:    ${data.get('ask', 0):,.2f}")
                    print(f"   Volume: {data.get('volume', 0):,.4f}")
                    print("-" * 60)

                except asyncio.TimeoutError:
                    continue

            logger.info("Stream completed")

    except websockets.exceptions.WebSocketException as e:
        logger.error("WebSocket error", error=str(e))
        print(f"\n❌ WebSocket connection failed: {e}")
        print("   Endpoint may not be implemented yet")
    except ConnectionRefusedError:
        print("\n❌ Connection refused - is the server running?")
        print("   Run: make run")


async def stream_trades(exchange: str, symbol: str, duration: int = 10):
    """
    Stream real-time trade data.

    Args:
        exchange: Exchange name
        symbol: Trading pair
        duration: How long to stream (seconds)
    """
    token = generate_demo_token()
    url = f"{WS_BASE_URL}/ws/trades/{exchange}/{symbol}?token={token}"

    print(f"\n💹 Streaming trade data: {exchange} {symbol}")
    print(f"   Duration: {duration} seconds")
    print("-" * 60)

    try:
        async with websockets.connect(url) as websocket:
            logger.info("WebSocket connected", url=url)

            end_time = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    # Display trade data
                    side_emoji = "🟢" if data.get("side") == "buy" else "🔴"
                    print(f"{side_emoji} {data.get('timestamp', 'N/A')}")
                    print(f"   Price:  ${data.get('price', 0):,.2f}")
                    print(f"   Volume: {data.get('volume', 0):,.6f}")
                    print(f"   Side:   {data.get('side', 'N/A').upper()}")
                    print("-" * 60)

                except asyncio.TimeoutError:
                    continue

            logger.info("Stream completed")

    except websockets.exceptions.WebSocketException as e:
        logger.error("WebSocket error", error=str(e))
        print(f"\n❌ WebSocket connection failed: {e}")
        print("   Endpoint may not be implemented yet")


async def stream_orders(exchange: str, duration: int = 10):
    """
    Stream order queue updates.

    Args:
        exchange: Exchange name
        duration: How long to stream (seconds)
    """
    token = generate_demo_token()
    url = f"{WS_BASE_URL}/ws/orders/{exchange}?token={token}"

    print(f"\n📋 Streaming order queue: {exchange}")
    print(f"   Duration: {duration} seconds")
    print("-" * 60)

    try:
        async with websockets.connect(url) as websocket:
            logger.info("WebSocket connected", url=url)

            end_time = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    # Display order data
                    print(f"📝 Order {data.get('order_id', 'N/A')}")
                    print(f"   Symbol:  {data.get('symbol', 'N/A')}")
                    print(f"   Side:    {data.get('side', 'N/A')}")
                    print(f"   Volume:  {data.get('volume', 0):,.6f}")
                    print(f"   Status:  {data.get('status', 'N/A')}")
                    print("-" * 60)

                except asyncio.TimeoutError:
                    continue

            logger.info("Stream completed")

    except websockets.exceptions.WebSocketException as e:
        logger.error("WebSocket error", error=str(e))
        print(f"\n❌ WebSocket connection failed: {e}")
        print("   Endpoint may not be implemented yet")


async def stream_balances(exchange_id: int, duration: int = 10):
    """
    Stream account balance updates.

    Args:
        exchange_id: Exchange ID
        duration: How long to stream (seconds)
    """
    token = generate_demo_token()
    url = f"{WS_BASE_URL}/ws/balances/{exchange_id}?token={token}"

    print(f"\n💰 Streaming balance updates: Exchange {exchange_id}")
    print(f"   Duration: {duration} seconds")
    print("-" * 60)

    try:
        async with websockets.connect(url) as websocket:
            logger.info("WebSocket connected", url=url)

            end_time = asyncio.get_event_loop().time() + duration

            while asyncio.get_event_loop().time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    # Display balance data
                    for currency, balance in data.items():
                        if isinstance(balance, dict):
                            print(f"💵 {currency}")
                            print(f"   Total: {balance.get('total', 0):,.8f}")
                            print(f"   Free:  {balance.get('free', 0):,.8f}")
                            print(f"   Used:  {balance.get('used', 0):,.8f}")
                    print("-" * 60)

                except asyncio.TimeoutError:
                    continue

            logger.info("Stream completed")

    except websockets.exceptions.WebSocketException as e:
        logger.error("WebSocket error", error=str(e))
        print(f"\n❌ WebSocket connection failed: {e}")
        print("   Endpoint may not be implemented yet")


async def demonstrate_auth_failure(exchange: str = "kraken", symbol: str = "BTC/USDC"):
    """
    Demonstrate authentication failure when connecting without a valid token.

    Args:
        exchange: Exchange name
        symbol: Trading pair
    """
    print("\n🔒 Demonstrating Authentication Failure")
    print("-" * 60)

    # Try connecting without token
    url_no_token = f"{WS_BASE_URL}/ws/tickers/{exchange}/{symbol}"
    print(f"Attempting connection without token: {url_no_token}")

    try:
        async with websockets.connect(url_no_token) as _websocket:
            print("❌ Unexpected: Connection succeeded without authentication")
    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "Unauthorized" in error_str:
            print("✅ Expected: Authentication failed (401 Unauthorized)")
            print("   WebSocket endpoints require JWT authentication")
        else:
            print(f"❌ Connection failed with error: {e}")

    # Try connecting with invalid token
    invalid_token = "invalid.jwt.token"
    url_invalid_token = f"{WS_BASE_URL}/ws/tickers/{exchange}/{symbol}?token={invalid_token}"
    print(f"\nAttempting connection with invalid token: {url_invalid_token[:80]}...")

    try:
        async with websockets.connect(url_invalid_token) as _websocket:
            print("❌ Unexpected: Connection succeeded with invalid token")
    except Exception as e:
        error_str = str(e)
        if "401" in error_str or "Unauthorized" in error_str:
            print("✅ Expected: Authentication failed (401 Unauthorized)")
            print("   Invalid JWT token rejected")
        else:
            print(f"❌ Connection failed with error: {e}")

    print("\n💡 Authentication Requirements:")
    print("   - All WebSocket endpoints require JWT authentication")
    print("   - Include ?token=jwt_token in the URL")
    print("   - Token must be valid and not expired")
    print("-" * 60)




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
    print("\n3. Installing demo data (exchanges, symbols)...")
    await install_demo_data()
    print("\n" + "=" * 60)
    print("✅ Test environment ready!")
    print("=" * 60)

async def run_websocket_examples(
    stream_type: str = "tickers",
    exchange: str = "kraken",
    symbol: str = "BTC/USDC",
    exchange_id: int = 1,
    duration: int = 10,
    show_auth_demo: bool = False,
):
    """Run WebSocket streaming examples."""
    print("\n" + "=" * 60)
    print("Fullon Master API - Cache WebSocket Example")
    print("=" * 60)

    # Demonstrate authentication requirements
    if show_auth_demo:
        await demonstrate_auth_failure(exchange, symbol)

    try:
        if stream_type == "tickers":
            await stream_tickers(exchange, symbol, duration)
        elif stream_type == "trades":
            await stream_trades(exchange, symbol, duration)
        elif stream_type == "orders":
            await stream_orders(exchange, duration)
        elif stream_type == "balances":
            await stream_balances(exchange_id, duration)
        else:
            print(f"\n❌ Unknown stream type: {stream_type}")
            print("   Valid options: tickers, trades, orders, balances")

    except KeyboardInterrupt:
        print("\n\n⏹️  Stream stopped by user")

    print("\n" + "=" * 60)
    print("💡 WebSocket Streaming Tips:")
    print("   - WebSockets provide real-time data with low latency")
    print("   - Use for live price feeds, order updates, balances")
    print("   - Connection automatically reconnects on disconnection")
    print("   - All endpoints require JWT authentication (?token=...)")
    print("   - These streams are PROXIED from fullon_cache_api")
    print("   - Use --auth-demo to see authentication failure examples")
    print("=" * 60)

async def main(
    stream_type: str = "tickers",
    exchange: str = "kraken",
    symbol: str = "BTC/USDC",
    exchange_id: int = 1,
    duration: int = 10,
    show_auth_demo: bool = False,
):
    """Main entry point - self-contained with setup and cleanup."""
    print("=" * 60)
    print("Fullon Master API - Cache WebSocket Example")
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

        # Run WebSocket examples
        await run_websocket_examples(stream_type, exchange, symbol, exchange_id, duration, show_auth_demo)

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
    parser = argparse.ArgumentParser(description="Cache WebSocket Streaming Example")
    parser.add_argument(
        "--stream",
        type=str,
        default="tickers",
        choices=["tickers", "trades", "orders", "balances"],
        help="Type of stream to connect to",
    )
    parser.add_argument(
        "--exchange", type=str, default="kraken", help="Exchange name (demo: kraken)"
    )
    parser.add_argument(
        "--symbol", type=str, default="BTC/USDC", help="Trading pair symbol (demo: BTC/USDC)"
    )
    parser.add_argument("--exchange-id", type=int, default=1, help="Exchange ID (for balances)")
    parser.add_argument("--duration", type=int, default=10, help="Streaming duration (seconds)")
    parser.add_argument(
        "--auth-demo",
        action="store_true",
        help="Show authentication failure demonstration before streaming",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            stream_type=args.stream,
            exchange=args.exchange,
            symbol=args.symbol,
            exchange_id=args.exchange_id,
            duration=args.duration,
            show_auth_demo=args.auth_demo,
        )
    )
