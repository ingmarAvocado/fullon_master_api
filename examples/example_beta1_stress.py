#!/usr/bin/env python3
"""
Example Beta1 Stress Test: Load Testing for OHLCV API

Performs stress testing on the Fullon Master API server using wrk.

Features:
- Multiple test scenarios (light, medium, heavy, extreme)
- Tests all 4 symbols: BTC/USD:BTC, ETH/USD:BTC (Bitmex), GOLD, SPX (Yahoo)
- API key authentication via Lua script
- Detailed performance metrics and reporting
- Configurable duration, threads, and connections

Prerequisites:
    1. wrk installed: sudo pacman -S wrk
    2. Server running: python examples/example_beta1_server.py
    3. API key available (uses hardcoded key or .beta1_api_key file)

Usage:
    # Run light stress test (default)
    python examples/example_beta1_stress.py

    # Run medium stress test
    python examples/example_beta1_stress.py --scenario medium

    # Run heavy stress test
    python examples/example_beta1_stress.py --scenario heavy

    # Custom stress test
    python examples/example_beta1_stress.py --threads 12 --connections 400 --duration 60

    # Test specific symbol only
    python examples/example_beta1_stress.py --symbol BTC/USD:BTC --exchange bitmex

    # Test all symbols sequentially
    python examples/example_beta1_stress.py --all
"""

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

# Hardcoded API key as global variable
HARDCODED_API_KEY = "l7oFEnPvimQinTzH_r3NpZsGhot_kDn4gqjrrIlz1G8"
#HARDCODED_API_KEY = "EqHN77OSw13Q0gko3COYerlH3TplkEU2YKWg7i0Y9kE"
#

API_BASE_URL = "http://localhost:8222"

# Stress test scenarios
SCENARIOS = {
    "light": {
        "threads": 2,
        "connections": 10,
        "duration": 10,
        "description": "Light load test (2 threads, 10 connections, 10s)"
    },
    "medium": {
        "threads": 4,
        "connections": 50,
        "duration": 30,
        "description": "Medium load test (4 threads, 50 connections, 30s)"
    },
    "heavy": {
        "threads": 8,
        "connections": 200,
        "duration": 60,
        "description": "Heavy load test (8 threads, 200 connections, 60s)"
    },
    "extreme": {
        "threads": 16,
        "connections": 500,
        "duration": 120,
        "description": "Extreme load test (16 threads, 500 connections, 120s)"
    }
}


def get_api_key(args_api_key: str | None = None) -> str | None:
    """
    Get API key from hardcoded global variable, command line, environment variable, or .beta1_api_key file.

    Priority:
        1. Hardcoded global variable (HARDCODED_API_KEY)
        2. Command line argument (--api-key)
        3. Environment variable (FULLON_API_KEY)
        4. File (.beta1_api_key in examples directory)

    Args:
        args_api_key: API key from command line argument

    Returns:
        str: API key if found
        None: If no API key found
    """
    # Priority 1: Hardcoded global variable
    if HARDCODED_API_KEY:
        return HARDCODED_API_KEY

    # Priority 2: Command line argument
    if args_api_key:
        return args_api_key

    # Priority 3: Environment variable
    env_key = os.getenv("FULLON_API_KEY")
    if env_key:
        return env_key

    # Priority 4: File
    api_key_file = Path(__file__).parent / ".beta1_api_key"
    if api_key_file.exists():
        try:
            return api_key_file.read_text().strip()
        except Exception as e:
            print(f"⚠️  Could not read API key from {api_key_file}: {e}")

    return None


async def check_server_running(url: str = API_BASE_URL, timeout: float = 2.0) -> bool:
    """
    Check if server is running and healthy.

    Args:
        url: Base URL of the server
        timeout: Timeout for health check

    Returns:
        True if server is running, False otherwise
    """
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.get(f"{url}/health", timeout=timeout)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
            return False


def create_wrk_lua_script(api_key: str) -> str:
    """
    Create Lua script for wrk to add API key authentication.

    Args:
        api_key: API key for authentication

    Returns:
        str: Lua script content
    """
    return f'''-- Lua script for wrk with API key authentication
wrk.method = "GET"
wrk.headers["X-API-Key"] = "{api_key}"
wrk.headers["Accept"] = "application/json"
'''


def build_ohlcv_url(exchange: str, symbol: str, timeframe: str = "1d", limit: int = 10, base_url: str = API_BASE_URL) -> str:
    """
    Build OHLCV timeseries URL.

    Args:
        exchange: Exchange name (e.g., "bitmex", "yahoo")
        symbol: Trading pair symbol (e.g., "BTC/USD:BTC", "GOLD")
        timeframe: Timeframe (e.g., "1m", "1h", "1d")
        limit: Number of candles to retrieve
        base_url: API base URL

    Returns:
        str: Full URL for OHLCV timeseries endpoint
    """
    from datetime import timedelta

    # URL encode the symbol
    encoded_symbol = quote(symbol, safe="")

    # Use timeseries endpoint for aggregated OHLCV data
    url = f"{base_url}/api/v1/ohlcv/timeseries/{exchange}/{encoded_symbol}/ohlcv"

    # Calculate time range based on limit and timeframe
    end_time = datetime.now()

    # Parse timeframe to calculate start time
    timeframe_map = {
        "1m": timedelta(minutes=1),
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "1d": timedelta(days=1),
        "1w": timedelta(weeks=1),
    }

    interval = timeframe_map.get(timeframe, timedelta(days=1))
    start_time = end_time - (interval * limit)

    # Add query parameters
    params = f"?timeframe={timeframe}&start_time={start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}&end_time={end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}&limit={limit}"

    return url + params


def run_wrk_test(url: str, lua_script_path: str, threads: int, connections: int, duration: int) -> dict:
    """
    Run wrk load test and parse results.

    Args:
        url: Target URL for load testing
        lua_script_path: Path to Lua script for authentication
        threads: Number of threads to use
        connections: Number of connections to keep open
        duration: Test duration in seconds

    Returns:
        dict: Parsed wrk results
    """
    print(f"\n🔥 Starting wrk load test...")
    print(f"   URL: {url}")
    print(f"   Threads: {threads}")
    print(f"   Connections: {connections}")
    print(f"   Duration: {duration}s")
    print(f"   Lua Script: {lua_script_path}")

    cmd = [
        "wrk",
        "-t", str(threads),
        "-c", str(connections),
        "-d", f"{duration}s",
        "-s", lua_script_path,
        "--latency",
        url
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration + 30  # Add 30s buffer for wrk overhead
        )

        print(f"\n{'=' * 100}")
        print("WRK OUTPUT")
        print(f"{'=' * 100}")
        print(result.stdout)

        if result.stderr:
            print(f"\nSTDERR:\n{result.stderr}")

        # Parse wrk output for key metrics
        metrics = parse_wrk_output(result.stdout)

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "metrics": metrics
        }

    except subprocess.TimeoutExpired:
        print(f"❌ wrk test timed out after {duration + 30}s")
        return {
            "success": False,
            "error": "timeout",
            "metrics": {}
        }
    except Exception as e:
        print(f"❌ Error running wrk: {e}")
        return {
            "success": False,
            "error": str(e),
            "metrics": {}
        }


def parse_wrk_output(output: str) -> dict:
    """
    Parse wrk output to extract key metrics.

    Args:
        output: wrk stdout output

    Returns:
        dict: Parsed metrics
    """
    metrics = {}

    # Extract key metrics using simple parsing
    lines = output.split("\n")
    for line in lines:
        if "Requests/sec:" in line:
            metrics["requests_per_sec"] = line.split()[-1]
        elif "Transfer/sec:" in line:
            metrics["transfer_per_sec"] = line.split()[-1]
        elif "Latency" in line and "Stdev" not in line:
            parts = line.split()
            if len(parts) >= 2:
                metrics["avg_latency"] = parts[1]
        elif "requests in" in line:
            parts = line.split()
            metrics["total_requests"] = parts[0]
            metrics["total_duration"] = parts[2].rstrip(",")

    return metrics


def print_summary(results: list[dict]):
    """
    Print summary of stress test results.

    Args:
        results: List of test results
    """
    print(f"\n{'=' * 100}")
    print("STRESS TEST SUMMARY")
    print(f"{'=' * 100}\n")

    successful = sum(1 for r in results if r["result"]["success"])
    failed = len(results) - successful

    print(f"Total Tests: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if successful > 0:
        print(f"\n{'Symbol':<25} {'Requests/sec':<15} {'Avg Latency':<15} {'Total Requests':<15}")
        print("-" * 100)

        for r in results:
            if r["result"]["success"]:
                symbol = r["symbol"]
                metrics = r["result"]["metrics"]
                req_per_sec = metrics.get("requests_per_sec", "N/A")
                avg_latency = metrics.get("avg_latency", "N/A")
                total_req = metrics.get("total_requests", "N/A")

                print(f"{symbol:<25} {req_per_sec:<15} {avg_latency:<15} {total_req:<15}")

    print(f"\n{'=' * 100}\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Stress test Fullon Master API OHLCV endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run light stress test (default)
  %(prog)s

  # Run medium stress test
  %(prog)s --scenario medium

  # Run heavy stress test
  %(prog)s --scenario heavy

  # Custom stress test
  %(prog)s --threads 12 --connections 400 --duration 60

  # Test specific symbol only
  %(prog)s --symbol BTC/USD:BTC --exchange bitmex

  # Test all symbols sequentially
  %(prog)s --all
        """,
    )

    parser.add_argument(
        "--scenario",
        choices=["light", "medium", "heavy", "extreme"],
        default="light",
        help="Predefined stress test scenario (default: light)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        help="Number of threads (overrides scenario)",
    )
    parser.add_argument(
        "--connections",
        type=int,
        help="Number of connections (overrides scenario)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        help="Test duration in seconds (overrides scenario)",
    )
    parser.add_argument(
        "--exchange",
        default=None,
        help="Exchange name (e.g., bitmex, yahoo). If not specified, tests all exchanges",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Trading pair symbol (e.g., BTC/USD:BTC, GOLD). If not specified, tests all symbols",
    )
    parser.add_argument(
        "--timeframe",
        default="1d",
        help="Timeframe: 1m, 5m, 15m, 1h, 4h, 1d, etc. (default: 1d)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of candles to retrieve per request (default: 10)",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="API key for authentication (default: read from .beta1_api_key file or FULLON_API_KEY env var)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Test all available symbols (bitmex: BTC, ETH; yahoo: GOLD, SPX)",
    )

    args = parser.parse_args()

    print("=" * 100)
    print("Fullon Master API - OHLCV Stress Testing")
    print("Using wrk for load testing")
    print("=" * 100)

    # Get API key
    print("\n🔑 Getting API key...")
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("❌ No API key found")
        print("\n💡 Provide API key via:")
        print("   1. Command line: --api-key YOUR_KEY")
        print("   2. Environment: export FULLON_API_KEY=YOUR_KEY")
        print("   3. File: examples/.beta1_api_key")
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

    # Check if wrk is installed
    print("\n🔍 Checking if wrk is installed...")
    try:
        # wrk --version returns exit code 1, so just check if command exists
        result = subprocess.run(["wrk", "--version"], capture_output=True)
        if "wrk" in result.stdout.decode() or "wrk" in result.stderr.decode():
            print("   ✅ wrk is installed")
        else:
            raise FileNotFoundError("wrk not found")
    except FileNotFoundError:
        print("❌ wrk is not installed")
        print("\n💡 Install wrk:")
        print("   sudo pacman -S wrk  # Arch Linux")
        print("   sudo apt install wrk  # Ubuntu/Debian")
        print("   brew install wrk  # macOS")
        sys.exit(1)

    # Determine stress test parameters
    scenario = SCENARIOS[args.scenario]
    threads = args.threads if args.threads else scenario["threads"]
    connections = args.connections if args.connections else scenario["connections"]
    duration = args.duration if args.duration else scenario["duration"]

    print(f"\n📊 Stress Test Configuration:")
    print(f"   Scenario: {args.scenario.upper()}")
    print(f"   Description: {scenario['description']}")
    print(f"   Threads: {threads}")
    print(f"   Connections: {connections}")
    print(f"   Duration: {duration}s")
    print(f"   Timeframe: {args.timeframe}")
    print(f"   Limit: {args.limit}")

    # Create Lua script for wrk with API key authentication
    lua_script_content = create_wrk_lua_script(api_key)

    # Use temporary file for Lua script
    with tempfile.NamedTemporaryFile(mode='w', suffix='.lua', delete=False) as lua_file:
        lua_file.write(lua_script_content)
        lua_script_path = lua_file.name

    try:
        # Define symbols to test
        symbols_to_test = []

        if args.all or (not args.exchange and not args.symbol):
            # Test all 4 symbols
            symbols_to_test = [
                ("bitmex", "BTC/USD:BTC"),
                ("bitmex", "ETH/USD:BTC"),
                ("yahoo", "GOLD"),
                ("yahoo", "SPX"),
            ]
            print(f"\n📊 Testing ALL symbols...")
        elif args.exchange and args.symbol:
            # Test specific symbol
            symbols_to_test = [(args.exchange, args.symbol)]
            print(f"\n📊 Testing {args.symbol} ({args.exchange})...")
        else:
            print("❌ Error: Must specify both --exchange and --symbol, or use --all")
            sys.exit(1)

        # Run stress tests for each symbol
        results = []
        for exchange, symbol in symbols_to_test:
            print(f"\n{'=' * 100}")
            print(f"Testing: {exchange.upper()} - {symbol}")
            print(f"{'=' * 100}")

            # Build URL for this symbol
            url = build_ohlcv_url(exchange, symbol, args.timeframe, args.limit)

            # Run wrk test
            result = run_wrk_test(url, lua_script_path, threads, connections, duration)

            results.append({
                "exchange": exchange,
                "symbol": f"{exchange}/{symbol}",
                "result": result
            })

        # Print summary
        print_summary(results)

        # Check if all tests passed
        all_passed = all(r["result"]["success"] for r in results)
        if all_passed:
            print("✅ All stress tests completed successfully")
        else:
            print("⚠️  Some stress tests failed")
            sys.exit(1)

    finally:
        # Clean up temporary Lua script
        try:
            Path(lua_script_path).unlink()
        except:
            pass

    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
