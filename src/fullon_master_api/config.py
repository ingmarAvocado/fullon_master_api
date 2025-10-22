"""
Configuration management for Fullon Master API.

Uses pydantic-settings for environment-based configuration.
"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_title: str = "Fullon Master API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    api_description: str = "Unified API Gateway for Fullon Trading Platform"

    # JWT Authentication
    jwt_secret_key: str = "dev-secret-key-change-in-production"  # Override in .env for production!
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # CORS Configuration
    cors_origins: List[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "beautiful"
    log_console: bool = True
    log_colors: bool = True

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Allow extra env vars (for fullon_orm, fullon_cache, etc.)
    )


# Global settings instance
settings = Settings()
