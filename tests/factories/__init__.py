"""Test data factories for fullon_master_api.

This module provides factory classes for creating test data following
the factory pattern used in fullon_orm. Factories provide:

- Consistent test data generation
- Easy creation of related objects
- Reusable fixtures
- Clear, readable test code

Usage:
    from tests.factories import UserFactory

    async def test_example(db_context):
        user = await UserFactory.create(db_context.session)
        assert user.uid is not None
"""

from .base_factory import BaseFactory
from .user_factory import UserFactory

__all__ = [
    "BaseFactory",
    "UserFactory",
]
