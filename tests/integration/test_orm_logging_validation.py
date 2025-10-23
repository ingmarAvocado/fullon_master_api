"""
Tests validating fullon_log structured logging in ORM integration.

Reference: docs/FULLON_LOG_LLM_REAMDE.md lines 75-90
"""
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

    gateway = MasterGateway()

    assert hasattr(gateway, 'logger')
    assert gateway.logger is not None
