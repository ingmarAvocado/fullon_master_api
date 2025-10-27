"""
HealthMonitor Service - Self-Healing Health Check with ProcessCache Monitoring & Auto-Restart.

This service provides comprehensive system health monitoring with automatic recovery
capabilities. It monitors services, processes, and system components, performing
auto-restart operations when issues are detected.

Key Features:
- ProcessCache integration for system monitoring
- Configurable auto-restart with safety controls
- Cooldown mechanisms to prevent restart loops
- Comprehensive health metrics and reporting
- Background monitoring with configurable intervals
- Action history for audit trails

Architecture:
- Runs as background service in ServiceManager
- Integrates with ProcessCache for process monitoring
- Uses configuration settings for safety controls
- Provides health data to /health endpoint
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from fullon_log import get_component_logger

try:
    from ..config import settings
except ImportError:
    # For testing, create mock settings
    from types import SimpleNamespace

    settings = SimpleNamespace()
    settings.health_check_interval_seconds = 300
    settings.health_stale_process_threshold_minutes = 10
    settings.health_auto_restart_enabled = True
    settings.health_auto_restart_cooldown_seconds = 300
    settings.health_auto_restart_max_per_hour = 5
    settings.health_services_to_monitor = ["ticker", "ohlcv", "account"]
    settings.health_enable_process_cache_checks = True
    settings.health_enable_database_checks = True
    settings.health_enable_redis_checks = True


logger = get_component_logger("fullon.master_api.services.health_monitor")


@dataclass
class HealthCheckResult:
    """Result of a comprehensive health check."""

    timestamp: datetime
    checks_performed: List[str]
    issues_found: List[str]
    recovery_actions: List[str]
    overall_status: str
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AutoRestartConfig:
    """Configuration for auto-restart behavior."""

    enabled: bool = True
    cooldown_seconds: int = 300  # 5 minutes between restarts
    max_restarts_per_hour: int = 5
    services_to_monitor: List[str] = field(default_factory=lambda: ["ticker", "ohlcv", "account"])


@dataclass
class HealthMonitorConfig:
    """Configuration for HealthMonitor service."""

    check_interval_seconds: int = 300  # 5 minutes
    stale_process_threshold_minutes: int = 10
    auto_restart: AutoRestartConfig = field(default_factory=AutoRestartConfig)
    enable_process_cache_checks: bool = True
    enable_database_checks: bool = True
    enable_redis_checks: bool = True


class HealthMonitor:
    """
    Self-healing health monitoring service.

    Monitors system health and performs automatic recovery operations.
    Integrates with ProcessCache for comprehensive system monitoring.
    """

    def __init__(self, service_manager, config: Optional[HealthMonitorConfig] = None):
        """
        Initialize HealthMonitor service.

        Args:
            service_manager: ServiceManager instance for service control
            config: HealthMonitor configuration
        """
        self.service_manager = service_manager
        self.config = config or HealthMonitorConfig()
        self.logger = logger

        # State tracking
        self.is_running = False
        self.last_check_result: Optional[HealthCheckResult] = None
        self.action_history: List[Dict[str, Any]] = []
        self.service_restart_counts: Dict[str, List[datetime]] = {}
        self.monitoring_task: Optional[asyncio.Task] = None

        # Metrics
        self.total_checks = 0
        self.total_issues_found = 0
        self.total_recovery_actions = 0
        self.uptime_start = datetime.now()

        self.logger.info(
            "HealthMonitor initialized",
            check_interval_seconds=self.config.check_interval_seconds,
            auto_restart_enabled=self.config.auto_restart.enabled,
            cooldown_seconds=self.config.auto_restart.cooldown_seconds,
            max_restarts_per_hour=self.config.auto_restart.max_restarts_per_hour,
            services_to_monitor=self.config.auto_restart.services_to_monitor,
        )

    def _config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for logging."""
        return {
            "check_interval_seconds": self.config.check_interval_seconds,
            "auto_restart_enabled": self.config.auto_restart.enabled,
            "cooldown_seconds": self.config.auto_restart.cooldown_seconds,
            "max_restarts_per_hour": self.config.auto_restart.max_restarts_per_hour,
            "services_to_monitor": self.config.auto_restart.services_to_monitor,
        }

    async def start(self):
        """Start the health monitoring service."""
        if self.is_running:
            self.logger.warning("HealthMonitor already running")
            return

        self.is_running = True
        self.uptime_start = datetime.now()
        self.logger.info("HealthMonitor starting")

        # Start background monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Perform initial health check
        await self.perform_health_check_and_recovery()

        self.logger.info("HealthMonitor started successfully")

    async def stop(self):
        """Stop the health monitoring service."""
        if not self.is_running:
            self.logger.info("HealthMonitor stopping")
            return

        self.is_running = False

        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        self.logger.info("HealthMonitor stopped")

    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                if self.is_running:  # Check again after sleep
                    await self.perform_health_check_and_recovery()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(60)  # Wait before retrying

    async def perform_health_check_and_recovery(self) -> HealthCheckResult:
        """
        Perform comprehensive health check and recovery operations.

        Returns:
            HealthCheckResult: Detailed results of the health check
        """
        start_time = datetime.now()
        result = HealthCheckResult(
            timestamp=start_time,
            checks_performed=[],
            issues_found=[],
            recovery_actions=[],
            overall_status="healthy",
        )

        self.logger.info("Performing comprehensive health check and recovery")

        # 1. Check service health and auto-restart
        if "service_health" not in result.checks_performed:
            result.checks_performed.append("service_health")
            await self._check_service_health(result)

        # 2. Check ProcessCache health
        if self.config.enable_process_cache_checks:
            result.checks_performed.append("process_cache")
            await self._check_process_cache_health(result)

        # 3. Check database connectivity
        if self.config.enable_database_checks:
            result.checks_performed.append("database")
            await self._check_database_health(result)

        # 4. Check Redis connectivity
        if self.config.enable_redis_checks:
            result.checks_performed.append("redis")
            await self._check_redis_health(result)

        # Determine overall status
        if result.issues_found:
            result.overall_status = "degraded"
        if result.recovery_actions:
            result.overall_status = "recovering"

        # Update metrics
        result.metrics = self._get_current_metrics()

        # Store result
        self.last_check_result = result
        self.total_checks += 1
        self.total_issues_found += len(result.issues_found)
        self.total_recovery_actions += len(result.recovery_actions)

        # Log summary
        self.logger.info(
            "Health check and recovery completed",
            status=result.overall_status,
            issues=len(result.issues_found),
            recoveries=len(result.recovery_actions),
            duration=(datetime.now() - start_time).total_seconds(),
        )

        return result

    async def _check_service_health(self, result: HealthCheckResult):
        """Check service health and perform auto-restart if configured."""
        service_status = self.service_manager.get_all_status()

        for service_name, status in service_status["services"].items():
            if service_name not in self.config.auto_restart.services_to_monitor:
                continue

            if not status.get("is_running", False):
                result.issues_found.append(f"Service {service_name} is not running")

                # Check if auto-restart is allowed
                if self.config.auto_restart.enabled and self._can_restart_service(service_name):
                    try:
                        await self.service_manager.restart_service(service_name)
                        result.recovery_actions.append(f"Auto-restarted service {service_name}")
                        self._record_restart_action(
                            service_name, "auto_restart", "service_not_running"
                        )
                        self.logger.info(f"Auto-recovery: restarted service {service_name}")
                    except Exception as e:
                        result.issues_found.append(f"Failed to restart {service_name}: {str(e)}")
                        self.logger.error(f"Auto-recovery failed for {service_name}", error=str(e))

    async def _check_process_cache_health(self, result: HealthCheckResult):
        """Check ProcessCache health and monitor for stale processes."""
        try:
            from fullon_cache import ProcessCache

            async with ProcessCache() as cache:
                # Get system health
                system_health = await cache.get_system_health()
                result.metrics["process_cache_system_health"] = system_health

                # Get active processes
                active_processes = await cache.get_active_processes()
                result.metrics["process_cache_active_count"] = len(active_processes)

                # Check for stale processes
                stale_threshold = time.time() - (self.config.stale_process_threshold_minutes * 60)
                stale_processes = [
                    p for p in active_processes if p.get("last_seen", 0) < stale_threshold
                ]

                if stale_processes:
                    for p in stale_processes:
                        issue = f"Stale process: {p.get('component', 'unknown')} ({p.get('process_type', 'unknown')})"
                        result.issues_found.append(issue)

        except ImportError:
            result.issues_found.append("ProcessCache not available")
        except Exception as e:
            result.issues_found.append(f"ProcessCache check failed: {str(e)}")
            self.logger.warning("ProcessCache health check failed", error=str(e))

    async def _check_database_health(self, result: HealthCheckResult):
        """Check database connectivity."""
        try:
            from fullon_orm.database import get_db_manager
            from sqlalchemy import text

            db_manager = get_db_manager()
            async with db_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
        except Exception as e:
            result.issues_found.append(f"Database connectivity issue: {str(e)}")

    async def _check_redis_health(self, result: HealthCheckResult):
        """Check Redis connectivity."""
        try:
            from fullon_cache import ProcessCache

            async with ProcessCache() as cache:
                await cache.ping()
        except ImportError:
            result.issues_found.append("Redis check skipped - ProcessCache not available")
        except Exception as e:
            result.issues_found.append(f"Redis connectivity issue: {str(e)}")

    def _can_restart_service(self, service_name: str) -> bool:
        """
        Check if a service can be restarted based on cooldown and rate limits.

        Args:
            service_name: Name of the service to check

        Returns:
            bool: True if restart is allowed
        """
        now = datetime.now()
        recent_restarts = self.service_restart_counts.get(service_name, [])

        # Remove restarts older than 1 hour
        recent_restarts = [
            restart_time
            for restart_time in recent_restarts
            if now - restart_time < timedelta(hours=1)
        ]

        # Check rate limit
        if len(recent_restarts) >= self.config.auto_restart.max_restarts_per_hour:
            self.logger.warning(
                f"Service {service_name} restart rate limit exceeded",
                recent_restarts=len(recent_restarts),
                limit=self.config.auto_restart.max_restarts_per_hour,
            )
            return False

        # Check cooldown
        if recent_restarts:
            last_restart = max(recent_restarts)
            cooldown_end = last_restart + timedelta(
                seconds=self.config.auto_restart.cooldown_seconds
            )
            if now < cooldown_end:
                remaining = (cooldown_end - now).total_seconds()
                self.logger.warning(
                    f"Service {service_name} restart cooldown active",
                    remaining_seconds=int(remaining),
                )
                return False

        return True

    def _record_restart_action(self, service_name: str, action_type: str, reason: str):
        """Record a restart action in the history."""
        now = datetime.now()

        # Update restart counts
        if service_name not in self.service_restart_counts:
            self.service_restart_counts[service_name] = []
        self.service_restart_counts[service_name].append(now)

        # Add to action history
        action = {
            "timestamp": now.isoformat(),
            "service_name": service_name,
            "action_type": action_type,
            "reason": reason,
        }
        self.action_history.append(action)

        # Keep only last 100 actions
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]

    def _get_current_metrics(self) -> Dict[str, Any]:
        """Get current health monitoring metrics."""
        uptime = datetime.now() - self.uptime_start

        return {
            "uptime_seconds": uptime.total_seconds(),
            "total_checks": self.total_checks,
            "total_issues_found": self.total_issues_found,
            "total_recovery_actions": self.total_recovery_actions,
            "service_restart_counts": {
                service: len(restarts) for service, restarts in self.service_restart_counts.items()
            },
            "action_history_count": len(self.action_history),
            "is_running": self.is_running,
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status for API response.

        Returns:
            dict: Complete health status including monitoring state
        """
        status = {
            "status": "healthy",
            "monitoring": {
                "enabled": True,
                "is_running": self.is_running,
                "check_interval_seconds": self.config.check_interval_seconds,
                "last_check": None,
                "next_check": None,
            },
            "auto_restart": {
                "enabled": self.config.auto_restart.enabled,
                "cooldown_seconds": self.config.auto_restart.cooldown_seconds,
                "max_restarts_per_hour": self.config.auto_restart.max_restarts_per_hour,
                "services_to_monitor": self.config.auto_restart.services_to_monitor,
            },
            "metrics": self._get_current_metrics(),
            "issues": [],
            "recovery_actions": [],
        }

        # Add last check results if available
        if self.last_check_result:
            status["monitoring"]["last_check"] = self.last_check_result.timestamp.isoformat()
            status["issues"] = self.last_check_result.issues_found
            status["recovery_actions"] = self.last_check_result.recovery_actions
            status["status"] = self.last_check_result.overall_status

            # Calculate next check time
            next_check = self.last_check_result.timestamp + timedelta(
                seconds=self.config.check_interval_seconds
            )
            status["monitoring"]["next_check"] = next_check.isoformat()

        # Add recent action history (last 10 actions)
        status["recent_actions"] = self.action_history[-10:] if self.action_history else []

        return status
