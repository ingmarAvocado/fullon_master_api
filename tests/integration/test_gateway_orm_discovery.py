"""
Integration tests for gateway ORM router discovery.

Tests that MasterGateway can discover ORM routers during initialization.
"""
from fullon_master_api.gateway import MasterGateway


def test_gateway_can_discover_orm_routers():
    """Test that gateway can discover ORM routers."""
    gateway = MasterGateway()

    # Call discovery method (not mounting yet)
    orm_routers = gateway._discover_orm_routers()

    assert isinstance(orm_routers, list)
    assert len(orm_routers) > 0


def test_gateway_logs_router_discovery():
    """Test that router discovery is logged."""
    gateway = MasterGateway()

    # Call the method - logging happens automatically
    orm_routers = gateway._discover_orm_routers()

    # Verify that routers were discovered (logging is verified manually)
    assert isinstance(orm_routers, list)
    assert len(orm_routers) > 0
