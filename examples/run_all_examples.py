#!/usr/bin/env python3
"""
Run All Examples - Test Suite for Fullon Master API

Executes all example scripts in sequence to demonstrate and verify functionality.

Usage:
    python examples/run_all_examples.py
    python examples/run_all_examples.py --skip-websocket
"""
import asyncio
import argparse
import sys
from pathlib import Path
from typing import List, Tuple
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.run_all")

# Add examples to path
sys.path.insert(0, str(Path(__file__).parent))

# Import all example modules
import example_health_check
import example_swagger_docs
import example_jwt_login
import example_authenticated_request
import example_orm_routes
import example_ohlcv_routes
import example_cache_websocket


async def run_example(name: str, coro) -> Tuple[str, bool, str]:
    """
    Run a single example and capture result.

    Args:
        name: Example name
        coro: Coroutine to execute

    Returns:
        Tuple of (name, success, error_message)
    """
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}\n")

    try:
        await coro
        logger.info(f"Example completed successfully", example=name)
        return (name, True, "")

    except Exception as e:
        logger.error(f"Example failed", example=name, error=str(e))
        return (name, False, str(e))


async def run_all(skip_websocket: bool = False):
    """
    Run all examples in sequence.

    Args:
        skip_websocket: Skip WebSocket example (takes longer)
    """
    print("=" * 60)
    print("Fullon Master API - Running All Examples")
    print("=" * 60)

    results: List[Tuple[str, bool, str]] = []

    # Example 1: Health Check (always first - verifies server is running)
    results.append(
        await run_example("Health Check", example_health_check.main())
    )

    # Example 2: Swagger Documentation
    results.append(
        await run_example(
            "Swagger Documentation", example_swagger_docs.main(open_browser_flag=False)
        )
    )

    # Example 3: JWT Login
    results.append(
        await run_example(
            "JWT Login", example_jwt_login.main(username="admin", password="admin")
        )
    )

    # Example 4: Authenticated Requests
    results.append(
        await run_example("Authenticated Requests", example_authenticated_request.main())
    )

    # Example 5: ORM Routes
    results.append(await run_example("ORM Routes", example_orm_routes.main()))

    # Example 6: OHLCV Routes
    results.append(await run_example("OHLCV Routes", example_ohlcv_routes.main()))

    # Example 7: Cache WebSocket (optional - takes time)
    if not skip_websocket:
        results.append(
            await run_example(
                "Cache WebSocket",
                example_cache_websocket.main(duration=5),  # Short duration for testing
            )
        )
    else:
        print("\n⏭️  Skipping WebSocket example (--skip-websocket flag)")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Example Results Summary")
    print("=" * 60)

    passed = 0
    failed = 0

    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:10} {name}")
        if not success and error:
            print(f"           Error: {error[:60]}")

        if success:
            passed += 1
        else:
            failed += 1

    print("=" * 60)
    print(f"Total: {len(results)} examples")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\n⚠️  Some examples failed (likely endpoints not yet implemented)")
        print("   This is expected during development!")
    else:
        print("\n✅ All examples passed!")

    print("=" * 60)

    # Return exit code
    return 0 if failed == 0 else 1


async def main(skip_websocket: bool = False):
    """Main entry point."""
    print("\n🚀 Starting example test suite...\n")

    # Check if server is running first
    print("⏳ Checking if server is running...")
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health", timeout=2.0)
            if response.status_code == 200:
                print("✅ Server is running!\n")
            else:
                print(f"⚠️  Server returned status {response.status_code}\n")

    except (httpx.ConnectError, httpx.TimeoutException):
        print("❌ Server is not running!")
        print("\nPlease start the server first:")
        print("  make run")
        print("  # or")
        print("  python examples/example_start_server.py\n")
        return 1

    # Run all examples
    exit_code = await run_all(skip_websocket)

    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run all Fullon Master API examples")
    parser.add_argument(
        "--skip-websocket",
        action="store_true",
        help="Skip WebSocket example (takes longer to run)",
    )

    args = parser.parse_args()

    exit_code = asyncio.run(main(skip_websocket=args.skip_websocket))
    sys.exit(exit_code)
