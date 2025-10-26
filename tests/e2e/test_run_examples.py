"""
E2E Tests: Run Example Scripts

Validates that all example scripts run successfully without errors.
This ensures examples are production-ready and self-contained.
"""
import subprocess
import sys
from pathlib import Path
import pytest
from fullon_log import get_component_logger

logger = get_component_logger("fullon.master_api.tests.e2e.run_examples")

# Path to examples directory
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


class TestExampleScripts:
    """Test that example scripts run successfully."""

    def test_example_health_check(self):
        """Test example_health_check.py runs without errors."""
        script = EXAMPLES_DIR / "example_health_check.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=30
        )

        # Log output for debugging
        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_health_check.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_jwt_login(self):
        """Test example_jwt_login.py runs without errors."""
        script = EXAMPLES_DIR / "example_jwt_login.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_jwt_login.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_api_key_auth(self):
        """Test example_api_key_auth.py runs without errors."""
        script = EXAMPLES_DIR / "example_api_key_auth.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_api_key_auth.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_authenticated_request(self):
        """Test example_authenticated_request.py runs without errors."""
        script = EXAMPLES_DIR / "example_authenticated_request.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_authenticated_request.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_orm_routes(self):
        """Test example_orm_routes.py runs without errors."""
        script = EXAMPLES_DIR / "example_orm_routes.py"

        # This example creates its own server, DB, and cleans up
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,  # Longer timeout for full example
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_orm_routes.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_ohlcv_routes(self):
        """Test example_ohlcv_routes.py runs without errors."""
        script = EXAMPLES_DIR / "example_ohlcv_routes.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_ohlcv_routes.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_bot_management(self):
        """Test example_bot_management.py runs without errors."""
        script = EXAMPLES_DIR / "example_bot_management.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=90
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_bot_management.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_trade_analytics(self):
        """Test example_trade_analytics.py runs without errors."""
        script = EXAMPLES_DIR / "example_trade_analytics.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_trade_analytics.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_exchange_catalog(self):
        """Test example_exchange_catalog.py runs without errors."""
        script = EXAMPLES_DIR / "example_exchange_catalog.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_exchange_catalog.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_order_management(self):
        """Test example_order_management.py runs without errors."""
        script = EXAMPLES_DIR / "example_order_management.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=180,  # Longer timeout for complex example with database setup
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_order_management.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_service_control(self):
        """Test example_service_control.py runs without errors."""
        script = EXAMPLES_DIR / "example_service_control.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_service_control.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_strategy_management(self):
        """Test example_strategy_management.py runs without errors."""
        script = EXAMPLES_DIR / "example_strategy_management.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_strategy_management.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_swagger_docs(self):
        """Test example_swagger_docs.py runs without errors."""
        script = EXAMPLES_DIR / "example_swagger_docs.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_swagger_docs.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_symbol_operations(self):
        """Test example_symbol_operations.py runs without errors."""
        script = EXAMPLES_DIR / "example_symbol_operations.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_symbol_operations.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_dashboard_views(self):
        """Test example_dashboard_views.py runs without errors."""
        script = EXAMPLES_DIR / "example_dashboard_views.py"

        result = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_dashboard_views.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    @pytest.mark.slow
    def test_run_all_examples(self):
        """Test run_all_examples.py script (comprehensive test)."""
        script = EXAMPLES_DIR / "run_all_examples.py"

        result = subprocess.run(
            [sys.executable, str(script), "--skip-websocket"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes for full suite
        )

        if result.returncode != 0:
            logger.error(
                "run_all_examples failed",
                stdout=result.stdout[-2000:],
                stderr=result.stderr[-2000:],
            )

        # Check for summary in output
        assert "Example Results Summary" in result.stdout or "All examples passed" in result.stdout

        # Exit code 0 means all examples passed
        assert result.returncode == 0, f"Some examples failed:\n{result.stdout[-1000:]}"
