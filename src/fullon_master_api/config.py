"""
Configuration management for Fullon Master API.

Uses pydantic-settings for environment-based configuration.
"""
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # API Key Authentication
    enable_api_key_auth: bool = True
    api_key_header_name: str = "X-API-Key"

    # Admin Configuration (NEW - Phase 6)
    admin_mail: str = "admin@fullon"  # Admin user email for service control

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

    # Health Monitor Configuration (Issue #43)
    health_monitor_enabled: bool = True
    health_check_interval_seconds: int = 300  # 5 minutes
    health_stale_process_threshold_minutes: int = 10
    health_auto_restart_enabled: bool = True
    health_auto_restart_cooldown_seconds: int = 300  # 5 minutes
    health_auto_restart_max_per_hour: int = 5
    health_services_to_monitor: List[str] = ["ticker", "ohlcv", "account"]
    health_enable_process_cache_checks: bool = True
    health_enable_database_checks: bool = True
    health_enable_redis_checks: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra env vars (for fullon_orm, fullon_cache, etc.)
    )


# Global settings instance
settings = Settings()
