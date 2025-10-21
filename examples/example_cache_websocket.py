#!/usr/bin/env python3
"""
Example: Cache WebSocket Streaming

Demonstrates:
- WebSocket connection to cache API
- Real-time ticker data streaming
- Real-time trade updates
- Account balance updates
- Order queue monitoring
- Proper WebSocket lifecycle management

Expected WebSocket Endpoints (proxied from fullon_cache_api):
- ws://localhost:8000/ws/tickers/{exchange}/{symbol}
- ws://localhost:8000/ws/trades/{exchange}/{symbol}
- ws://localhost:8000/ws/orders/{exchange}
- ws://localhost:8000/ws/balances/{exchange_id}

Usage:
    python examples/example_cache_websocket.py
    python examples/example_cache_websocket.py --stream tickers --symbol BTC/USDT
"""
import asyncio
import websockets
import json
import argparse
from typing import Optional
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.cache_websocket")

WS_BASE_URL = "ws://localhost:8000"


async def stream_tickers(exchange: str, symbol: str, duration: int = 10):
    """
    Stream real-time ticker data.

    Args:
        exchange: Exchange name (e.g., "binance")
        symbol: Trading pair (e.g., "BTC/USDT")
        duration: How long to stream (seconds)
    """
    url = f"{WS_BASE_URL}/ws/tickers/{exchange}/{symbol}"

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
        print(f"\n❌ Connection refused - is the server running?")
        print("   Run: make run")


async def stream_trades(exchange: str, symbol: str, duration: int = 10):
    """
    Stream real-time trade data.

    Args:
        exchange: Exchange name
        symbol: Trading pair
        duration: How long to stream (seconds)
    """
    url = f"{WS_BASE_URL}/ws/trades/{exchange}/{symbol}"

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
    url = f"{WS_BASE_URL}/ws/orders/{exchange}"

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
    url = f"{WS_BASE_URL}/ws/balances/{exchange_id}"

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


async def main(
    stream_type: str = "tickers",
    exchange: str = "kraken",
    symbol: str = "BTC/USDC",
    exchange_id: int = 1,
    duration: int = 10,
):
    """Run WebSocket streaming example."""
    print("=" * 60)
    print("Fullon Master API - Cache WebSocket Example")
    print("=" * 60)

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
    print("   - These streams are PROXIED from fullon_cache_api")
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
    parser.add_argument(
        "--exchange-id", type=int, default=1, help="Exchange ID (for balances)"
    )
    parser.add_argument(
        "--duration", type=int, default=10, help="Streaming duration (seconds)"
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            stream_type=args.stream,
            exchange=args.exchange,
            symbol=args.symbol,
            exchange_id=args.exchange_id,
            duration=args.duration,
        )
    )
