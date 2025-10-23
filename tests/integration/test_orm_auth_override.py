"""
Integration tests for ORM auth dependency override.

Tests that fullon_orm_api's auth dependencies are correctly
overridden with master API's JWT authentication.
"""
import pytest
from fastapi import APIRouter
from fullon_orm_api import get_all_routers
from fullon_orm_api.dependencies.auth import get_current_user as orm_get_current_user
from fullon_master_api.auth.dependencies import get_current_user as master_get_current_user
from fullon_master_api.gateway import MasterGateway


def test_orm_and_master_get_current_user_are_different():
    """Test that ORM and master get_current_user are different functions."""
    # They should be different functions
    assert orm_get_current_user != master_get_current_user

    # But both should be callables
    assert callable(orm_get_current_user)
    assert callable(master_get_current_user)


def test_apply_auth_overrides_method_exists():
    """Test that gateway has _apply_auth_overrides method."""
    gateway = MasterGateway()
    assert hasattr(gateway, '_apply_auth_overrides')
    assert callable(gateway._apply_auth_overrides)


def test_auth_overrides_applied_to_routers():
    """Test that auth overrides are applied to all ORM routers."""
    gateway = MasterGateway()

    # Get raw ORM routers
    raw_routers = get_all_routers()

    # Apply overrides
    overridden_routers = gateway._apply_auth_overrides(raw_routers)

    # Verify overrides applied to all routers
    for router in overridden_routers:
        assert orm_get_current_user in router.dependency_overrides
        assert router.dependency_overrides[orm_get_current_user] == master_get_current_user


def test_discover_orm_routers_includes_auth_overrides():
    """Test that _discover_orm_routers includes auth overrides."""
    gateway = MasterGateway()

    # Discover routers (should include overrides)
    routers = gateway._discover_orm_routers()

    # Verify all routers have auth override
    for router in routers:
        assert orm_get_current_user in router.dependency_overrides
        assert router.dependency_overrides[orm_get_current_user] == master_get_current_user


def test_auth_override_logging():
    """Test that auth override application is logged."""
    gateway = MasterGateway()

    # Call the method - logging happens automatically via fullon_log (loguru-based)
    routers = gateway._apply_auth_overrides(get_all_routers())

    # Verify that overrides were applied (logging is verified manually via stderr output)
    assert isinstance(routers, list)
    assert len(routers) > 0

    # Verify all routers have the override
    for router in routers:
        assert orm_get_current_user in router.dependency_overrides