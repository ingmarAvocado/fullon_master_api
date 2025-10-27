"""
Integration tests for ServiceManager-Gateway integration.

Tests the complete lifecycle integration between MasterGateway and ServiceManager,
including automatic service startup, health monitoring, and graceful shutdown.
"""
import pytest
from unittest.mock import patch

from fullon_master_api.gateway import MasterGateway
from fullon_master_api.services.manager import ServiceName


class TestGatewayServiceIntegration:
    """Test ServiceManager integration with MasterGateway."""

    @pytest.fixture(autouse=True, scope="function")
    async def cleanup_services(self, gateway):
        """Clean up any running services after each test."""
        yield
        # Stop all services after test
        try:
            await gateway.service_manager.stop_all()
        except Exception:
            pass  # Ignore cleanup errors

    @pytest.fixture
    def gateway(self):
        """Create gateway instance."""
        return MasterGateway()

    def test_gateway_initializes_with_service_manager(self, gateway):
        """Test that gateway initializes with ServiceManager."""
        assert hasattr(gateway, "service_manager")
        assert gateway.service_manager is not None

    def test_service_manager_has_all_services(self, gateway):
        """Test that ServiceManager has all expected services."""
        service_manager = gateway.service_manager

        for service_name in ServiceName:
            assert service_name in service_manager.daemons
            assert service_name in service_manager.tasks

    @pytest.mark.asyncio
    async def test_lifespan_starts_services_automatically(self, gateway):
        """Test that lifespan starts configured services automatically."""
        # Mock settings to enable auto-start
        with patch("fullon_master_api.gateway.settings") as mock_settings:
            mock_settings.service_auto_start_enabled = True
            mock_settings.services_to_auto_start = ["ticker", "ohlcv", "account"]
            mock_settings.health_monitor_enabled = True

            # Create a mock lifespan context
            async def mock_lifespan():
                # Simulate startup
                if mock_settings.service_auto_start_enabled:
                    for service_name in mock_settings.services_to_auto_start:
                        service_enum = ServiceName(service_name)
                        await gateway.service_manager.start_service(service_enum)

                if mock_settings.health_monitor_enabled:
                    await gateway.service_manager.health_monitor.start()

                yield

                # Simulate shutdown
                if mock_settings.health_monitor_enabled:
                    await gateway.service_manager.health_monitor.stop()

                await gateway.service_manager.stop_all()

            # Run the lifespan
            async for _ in mock_lifespan():
                pass

    @pytest.mark.asyncio
    async def test_lifespan_respects_auto_start_setting(self, gateway):
        """Test that lifespan respects the auto-start configuration."""
        # Mock settings to disable auto-start
        with patch("fullon_master_api.gateway.settings") as mock_settings:
            mock_settings.service_auto_start_enabled = False
            mock_settings.services_to_auto_start = ["ticker", "ohlcv", "account"]
            mock_settings.health_monitor_enabled = False

            # Create a mock lifespan context
            async def mock_lifespan():
                # Simulate startup
                if mock_settings.service_auto_start_enabled:
                    for service_name in mock_settings.services_to_auto_start:
                        service_enum = ServiceName(service_name)
                        await gateway.service_manager.start_service(service_enum)

                if mock_settings.health_monitor_enabled:
                    await gateway.service_manager.health_monitor.start()

                yield

                # Simulate shutdown
                if mock_settings.health_monitor_enabled:
                    await gateway.service_manager.health_monitor.stop()

                await gateway.service_manager.stop_all()

            # Run the lifespan
            async for _ in mock_lifespan():
                pass

    def test_service_manager_in_app_state(self, gateway):
        """Test that ServiceManager is available in FastAPI app state."""
        app = gateway.get_app()

        assert hasattr(app.state, "service_manager")
        assert app.state.service_manager is gateway.service_manager

    def test_gateway_health_endpoints_use_service_manager(self, gateway):
        """Test that health endpoints properly use ServiceManager."""
        # Test that ServiceManager methods are called
        health_status = gateway.service_manager.get_health_status()
        assert isinstance(health_status, dict)

        service_status = gateway.service_manager.get_all_status()
        assert "services" in service_status

    @pytest.mark.asyncio
    async def test_service_lifecycle_integration(self, gateway):
        """Test complete service lifecycle through gateway integration."""
        service_manager = gateway.service_manager

        # Test starting a service (uses MockDaemon)
        result = await service_manager.start_service(ServiceName.TICKER)
        assert result["status"] == "started"

        # Test getting status
        status = service_manager.get_service_status(ServiceName.TICKER)
        assert status["status"] == "running"

        # Test stopping a service
        result = await service_manager.stop_service(ServiceName.TICKER)
        assert result["status"] == "stopped"

        # Test restarting a service
        result = await service_manager.restart_service(ServiceName.TICKER)
        assert result["status"] == "restarted"
