"""
Master API Gateway - Main application entry point.

Composes existing Fullon APIs (ORM, OHLCV, Cache) with centralized JWT authentication.
Follows ADR-001: Router Composition Over Direct Library Usage.
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fullon_log import get_component_logger
from fullon_ohlcv_api import get_all_routers as get_ohlcv_routers
from fullon_orm_api import get_all_routers as get_orm_routers
from fullon_orm_api.dependencies.auth import get_current_user as orm_get_current_user

from .auth.dependencies import get_current_user as master_get_current_user
from .auth.middleware import JWTMiddleware
from .config import settings
from .routers.auth import router as auth_router
from .routers.services import router as services_router
from .services.manager import ServiceManager


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
        self.logger = get_component_logger("fullon.master_api")
        # Initialize ServiceManager for async background tasks
        self.service_manager = ServiceManager()
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

        # Set ServiceManager in app state for dependency injection
        app.state.service_manager = self.service_manager

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
        # Exclude cache WebSocket paths - they use their own authenticate_websocket() function
        app.add_middleware(
            JWTMiddleware,
            secret_key=settings.jwt_secret_key,
            exclude_paths=[
                "/",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/health",
                f"{settings.api_prefix}/auth/login",
                f"{settings.api_prefix}/auth/verify",
                f"{settings.api_prefix}/cache/ws/*",  # Cache WebSocket endpoints (wildcard)
            ],
        )

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

        # Include service control router (admin-only)
        app.include_router(services_router, prefix=settings.api_prefix)

        # Mount ORM API routers (NEW - Issue #17)
        self._mount_orm_routers(app)

        # Mount OHLCV API routers (Phase 4 - NEW)
        self._mount_ohlcv_routers(app)

        # Mount Cache API WebSocket routers (Phase 5 - NEW)
        self._mount_cache_routers(app)

        # Add shutdown handler for graceful service stopping
        @app.on_event("shutdown")
        async def shutdown_event():
            """Gracefully stop all services on shutdown."""
            self.logger.info("Shutting down services...")
            await self.service_manager.stop_all()
            self.logger.info("All services stopped")

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
                prefix=getattr(router, "prefix", None),
                tags=getattr(router, "tags", []),
            )

        # Apply auth dependency overrides (NEW in Issue #16)
        orm_routers = self._apply_auth_overrides(orm_routers)

        return orm_routers

    def _discover_ohlcv_routers(self) -> list:
        """
        Discover all routers from fullon_ohlcv_api.

        Returns OHLCV API routers without mounting them. This allows
        inspection and validation before integration.

        Returns:
            List of APIRouter instances from fullon_ohlcv_api

        Raises:
            ImportError: If fullon_ohlcv_api is not installed
            RuntimeError: If router discovery fails
        """
        try:
            # Get OHLCV routers from fullon_ohlcv_api
            ohlcv_routers = get_ohlcv_routers()

            # Validate we got routers back
            if not ohlcv_routers:
                self.logger.warning("No OHLCV routers discovered")
                return []

            # Apply auth override to each router
            for router in ohlcv_routers:
                self._apply_ohlcv_auth_overrides(router)

            self.logger.info(
                "OHLCV routers discovered with auth override", router_count=len(ohlcv_routers)
            )

            return ohlcv_routers

        except ImportError as e:
            self.logger.error("fullon_ohlcv_api import failed", error=str(e))
            raise ImportError(
                "fullon_ohlcv_api not installed. Run: pip install fullon_ohlcv_api"
            ) from e
        except Exception as e:
            self.logger.error("OHLCV router discovery failed", error=str(e))
            raise RuntimeError("Failed to discover OHLCV routers") from e

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
            if not hasattr(router, "dependency_overrides"):
                router.dependency_overrides = {}

            # Override ORM API's get_current_user with master API's version
            router.dependency_overrides[orm_get_current_user] = master_get_current_user

            # Structured logging (key=value pattern from fullon_log)
            self.logger.debug(
                "Auth dependency overridden for ORM router",
                prefix=getattr(router, "prefix", None),
                override_count=len(router.dependency_overrides),
            )

        self.logger.info("Auth overrides applied to ORM routers", router_count=len(routers))

        return routers

    def _apply_ohlcv_auth_overrides(self, router) -> None:
        """
        Override auth dependencies in router to use master API auth.

        Replaces any existing auth dependencies in OHLCV router routes
        with master API's get_current_user dependency. This ensures
        OHLCV endpoints use centralized JWT authentication.

        WHY OHLCV REQUIRES AUTHENTICATION:
        - Read-only endpoints still need user identification for access control
        - Enables per-user rate limiting and audit logging
        - Consistent with master API security model (all endpoints require auth)
        - Allows tracking which users access which market data

        Args:
            router: APIRouter to override auth dependencies
        """
        override_count = 0

        for route in router.routes:
            if hasattr(route, "dependant"):
                # Inspect route dependencies
                dependencies = route.dependant.dependencies

                # Look for auth-related dependencies to override
                auth_dependency_found = False
                for dep in dependencies:
                    # Check if dependency might be auth-related
                    # (This is a heuristic - adjust based on fullon_ohlcv_api's actual auth)
                    if hasattr(dep, "call") and dep.call:
                        dep_name = getattr(dep.call, "__name__", "")

                        # Override if looks like auth dependency
                        if "auth" in dep_name.lower() or "user" in dep_name.lower():
                            # Replace with master API auth
                            dep.call = master_get_current_user
                            override_count += 1
                            auth_dependency_found = True

                            self.logger.debug(
                                "Auth dependency overridden",
                                route_path=route.path,
                                original_dep=dep_name,
                                new_dep="get_current_user",
                            )

                # If no auth dependency found, ADD it (OHLCV requires auth)
                if not auth_dependency_found:
                    # Add get_current_user as dependency
                    route.dependencies.append(Depends(master_get_current_user))
                    override_count += 1

                    self.logger.debug(
                        "Auth dependency added",
                        route_path=route.path,
                        dependency="get_current_user",
                    )

        self.logger.info(
            "Auth overrides applied to OHLCV router",
            route_count=len(router.routes),
            overrides=override_count,
        )

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
            router_prefix = getattr(router, "prefix", "")
            router_tags = getattr(router, "tags", [])

            # Mount with /api/v1/orm prefix
            app.include_router(router, prefix=f"{settings.api_prefix}/orm")

            # Structured logging (fullon_log pattern)
            self.logger.info(
                "ORM router mounted",
                prefix=f"{settings.api_prefix}/orm{router_prefix}",
                tags=router_tags,
                route_count=len(router.routes),
            )

        self.logger.info(
            "All ORM routers mounted",
            total_routers=len(orm_routers),
            base_prefix=f"{settings.api_prefix}/orm",
        )

    def _mount_ohlcv_routers(self, app: FastAPI) -> None:
        """
        Mount fullon_ohlcv_api routers with auth override.

        Mounts OHLCV routers at /api/v1/ohlcv/* prefix following ADR-001.
        Auth dependencies are overridden to use master API JWT auth.

        Args:
            app: FastAPI application instance
        """
        # Discover OHLCV routers (includes auth override from Issue #26)
        ohlcv_routers = self._discover_ohlcv_routers()

        if not ohlcv_routers:
            self.logger.warning("No OHLCV routers to mount")
            return

        # Mount each router with OHLCV prefix
        # IMPORTANT: Mount in reverse order so more specific routes (with more path params)
        # are registered first and matched before less specific routes
        for router in reversed(ohlcv_routers):
            # Get router metadata
            router_prefix = getattr(router, "prefix", "")
            router_tags = getattr(router, "tags", [])

            # Mount with /api/v1/ohlcv prefix (always add category prefix)
            app.include_router(router, prefix=f"{settings.api_prefix}/ohlcv")

            # Structured logging (fullon_log pattern)
            self.logger.info(
                "OHLCV router mounted",
                prefix=f"{settings.api_prefix}/ohlcv{router_prefix}",
                tags=router_tags,
                route_count=len(router.routes),
            )

            # Log individual routes for debugging
            for route in router.routes:
                self.logger.debug(
                    "OHLCV route registered",
                    path=route.path,
                    methods=getattr(route, "methods", ["GET"]),
                    name=getattr(route, "name", "unknown"),
                )

        self.logger.info(
            "All OHLCV routers mounted",
            total_routers=len(ohlcv_routers),
            base_prefix=f"{settings.api_prefix}/ohlcv",
        )

    def _mount_cache_routers(self, app: FastAPI) -> None:
        """
        Mount cache WebSocket routers from fullon_cache_api.

        This mounts 8 WebSocket endpoints:
        - /ws/tickers/{connection_id}
        - /ws/orders/{connection_id}
        - /ws/trades/{connection_id}
        - /ws/accounts/{connection_id}
        - /ws/bots/{connection_id}
        - /ws/ohlcv/{connection_id}
        - /ws/process/{connection_id}
        """
        from fullon_cache_api.main import create_app as create_cache_app

        # Get cache app with all 8 WebSocket routers
        cache_app = create_cache_app()

        # Mount cache app under /api/v1/cache prefix
        app.mount("/api/v1/cache", cache_app)

        self.logger.info(
            "Cache WebSocket routers mounted",
            prefix="/api/v1/cache",
            endpoint_count=8,
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
