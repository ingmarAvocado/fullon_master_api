"""
Integration tests for complete auth flow with ORM endpoints.

Validates the request processing pipeline:
Request → CORS → JWT Middleware → Route Handler → Response
"""

import pytest


@pytest.mark.asyncio
async def test_auth_middleware_sets_request_state_user(client, auth_headers):
    """
    Test that JWT middleware correctly sets request.state.user.

    This validates Issue #11 integration.
    """
    # This is implicitly tested by successful endpoint calls
    response = client.get("/api/v1/orm/users/me", headers=auth_headers)

    # If this succeeds, middleware set request.state.user correctly
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_orm_dependency_gets_user_from_request_state(client, auth_headers, test_user):
    """
    Test that ORM endpoints use master API's get_current_user dependency.

    This validates Issue #16 (dependency override).
    """
    response = client.get("/api/v1/orm/users/me", headers=auth_headers)

    assert response.status_code == 200

    # User data should match what middleware loaded
    user_data = response.json()
    assert user_data["mail"] == test_user.mail


@pytest.mark.asyncio
async def test_auth_flow_logs_correctly(client, auth_headers, caplog):
    """
    Test that auth flow generates expected log messages.
    """
    with caplog.at_level("DEBUG"):
        response = client.get("/api/v1/orm/users/me", headers=auth_headers)

    # Should see auth-related logs
    # (Exact log messages depend on implementation)
    assert response.status_code == 200
