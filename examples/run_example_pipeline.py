#!/usr/bin/env python3
"""
Example: Full Pipeline with Master API Server

Demonstrates the complete API testing pipeline:
1. Set up isolated test database
2. Start API server in background
3. Run all API examples
4. Clean up server and database

Usage:
    python examples/run_example_pipeline.py
    python examples/run_example_pipeline.py --skip-websocket
"""

import asyncio
import contextlib
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# CRITICAL: Set test database name FIRST, before ANY imports
from demo_data import generate_test_db_name

test_db_base = generate_test_db_name()
test_db_orm = test_db_base
test_db_ohlcv = f"{test_db_base}_ohlcv"

os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv

# Now safe to import modules
from demo_data import create_dual_test_databases, drop_dual_test_databases, install_demo_data
from fullon_log import get_component_logger
from fullon_orm import init_db

logger = get_component_logger("fullon.master_api.pipeline.test")


async def set_database():
    """Set up dual test databases for full API testing."""
    print("\n🔍 Setting up dual test databases for API testing")
    print("=" * 50)

    logger.debug("Creating dual test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)
    orm_db_name, ohlcv_db_name = await create_dual_test_databases(test_db_base)
    logger.debug("Using dual test databases", orm_db=orm_db_name, ohlcv_db=ohlcv_db_name)

    # Initialize database schema
    logger.debug("Initializing database schema")
    await init_db()

    # Install demo data
    logger.debug("Installing demo data")
    await install_demo_data()
    logger.info("Demo data installed successfully")


async def start_api_server():
    """Start the FastAPI server in the background."""
    print("\n🚀 Starting Fullon Master API server...")

    # Import after database is set up
    from fullon_master_api.app import app
    import uvicorn

    # Create config for server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False,  # Reduce noise in tests
    )

    server = uvicorn.Server(config)

    # Start server in background task
    server_task = asyncio.create_task(server.serve())

    # Wait for server to be ready
    print("⏳ Waiting for server to start...")
    await asyncio.sleep(3)

    # Verify server is running
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health", timeout=2.0)
            if response.status_code == 200:
                print("✅ Server is running!")
            else:
                print(f"⚠️  Server returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Server health check failed: {e}")
        raise

    return server, server_task


async def stop_api_server(server, server_task):
    """Stop the FastAPI server gracefully."""
    print("\n⏹️  Stopping API server...")

    # Signal server to shutdown
    server.should_exit = True

    # Cancel the server task
    server_task.cancel()

    # Wait for graceful shutdown
    with contextlib.suppress(asyncio.CancelledError):
        await server_task

    print("✅ Server stopped")


async def run_examples(skip_websocket: bool = False):
    """Run all API examples."""
    print("\n📊 Running API examples...")

    import run_all_examples

    success = await run_all_examples.run_all(skip_websocket=skip_websocket)
    return success == 0


async def run_pipeline(skip_websocket: bool = False):
    """Run the complete API testing pipeline."""
    print("\n🧪 FULL API TESTING PIPELINE")
    print("=" * 60)

    server = None
    server_task = None

    try:
        # Phase 1: Database setup
        print("\n📚 Phase 1: Database Setup")
        await set_database()
        print("✅ Database setup complete")

        # Phase 2: Start API server
        print("\n🌐 Phase 2: API Server Startup")
        server, server_task = await start_api_server()
        print("✅ API server started")

        # Phase 3: Run examples
        print("\n🧪 Phase 3: Running Examples")
        success = await run_examples(skip_websocket=skip_websocket)

        if success:
            print("\n✅ All examples passed!")
        else:
            print("\n⚠️  Some examples failed")

        return success

    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        logger.exception("Pipeline failed")
        return False

    finally:
        # Phase 4: Cleanup
        print("\n🧹 Phase 4: Cleanup")

        if server and server_task:
            await stop_api_server(server, server_task)

        try:
            logger.debug("Dropping dual test databases", orm_db=test_db_orm, ohlcv_db=test_db_ohlcv)
            await drop_dual_test_databases(test_db_orm, test_db_ohlcv)
            logger.debug("Test databases cleaned up successfully")
            print("✅ Database cleanup complete")
        except Exception as db_cleanup_error:
            logger.warning("Error during database cleanup", error=str(db_cleanup_error))
            print(f"⚠️  Database cleanup warning: {db_cleanup_error}")


async def main(skip_websocket: bool = False):
    """Run the complete pipeline example."""
    start_time = datetime.now()

    print("=" * 60)
    print("🧪 FULLON MASTER API - FULL TESTING PIPELINE")
    print("=" * 60)
    print("\nPattern:")
    print("  Phase 1: Set up isolated test databases")
    print("  Phase 2: Start FastAPI server in background")
    print("  Phase 3: Run all API examples")
    print("  Phase 4: Clean up server and databases")
    print("\n" + "=" * 60)

    try:
        # Run the pipeline
        success = await run_pipeline(skip_websocket=skip_websocket)

        # Print summary
        elapsed = (datetime.now() - start_time).total_seconds()

        print("\n" + "=" * 60)
        if success:
            print("✅ FULL PIPELINE TEST COMPLETED SUCCESSFULLY")
        else:
            print("⚠️  PIPELINE TEST COMPLETED WITH WARNINGS")
        print("=" * 60)

        print(f"\n⏱️  Total time: {elapsed:.2f} seconds")
        print("\n📋 Summary:")
        print("  ✅ Isolated test database setup")
        print("  ✅ API server lifecycle management")
        print("  ✅ Example execution")
        print("  ✅ Automatic cleanup")
        print("\n💡 Pipeline ready for CI/CD integration")

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user")
        logger.warning("Pipeline interrupted by user")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        print(f"\n❌ Pipeline test failed: {e}")
        logger.exception("Pipeline test failed")
        return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run full Fullon Master API testing pipeline")
    parser.add_argument(
        "--skip-websocket",
        action="store_true",
        help="Skip WebSocket example (takes longer to run)",
    )

    args = parser.parse_args()

    # Set up signal handling for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n⚠️  Received interrupt signal, shutting down...")
        sys.exit(130)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    exit_code = asyncio.run(main(skip_websocket=args.skip_websocket))
    sys.exit(exit_code)
