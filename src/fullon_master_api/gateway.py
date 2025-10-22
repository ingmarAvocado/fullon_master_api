"""
Master API Gateway - Main application entry point.

Composes existing Fullon APIs (ORM, OHLCV, Cache) with centralized JWT authentication.
Follows ADR-001: Router Composition Over Direct Library Usage.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fullon_log import get_component_logger
from fullon_orm_api import get_all_routers as get_orm_routers

from .auth.middleware import JWTMiddleware
from .config import settings
from .routers.auth import router as auth_router

logger = get_component_logger("fullon.master_api.gateway")


class MasterGateway:
    """
    Main API Gateway composing all Fullon APIs.

    Architecture:
    - Composes fullon_orm_api, fullon_ohlcv_api, fullon_cache_api
    - Provides centralized JWT authentication via middleware
    - Proxies WebSocket connections for real-time data
    - Unified health monitoring across all subsystems

    ADR References:
    - ADR-001: Router Composition Over Direct Library Usage
    - ADR-002: WebSocket Proxy for Cache API
    - ADR-003: No Service Control in API Gateway
    - ADR-004: Authentication via Middleware
    """

    def __init__(self):
        """Initialize the Master API Gateway."""
        self.app = self._create_app()
        logger.info("Master API Gateway initialized")

    def _create_app(self) -> FastAPI:
        """
        Create and configure the FastAPI application.

        Returns:
            FastAPI: Configured application instance
        """
        app = FastAPI(
            title=settings.api_title,
            version=settings.api_version,
            description=settings.api_description,
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=settings.cors_allow_credentials,
            allow_methods=settings.cors_allow_methods,
            allow_headers=settings.cors_allow_headers,
        )

        logger.info(
            "CORS middleware configured",
            origins=settings.cors_origins,
        )

        # Add JWT authentication middleware
        app.add_middleware(JWTMiddleware, secret_key=settings.jwt_secret_key)

        logger.info("JWT middleware configured")

        # Basic health endpoint (no auth required)
        @app.get("/health")
        async def health():
            """Basic health check endpoint."""
            return {
                "status": "healthy",
                "version": settings.api_version,
                "service": "fullon_master_api",
            }

        @app.get("/")
        async def root():
            """API root endpoint with documentation links."""
            return {
                "service": settings.api_title,
                "version": settings.api_version,
                "docs": "/docs",
                "health": "/health",
                "api": settings.api_prefix,
            }

        # Include auth router
        app.include_router(auth_router, prefix=settings.api_prefix)

        logger.info(
            "FastAPI application created",
            title=settings.api_title,
            version=settings.api_version,
        )

        return app

    def _discover_orm_routers(self) -> list:
        """
        Discover ORM API routers from fullon_orm_api.

        Returns:
            List of APIRouter instances from fullon_orm_api
        """
        orm_routers = get_orm_routers()
        logger.info("Discovered ORM routers", count=len(orm_routers))

        for router in orm_routers:
            logger.debug(
                "ORM router discovered",
                prefix=getattr(router, 'prefix', None),
                tags=getattr(router, 'tags', [])
            )

        return orm_routers

    def get_app(self) -> FastAPI:
        """
        Get the configured FastAPI application.

        Returns:
            FastAPI: Application instance
        """
        return self.app


# Create gateway instance
gateway = MasterGateway()
app = gateway.get_app()
