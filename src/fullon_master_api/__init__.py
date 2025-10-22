"""
Fullon Master API - Unified API Gateway.

Composes existing Fullon APIs with centralized JWT authentication.
"""
from .config import settings
from .gateway import MasterGateway, app

__version__ = "1.0.0"
__all__ = ["MasterGateway", "app", "settings"]
