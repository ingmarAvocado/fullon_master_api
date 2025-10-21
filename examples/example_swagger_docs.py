#!/usr/bin/env python3
"""
Example: Accessing API Documentation

Demonstrates:
- Opening Swagger UI documentation
- Opening ReDoc documentation
- Viewing OpenAPI schema programmatically
- Listing all available endpoints

Usage:
    python examples/example_swagger_docs.py
    python examples/example_swagger_docs.py --open-browser

Expected Output:
- Lists all API endpoints
- Optionally opens browser to documentation
"""
import asyncio
import httpx
import webbrowser
import argparse
from typing import Optional
from fullon_log import get_component_logger

logger = get_component_logger("fullon.examples.swagger_docs")

API_BASE_URL = "http://localhost:8000"


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
            print("   Run: make run")
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


async def main(open_browser_flag: bool = False):
    """Run API documentation example."""
    print("=" * 60)
    print("Fullon Master API - Documentation Explorer")
    print("=" * 60)

    # Show documentation URLs
    show_documentation_urls()

    # Fetch OpenAPI schema
    print("\n⏳ Fetching OpenAPI schema...")
    schema = await get_openapi_schema()

    if not schema:
        print("\n⚠️  Could not fetch schema - is the server running?")
        print("\nTo start the server:")
        print("  make run")
        print("=" * 60)
        return

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Documentation Explorer")
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open Swagger UI in browser",
    )

    args = parser.parse_args()

    asyncio.run(main(args.open_browser))
