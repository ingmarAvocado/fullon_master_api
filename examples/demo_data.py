#!/usr/bin/env python3
"""
Demo Data Setup for fullon_master_api Examples

Creates isolated test database with minimal data needed for API examples:
- Test exchanges (kraken, bitmex, hyperliquid)
- Test symbols (BTC/USDC, BTC/USD:BTC, BTC/USDC:USDC)
- Test user for authentication
- Test bots for trading operations

Usage:
    python examples/demo_data.py --setup      # Create test DB and install data
    python examples/demo_data.py --cleanup    # Drop test DB
    python examples/demo_data.py --run-all    # Setup, run examples, cleanup
"""

import argparse
import asyncio
import os
import random
import string
import sys
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    print("⚠️  python-dotenv not available, make sure .env variables are set manually")
except Exception as e:
    print(f"⚠️  Could not load .env file: {e}")

import redis
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext, init_db
from fullon_orm.models import Bot, CatStrategy, Exchange, Feed, Strategy, Symbol, User
from fullon_orm.models.user import RoleEnum

# Create fullon logger alongside color output
fullon_logger = get_component_logger("fullon.master_api.example.demo_data")


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'


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


def generate_test_db_name(worker_id: str = "") -> str:
    """Generate worker-aware test database name."""
    base_name = os.getenv('DB_TEST_NAME', 'fullon_master_api_test')

    if worker_id:
        return f"{base_name}_{worker_id}"
    else:
        # Fallback to random for manual/CLI usage
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{base_name}_{random_suffix}"


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
                host=host,
                port=port,
                user=user,
                password=password,
                database="postgres"
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
                host=host,
                port=port,
                user=user,
                password=password,
                database="postgres"
            )

            try:
                # Connection termination and database dropping require direct SQL (administrative)
                await conn.execute("""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = $1
                    AND pid <> pg_backend_pid()
                """, db_name)

                await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')

                print_success(f"Test database dropped: {db_name}")
                return True

            finally:
                await conn.close()

    except Exception as e:
        print_error(f"Failed to drop test database: {e}")
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
    original_db_url = os.getenv('DATABASE_URL', '')
    original_db_name = os.getenv('DB_NAME', '')

    # Update DATABASE_URL and DB_NAME to point to test database
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")

    test_db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"
    os.environ['DATABASE_URL'] = test_db_url
    os.environ['DB_NAME'] = db_name

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
            os.environ['DATABASE_URL'] = original_db_url
        else:
            os.environ.pop('DATABASE_URL', None)

        if original_db_name:
            os.environ['DB_NAME'] = original_db_name
        else:
            os.environ.pop('DB_NAME', None)

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
    """Install demo data matching fullon_orm demo_install.py exactly"""
    print_header("INSTALLING DEMO DATA")
    fullon_logger.info("Starting demo data installation (matching fullon_orm)")

    # Clear cache before starting transaction (outside transaction context)
    await clear_fullon_cache()

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

            # Install exchanges
            ex_id, cat_ex_id = await install_exchanges_internal(db, uid=uid)
            if not ex_id or not cat_ex_id:
                print_error("Could not install admin exchanges")
                await db.rollback()
                return False
            # Commit exchange creation before proceeding
            await db.commit()
            print_success("Exchanges created successfully")

            # Install symbols for all created exchanges
            await install_symbols_for_all_exchanges_internal(db, uid=uid)
            await db.commit()
            print_success("Symbols installed successfully")

            # Install bots for testing API operations
            await install_bots_internal(db, uid=uid, ex_id=ex_id, cat_ex_id=cat_ex_id)
            await db.commit()
            print_success("Bots installed successfully")

            # Install OHLCV sample data (separate context for OHLCV database)
            await install_ohlcv_sample_data()
            print_success("OHLCV sample data installed successfully")

            print_success("Demo data installation complete!")
            fullon_logger.info("Demo data installation completed successfully")
            return True

    except Exception as e:
        print_error(f"Failed to install demo data: {e}")
        fullon_logger.error(f"Demo data installation failed: {e}")
        return False


async def install_ohlcv_sample_data():
    """
    Install realistic OHLCV sample data using fullon_ohlcv repositories.

    Architecture:
    1. Use CandleRepository to properly initialize symbol tables
    2. Call init_symbol() to create TimescaleDB hypertables:
       - kraken.btc_usdc_trades
       - kraken.btc_usdc_candles1m
       - kraken.btc_usdc_candles1m_view (continuous aggregate)
    3. Insert 30 days of 1-minute candles (43,200 candles)
    4. TimeseriesRepository will aggregate these into hourly/daily on query
    """
    print_info("Installing OHLCV sample data via fullon_ohlcv repositories...")

    try:
        from fullon_ohlcv.repositories.ohlcv import CandleRepository
        from fullon_ohlcv.models import Candle
        from datetime import datetime, timedelta, timezone
        import random

        # Get OHLCV database configuration
        ohlcv_db_name = os.getenv("DB_OHLCV_NAME", os.getenv("DB_NAME", "fullon2"))
        print_info(f"  Using OHLCV database: {ohlcv_db_name}")

        # CRITICAL: Override DB_NAME for fullon_ohlcv to use correct database
        original_db_name = os.environ.get('DB_NAME')
        os.environ['DB_NAME'] = ohlcv_db_name

        # Step 1: Initialize CandleRepository
        print_info("  Initializing CandleRepository for hyperliquid/BTC/USDC...")
        repo = CandleRepository(
            exchange="hyperliquid",
            symbol="BTC/USDC",
            test=False  # Uses DB_NAME from environment
        )
        await repo.initialize()
        print_success("  Repository initialized")

        # Step 2: Create symbol tables via init_symbol()
        print_info("  Creating TimescaleDB tables via init_symbol()...")
        success = await repo.init_symbol()
        if not success:
            raise Exception("init_symbol() failed - check TimescaleDB extension")

        print_success("  ✅ Created TimescaleDB tables:")
        print_info("     - hyperliquid.btc_usdc_trades (hypertable)")
        print_info("     - hyperliquid.btc_usdc_candles1m (hypertable)")
        print_info("     - hyperliquid.btc_usdc_candles1m_view (continuous aggregate)")

        # Step 3: Generate 30 days of realistic 1-minute candles
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        total_days = 30
        total_candles = total_days * 24 * 60  # 43,200

        print_info(f"  Generating {total_candles:,} x 1-minute candles ({total_days} days)...")

        # Realistic price simulation
        base_price = 43000.0
        current_price = base_price

        # Insert in batches
        batch_size = 1000
        candles_inserted = 0

        for batch_start in range(0, total_candles, batch_size):
            batch_candles = []
            batch_end = min(batch_start + batch_size, total_candles)

            for i in range(batch_start, batch_end):
                timestamp = now - timedelta(minutes=total_candles - 1 - i)

                # Random walk with mean reversion
                drift = random.uniform(-0.0005, 0.0005)
                volatility = random.uniform(-30, 30)
                current_price = current_price * (1 + drift) + volatility

                # Mean reversion
                if current_price > base_price * 1.1:
                    current_price -= random.uniform(50, 150)
                elif current_price < base_price * 0.9:
                    current_price += random.uniform(50, 150)

                # OHLC for this minute
                open_price = current_price
                high = open_price + random.uniform(5, 25)
                low = open_price - random.uniform(5, 20)
                close_price = open_price + random.uniform(-15, 15)
                volume = random.uniform(0.5, 5.0)

                # Ensure validity
                high = max(high, open_price, close_price)
                low = min(low, open_price, close_price)

                candle = Candle(
                    timestamp=timestamp,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close_price,
                    vol=volume
                )
                batch_candles.append(candle)

            await repo.save_candles(batch_candles)
            candles_inserted += len(batch_candles)

            if (candles_inserted % 5000) == 0 or candles_inserted == total_candles:
                print_info(f"    Progress: {candles_inserted:,}/{total_candles:,}...")

        print_success(f"  ✅ Inserted {candles_inserted:,} x 1-minute candles")
        print_info(f"  📊 Data spans {total_days} days")
        print_info("  📈 TimeseriesRepository will aggregate on query:")
        print_info(f"     - 1m: {total_candles:,} candles")
        print_info(f"     - 1h: {total_candles // 60:,} candles")
        print_info(f"     - 1d: {total_candles // 1440:,} candles")

        await repo.close()

        # Restore original DB_NAME
        if original_db_name:
            os.environ['DB_NAME'] = original_db_name
        else:
            os.environ.pop('DB_NAME', None)

        print_success("  OHLCV sample data installation complete!")

    except ImportError as e:
        print_error(f"Failed to import fullon_ohlcv: {e}")
        print_warning("  Make sure fullon_ohlcv is installed")
        print_warning("  OHLCV examples will return empty results")
        fullon_logger.warning(f"OHLCV sample data skipped: {e}")

    except Exception as e:
        print_error(f"Failed to install OHLCV sample data: {e}")
        import traceback
        print_error(traceback.format_exc())
        print_warning("  OHLCV examples may return empty results")
        fullon_logger.warning(f"OHLCV sample data failed: {e}")


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
        password=hashed_password,  # Now properly hashed with bcrypt!
        f2a="---",
        role=RoleEnum.ADMIN,
        name="robert",
        lastname="plant",
        phone="666666666",
        id_num="3242"
    )

    try:
        created_user = await db.users.add_user(user)
        print_success(f"Admin user created: {created_user.name} {created_user.lastname}")
        return created_user.uid
    except Exception as e:
        print_error(f"Failed to create admin user: {e}")
        return None


async def install_exchanges_internal(db: DatabaseContext, uid: int) -> tuple[int | None, int | None]:
    """Install exchanges using provided DatabaseContext and ORM models (adapted fullon_orm pattern for 3 exchanges)."""
    print_info("Installing exchanges...")

    # Define the exchanges to create (matching fullon_orm demo exactly)
    exchanges_to_create = ["kraken", "bitmex", "hyperliquid"]

    # Use repository method to get existing cat_exchanges
    cat_exchanges = await db.exchanges.get_cat_exchanges(all=True)
    print_info(f"  Found {len(cat_exchanges)} existing category exchanges in database")
    for ce in cat_exchanges:
        print_info(f"    - {ce.name} (ID: {ce.cat_ex_id})")

    created_exchanges = []

    for exchange_name in exchanges_to_create:
        user_exchange_name = f"{exchange_name}1"

        # Check if category exchange exists (fullon_orm pattern)
        cat_ex_id = None
        for ce in cat_exchanges:
            if ce.name == exchange_name:
                cat_ex_id = ce.cat_ex_id
                print_info(f"  Category exchange '{exchange_name}' already exists with ID: {cat_ex_id}")
                break

        # If no category exchange exists, create one (fullon_orm pattern)
        if not cat_ex_id:
            cat_exchange = await db.exchanges.create_cat_exchange(exchange_name, "")
            cat_ex_id = cat_exchange.cat_ex_id
            print_info(f"  Created category exchange: {exchange_name}")

        # Check if user already has this exchange (fullon_orm pattern)
        user_exchanges = await db.exchanges.get_user_exchanges(uid)
        existing_exchange = None
        for ue in user_exchanges:
            if ue.name == user_exchange_name and ue.cat_ex_id == cat_ex_id:
                existing_exchange = ue
                break

        if existing_exchange:
            ex_id = existing_exchange.ex_id
            print_info(f"  User exchange '{user_exchange_name}' already exists")
            created_exchanges.append((ex_id, cat_ex_id))
        else:
            # Create user exchange (fullon_orm pattern)
            exchange = Exchange(
                uid=uid,
                cat_ex_id=cat_ex_id,
                name=user_exchange_name,
                test=False,
                active=True
            )

            created_exchange = await db.exchanges.add_user_exchange(exchange)
            ex_id = created_exchange.ex_id
            print_success(f"Exchange created: {user_exchange_name}")
            created_exchanges.append((ex_id, cat_ex_id))

    # Return the first exchange (for backward compatibility with existing code)
    if created_exchanges:
        return created_exchanges[0]
    else:
        return (None, None)


async def install_symbols_for_all_exchanges_internal(db: DatabaseContext, uid: int):
    """Install symbols for all exchanges belonging to the admin user."""
    print_info("Installing symbols for all exchanges...")

    # Install symbols once for all exchanges (not per exchange)
    # The install_symbols_internal function handles ALL exchanges at once
    await install_symbols_internal(db, cat_ex_id=None)  # Pass None since we're doing all exchanges


async def install_symbols_internal(db: DatabaseContext, cat_ex_id: int | None):
    """Install symbols using provided DatabaseContext and ORM models (fullon_orm pattern)."""
    print_info("Installing symbols...")

    # Clear cache and get fresh cat_exchanges (they were just created) - like ticker service
    try:
        from fullon_orm.cache import cache_manager
        cache_manager.region.invalidate()  # Clear entire cache
        cache_manager.invalidate_exchange_caches()
        print_info("  Cache cleared before symbol installation")
    except Exception as cache_error:
        print_warning(f"Could not clear cache (continuing anyway): {cache_error}")

    # Get all cat_exchanges to install symbols for each
    cat_exchanges = await db.exchanges.get_cat_exchanges(all=True)
    cat_exchanges_dict = {ce.name: ce.cat_ex_id for ce in cat_exchanges}

    print_info(f"  Found {len(cat_exchanges)} category exchanges:")
    for name, cat_id in cat_exchanges_dict.items():
        print_info(f"    - {name} (ID: {cat_id})")

    # Define symbol data for each exchange (matching fullon_orm exactly)
    exchange_symbols = {
        "kraken": [
            {
                "symbol": "BTC/USDC",
                "updateframe": "1h",
                "backtest": 1,
                "decimals": 6,
                "base": "BTC",
                "quote": "USD",
                "futures": True,
            }
        ],
        "bitmex": [
            {
                "symbol": "BTC/USD:BTC",
                "updateframe": "1h",
                "backtest": 3,
                "decimals": 6,
                "base": "BTC",
                "quote": "USD",
                "futures": True,
            }
        ],
        "hyperliquid": [
            {
                "symbol": "BTC/USDC:USDC",
                "updateframe": "1h",
                "backtest": 3,
                "decimals": 6,
                "base": "BTC",
                "quote": "USDC",
                "futures": True,
            }
        ]
    }

    # Create symbols for each exchange
    all_symbols_data = []
    for exchange_name, symbols in exchange_symbols.items():
        if exchange_name in cat_exchanges_dict:
            exchange_cat_id = cat_exchanges_dict[exchange_name]
            for symbol_data in symbols:
                symbol_data["cat_ex_id"] = exchange_cat_id
                all_symbols_data.append(symbol_data)
            print_info(f"  Prepared {len(symbols)} symbols for {exchange_name}")
        else:
            print_warning(f"  Exchange {exchange_name} not found, skipping symbols")

    symbols_created = 0
    for symbol_data in all_symbols_data:
        try:
            # Check if symbol already exists using repository method (avoid constraint violations)
            existing_symbol = None
            try:
                existing_symbol = await db.symbols.get_by_symbol(
                    symbol_data["symbol"],
                    cat_ex_id=symbol_data["cat_ex_id"]
                )
            except (AttributeError, Exception):
                # Method might not exist or fail, continue with creation
                pass

            if existing_symbol:
                print_warning(f"  Symbol {symbol_data['symbol']} already exists")
                continue

            # Create Symbol model instance
            symbol = Symbol(
                symbol=symbol_data["symbol"],
                cat_ex_id=symbol_data["cat_ex_id"],
                updateframe=symbol_data["updateframe"],
                backtest=symbol_data["backtest"],
                decimals=symbol_data["decimals"],
                base=symbol_data["base"],
                quote=symbol_data["quote"],
                futures=symbol_data["futures"]
            )

            # Use repository method if available (preferred fullon_orm pattern)
            try:
                created_symbol = await db.symbols.add_symbol(symbol)
                if created_symbol:
                    symbols_created += 1
                    print_info(f"  Added symbol: {symbol_data['symbol']}")
            except AttributeError:
                # Fallback to direct session add if repository method doesn't exist
                db.session.add(symbol)
                symbols_created += 1
                print_info(f"  Added symbol: {symbol_data['symbol']}")

        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                print_warning(f"  Symbol {symbol_data['symbol']} already exists")
            else:
                print_error(f"  Failed to create symbol {symbol_data['symbol']}: {e}")
                # Don't rollback individual operations - let main transaction handle errors

    if symbols_created > 0:
        print_success(f"Symbols installed successfully ({symbols_created} new)")
    else:
        print_info("All symbols already existed")


async def install_bots_internal(db: DatabaseContext, uid: int, ex_id: int, cat_ex_id: int):
    """Install bots using provided DatabaseContext and ORM models."""
    print_info("Installing bots, strategies and feeds...")

    try:
        # First ensure we have the required cat_strategies using repository
        cat_strategy_names = ['rsi_hayden_long', 'rsi_hayden_short', 'llm_trader']
        cat_strategies = {}

        for name in cat_strategy_names:
            # Check if strategy exists using repository method
            try:
                cat_str_id = await db.strategies.get_cat_str_id(name)
                if cat_str_id:
                    cat_strategies[name] = cat_str_id
                    continue
            except:
                pass  # Method might not exist, continue with install

            # Install strategy using repository method (fullon_orm pattern)
            try:
                # Create CatStrategy model instance (fullon_orm pattern)
                cat_strategy = CatStrategy(
                    name=name,
                    take_profit=Decimal("2.0"),
                    stop_loss=Decimal("1.0"),
                    pre_load_bars=200,
                    feeds=2 if 'rsi' in name else 4
                )
                installed_strategy = await db.strategies.install_strategy(cat_strategy)
                if installed_strategy:
                    cat_strategies[name] = installed_strategy.cat_str_id
                    print_info(f"  Created strategy category: {name}")
                else:
                    print_error(f"  Failed to create strategy category: {name}")
                    raise Exception(f"Strategy installation failed for {name}")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print_warning(f"  Strategy category {name} already exists")
                    # Try alternative approach to get existing strategy
                    cat_str_id = await db.strategies.get_cat_str_id(name)
                    if cat_str_id:
                        cat_strategies[name] = cat_str_id
                    else:
                        raise Exception(f"Could not create or find strategy {name}")
                else:
                    raise e

        # Get cat_exchanges to find kraken
        cat_exchanges = await db.exchanges.get_cat_exchanges(all=True)
        cat_exchanges_dict = {ce.name: ce.cat_ex_id for ce in cat_exchanges}

        kraken_cat_id = cat_exchanges_dict.get('kraken')
        if not kraken_cat_id:
            raise Exception("Kraken exchange not found")

        btc_symbol = await db.symbols.get_by_symbol("BTC/USDC", cat_ex_id=kraken_cat_id)
        if not btc_symbol:
            raise Exception("BTC/USDC symbol not found for kraken exchange")
        symbol_id = btc_symbol.symbol_id

        # Create bots with strategies and feeds using ORM models
        bot_data = [
            {
                'bot': Bot(uid=uid, name='HAYDEN RSI LONG BTC/USDC', dry_run=True, active=True),
                'strategy_data': {
                    'cat_str_id': cat_strategies['rsi_hayden_long'],
                    'leverage': 2, 'size': None, 'size_pct': Decimal("20"),
                    'size_currency': "USD", 'take_profit': Decimal("3"),
                    'trailing_stop': Decimal("3"), 'timeout': None
                },
                'feeds_data': [
                    {'period': 'Ticks', 'compression': 1, 'order': 1},
                    {'period': 'Minutes', 'compression': 60, 'order': 2}
                ]
            },
            {
                'bot': Bot(uid=uid, name='HAYDEN RSI SHORT BTC/USDC', dry_run=True, active=True),
                'strategy_data': {
                    'cat_str_id': cat_strategies['rsi_hayden_short'],
                    'leverage': 2, 'size': None, 'size_pct': Decimal("20"),
                    'size_currency': "USD", 'take_profit': Decimal("2"),
                    'trailing_stop': Decimal("1"), 'timeout': None
                },
                'feeds_data': [
                    {'period': 'Ticks', 'compression': 1, 'order': 1},
                    {'period': 'Minutes', 'compression': 60, 'order': 2}
                ]
            },
            {
                'bot': Bot(uid=uid, name='HTEST LLM trader', dry_run=True, active=True),
                'strategy_data': {
                    'cat_str_id': cat_strategies['llm_trader'],
                    'leverage': 2, 'size': None, 'size_pct': Decimal("20"),
                    'size_currency': "USD", 'take_profit': Decimal("2"), 'timeout': None
                },
                'feeds_data': [
                    {'period': 'Ticks', 'compression': 1, 'order': 1},
                    {'period': 'Minutes', 'compression': 60, 'order': 2},
                    {'period': 'Minutes', 'compression': 240, 'order': 3},
                    {'period': 'Days', 'compression': 1, 'order': 4}
                ]
            }
        ]

        # Create each bot using repository methods
        for bot_config in bot_data:
            bot_model = bot_config['bot']

            # Check if bot already exists using repository (if method exists)
            try:
                existing_bots = await db.bots.get_bots_by_user(bot_model.uid)
                bot_exists = any(b.name == bot_model.name for b in existing_bots if hasattr(b, 'name'))

                if bot_exists:
                    print_warning(f"  Bot '{bot_model.name}' already exists")
                    continue
            except:
                pass  # Method might not exist or fail, continue with creation

            try:
                # Create bot using repository method with model instance
                created_bot = await db.bots.add_bot(bot_model)
                bot_id = created_bot.bot_id
                print_info(f"  Created bot: {bot_model.name}")

                # Add exchange to bot using repository method
                await db.bots.add_exchange_to_bot(bot_id, ex_id)

                # Add strategy using repository method - create Strategy model instance
                strategy_data = bot_config['strategy_data'].copy()
                strategy_data['bot_id'] = bot_id

                # Create Strategy model instance with explicit field assignment
                strategy = Strategy(
                    bot_id=strategy_data['bot_id'],
                    cat_str_id=strategy_data['cat_str_id'],
                    leverage=strategy_data.get('leverage'),
                    size=strategy_data.get('size'),
                    size_pct=strategy_data.get('size_pct'),
                    size_currency=strategy_data.get('size_currency'),
                    take_profit=strategy_data.get('take_profit'),
                    trailing_stop=strategy_data.get('trailing_stop'),
                    timeout=strategy_data.get('timeout')
                )
                created_strategy = await db.strategies.add_bot_strategy(strategy)
                str_id = created_strategy.str_id if created_strategy else None

                if str_id:
                    # Add feeds using repository pattern if available
                    for feed_data in bot_config['feeds_data']:
                        # Create Feed model instance
                        feed = Feed(
                            symbol_id=symbol_id,
                            str_id=str_id,
                            period=feed_data['period'],
                            compression=feed_data['compression'],
                            order=feed_data['order']
                        )

                        # Use repository method if available (preferred fullon_orm pattern)
                        try:
                            await db.feeds.add_feed(feed)
                        except AttributeError:
                            # Fallback to session add if feed repository doesn't exist
                            db.session.add(feed)

            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print_warning(f"  Bot '{bot_model.name}' already exists")
                    continue
                else:
                    raise e

        print_success("All bots, strategies and feeds installed successfully")

    except Exception as e:
        print_error(f"Failed to create bots: {e}")
        raise


async def run_examples():
    """Run all master API examples against demo data"""
    print_header("RUNNING EXAMPLES")

    examples_dir = os.path.dirname(__file__)

    # Import run_all_examples from examples directory
    import sys
    sys.path.insert(0, examples_dir)

    try:
        import run_all_examples
        success = await run_all_examples.run_all(skip_websocket=True)
        return success == 0
    except Exception as e:
        print_error(f"Failed to run examples: {e}")
        return False


async def setup_demo_environment():
    """Setup demo environment with test database and data"""
    test_db_name = generate_test_db_name()

    async with database_context_for_test(test_db_name):
        await install_demo_data()
        print_success("\nDemo environment ready!")
        print_info(f"Test database: {test_db_name}")
        print_info("Use --cleanup when done to remove test database")

        return test_db_name


async def run_full_demo():
    """Setup, run examples, and cleanup"""
    test_db_name = generate_test_db_name()

    async with database_context_for_test(test_db_name):
        await install_demo_data()
        success = await run_examples()

        if success:
            print_success("\n✅ All examples passed!")
        else:
            print_warning("\n⚠️ Some examples failed")

        return success


async def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Demo Data Setup for fullon_master_api Examples",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--setup', action='store_true',
                        help='Create test database and install demo data')
    parser.add_argument('--cleanup', metavar='DB_NAME',
                        help='Drop specific test database')
    parser.add_argument('--run-all', action='store_true',
                        help='Setup, run all examples, then cleanup')
    parser.add_argument('--examples-only', action='store_true',
                        help='Run examples against existing database')

    args = parser.parse_args()

    if args.setup:
        db_name = await setup_demo_environment()
        print_info(f"\nTo cleanup later, run: python {sys.argv[0]} --cleanup {db_name}")

    elif args.cleanup:
        success = await drop_test_database(args.cleanup)
        sys.exit(0 if success else 1)

    elif args.run_all:
        success = await run_full_demo()
        sys.exit(0 if success else 1)

    elif args.examples_only:
        success = await run_examples()
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
        sys.exit(1)
