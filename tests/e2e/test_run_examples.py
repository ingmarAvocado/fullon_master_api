"""
E2E Tests: Run Example Scripts

Validates that all example scripts run successfully without errors.
This ensures examples are production-ready and self-contained.
"""
import os
import subprocess
import sys
from pathlib import Path
import pytest
from fullon_log import get_component_logger

logger = get_component_logger("fullon.master_api.tests.e2e.run_examples")

# Path to examples directory
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


def run_example_script(script_path: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run an example script in a clean environment to avoid test interference."""
    # Run in clean environment to avoid test database interference
    clean_env = os.environ.copy()
    # Remove test-related environment variables that might interfere
    test_vars = [k for k in clean_env.keys() if k.startswith(("DB_", "REDIS_", "PYTEST_"))]
    for var in test_vars:
        del clean_env[var]

    return subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=clean_env,
    )


class TestExampleScripts:
    """Test that example scripts run successfully."""

    def test_example_health_check(self):
        """Test example_health_check.py runs without errors."""
        script = EXAMPLES_DIR / "example_health_check.py"
        result = run_example_script(script)

        # Log output for debugging
        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_health_check.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:],
            )

        assert (
            result.returncode == 0
        ), f"Example failed with exit code {result.returncode}:\n{result.stderr}"

    def test_example_jwt_login(self):
        """Test example_jwt_login.py runs without errors."""
        script = EXAMPLES_DIR / "example_jwt_login.py"
        result = run_example_script(script)

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
        result = run_example_script(script)

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
        result = run_example_script(script)

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_authenticated_request.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:],
            )

        assert (
            result.returncode == 0
        ), f"Example failed with exit code {result.returncode}. stderr:\n{result.stderr[-1000:]}"

    def test_example_orm_routes(self):
        """Test example_orm_routes.py runs without errors."""
        script = EXAMPLES_DIR / "example_orm_routes.py"
        # This example creates its own server, DB, and cleans up
        result = run_example_script(script, timeout=60)

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
        result = run_example_script(script, timeout=60)

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
        result = run_example_script(script, timeout=60)

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
        result = run_example_script(script, timeout=60)

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
        result = run_example_script(script, timeout=60)

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_exchange_catalog.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    @pytest.mark.slow
    @pytest.mark.skip(
        reason="Very slow test - run separately with: pytest tests/e2e/test_run_examples.py::TestExampleScripts::test_example_order_management -v"
    )
    def test_example_order_management(self):
        """Test example_order_management.py runs without errors."""
        script = EXAMPLES_DIR / "example_order_management.py"
        result = run_example_script(script, timeout=300)

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
        result = run_example_script(script, timeout=60)

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_service_control.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:],
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    @pytest.mark.skip(reason="Sometimes slow in CI - run separately if needed")
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

    @pytest.mark.skip(reason="Sometimes slow in CI - run separately if needed")
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

    @pytest.mark.skip(reason="Sometimes slow in CI - run separately if needed")
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

    @pytest.mark.skip(reason="Sometimes slow in CI - run separately if needed")
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
        """Test run_all_examples.py script error handling when NO server is running."""
        # NOTE: This test is problematic in parallel execution because:
        # 1. Individual example scripts start their own servers on localhost:8000
        # 2. During parallel pytest execution, multiple examples might conflict
        # 3. This test tries to verify error handling when NO server exists
        #
        # Solution: Skip during parallel execution (when worker_id is present)
        # To run this test: pytest tests/e2e/test_run_examples.py::TestExampleScripts::test_run_all_examples -v

        import os
        worker_id = os.environ.get('PYTEST_XDIST_WORKER')
        if worker_id:
            pytest.skip(
                "Skipping test_run_all_examples during parallel execution to avoid port conflicts. "
                "Run with: pytest tests/e2e/test_run_examples.py::TestExampleScripts::test_run_all_examples -v"
            )

        import httpx

        # Check if server is running on localhost:8000
        try:
            response = httpx.get("http://localhost:8000/health", timeout=1.0)
            if response.status_code == 200:
                pytest.skip(
                    "Server is running on localhost:8000 - this test requires NO server "
                    "to verify error handling. Stop the server to run this test."
                )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout):
            # Good - no server running, we can test the error case
            pass

        script = EXAMPLES_DIR / "run_all_examples.py"

        result = subprocess.run(
            [sys.executable, str(script), "--skip-websocket"],
            capture_output=True,
            text=True,
            timeout=10,  # Should fail immediately if no server
        )

        # This script expects an external server to be running
        # Since we're testing standalone examples, it should fail with server not running
        assert result.returncode != 0, "run_all_examples should fail when no server is running"

        # Check that it gives the expected error message
        assert "Server is not running" in result.stdout
        assert "Please start the server first" in result.stdout
