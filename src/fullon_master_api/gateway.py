"""
Master API Gateway - Main application entry point.

Composes existing Fullon APIs (ORM, OHLCV, Cache) with centralized JWT authentication.
Follows ADR-001: Router Composition Over Direct Library Usage.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fullon_log import get_component_logger
from fullon_orm_api import get_all_routers as get_orm_routers
from fullon_orm_api.dependencies.auth import get_current_user as orm_get_current_user

from .auth.dependencies import get_current_user as master_get_current_user
from .auth.middleware import JWTMiddleware
from .config import settings
from .routers.auth import router as auth_router


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
        # CRITICAL: Create component-specific logger
        self.logger = get_component_logger("fullon.master_api.gateway")
        self.app = self._create_app()
        self.logger.info("Master API Gateway initialized")

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

        self.logger.info(
            "CORS middleware configured",
            origins=settings.cors_origins,
        )

        # Add JWT authentication middleware
        app.add_middleware(JWTMiddleware, secret_key=settings.jwt_secret_key)

        self.logger.info("JWT middleware configured")

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

        # Mount ORM API routers (NEW - Issue #17)
        self._mount_orm_routers(app)

        self.logger.info(
            "FastAPI application created",
            title=settings.api_title,
            version=settings.api_version,
        )

        return app

    def _discover_orm_routers(self) -> list:
        """
        Discover ORM API routers and apply auth overrides.

        Returns:
            List of APIRouter instances with auth overrides applied
        """
        orm_routers = get_orm_routers()

        # Structured logging with key=value pairs
        self.logger.info("Discovered ORM routers", count=len(orm_routers))

        for router in orm_routers:
            self.logger.debug(
                "ORM router discovered",
                prefix=getattr(router, 'prefix', None),
                tags=getattr(router, 'tags', [])
            )

        # Apply auth dependency overrides (NEW in Issue #16)
        orm_routers = self._apply_auth_overrides(orm_routers)

        return orm_routers

    def _apply_auth_overrides(self, routers: list) -> list:
        """
        Apply auth dependency overrides to ORM routers.

        Overrides fullon_orm_api's get_current_user dependency with
        master API's version that reads from request.state.user.

        Critical: Both dependencies return User ORM model instances (NOT dictionaries).
        Reference: docs/FULLON_ORM_LLM_README.md lines 1-9

        Args:
            routers: List of APIRouter instances from fullon_orm_api

        Returns:
            List of routers with auth overrides applied
        """
        for router in routers:
            # Initialize dependency_overrides if it doesn't exist
            if not hasattr(router, 'dependency_overrides'):
                router.dependency_overrides = {}

            # Override ORM API's get_current_user with master API's version
            router.dependency_overrides[orm_get_current_user] = master_get_current_user

            # Structured logging (key=value pattern from fullon_log)
            self.logger.debug(
                "Auth dependency overridden for ORM router",
                prefix=getattr(router, 'prefix', None),
                override_count=len(router.dependency_overrides)
            )

        self.logger.info(
            "Auth overrides applied to ORM routers",
            router_count=len(routers)
        )

        return routers

    def _mount_orm_routers(self, app: FastAPI) -> None:
        """
        Mount fullon_orm_api routers with auth override.

        Mounts ORM routers at /api/v1/orm/* prefix following ADR-001.
        Auth dependencies are overridden to use master API JWT auth.

        Args:
            app: FastAPI application instance
        """
        # Discover ORM routers (includes auth override from Issue #16)
        orm_routers = self._discover_orm_routers()

        # Mount each router with ORM prefix
        for router in orm_routers:
            # Get router metadata
            router_prefix = getattr(router, 'prefix', '')
            router_tags = getattr(router, 'tags', [])

            # Mount with /api/v1/orm prefix
            app.include_router(
                router,
                prefix=f"{settings.api_prefix}/orm"
            )

            # Structured logging (fullon_log pattern)
            self.logger.info(
                "ORM router mounted",
                prefix=f"{settings.api_prefix}/orm{router_prefix}",
                tags=router_tags,
                route_count=len(router.routes)
            )

        self.logger.info(
            "All ORM routers mounted",
            total_routers=len(orm_routers),
            base_prefix=f"{settings.api_prefix}/orm"
        )

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
