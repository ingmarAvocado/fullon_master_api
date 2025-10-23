"""Base factory for creating test data in fullon_master_api tests."""
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Type, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from fullon_orm.base import Base

T = TypeVar("T", bound=Base)


class BaseFactory:
    """Base factory class for creating test objects.

    Provides utility methods for generating random test data and
    a consistent interface for creating model instances.
    """

    model: Type[Base] = None

    @classmethod
    def random_string(cls, length: int = 10, prefix: str = "") -> str:
        """Generate a random string.

        Args:
            length: Length of random part (default: 10)
            prefix: Optional prefix to add (default: "")

        Returns:
            Random string with optional prefix
        """
        chars = string.ascii_letters + string.digits
        random_part = "".join(random.choice(chars) for _ in range(length))
        return f"{prefix}{random_part}" if prefix else random_part

    @classmethod
    def random_email(cls, domain: str = "example.com") -> str:
        """Generate a random email address.

        Args:
            domain: Email domain (default: "example.com")

        Returns:
            Random email address
        """
        username = cls.random_string(8)
        return f"{username}@{domain}"

    @classmethod
    def random_phone(cls) -> str:
        """Generate a random phone number.

        Returns:
            10-digit phone number as string
        """
        return "".join(random.choice(string.digits) for _ in range(10))

    @classmethod
    def random_int(cls, min_val: int = 1, max_val: int = 1000) -> int:
        """Generate a random integer.

        Args:
            min_val: Minimum value (default: 1)
            max_val: Maximum value (default: 1000)

        Returns:
            Random integer in range
        """
        return random.randint(min_val, max_val)

    @classmethod
    def random_float(cls, min_val: float = 0.0, max_val: float = 100.0, decimals: int = 2) -> float:
        """Generate a random float.

        Args:
            min_val: Minimum value (default: 0.0)
            max_val: Maximum value (default: 100.0)
            decimals: Decimal places to round to (default: 2)

        Returns:
            Random float in range
        """
        value = random.uniform(min_val, max_val)
        return round(value, decimals)

    @classmethod
    def random_bool(cls) -> bool:
        """Generate a random boolean.

        Returns:
            Random True or False
        """
        return random.choice([True, False])

    @classmethod
    def random_datetime(cls, days_back: int = 30) -> datetime:
        """Generate a random datetime within the last N days.

        Args:
            days_back: Number of days to look back (default: 30)

        Returns:
            Random UTC datetime
        """
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=days_back)
        random_seconds = random.randint(0, int((now - past).total_seconds()))
        return past + timedelta(seconds=random_seconds)

    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        """Get default values for the model.

        Override in subclasses to provide model-specific defaults.

        Returns:
            Dictionary of default field values
        """
        return {}

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        **kwargs
    ) -> T:
        """Create and persist a model instance.

        Args:
            session: SQLAlchemy async session
            **kwargs: Field values to override defaults

        Returns:
            Created model instance with database-assigned ID

        Raises:
            NotImplementedError: If model attribute not set in subclass
        """
        if cls.model is None:
            raise NotImplementedError("model attribute must be set in factory subclass")

        # Merge defaults with provided kwargs
        defaults = cls.get_defaults()
        defaults.update(kwargs)

        # Create instance
        instance = cls.model(**defaults)

        # Add to session and flush to get ID assigned
        session.add(instance)
        await session.flush()

        return instance

    @classmethod
    async def create_batch(
        cls,
        session: AsyncSession,
        count: int,
        **kwargs
    ) -> list[T]:
        """Create multiple instances.

        Args:
            session: SQLAlchemy async session
            count: Number of instances to create
            **kwargs: Field values to apply to all instances

        Returns:
            List of created model instances
        """
        instances = []
        for _ in range(count):
            instance = await cls.create(session, **kwargs)
            instances.append(instance)
        return instances
