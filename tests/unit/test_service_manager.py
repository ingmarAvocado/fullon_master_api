"""
Unit tests for ServiceManager.

Tests async background task management for Fullon services.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fullon_master_api.services.manager import ServiceManager, ServiceName, MockDaemon


class TestServiceManager:
    """Test ServiceManager functionality."""

    def test_initialization(self):
        """Test ServiceManager initializes with mock daemons when libraries unavailable."""
        # ServiceManager automatically falls back to mock daemons when imports fail
        manager = ServiceManager()

        # Now includes 4 services: ticker, ohlcv, account, health_monitor
        assert len(manager.daemons) == 4

        # Check that ticker, ohlcv, account are MockDaemons
        from fullon_master_api.services.health_monitor import HealthMonitor
        for service_name in [ServiceName.TICKER, ServiceName.OHLCV, ServiceName.ACCOUNT]:
            assert isinstance(manager.daemons[service_name], MockDaemon)

        # health_monitor is a HealthMonitor instance
        assert isinstance(manager.daemons[ServiceName.HEALTH_MONITOR], HealthMonitor)

        assert all(task is None for task in manager.tasks.values())

    def test_service_names_enum(self):
        """Test ServiceName enum values."""
        assert ServiceName.TICKER == "ticker"
        assert ServiceName.OHLCV == "ohlcv"
        assert ServiceName.ACCOUNT == "account"
        assert ServiceName.HEALTH_MONITOR == "health_monitor"

    @pytest.mark.asyncio
    async def test_start_service_success(self):
        """Test successful service start."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        result = await manager.start_service(service_name)

        assert result["service"] == service_name
        assert result["status"] == "started"
        assert manager.tasks[service_name] is not None
        assert isinstance(manager.tasks[service_name], asyncio.Task)

    @pytest.mark.asyncio
    async def test_start_service_already_running(self):
        """Test starting a service that's already running raises ValueError."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        # Start service first
        await manager.start_service(service_name)

        # Try to start again
        with pytest.raises(ValueError, match="is already running"):
            await manager.start_service(service_name)

    @pytest.mark.asyncio
    async def test_stop_service_success(self):
        """Test successful service stop."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        # Start service first
        await manager.start_service(service_name)

        # Stop service
        result = await manager.stop_service(service_name)

        assert result["service"] == service_name
        assert result["status"] == "stopped"
        assert manager.tasks[service_name] is None

    @pytest.mark.asyncio
    async def test_stop_service_not_running(self):
        """Test stopping a service that's not running raises ValueError."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        with pytest.raises(ValueError, match="is not running"):
            await manager.stop_service(service_name)

    @pytest.mark.asyncio
    async def test_restart_service(self):
        """Test service restart functionality."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        # Start service
        await manager.start_service(service_name)
        first_task = manager.tasks[service_name]

        # Restart service
        result = await manager.restart_service(service_name)

        assert result["service"] == service_name
        assert result["status"] == "restarted"
        # Task should be different after restart
        assert manager.tasks[service_name] is not first_task
        assert manager.tasks[service_name] is not None

    def test_get_service_status_stopped(self):
        """Test getting status of stopped service."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        status = manager.get_service_status(service_name)

        assert status["service"] == service_name
        assert status["status"] == "stopped"
        assert status["is_running"] is False

    def test_get_service_status_running(self):
        """Test getting status of running service."""
        manager = ServiceManager()
        service_name = ServiceName.TICKER

        # Mock a running task (create a mock task object)
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        manager.tasks[service_name] = mock_task

        # Set the daemon as running
        manager.daemons[service_name].running = True

        status = manager.get_service_status(service_name)

        assert status["service"] == service_name
        assert status["status"] == "running"
        assert status["is_running"] is True

    def test_get_all_status(self):
        """Test getting status of all services."""
        manager = ServiceManager()

        status = manager.get_all_status()

        assert "services" in status
        # Now includes 4 services: ticker, ohlcv, account, health_monitor
        assert len(status["services"]) == 4

        for service_name in ServiceName:
            assert service_name in status["services"]
            service_status = status["services"][service_name]
            assert service_status["status"] == "stopped"
            assert service_status["is_running"] is False

    @pytest.mark.asyncio
    async def test_stop_all_services(self):
        """Test stopping all services."""
        manager = ServiceManager()

        # Start all services
        for service_name in ServiceName:
            await manager.start_service(service_name)

        # Verify all are running
        for service_name in ServiceName:
            assert manager.tasks[service_name] is not None

        # Stop all
        await manager.stop_all()

        # Verify all are stopped
        for service_name in ServiceName:
            assert manager.tasks[service_name] is None


class TestMockDaemon:
    """Test MockDaemon functionality."""

    def test_mock_daemon_initialization(self):
        """Test MockDaemon initializes correctly."""
        daemon = MockDaemon("test")

        assert daemon.name == "test"
        assert daemon.running is False

    @pytest.mark.asyncio
    async def test_mock_daemon_start_stop(self):
        """Test MockDaemon start/stop lifecycle."""
        daemon = MockDaemon("test")

        # Start daemon
        start_task = asyncio.create_task(daemon.start())
        await asyncio.sleep(0.1)  # Let it start

        assert daemon.running is True

        # Stop daemon
        await daemon.stop()
        start_task.cancel()

        try:
            await start_task
        except asyncio.CancelledError:
            pass

        assert daemon.running is False

    def test_mock_daemon_is_running(self):
        """Test MockDaemon is_running method."""
        daemon = MockDaemon("test")

        assert daemon.is_running() is False

        daemon.running = True
        assert daemon.is_running() is True
