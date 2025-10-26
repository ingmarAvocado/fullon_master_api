"""
Admin-only service control endpoints.

Provides start/stop/restart/status operations for Fullon services.
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from fullon_log import get_component_logger
from fullon_orm.models import User

from ..auth.dependencies import get_admin_user
from ..services.manager import ServiceManager, ServiceName

router = APIRouter(tags=["services"])
logger = get_component_logger("fullon.master_api.routers.services")


def get_service_manager(request: Request) -> ServiceManager:
    """Dependency to get ServiceManager from app state."""
    if not hasattr(request.app.state, "service_manager"):
        logger.error("ServiceManager not found in app state")
        raise RuntimeError("ServiceManager not initialized")
    return request.app.state.service_manager


@router.post("/services/{service_name}/start")
async def start_service(
    service_name: ServiceName,
    admin_user: User = Depends(get_admin_user),
    manager: ServiceManager = Depends(get_service_manager),
):
    """
    Start a service (admin only).

    Args:
        service_name: Service to start ('ticker', 'ohlcv', 'account')

    Returns:
        dict with status information
    """
    try:
        result = await manager.start_service(service_name)
        logger.info("Service started by admin", service=service_name, user_id=admin_user.uid)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/services/{service_name}/stop")
async def stop_service(
    service_name: ServiceName,
    admin_user: User = Depends(get_admin_user),
    manager: ServiceManager = Depends(get_service_manager),
):
    """
    Stop a service (admin only).

    Args:
        service_name: Service to stop ('ticker', 'ohlcv', 'account')

    Returns:
        dict with status information
    """
    try:
        result = await manager.stop_service(service_name)
        logger.info("Service stopped by admin", service=service_name, user_id=admin_user.uid)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/services/{service_name}/restart")
async def restart_service(
    service_name: ServiceName,
    admin_user: User = Depends(get_admin_user),
    manager: ServiceManager = Depends(get_service_manager),
):
    """
    Restart a service (admin only).

    Args:
        service_name: Service to restart ('ticker', 'ohlcv', 'account')

    Returns:
        dict with status information
    """
    try:
        result = await manager.restart_service(service_name)
        logger.info("Service restarted by admin", service=service_name, user_id=admin_user.uid)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/services/{service_name}/status")
async def get_service_status(
    service_name: ServiceName,
    admin_user: User = Depends(get_admin_user),
    manager: ServiceManager = Depends(get_service_manager),
):
    """
    Get status of a specific service (admin only).

    Args:
        service_name: Service to check ('ticker', 'ohlcv', 'account')

    Returns:
        dict with service status information
    """
    return manager.get_service_status(service_name)


@router.get("/services")
async def get_all_services_status(
    admin_user: User = Depends(get_admin_user),
    manager: ServiceManager = Depends(get_service_manager),
):
    """
    Get status of all services (admin only).

    Returns:
        dict with all services status information
    """
    return manager.get_all_status()
