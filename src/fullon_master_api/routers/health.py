"""
Health Router - Dedicated health monitoring endpoints.

Provides comprehensive health monitoring endpoints that follow LRRS principles
by separating health monitoring logic from the main gateway.
"""
from fastapi import APIRouter, Depends
from fullon_log import get_component_logger

from ..auth.dependencies import get_current_user
from ..services.manager import ServiceManager

logger = get_component_logger("fullon.master_api.routers.health")

router = APIRouter(
    prefix="/health",
    tags=["Health Monitoring"],
    dependencies=[],  # No auth required for health checks
)


@router.get("", summary="Comprehensive Health Check")
async def get_health(service_manager: ServiceManager = Depends()):
    """
    Get comprehensive system health status.

    Returns detailed health information including:
    - Service status and monitoring
    - Process health via ProcessCache
    - Auto-restart configuration and status
    - Recent recovery actions
    - System metrics and uptime

    This endpoint is designed for monitoring systems and provides
    all the information needed for health dashboards and alerts.
    """
    try:
        # Get health status from HealthMonitor service
        health_data = service_manager.get_health_status()

        # Add basic service info
        from ..config import settings

        health_data.update(
            {
                "version": settings.api_version,
                "service": "fullon_master_api",
            }
        )

        # Also include basic service status for backward compatibility
        service_status = service_manager.get_all_status()
        health_data["services"] = service_status["services"]

        return health_data

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        from ..config import settings

        return {
            "status": "unhealthy",
            "version": settings.api_version,
            "service": "fullon_master_api",
            "error": str(e),
            "issues": ["Health check system failure"],
        }


@router.get("/services", summary="Service Status Only")
async def get_service_health(service_manager: ServiceManager = Depends()):
    """
    Get service status information only.

    Returns:
        dict: Service status for all managed services
    """
    return service_manager.get_all_status()


@router.get("/monitor", summary="Health Monitor Status")
async def get_monitor_status(service_manager: ServiceManager = Depends()):
    """
    Get HealthMonitor service status and configuration.

    Returns:
        dict: HealthMonitor status, configuration, and metrics
    """
    return service_manager.get_health_status()


@router.post("/check", summary="Trigger Health Check")
async def trigger_health_check(service_manager: ServiceManager = Depends()):
    """
    Manually trigger a health check and recovery cycle.

    This endpoint allows administrators to manually trigger
    health checks and auto-recovery operations.

    Returns:
        dict: Results of the health check and any recovery actions
    """
    try:
        # Trigger health check via HealthMonitor
        if hasattr(service_manager, "health_monitor"):
            result = await service_manager.health_monitor.perform_health_check_and_recovery()
            return {
                "status": "completed",
                "result": result,
            }
        else:
            return {"status": "error", "error": "HealthMonitor service not available"}

    except Exception as e:
        logger.error("Manual health check failed", error=str(e))
        return {"status": "error", "error": str(e)}
