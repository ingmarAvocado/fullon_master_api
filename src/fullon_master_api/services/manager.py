"""
ServiceManager for async background task management.

Manages lifecycle of Fullon service daemons as async background tasks.
"""
import asyncio
from enum import Enum
from typing import Dict, Optional

from fullon_log import get_component_logger

logger = get_component_logger("fullon.master_api.services")


class ServiceName(str, Enum):
    """Enumeration of available services."""

    TICKER = "ticker"
    OHLCV = "ohlcv"
    ACCOUNT = "account"


class ServiceManager:
    """
    Manages lifecycle of Fullon service daemons as async background tasks.

    Services run as asyncio tasks within the master API process, not as
    separate processes or subprocesses. This provides centralized control
    while maintaining proper isolation.

    Services:
    - ticker: Real-time ticker data collection (fullon_ticker_service)
    - ohlcv: Historic + live OHLCV/trade collection (fullon_ohlcv_service)
    - account: Adaptive account monitoring (fullon_account_service)
    """

    def __init__(self):
        """Initialize ServiceManager with service daemons."""
        # Import service daemons as libraries
        try:
            from fullon_account_service import AccountDaemon
            from fullon_ohlcv_service import OhlcvDaemon
            from fullon_ticker_service import TickerDaemon

            self.daemons = {
                ServiceName.TICKER: TickerDaemon(),
                ServiceName.OHLCV: OhlcvDaemon(),
                ServiceName.ACCOUNT: AccountDaemon(),
            }
        except ImportError as e:
            logger.error("Failed to import service daemons", error=str(e))
            # Create mock daemons for testing/development
            self.daemons = {
                ServiceName.TICKER: MockDaemon("ticker"),
                ServiceName.OHLCV: MockDaemon("ohlcv"),
                ServiceName.ACCOUNT: MockDaemon("account"),
            }
            logger.warning("Using mock daemons - service libraries not available")

        self.tasks: Dict[ServiceName, Optional[asyncio.Task]] = {
            ServiceName.TICKER: None,
            ServiceName.OHLCV: None,
            ServiceName.ACCOUNT: None,
        }

        logger.info("ServiceManager initialized")

    async def start_service(self, service_name: ServiceName) -> dict:
        """
        Start a service as background task.

        Args:
            service_name: Service to start

        Returns:
            dict with status information

        Raises:
            ValueError: If service is already running
        """
        if self.tasks[service_name] is not None:
            raise ValueError(f"{service_name} is already running")

        daemon = self.daemons[service_name]

        # Create background task for daemon.start()
        # Note: daemon.start() should be an async method that runs indefinitely
        self.tasks[service_name] = asyncio.create_task(daemon.start())

        logger.info(f"{service_name} service started")
        return {"service": service_name, "status": "started"}

    async def stop_service(self, service_name: ServiceName) -> dict:
        """
        Stop a running service gracefully.

        Args:
            service_name: Service to stop

        Returns:
            dict with status information

        Raises:
            ValueError: If service is not running
        """
        if self.tasks[service_name] is None:
            raise ValueError(f"{service_name} is not running")

        daemon = self.daemons[service_name]

        # Graceful shutdown - call daemon.stop() if available
        if hasattr(daemon, "stop") and callable(getattr(daemon, "stop")):
            try:
                await daemon.stop()
            except Exception as e:
                logger.warning(f"Error during {service_name} graceful shutdown", error=str(e))

        # Cancel background task
        task = self.tasks[service_name]
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.tasks[service_name] = None

        logger.info(f"{service_name} service stopped")
        return {"service": service_name, "status": "stopped"}

    async def restart_service(self, service_name: ServiceName) -> dict:
        """
        Restart a service (stop then start).

        Args:
            service_name: Service to restart

        Returns:
            dict with status information
        """
        if self.tasks[service_name] is not None:
            await self.stop_service(service_name)

        await asyncio.sleep(1)  # Brief pause between stop and start
        await self.start_service(service_name)

        logger.info(f"{service_name} service restarted")
        return {"service": service_name, "status": "restarted"}

    def get_service_status(self, service_name: ServiceName) -> dict:
        """
        Get status of a specific service.

        Args:
            service_name: Service to check

        Returns:
            dict with service status information
        """
        is_running = self.tasks[service_name] is not None
        daemon = self.daemons[service_name]

        # Check if daemon has is_running method
        daemon_running = False
        if hasattr(daemon, "is_running") and callable(getattr(daemon, "is_running")):
            try:
                daemon_running = daemon.is_running()
            except Exception as e:
                logger.warning(f"Error checking {service_name} daemon status", error=str(e))

        return {
            "service": service_name,
            "status": "running" if is_running else "stopped",
            "is_running": daemon_running if is_running else False,
        }

    def get_all_status(self) -> dict:
        """
        Get status of all services.

        Returns:
            dict with all services status information
        """
        return {
            "services": {
                service_name: self.get_service_status(service_name) for service_name in ServiceName
            }
        }

    async def stop_all(self) -> None:
        """Stop all running services (for graceful shutdown)."""
        for service_name in ServiceName:
            if self.tasks[service_name] is not None:
                try:
                    await self.stop_service(service_name)
                except Exception as e:
                    logger.error(f"Error stopping {service_name}", error=str(e))


class MockDaemon:
    """Mock daemon for testing when service libraries are not available."""

    def __init__(self, name: str):
        self.name = name
        self.running = False

    async def start(self):
        """Mock start method - runs indefinitely."""
        self.running = True
        logger.info(f"Mock {self.name} daemon started")
        try:
            while True:
                await asyncio.sleep(1)  # Keep running
        except asyncio.CancelledError:
            self.running = False
            logger.info(f"Mock {self.name} daemon stopped")
            raise

    async def stop(self):
        """Mock stop method."""
        self.running = False
        logger.info(f"Mock {self.name} daemon stop requested")

    def is_running(self) -> bool:
        """Check if daemon is running."""
        return self.running
