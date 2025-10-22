"""
Integration tests for gateway functionality.

Tests middleware integration and application composition.
"""
from fullon_master_api.auth.middleware import JWTMiddleware
from fullon_master_api.gateway import MasterGateway


def test_middleware_integration():
    """
    Test for Issue #12: [Phase 2] Integrate middleware into gateway.py

    Add JWTMiddleware to main application.

    Implementation requirements:
    - Import JWTMiddleware in src/fullon_master_api/gateway.py
    - Add middleware to app: app.add_middleware(JWTMiddleware)
    - Include auth router: app.include_router(auth_router)
    - Ensure middleware runs before routes

    This test should pass when the implementation is complete.
    """
    # Create gateway instance
    gateway = MasterGateway()
    app = gateway.get_app()

    # Verify JWTMiddleware is added to the application
    middleware_classes = [middleware.cls for middleware in app.user_middleware]
    assert JWTMiddleware in middleware_classes, "JWTMiddleware not found in app middlewares"

    # Verify middleware order - JWT runs before CORS in the middleware stack
    from fastapi.middleware.cors import CORSMiddleware
    cors_index = None
    jwt_index = None

    for i, middleware in enumerate(app.user_middleware):
        if middleware.cls == CORSMiddleware:
            cors_index = i
        elif middleware.cls == JWTMiddleware:
            jwt_index = i

    assert cors_index is not None, "CORSMiddleware not found"
    assert jwt_index is not None, "JWTMiddleware not found"
    assert jwt_index < cors_index, "JWTMiddleware should run before CORSMiddleware"

