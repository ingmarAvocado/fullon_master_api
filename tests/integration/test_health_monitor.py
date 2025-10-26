"""
Integration tests for HealthMonitor service.

Tests the self-healing health check functionality with ProcessCache monitoring
and auto-restart capabilities.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from fullon_master_api.services.health_monitor import (
    HealthMonitor,
    HealthMonitorConfig,
    AutoRestartConfig,
)


class TestHealthMonitor:
    """Test HealthMonitor service functionality."""

    @pytest.fixture
    def health_config(self):
        """Create test HealthMonitor configuration."""
        return HealthMonitorConfig(
            check_interval_seconds=1,  # Fast for testing
            stale_process_threshold_minutes=1,
            auto_restart=AutoRestartConfig(
                enabled=True,
                cooldown_seconds=1,  # Fast cooldown for testing
                max_restarts_per_hour=10,
                services_to_monitor=["ticker", "ohlcv"],
            ),
            enable_process_cache_checks=True,
            enable_database_checks=True,
            enable_redis_checks=True,
        )

    @pytest.fixture
    def mock_service_manager(self):
        """Create mock ServiceManager."""
        manager = AsyncMock()
        manager.get_all_status.return_value = {
            "services": {
                "ticker": {"service": "ticker", "status": "stopped", "is_running": False},
                "ohlcv": {"service": "ohlcv", "status": "running", "is_running": True},
            }
        }
        manager.restart_service = AsyncMock(
            return_value={"service": "ticker", "status": "restarted"}
        )
        return manager

    @pytest.fixture
    async def health_monitor(self, mock_service_manager, health_config):
        """Create HealthMonitor instance for testing."""
        monitor = HealthMonitor(mock_service_manager, health_config)
        yield monitor
        # Cleanup
        if monitor.is_running:
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_health_monitor_initialization(self, health_monitor, health_config):
        """Test HealthMonitor initializes correctly."""
        assert not health_monitor.is_running
        assert health_monitor.config == health_config
        assert health_monitor.total_checks == 0
        assert health_monitor.action_history == []

    @pytest.mark.asyncio
    async def test_health_monitor_start_stop(self, health_monitor):
        """Test HealthMonitor can start and stop."""
        # Start
        await health_monitor.start()
        assert health_monitor.is_running

        # Stop
        await health_monitor.stop()
        assert not health_monitor.is_running

    @pytest.mark.asyncio
    async def test_perform_health_check_service_restart(self, health_monitor, mock_service_manager):
        """Test health check performs service restart for failed services."""
        # Perform health check
        result = await health_monitor.perform_health_check_and_recovery()

        # Verify service restart was called
        mock_service_manager.restart_service.assert_called_once_with("ticker")

        # Verify result structure
        assert "timestamp" in result
        assert "checks_performed" in result
        assert "issues_found" in result
        assert "recovery_actions" in result
        assert "overall_status" in result
        assert "metrics" in result

        # Verify issues and recoveries
        assert len(result["issues_found"]) > 0
        assert len(result["recovery_actions"]) > 0
        assert result["overall_status"] == "recovering"

    @pytest.mark.asyncio
    async def test_get_health_status(self, health_monitor):
        """Test get_health_status returns proper structure."""
        status = health_monitor.get_health_status()

        # Verify required fields
        required_fields = [
            "status",
            "monitoring",
            "auto_restart",
            "metrics",
            "issues",
            "recovery_actions",
            "recent_actions",
        ]

        for field in required_fields:
            assert field in status

        # Verify monitoring section
        monitoring = status["monitoring"]
        assert "enabled" in monitoring
        assert "is_running" in monitoring
        assert "check_interval_seconds" in monitoring

        # Verify auto_restart section
        auto_restart = status["auto_restart"]
        assert "enabled" in auto_restart
        assert "cooldown_seconds" in auto_restart
        assert "max_restarts_per_hour" in auto_restart
        assert "services_to_monitor" in auto_restart

    @pytest.mark.asyncio
    async def test_restart_cooldown_prevents_frequent_restarts(
        self, health_monitor, mock_service_manager
    ):
        """Test cooldown mechanism prevents restart loops."""
        # First restart should work
        can_restart = health_monitor._can_restart_service("ticker")
        assert can_restart

        # Record a restart
        health_monitor._record_restart_action("ticker", "auto_restart", "test")

        # Immediate restart should be blocked by cooldown
        can_restart = health_monitor._can_restart_service("ticker")
        assert not can_restart

    @pytest.mark.asyncio
    async def test_restart_rate_limiting(self, health_monitor):
        """Test rate limiting prevents too many restarts per hour."""
        # Record maximum allowed restarts
        max_restarts = health_monitor.config.auto_restart.max_restarts_per_hour
        for i in range(max_restarts):
            health_monitor._record_restart_action("ticker", "auto_restart", f"test_{i}")

        # Next restart should be blocked
        can_restart = health_monitor._can_restart_service("ticker")
        assert not can_restart

    @pytest.mark.asyncio
    async def test_process_cache_health_check(self, health_monitor):
        """Test ProcessCache health checking."""
        with patch("fullon_master_api.services.health_monitor.ProcessCache") as mock_cache:
            # Setup mock
            mock_cache.return_value.__aenter__.return_value.get_system_health = AsyncMock(
                return_value={"healthy": True, "total_processes": 5}
            )
            mock_cache.return_value.__aenter__.return_value.get_active_processes = AsyncMock(
                return_value=[{"component": "ticker", "last_seen": 1234567890}]
            )

            # Perform health check
            result = await health_monitor.perform_health_check_and_recovery()

            # Verify ProcessCache was called
            assert "process_cache" in result["checks_performed"]

    @pytest.mark.asyncio
    async def test_database_health_check(self, health_monitor):
        """Test database connectivity health check."""
        result = await health_monitor.perform_health_check_and_recovery()

        # Database check should be performed
        assert "database" in result["checks_performed"]

    @pytest.mark.asyncio
    async def test_action_history_tracking(self, health_monitor):
        """Test action history is properly maintained."""
        # Record some actions
        health_monitor._record_restart_action("ticker", "auto_restart", "test1")
        health_monitor._record_restart_action("ohlcv", "manual_restart", "test2")

        # Check history
        assert len(health_monitor.action_history) == 2

        # Check recent actions in status
        status = health_monitor.get_health_status()
        assert len(status["recent_actions"]) == 2

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, health_monitor):
        """Test metrics are properly tracked."""
        initial_checks = health_monitor.total_checks

        # Perform health check
        await health_monitor.perform_health_check_and_recovery()

        # Check metrics updated
        assert health_monitor.total_checks == initial_checks + 1

        # Check metrics in status
        status = health_monitor.get_health_status()
        metrics = status["metrics"]
        assert "total_checks" in metrics
        assert "uptime_seconds" in metrics
        assert metrics["total_checks"] >= 1
