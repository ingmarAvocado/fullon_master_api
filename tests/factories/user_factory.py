"""Factory for creating User test data in fullon_master_api tests."""
from typing import Optional

from fullon_orm.models import User
from fullon_orm.models.user import RoleEnum
from .base_factory import BaseFactory


class UserFactory(BaseFactory):
    """Factory for creating User instances for testing.

    Provides methods to create users with various configurations:
    - Regular users
    - Admin users
    - Users with managers
    - Users with custom attributes
    """

    model = User

    @classmethod
    def get_defaults(cls) -> dict:
        """Get default values for User model.

        Returns:
            Dictionary with default user attributes
        """
        return {
            "mail": cls.random_email(domain="example.com"),
            "password": "hashed_password_123",  # Simulated bcrypt hash
            "f2a": "",  # Two-factor authentication (empty = disabled)
            "role": RoleEnum.USER,  # Default to regular user
            "name": cls.random_string(6, prefix="Test"),
            "lastname": cls.random_string(8, prefix="User"),
            "phone": "",
            "id_num": "",
            "note": None,
            "manager": None,
            "external_id": None,
            "active": True,
        }

    @classmethod
    async def create_admin(cls, session, **kwargs):
        """Create an admin user.

        Args:
            session: SQLAlchemy async session
            **kwargs: Additional user attributes

        Returns:
            Admin User instance
        """
        return await cls.create(session, role=RoleEnum.ADMIN, **kwargs)

    @classmethod
    async def create_inactive(cls, session, **kwargs):
        """Create an inactive user.

        Args:
            session: SQLAlchemy async session
            **kwargs: Additional user attributes

        Returns:
            Inactive User instance
        """
        return await cls.create(session, active=False, **kwargs)

    @classmethod
    async def create_with_manager(cls, session, manager: Optional[User] = None, **kwargs):
        """Create a user with a manager.

        Args:
            session: SQLAlchemy async session
            manager: Optional manager User instance (creates one if not provided)
            **kwargs: Additional user attributes

        Returns:
            User instance with manager assigned
        """
        if manager is None:
            manager = await cls.create_admin(session)

        return await cls.create(session, manager=manager.uid, **kwargs)

    @classmethod
    async def create_with_email(cls, session, email: str, **kwargs):
        """Create a user with specific email.

        Useful for testing authentication flows where email matters.

        Args:
            session: SQLAlchemy async session
            email: Email address for the user
            **kwargs: Additional user attributes

        Returns:
            User instance with specified email
        """
        return await cls.create(session, mail=email, **kwargs)

    @classmethod
    async def create_with_repository(cls, db_context, email: str = None, **kwargs):
        """Create user using repository (commits to database).

        Use this for integration tests where middleware needs to see the user.
        The repository's add_user() commits the transaction.

        Args:
            db_context: Test database context with repositories
            email: Optional email address
            **kwargs: Additional user attributes

        Returns:
            User instance with uid assigned
        """
        # Build user model with defaults
        defaults = cls.get_defaults()
        if email:
            defaults['mail'] = email
        defaults.update(kwargs)

        # Create User model
        from fullon_orm.models import User
        user = User(**defaults)

        # Use repository which commits
        created_user = await db_context.users.add_user(user)
        return created_user
