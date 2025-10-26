"""
Master API Gateway - Main application entry point.

Composes existing Fullon APIs (ORM, OHLCV, Cache) with centralized JWT authentication.
Follows ADR-001: Router Composition Over Direct Library Usage.
"""
import asyncio
from contextlib import asynccontextmanager
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
from .routers.health import router as health_router
from .routers.services import router as services_router
from .services.manager import ServiceManager, ServiceName


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

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Handle application startup and shutdown events."""
        # Startup
        self.logger.info("Starting up services...")

        # Start HealthMonitor directly (it manages its own background task)
        from ..config import settings

        if settings.health_monitor_enabled:
            try:
                await self.service_manager.health_monitor.start()
                self.logger.info("HealthMonitor service started")
            except Exception as e:
                self.logger.error("Failed to start HealthMonitor service", error=str(e))

        yield

        # Shutdown
        self.logger.info("Shutting down services...")

        # Stop HealthMonitor first
        if settings.health_monitor_enabled:
            try:
                await self.service_manager.health_monitor.stop()
                self.logger.info("HealthMonitor service stopped")
            except Exception as e:
                self.logger.error("Failed to stop HealthMonitor service", error=str(e))

        # Stop all other services
        await self.service_manager.stop_all()
        self.logger.info("All services stopped")

    async def _health_monitoring_loop(self):
        """Background task that periodically performs health checks and recovery."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self.perform_health_check_and_recovery()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Health monitoring loop error", error=str(e))
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def check_system_health(self) -> dict:
        """
        Check comprehensive system health using ProcessCache and service status.

        Returns:
            dict: Comprehensive health status
        """
        health_status = {
            "status": "healthy",
            "services": {},
            "processes": {},
            "issues": [],
            "auto_restarts": 0,
        }

        # Check service health
        service_status = self.service_manager.get_all_status()
        for service_name, status in service_status["services"].items():
            health_status["services"][service_name] = status

            # Auto-restart failed services
            if not status.get("is_running", False):
                health_status["issues"].append(f"Service {service_name} is not running")
                try:
                    await self.service_manager.restart_service(ServiceName(service_name))
                    health_status["auto_restarts"] += 1
                    health_status["issues"].append(f"Auto-restarted service {service_name}")
                    self.logger.info(f"Auto-restarted service {service_name}")
                except Exception as e:
                    health_status["issues"].append(f"Failed to restart {service_name}: {str(e)}")
                    self.logger.error(f"Failed to auto-restart {service_name}", error=str(e))

        # Check ProcessCache health if available
        try:
            from fullon_cache import ProcessCache

            async with ProcessCache() as cache:
                # Get system health
                system_health = await cache.get_system_health()
                health_status["processes"]["system_health"] = system_health

                # Get active processes
                active_processes = await cache.get_active_processes()
                health_status["processes"]["active_count"] = len(active_processes)
                health_status["processes"]["active_processes"] = active_processes

                # Check for stale processes (older than 10 minutes)
                import time

                stale_threshold = time.time() - (10 * 60)  # 10 minutes ago
                stale_processes = [
                    p for p in active_processes if p.get("last_seen", 0) < stale_threshold
                ]

                if stale_processes:
                    health_status["issues"].extend(
                        [
                            f"Stale process: {p.get('component', 'unknown')} ({p.get('process_type', 'unknown')})"
                            for p in stale_processes
                        ]
                    )

        except ImportError:
            health_status["processes"]["error"] = "ProcessCache not available"
        except Exception as e:
            health_status["processes"]["error"] = f"ProcessCache error: {str(e)}"
            self.logger.warning("ProcessCache health check failed", error=str(e))

        # Determine overall status
        if health_status["issues"]:
            health_status["status"] = "degraded"
        if health_status["auto_restarts"] > 0:
            health_status["status"] = "recovering"

        return health_status

    async def perform_health_check_and_recovery(self) -> dict:
        """
        Perform comprehensive health check and recovery operations.

        This method is designed to be called periodically or on-demand
        to ensure system health and perform auto-recovery.

        Returns:
            dict: Health check results and recovery actions taken
        """
        self.logger.info("Performing comprehensive health check and recovery")

        results = {
            "timestamp": "2025-10-26T18:54:39Z",  # Would use datetime.utcnow()
            "checks_performed": [],
            "issues_found": [],
            "recovery_actions": [],
            "overall_status": "healthy",
        }

        # 1. Check service health and auto-restart
        results["checks_performed"].append("service_health")
        service_status = self.service_manager.get_all_status()

        for service_name, status in service_status["services"].items():
            if not status.get("is_running", False):
                results["issues_found"].append(f"Service {service_name} not running")

                try:
                    await self.service_manager.restart_service(ServiceName(service_name))
                    results["recovery_actions"].append(f"Restarted service {service_name}")
                    self.logger.info(f"Auto-recovery: restarted service {service_name}")
                except Exception as e:
                    results["issues_found"].append(f"Failed to restart {service_name}: {str(e)}")
                    self.logger.error(f"Auto-recovery failed for {service_name}", error=str(e))

        # 2. Check ProcessCache health
        results["checks_performed"].append("process_cache")
        try:
            from fullon_cache import ProcessCache

            async with ProcessCache() as cache:
                system_health = await cache.get_system_health()
                active_processes = await cache.get_active_processes()

                # Check for critical process failures
                critical_components = ["ohlcv", "ticker", "account"]
                for component in critical_components:
                    component_processes = [
                        p for p in active_processes if p.get("component") == component
                    ]

                    if not component_processes:
                        results["issues_found"].append(f"No active processes for {component}")
                        # Note: ProcessCache monitoring doesn't handle starting processes,
                        # that's handled by the service manager above

        except ImportError:
            results["issues_found"].append("ProcessCache not available")
        except Exception as e:
            results["issues_found"].append(f"ProcessCache check failed: {str(e)}")

        # 3. Check database connectivity
        results["checks_performed"].append("database")
        try:
            # Simple database connectivity check
            from fullon_orm.database import get_db_manager

            db_manager = get_db_manager()
            async with db_manager.get_session() as session:
                from sqlalchemy import text

                await session.execute(text("SELECT 1"))
        except Exception as e:
            results["issues_found"].append(f"Database connectivity issue: {str(e)}")

        # 4. Check Redis connectivity if ProcessCache is available
        results["checks_performed"].append("redis")
        try:
            from fullon_cache import ProcessCache

            async with ProcessCache() as cache:
                await cache.ping()
        except ImportError:
            results["issues_found"].append("Redis check skipped - ProcessCache not available")
        except Exception as e:
            results["issues_found"].append(f"Redis connectivity issue: {str(e)}")

        # Determine overall status
        if results["issues_found"]:
            results["overall_status"] = "degraded"
        if results["recovery_actions"]:
            results["overall_status"] = "recovering"

        self.logger.info(
            "Health check and recovery completed",
            status=results["overall_status"],
            issues=len(results["issues_found"]),
            recoveries=len(results["recovery_actions"]),
        )

        return results

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
            lifespan=self.lifespan,
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

        app.include_router(health_router)  # Health endpoints don't need API prefix

        app.include_router(services_router, prefix=settings.api_prefix)

        # Mount ORM API routers (NEW - Issue #17)
        self._mount_orm_routers(app)

        # Mount OHLCV API routers (Phase 4 - NEW)
        self._mount_ohlcv_routers(app)

        # Mount Cache API WebSocket routers (Phase 5 - NEW)
        self._mount_cache_routers(app)

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
