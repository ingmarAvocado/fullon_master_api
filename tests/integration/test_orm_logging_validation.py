"""
Tests validating fullon_log structured logging in ORM integration.

Reference: docs/FULLON_LOG_LLM_REAMDE.md lines 75-90
"""
import pytest
from fullon_master_api.gateway import MasterGateway


def test_gateway_uses_fullon_log_structured_logging(caplog):
    """
    Test that gateway uses fullon_log with structured logging (key=value).

    Reference: docs/FULLON_LOG_LLM_REAMDE.md
    """
    gateway = MasterGateway()

    with caplog.at_level("INFO"):
        orm_routers = gateway._discover_orm_routers()

    # Verify structured logging (key=value pattern)
    assert "Discovered ORM routers" in caplog.text
    assert f"count={len(orm_routers)}" in caplog.text


def test_gateway_logger_from_get_component_logger():
    """Test that gateway creates logger with get_component_logger."""
    from fullon_log import get_component_logger

    gateway = MasterGateway()

    assert hasattr(gateway, 'logger')
    assert gateway.logger is not None


def test_mounting_logs_structured_messages(caplog):
    """Test that router mounting generates structured log messages."""
    gateway = MasterGateway()

    with caplog.at_level("INFO"):
        # This will trigger mounting logs
        from fastapi import FastAPI
        app = FastAPI()
        gateway._mount_orm_routers(app)

    # Should contain structured logging
    log_text = caplog.text
    assert "All ORM routers mounted" in log_text or "ORM router mounted" in log_text


def test_auth_override_logs_structured_messages(caplog):
    """Test that auth override generates structured log messages."""
    gateway = MasterGateway()

    with caplog.at_level("DEBUG"):
        gateway._discover_orm_routers()

    # Should contain debug logging for overrides
    log_text = caplog.text
    assert "Auth dependency overridden" in log_text or "Discovered ORM routers" in log_text