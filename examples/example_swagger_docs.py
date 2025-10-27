#!/usr/bin/env python3
"""
Example: Accessing API Documentation - Self-Contained Test

THIS EXAMPLE IS FULLY SELF-CONTAINED:
- Starts its own embedded test server
- Fetches OpenAPI schema programmatically
- Lists all available endpoints
- Stops the server when done

NO EXTERNAL SETUP REQUIRED - just run it!

Usage:
    python examples/example_swagger_docs.py
    python examples/example_swagger_docs.py --open-browser

Demonstrates:
- Opening Swagger UI documentation
- Opening ReDoc documentation
- Viewing OpenAPI schema programmatically
- Listing all available endpoints

Expected Output:
- Lists all API endpoints
- Optionally opens browser to documentation
"""
import asyncio
import httpx
import os
import sys
import webbrowser
import argparse
from pathlib import Path
from typing import Optional

# Load .env file FIRST before ANY other imports (critical for env var caching)
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv

    load_dotenv(project_root / ".env", override=True)  # Load .env first
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

# Disable service auto-start for examples (we only need the API, not background services)
os.environ["SERVICE_AUTO_START_ENABLED"] = "false"
os.environ["HEALTH_MONITOR_ENABLED"] = "false"

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.swagger_docs")

API_BASE_URL = "http://localhost:8000"


async def start_test_server():
    """Start uvicorn server as async background task."""
    import uvicorn
    from fullon_master_api.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    return server, task


async def wait_for_server(url: str, timeout: int = 30, interval: float = 0.5) -> bool:
    """
    Poll server health endpoint until ready or timeout.

    Args:
        url: Base URL of the server (e.g., "http://localhost:8000")
        timeout: Maximum seconds to wait for server
        interval: Seconds between polling attempts

    Returns:
        True if server is ready, False if timeout
    """
    start_time = asyncio.get_event_loop().time()

    async with httpx.AsyncClient() as client:
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                response = await client.get(f"{url}/health", timeout=1.0)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                # Server not ready yet, continue polling
                pass

            await asyncio.sleep(interval)

    return False


async def get_openapi_schema() -> Optional[dict]:
    """
    Fetch OpenAPI schema from API.

    Returns:
        dict: OpenAPI schema
        None: If fetch failed
    """
    schema_url = f"{API_BASE_URL}/openapi.json"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(schema_url)
            response.raise_for_status()

            schema = response.json()
            logger.info("OpenAPI schema retrieved", version=schema.get("openapi"))
            return schema

        except httpx.ConnectError:
            logger.error("Cannot connect to API")
            print("\n❌ Connection Failed")
            print(f"   Server not running on {API_BASE_URL}")
            return None

        except httpx.HTTPStatusError as e:
            logger.error("Failed to fetch schema", status_code=e.response.status_code)
            return None


def list_endpoints(schema: dict):
    """
    List all API endpoints from OpenAPI schema.

    Args:
        schema: OpenAPI schema dictionary
    """
    print("\n📋 Available API Endpoints:")
    print("=" * 60)

    paths = schema.get("paths", {})

    if not paths:
        print("   No endpoints found (schema may be empty)")
        return

    for path, methods in sorted(paths.items()):
        for method, details in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                summary = details.get("summary", "No description")
                tags = details.get("tags", [])
                tag_str = f"[{', '.join(tags)}]" if tags else ""

                print(f"\n{method.upper():6} {path}")
                print(f"       {summary}")
                if tag_str:
                    print(f"       Tags: {tag_str}")

                # Show if authentication required
                security = details.get("security", [])
                if security:
                    print("       🔒 Requires authentication")


def show_documentation_urls():
    """Display documentation URLs."""
    print("\n🌐 API Documentation:")
    print("=" * 60)
    print(f"📖 Swagger UI (Interactive):  {API_BASE_URL}/docs")
    print(f"📘 ReDoc (Alternative):       {API_BASE_URL}/redoc")
    print(f"📄 OpenAPI Schema (JSON):     {API_BASE_URL}/openapi.json")
    print(f"❤️  Health Check:              {API_BASE_URL}/health")
    print(f"🏠 API Root:                  {API_BASE_URL}/")


def open_documentation(open_browser: bool = False):
    """
    Open API documentation in browser.

    Args:
        open_browser: If True, open browser automatically
    """
    if open_browser:
        print("\n🌐 Opening Swagger UI in browser...")
        webbrowser.open(f"{API_BASE_URL}/docs")

        print("\n💡 You can also visit:")
        print(f"   ReDoc: {API_BASE_URL}/redoc")
    else:
        print("\n💡 To open documentation in browser:")
        print(f"   Visit: {API_BASE_URL}/docs")
        print(f"   Or run: python examples/example_swagger_docs.py --open-browser")


async def show_api_info(schema: dict):
    """
    Display API information from schema.

    Args:
        schema: OpenAPI schema dictionary
    """
    info = schema.get("info", {})

    print("\n📊 API Information:")
    print("=" * 60)
    print(f"Title:       {info.get('title', 'N/A')}")
    print(f"Version:     {info.get('version', 'N/A')}")
    print(f"Description: {info.get('description', 'N/A')}")
    print(f"OpenAPI:     {schema.get('openapi', 'N/A')}")


async def show_tags(schema: dict):
    """
    Display API tags/categories.

    Args:
        schema: OpenAPI schema dictionary
    """
    tags = schema.get("tags", [])

    if tags:
        print("\n🏷️  API Categories:")
        print("=" * 60)
        for tag in tags:
            name = tag.get("name", "")
            description = tag.get("description", "")
            print(f"• {name}")
            if description:
                print(f"  {description}")


async def run_examples(open_browser_flag: bool = False):
    """Run API documentation examples."""
    print("\n" + "=" * 60)
    print("API Documentation Explorer")
    print("=" * 60)

    # Show documentation URLs
    show_documentation_urls()

    # Fetch OpenAPI schema
    print("\n⏳ Fetching OpenAPI schema...")
    schema = await get_openapi_schema()

    if not schema:
        print("\n⚠️  Could not fetch schema")
        return False

    # Show API info
    await show_api_info(schema)

    # Show API categories
    await show_tags(schema)

    # List all endpoints
    list_endpoints(schema)

    # Open browser if requested
    open_documentation(open_browser_flag)

    print("\n" + "=" * 60)
    print("💡 Quick Tips:")
    print("   - Swagger UI allows testing endpoints interactively")
    print("   - Use the 'Authorize' button to add JWT token")
    print("   - ReDoc provides cleaner documentation view")
    print("   - OpenAPI schema can be used to generate client SDKs")
    print("=" * 60)

    return True


async def main(open_browser_flag: bool = False):
    """
    Main entry point - self-contained with setup and cleanup.
    """
    print("=" * 60)
    print("Fullon Master API - Documentation Explorer")
    print("SELF-CONTAINED: Starts, explores, and stops server automatically")
    print("=" * 60)

    server = None
    server_task = None
    try:
        # Start embedded test server
        print("\n1. Starting test server on localhost:8000...")
        server, server_task = await start_test_server()

        # Wait for server to be ready (polls health endpoint)
        if not await wait_for_server(API_BASE_URL, timeout=10):
            raise RuntimeError("Server failed to start within 10 seconds")

        print("   ✅ Server started")

        # Run examples
        success = await run_examples(open_browser_flag)

        if not success:
            logger.error("Documentation examples failed")

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

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Documentation Explorer")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open Swagger UI in browser",
    )

    args = parser.parse_args()

    asyncio.run(main(args.open_browser))
