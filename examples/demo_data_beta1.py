#!/usr/bin/env python3
"""
Demo Data Beta1 - Bitmex + Yahoo Multi-Exchange Setup

Creates test database with multi-exchange demo data:
- Test user for authentication (admin@fullon)
- Bitmex exchange: BTC/USD:BTC, ETH/USD:BTC
- Yahoo exchange: GOLD (Gold futures), SPX (S&P 500 index)
- OHLCV TimescaleDB tables for all symbols (no sample candles)

Note: Yahoo symbols use clean format (GOLD, SPX) which the Yahoo adapter
      translates to Yahoo Finance API format (GC=F, ^GSPC) automatically.

Used by example_beta1.py with fixed database names:
- fullon_beta1 (ORM database)
- fullon_beta1_ohlcv (OHLCV database)

Usage:
    python examples/demo_data_beta1.py --setup DB_NAME    # Create specific DB
    python examples/demo_data_beta1.py --cleanup DB_NAME  # Drop specific DB
"""

import argparse
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import redis
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext, init_db
from fullon_orm.models import Exchange, Symbol, User
from fullon_orm.models.user import RoleEnum

# Create fullon logger alongside color output
fullon_logger = get_component_logger("fullon.master_api.example.demo_data_beta1")


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.CYAN}→ {msg}{Colors.END}")


def print_header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.END}\n")


async def create_test_database(db_name: str) -> bool:
    """Create isolated test database using fullon_orm database utilities where possible"""
    print_info(f"Creating test database: {db_name}")
    fullon_logger.info(f"Creating isolated test database: {db_name}")

    try:
        # Try to use fullon_orm database utilities first
        try:
            from fullon_orm.database import DatabaseManager

            db_manager = DatabaseManager()

            # Use fullon_orm database creation if available
            await db_manager.create_database(db_name)
            print_success(f"Test database created via fullon_orm: {db_name}")
            fullon_logger.info(f"Test database created successfully via fullon_orm: {db_name}")
            return True

        except (ImportError, AttributeError):
            # Fallback to direct asyncpg for database creation (administrative operation)
            print_info("Using direct database creation (fullon_orm utilities not available)")

            import asyncpg

            host = os.getenv("DB_HOST", "localhost")
            port = int(os.getenv("DB_PORT", "5432"))
            user = os.getenv("DB_USER", "postgres")
            password = os.getenv("DB_PASSWORD", "")

            conn = await asyncpg.connect(
                host=host, port=port, user=user, password=password, database="postgres"
            )

            try:
                # Database creation requires direct SQL (administrative operation)
                await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
                await conn.execute(f'CREATE DATABASE "{db_name}"')

                print_success(f"Test database created: {db_name}")
                fullon_logger.info(f"Test database created successfully: {db_name}")
                return True

            finally:
                await conn.close()

    except Exception as e:
        print_error(f"Failed to create test database: {e}")
        fullon_logger.error(f"Failed to create test database {db_name}: {e}")
        return False


async def drop_test_database(db_name: str) -> bool:
    """Drop test database using fullon_orm database utilities where possible"""
    print_info(f"Dropping test database: {db_name}")

    try:
        # Try to use fullon_orm database utilities first
        try:
            from fullon_orm.database import DatabaseManager

            db_manager = DatabaseManager()

            # Use fullon_orm database dropping if available
            await db_manager.drop_database(db_name)
            print_success(f"Test database dropped via fullon_orm: {db_name}")
            return True

        except (ImportError, AttributeError):
            # Fallback to direct asyncpg for database operations (administrative)
            print_info("Using direct database operations (fullon_orm utilities not available)")

            import asyncpg

            host = os.getenv("DB_HOST", "localhost")
            port = int(os.getenv("DB_PORT", "5432"))
            user = os.getenv("DB_USER", "postgres")
            password = os.getenv("DB_PASSWORD", "")

            conn = await asyncpg.connect(
                host=host, port=port, user=user, password=password, database="postgres"
            )

            try:
                # Connection termination and database dropping require direct SQL (administrative)
                await conn.execute(
                    """
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = $1
                    AND pid <> pg_backend_pid()
                """,
                    db_name,
                )

                await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')

                print_success(f"Test database dropped: {db_name}")
                return True

            finally:
                await conn.close()

    except Exception as e:
        print_error(f"Failed to drop test database: {e}")
        return False


async def database_exists(db_name: str) -> bool:
    """
    Check if database exists.

    Args:
        db_name: Name of the database to check

    Returns:
        bool: True if database exists, False otherwise
    """
    try:
        import asyncpg

        host = os.getenv("DB_HOST", "localhost")
        port = int(os.getenv("DB_PORT", "5432"))
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")

        conn = await asyncpg.connect(
            host=host, port=port, user=user, password=password, database="postgres"
        )

        try:
            result = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                db_name
            )
            return result is not None

        finally:
            await conn.close()

    except Exception as e:
        fullon_logger.error(f"Failed to check if database exists: {e}")
        return False


async def create_dual_test_databases(base_name: str) -> tuple[str, str]:
    """
    Create both fullon_orm and fullon_ohlcv test databases.

    Returns:
        tuple[str, str]: (orm_db_name, ohlcv_db_name)
    """
    orm_db_name = base_name
    ohlcv_db_name = f"{base_name}_ohlcv"

    print_info(f"Creating dual test databases: {orm_db_name} + {ohlcv_db_name}")
    fullon_logger.info(f"Creating dual test databases: orm={orm_db_name}, ohlcv={ohlcv_db_name}")

    # Create both databases
    orm_success = await create_test_database(orm_db_name)
    ohlcv_success = await create_test_database(ohlcv_db_name)

    if orm_success and ohlcv_success:
        print_success("Both test databases created successfully")
        fullon_logger.info(f"Dual test databases created: orm={orm_db_name}, ohlcv={ohlcv_db_name}")
        return orm_db_name, ohlcv_db_name
    else:
        # Clean up if one failed
        if orm_success:
            await drop_test_database(orm_db_name)
        if ohlcv_success:
            await drop_test_database(ohlcv_db_name)
        raise RuntimeError("Failed to create both test databases")


async def drop_dual_test_databases(orm_db_name: str, ohlcv_db_name: str) -> bool:
    """Drop both fullon_orm and fullon_ohlcv test databases."""
    print_info(f"Dropping dual test databases: {orm_db_name} + {ohlcv_db_name}")
    fullon_logger.info(f"Dropping dual test databases: orm={orm_db_name}, ohlcv={ohlcv_db_name}")

    orm_success = await drop_test_database(orm_db_name)
    ohlcv_success = await drop_test_database(ohlcv_db_name)

    if orm_success and ohlcv_success:
        print_success("Both test databases dropped successfully")
        fullon_logger.info(f"Dual test databases dropped: orm={orm_db_name}, ohlcv={ohlcv_db_name}")
        return True
    else:
        print_warning(f"Some databases failed to drop: orm={orm_success}, ohlcv={ohlcv_success}")
        return False


@asynccontextmanager
async def database_context_for_test(db_name: str):
    """Context manager for test database lifecycle (following fullon_orm_api pattern)"""
    # Save original environment variables
    original_db_url = os.getenv("DATABASE_URL", "")
    original_db_name = os.getenv("DB_NAME", "")

    # Update DATABASE_URL and DB_NAME to point to test database
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    test_db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    os.environ["DATABASE_URL"] = test_db_url
    os.environ["DB_NAME"] = db_name

    try:
        # Create test database
        if not await create_test_database(db_name):
            raise Exception("Failed to create test database")

        # Clear Redis cache to avoid stale data
        try:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            r = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
            r.flushdb()
            print_info("Cleared Redis cache to avoid stale data")
        except Exception as e:
            print_warning(f"Could not clear Redis cache: {e}")

        # Initialize schema
        print_info("Initializing database schema...")
        await init_db()
        print_success("Database schema initialized")

        yield db_name

    finally:
        # Restore original environment variables
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_db_name:
            os.environ["DB_NAME"] = original_db_name
        else:
            os.environ.pop("DB_NAME", None)

        # Drop test database
        await drop_test_database(db_name)


async def clear_fullon_cache():
    """Clear fullon_orm cache outside of transaction context to avoid greenlet violations"""
    try:
        from fullon_orm.cache import cache_manager

        cache_manager.region.invalidate()
        cache_manager.invalidate_exchange_caches()
        print_info("Cleared fullon_orm cache")
    except Exception as e:
        print_warning(f"Could not clear fullon_orm cache: {e}")


async def install_demo_data():
    """Install demo data - Bitmex + Yahoo exchanges"""
    print_header("INSTALLING BITMEX + YAHOO DEMO DATA")
    fullon_logger.info("Starting demo data installation (Bitmex + Yahoo)")

    # Clear cache before starting transaction (outside transaction context)
    await clear_fullon_cache()

    api_key = None  # Store API key to return
    try:
        # Use multiple transactions with commits like ticker service (working pattern)
        async with DatabaseContext() as db:
            # Install user first
            uid = await install_admin_user_internal(db)
            if not uid:
                print_error("Could not install admin user")
                await db.rollback()
                return False
            # Commit user creation before proceeding
            await db.commit()
            print_success(f"Admin user created successfully with UID: {uid}")

            # Create API key for admin user
            api_key = await create_admin_api_key(db, uid)
            if not api_key:
                print_error("Could not create API key")
                await db.rollback()
                return False
            await db.commit()
            print_success(f"API key created successfully")

            # Install Bitmex exchange only
            ex_id, cat_ex_id = await install_bitmex_exchange_internal(db, uid=uid)
            if not ex_id or not cat_ex_id:
                print_error("Could not install Bitmex exchange")
                await db.rollback()
                return False
            # Commit exchange creation before proceeding
            await db.commit()
            print_success("Bitmex exchange created successfully")

            # Install Bitmex symbols
            await install_bitmex_symbols_internal(db, cat_ex_id=cat_ex_id)
            await db.commit()
            print_success("Bitmex symbols installed successfully")

            # Install Yahoo exchange
            yahoo_ex_id, yahoo_cat_ex_id = await install_yahoo_exchange_internal(db, uid=uid)
            if not yahoo_ex_id or not yahoo_cat_ex_id:
                print_error("Could not install Yahoo exchange")
                await db.rollback()
                return False
            # Commit exchange creation before proceeding
            await db.commit()
            print_success("Yahoo exchange created successfully")

            # Install Yahoo symbols
            await install_yahoo_symbols_internal(db, cat_ex_id=yahoo_cat_ex_id)
            await db.commit()
            print_success("Yahoo symbols installed successfully")

            # Initialize OHLCV symbol tables for all exchanges (no sample data)
            await init_ohlcv_symbol_tables()
            print_success("OHLCV symbol tables initialized successfully for all exchanges")

            print_success("Demo data installation complete!")
            fullon_logger.info("Demo data installation completed successfully")

            # Save API key to environment file for client to use
            if api_key:
                api_key_file = Path(__file__).parent / ".beta1_api_key"
                try:
                    api_key_file.write_text(api_key)
                    print_success(f"API key saved to {api_key_file}")
                except Exception as e:
                    print_warning(f"Could not save API key to file: {e}")

            return True

    except Exception as e:
        print_error(f"Failed to install demo data: {e}")
        fullon_logger.error(f"Demo data installation failed: {e}")
        import traceback
        print_error(traceback.format_exc())
        return False


async def install_admin_user_internal(db: DatabaseContext) -> int | None:
    """Install admin user using provided DatabaseContext and ORM models (fullon_orm pattern)."""
    print_info("Installing admin user...")

    # Check if user exists
    admin_email = os.getenv("ADMIN_MAIL", "admin@fullon")
    print_info(f"Using admin email: {admin_email}")

    existing_uid = await db.users.get_user_id(admin_email)
    if existing_uid:
        print_warning("Admin user already exists")
        return existing_uid

    # Create User ORM model with hashed password
    try:
        from fullon_master_api.auth.jwt import hash_password

        hashed_password = hash_password("password")
        print_info(f"Password hashed successfully (starts with: {hashed_password[:10]}...)")
    except Exception as e:
        print_error(f"Failed to hash password: {e}")
        # Fallback to plaintext (NOT RECOMMENDED for production!)
        hashed_password = "password"

    user = User(
        mail=admin_email,
        password=hashed_password,
        f2a="---",
        role=RoleEnum.ADMIN,
        name="robert",
        lastname="plant",
        phone="666666666",
        id_num="3242",
    )

    try:
        created_user = await db.users.add_user(user)
        print_success(f"Admin user created: {created_user.name} {created_user.lastname}")
        return created_user.uid
    except Exception as e:
        print_error(f"Failed to create admin user: {e}")
        return None


async def create_admin_api_key(db: DatabaseContext, uid: int) -> str | None:
    """Create API key for admin user using fullon_orm."""
    print_info("Creating API key for admin user...")

    try:
        import secrets
        from fullon_orm.models.api_key import ApiKey

        # Generate secure API key
        api_key_value = secrets.token_urlsafe(32)

        # Create ApiKey model
        api_key = ApiKey(
            uid=uid,
            key=api_key_value,
            name="Beta1 Admin Key",
            description="API key for beta1 example client",
            scopes="read,write,admin",
            is_active=True,
            expires_at=None  # No expiration
        )

        # Add to database
        created_key = await db.api_keys.add(api_key)
        print_success(f"API key created: {api_key_value[:20]}...")
        return created_key.key

    except Exception as e:
        print_error(f"Failed to create API key: {e}")
        import traceback
        print_error(traceback.format_exc())
        return None


async def install_bitmex_exchange_internal(
    db: DatabaseContext, uid: int
) -> tuple[int | None, int | None]:
    """Install Bitmex exchange only."""
    print_info("Installing Bitmex exchange...")

    exchange_name = "bitmex"
    user_exchange_name = "bitmex1"

    # Use repository method to get existing cat_exchanges
    cat_exchanges = await db.exchanges.get_cat_exchanges(all=True)
    print_info(f"  Found {len(cat_exchanges)} existing category exchanges in database")

    # Check if category exchange exists
    cat_ex_id = None
    for ce in cat_exchanges:
        if ce.name == exchange_name:
            cat_ex_id = ce.cat_ex_id
            print_info(f"  Category exchange '{exchange_name}' already exists with ID: {cat_ex_id}")
            break

    # If no category exchange exists, create one
    if not cat_ex_id:
        cat_exchange = await db.exchanges.create_cat_exchange(exchange_name, "")
        cat_ex_id = cat_exchange.cat_ex_id
        print_info(f"  Created category exchange: {exchange_name}")

    # Check if user already has this exchange
    user_exchanges = await db.exchanges.get_user_exchanges(uid)
    existing_exchange = None
    for ue in user_exchanges:
        if ue.name == user_exchange_name and ue.cat_ex_id == cat_ex_id:
            existing_exchange = ue
            break

    if existing_exchange:
        ex_id = existing_exchange.ex_id
        print_info(f"  User exchange '{user_exchange_name}' already exists")
        return (ex_id, cat_ex_id)
    else:
        # Create user exchange
        exchange = Exchange(
            uid=uid, cat_ex_id=cat_ex_id, name=user_exchange_name, test=False, active=True
        )

        created_exchange = await db.exchanges.add_user_exchange(exchange)
        ex_id = created_exchange.ex_id
        print_success(f"Exchange created: {user_exchange_name}")
        return (ex_id, cat_ex_id)


async def install_yahoo_exchange_internal(
    db: DatabaseContext, uid: int
) -> tuple[int | None, int | None]:
    """Install Yahoo exchange for data-only market data."""
    print_info("Installing Yahoo exchange...")

    exchange_name = "yahoo"
    user_exchange_name = "yahoo1"

    # Use repository method to get existing cat_exchanges
    cat_exchanges = await db.exchanges.get_cat_exchanges(all=True)
    print_info(f"  Found {len(cat_exchanges)} existing category exchanges in database")

    # Check if category exchange exists
    cat_ex_id = None
    for ce in cat_exchanges:
        if ce.name == exchange_name:
            cat_ex_id = ce.cat_ex_id
            print_info(f"  Category exchange '{exchange_name}' already exists with ID: {cat_ex_id}")
            break

    # If no category exchange exists, create one
    if not cat_ex_id:
        cat_exchange = await db.exchanges.create_cat_exchange(exchange_name, "")
        cat_ex_id = cat_exchange.cat_ex_id
        print_info(f"  Created category exchange: {exchange_name}")

    # Check if user already has this exchange
    user_exchanges = await db.exchanges.get_user_exchanges(uid)
    existing_exchange = None
    for ue in user_exchanges:
        if ue.name == user_exchange_name and ue.cat_ex_id == cat_ex_id:
            existing_exchange = ue
            break

    if existing_exchange:
        ex_id = existing_exchange.ex_id
        print_info(f"  User exchange '{user_exchange_name}' already exists")
        return (ex_id, cat_ex_id)
    else:
        # Create user exchange
        exchange = Exchange(
            uid=uid, cat_ex_id=cat_ex_id, name=user_exchange_name, test=False, active=True
        )

        created_exchange = await db.exchanges.add_user_exchange(exchange)
        ex_id = created_exchange.ex_id
        print_success(f"Exchange created: {user_exchange_name}")
        return (ex_id, cat_ex_id)


async def install_bitmex_symbols_internal(db: DatabaseContext, cat_ex_id: int):
    """Install Bitmex symbols only."""
    print_info("Installing Bitmex symbols...")

    # Clear cache before symbol installation
    try:
        from fullon_orm.cache import cache_manager

        cache_manager.region.invalidate()
        cache_manager.invalidate_exchange_caches()
        print_info("  Cache cleared before symbol installation")
    except Exception as cache_error:
        print_warning(f"Could not clear cache (continuing anyway): {cache_error}")

    # Define Bitmex symbols (from demo_data.py)
    symbols_data = [
        {
            "symbol": "BTC/USD:BTC",
            "updateframe": "1m",
            "backtest": 120,
            "decimals": 6,
            "base": "BTC",
            "quote": "USD",
            "futures": True,
        },
        {
            "symbol": "ETH/USD:BTC",
            "updateframe": "1m",
            "backtest": 120,
            "decimals": 6,
            "base": "ETH",
            "quote": "USD",
            "futures": True,
        }
    ]

    symbols_created = 0
    for symbol_data in symbols_data:
        try:
            # Check if symbol already exists
            existing_symbol = None
            try:
                existing_symbol = await db.symbols.get_by_symbol(symbol_data["symbol"], cat_ex_id=cat_ex_id)
            except (AttributeError, Exception):
                pass

            if existing_symbol:
                print_warning(f"  Symbol {symbol_data['symbol']} already exists")
                continue

            # Create Symbol model instance
            symbol = Symbol(
                symbol=symbol_data["symbol"],
                cat_ex_id=cat_ex_id,
                updateframe=symbol_data["updateframe"],
                backtest=symbol_data["backtest"],
                decimals=symbol_data["decimals"],
                base=symbol_data["base"],
                quote=symbol_data["quote"],
                futures=symbol_data["futures"],
            )

            # Use repository method
            created_symbol = await db.symbols.add_symbol(symbol)
            if created_symbol:
                symbols_created += 1
                print_info(f"  Added symbol: {symbol_data['symbol']}")

        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                print_warning(f"  Symbol {symbol_data['symbol']} already exists")
            else:
                print_error(f"  Failed to create symbol {symbol_data['symbol']}: {e}")

    if symbols_created > 0:
        print_success(f"Symbols installed successfully ({symbols_created} new)")
    else:
        print_info("All symbols already existed")


async def install_yahoo_symbols_internal(db: DatabaseContext, cat_ex_id: int):
    """Install Yahoo symbols for market data (gold and SPX)."""
    print_info("Installing Yahoo symbols...")

    # Clear cache before symbol installation
    try:
        from fullon_orm.cache import cache_manager

        cache_manager.region.invalidate()
        cache_manager.invalidate_exchange_caches()
        print_info("  Cache cleared before symbol installation")
    except Exception as cache_error:
        print_warning(f"Could not clear cache (continuing anyway): {cache_error}")

    # Define Yahoo symbols (clean format - adapter translates to Yahoo API format)
    symbols_data = [
        {
            "symbol": "GOLD",  # Yahoo adapter translates to GC=F (Gold futures)
            "updateframe": "1d",
            "backtest": 100,
            "decimals": 2,
            "base": "GOLD",
            "quote": "USD",
            "futures": True,
        },
        {
            "symbol": "SPX",  # Yahoo adapter translates to ^GSPC (S&P 500 index)
            "updateframe": "1d",
            "backtest": 100,
            "decimals": 2,
            "base": "SPX",
            "quote": "USD",
            "futures": False,
        }
    ]

    symbols_created = 0
    for symbol_data in symbols_data:
        try:
            # Check if symbol already exists
            existing_symbol = None
            try:
                existing_symbol = await db.symbols.get_by_symbol(symbol_data["symbol"], cat_ex_id=cat_ex_id)
            except (AttributeError, Exception):
                pass

            if existing_symbol:
                print_warning(f"  Symbol {symbol_data['symbol']} already exists")
                continue

            # Create Symbol model instance
            symbol = Symbol(
                symbol=symbol_data["symbol"],
                cat_ex_id=cat_ex_id,
                updateframe=symbol_data["updateframe"],
                backtest=symbol_data["backtest"],
                decimals=symbol_data["decimals"],
                base=symbol_data["base"],
                quote=symbol_data["quote"],
                futures=symbol_data["futures"],
            )

            # Use repository method
            created_symbol = await db.symbols.add_symbol(symbol)
            if created_symbol:
                symbols_created += 1
                print_info(f"  Added symbol: {symbol_data['symbol']}")

        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                print_warning(f"  Symbol {symbol_data['symbol']} already exists")
            else:
                print_error(f"  Failed to create symbol {symbol_data['symbol']}: {e}")

    if symbols_created > 0:
        print_success(f"Symbols installed successfully ({symbols_created} new)")
    else:
        print_info("All symbols already existed")


async def init_ohlcv_symbol_tables():
    """
    Initialize OHLCV symbol tables for all exchanges and symbols (no sample data).

    Creates TimescaleDB tables but does NOT insert any candles/trades.
    Symbols: Bitmex (BTC/USD:BTC, ETH/USD:BTC), Yahoo (GOLD, SPX)

    Note: Yahoo uses clean symbol format (GOLD, SPX) which are automatically
          translated to Yahoo API format (GC=F, ^GSPC) by the adapter.
    """
    print_info("Initializing OHLCV symbol tables for all exchanges...")

    # Define all symbols to initialize (clean format for Yahoo)
    symbols_to_init = [
        ("bitmex", "BTC/USD:BTC"),
        ("bitmex", "ETH/USD:BTC"),
        ("yahoo", "GOLD"),  # Yahoo adapter translates to GC=F
        ("yahoo", "SPX"),   # Yahoo adapter translates to ^GSPC
    ]

    try:
        from fullon_ohlcv.repositories.ohlcv import CandleRepository

        # Get OHLCV database configuration
        ohlcv_db_name = os.getenv("DB_OHLCV_NAME", os.getenv("DB_NAME", "fullon2"))
        print_info(f"  Using OHLCV database: {ohlcv_db_name}")

        # CRITICAL: Override DB_NAME for fullon_ohlcv to use correct database
        original_db_name = os.environ.get("DB_NAME")
        os.environ["DB_NAME"] = ohlcv_db_name

        # Initialize each symbol
        for exchange, symbol in symbols_to_init:
            try:
                print_info(f"  Initializing CandleRepository for {exchange}/{symbol}...")
                repo = CandleRepository(
                    exchange=exchange,
                    symbol=symbol,
                    test=False,  # Uses DB_NAME from environment
                )
                await repo.initialize()
                print_success(f"    Repository initialized for {exchange}/{symbol}")

                # Create symbol tables via init_symbol()
                print_info(f"    Creating TimescaleDB tables via init_symbol()...")
                success = await repo.init_symbol()
                if not success:
                    raise Exception(f"init_symbol() failed for {exchange}/{symbol}")

                # Normalize symbol name for table names
                table_name = symbol.replace("/", "_").replace(":", "_").replace("=", "_").replace("^", "").lower()
                print_success(f"    ✅ Created TimescaleDB tables:")
                print_info(f"       - {exchange}.{table_name}_trades (hypertable)")
                print_info(f"       - {exchange}.{table_name}_candles1m (hypertable)")
                print_info(f"       - {exchange}.{table_name}_candles1m_view (continuous aggregate)")

                await repo.close()

            except Exception as e:
                print_error(f"    Failed to initialize {exchange}/{symbol}: {e}")
                print_warning(f"    Continuing with remaining symbols...")

        # Restore original DB_NAME
        if original_db_name:
            os.environ["DB_NAME"] = original_db_name
        else:
            os.environ.pop("DB_NAME", None)

        print_success("  OHLCV symbol tables initialized!")
        print_info("  📝 No sample data inserted - tables are empty")

    except ImportError as e:
        print_error(f"Failed to import fullon_ohlcv: {e}")
        print_warning("  Make sure fullon_ohlcv is installed")
        print_warning("  OHLCV tables will not be created")
        fullon_logger.warning(f"OHLCV table initialization skipped: {e}")

    except Exception as e:
        print_error(f"Failed to initialize OHLCV symbol tables: {e}")
        import traceback

        print_error(traceback.format_exc())
        print_warning("  OHLCV tables may not be available")
        fullon_logger.warning(f"OHLCV table initialization failed: {e}")


async def setup_demo_environment(db_name: str = "fullon_beta1"):
    """
    Setup demo environment with test database and multi-exchange data.

    Args:
        db_name: Name for the ORM database (default: fullon_beta1)
                 OHLCV database will be {db_name}_ohlcv
    """
    test_db_name = db_name
    ohlcv_db_name = f"{test_db_name}_ohlcv"

    print_header("BITMEX + YAHOO DEMO SETUP")
    print_info(f"ORM Database: {test_db_name}")
    print_info(f"OHLCV Database: {ohlcv_db_name}")

    # Create dual databases
    orm_db, ohlcv_db = await create_dual_test_databases(test_db_name)

    # Set environment for ORM database
    original_db_name = os.environ.get("DB_NAME")
    os.environ["DB_NAME"] = orm_db

    try:
        # Initialize ORM schema
        print_info("Initializing ORM database schema...")
        await init_db()
        print_success("ORM database schema initialized")

        # Install demo data
        await install_demo_data()

        print_success("\nDemo environment ready!")
        print_info(f"ORM Database: {orm_db}")
        print_info(f"OHLCV Database: {ohlcv_db}")
        print_info(f"\nTo cleanup, run: python {sys.argv[0]} --cleanup {test_db_name}")

        return test_db_name

    finally:
        # Restore original DB_NAME
        if original_db_name:
            os.environ["DB_NAME"] = original_db_name
        else:
            os.environ.pop("DB_NAME", None)


async def cleanup_demo_environment(base_db_name: str):
    """Cleanup demo environment by dropping both databases"""
    ohlcv_db_name = f"{base_db_name}_ohlcv"

    print_header("CLEANUP DEMO ENVIRONMENT")

    success = await drop_dual_test_databases(base_db_name, ohlcv_db_name)

    if success:
        print_success("\n✅ Demo environment cleaned up successfully!")
    else:
        print_warning("\n⚠️ Some cleanup operations failed")

    return success


async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Demo Data Beta1 - Bitmex + Yahoo Multi-Exchange Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--setup",
        metavar="DB_NAME",
        nargs="?",
        const="fullon_beta1",
        help="Create test database and install Bitmex + Yahoo demo data (default: fullon_beta1)",
    )
    parser.add_argument("--cleanup", metavar="DB_NAME", help="Drop specific test database (both ORM and OHLCV)")

    args = parser.parse_args()

    if args.setup:
        db_name = await setup_demo_environment(args.setup)
        sys.exit(0)

    elif args.cleanup:
        success = await cleanup_demo_environment(args.cleanup)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print_warning("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"\nUnexpected error: {e}")
        import traceback
        print_error(traceback.format_exc())
        sys.exit(1)
