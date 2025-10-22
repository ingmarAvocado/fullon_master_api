"""
Main entry point for Fullon Master API.

Usage:
    uvicorn fullon_master_api.main:app --reload
    # or
    python -m fullon_master_api.main
"""

if __name__ == "__main__":
    import uvicorn

    from .config import settings

    uvicorn.run(
        "fullon_master_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
