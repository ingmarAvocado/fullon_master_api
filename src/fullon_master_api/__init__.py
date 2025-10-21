"""
Fullon Master API - Unified API Gateway.

Composes existing Fullon APIs with centralized JWT authentication.
"""
from .gateway import MasterGateway, app
from .config import settings

__version__ = "1.0.0"
__all__ = ["MasterGateway", "app", "settings"]
