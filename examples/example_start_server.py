#!/usr/bin/env python3
"""
Example: Start Server

Demonstrates:
- Starting the Fullon Master API server programmatically
- Using uvicorn to run the FastAPI application
- Configuration via environment variables
- Graceful shutdown handling

Usage:
    python examples/example_start_server.py

    Or use the Makefile:
    make run

Expected Output:
    INFO:     Started server process [12345]
    INFO:     Waiting for application startup.
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://0.0.0.0:8000
"""
import uvicorn
import sys
from pathlib import Path

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fullon_master_api.config import settings
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.start_server")


def start_server(
    host: str = None,
    port: int = None,
    reload: bool = None,
    log_level: str = None,
):
    """
    Start the Fullon Master API server.

    Args:
        host: Server host (default from settings)
        port: Server port (default from settings)
        reload: Enable auto-reload (default from settings)
        log_level: Logging level (default from settings)
    """
    # Use provided values or fall back to settings
    host = host or settings.host
    port = port or settings.port
    reload = reload if reload is not None else settings.reload
    log_level = log_level or settings.log_level.lower()

    logger.info(
        "Starting Fullon Master API",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )

    print("=" * 60)
    print("🚀 Fullon Master API - Server Starting")
    print("=" * 60)
    print(f"Host:      {host}")
    print(f"Port:      {port}")
    print(f"Reload:    {reload}")
    print(f"Log Level: {log_level}")
    print(f"\n📖 API Documentation:")
    print(f"   Swagger UI: http://{host}:{port}/docs")
    print(f"   ReDoc:      http://{host}:{port}/redoc")
    print(f"   Health:     http://{host}:{port}/health")
    print("\n💡 Press CTRL+C to stop the server")
    print("=" * 60)
    print()

    # Start uvicorn server
    try:
        uvicorn.run(
            "fullon_master_api.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
        )
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        print("\n\n✅ Server stopped gracefully")
    except Exception as e:
        logger.error("Server startup failed", error=str(e))
        print(f"\n\n❌ Server failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start Fullon Master API server")
    parser.add_argument("--host", type=str, help="Server host")
    parser.add_argument("--port", type=int, help="Server port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", type=str, help="Logging level")

    args = parser.parse_args()

    start_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
