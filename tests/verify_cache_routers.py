"""Verify cache routers are discoverable."""
from fullon_cache_api import create_app


def main():
    cache_app = create_app()

    print("Cache API Routes:")
    for route in cache_app.routes:
        print(f"  {route.path} -> {route.name}")

    assert len(cache_app.routes) >= 8, "Expected at least 8 WebSocket routes"
    print(f"\nTotal routes: {len(cache_app.routes)}")

if __name__ == "__main__":
    main()
