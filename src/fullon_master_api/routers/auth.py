"""
Authentication router for Fullon Master API.

Provides JWT token-based authentication endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from fullon_log import get_component_logger
from fullon_orm.models import User

from ..auth.dependencies import get_current_user
from ..auth.jwt import JWTHandler, authenticate_user
from ..config import settings

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Initialize JWT handler
jwt_handler = JWTHandler(settings.jwt_secret_key, settings.jwt_algorithm)

# Security scheme
security = HTTPBearer()

# Module logger
logger = get_component_logger("fullon.master_api.auth")


async def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Dependency to get current user with configured secret key."""
    return await get_current_user(credentials, secret_key=settings.jwt_secret_key)


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> dict:
    """
    Authenticate user and return JWT access token.

    Args:
        form_data: OAuth2 password request form with username and password

    Returns:
        Dictionary containing access token, token type, and expiration

    Raises:
        HTTPException: 401 if authentication fails
    """
    logger.info("Login attempt", username=form_data.username)

    # Authenticate user against database
    user: User | None = await authenticate_user(form_data.username, form_data.password)

    if not user:
        logger.warning(
            "Login failed",
            username=form_data.username,
            reason="invalid_credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate JWT token using User ORM properties
    token = jwt_handler.generate_token(
        user_id=user.uid,
        username=user.username,
        email=user.email
    )

    logger.info(
        "Login successful",
        username=form_data.username,
        user_id=user.uid
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expiration_minutes * 60
    }


@router.get("/verify")
async def verify_token(
    current_user: User = Depends(get_current_user_dependency)
) -> dict:
    """
    Verify JWT token and return current user information.

    Args:
        current_user: Authenticated user from JWT token

    Returns:
        Dictionary containing user information

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    logger.info("Token verification successful", user_id=current_user.uid)

    return {
        "user_id": current_user.uid,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": True  # Assuming user is active if authenticated
    }
