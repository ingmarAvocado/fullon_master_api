#!/usr/bin/env python3
"""
Example demonstrating OHLCV Historic Collector Resume Functionality.

This example shows how the historic collector now intelligently resumes
from where it left off instead of restarting from scratch every time.

Key Features:
1. Checks for existing data before starting collection
2. Resumes from last collected timestamp if data exists
3. Starts from backtest period only when no data exists
4. Prevents duplicate data collection
5. Improves efficiency and reduces API calls

Usage:
    python examples/example_ohlcv_resume.py
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from fullon_ohlcv.repositories.ohlcv import CandleRepository
from fullon_ohlcv_service.ohlcv.historic_collector import HistoricOHLCVCollector
from fullon_orm import DatabaseContext
from fullon_log import get_component_logger

logger = get_component_logger("example.ohlcv_resume")


async def demonstrate_resume_functionality():
    """Demonstrate how the historic collector resumes from existing data."""

    print("=" * 70)
    print("OHLCV Historic Collector Resume Functionality Demonstration")
    print("=" * 70)
    print()

    # Get admin email from environment
    admin_email = os.getenv("ADMIN_MAIL", "admin@fullon")

    async with DatabaseContext() as db:
        # Get admin user
        admin_uid = await db.users.get_user_id(admin_email)
        if not admin_uid:
            print(f"❌ Admin user {admin_email} not found")
            return

        # Get a symbol to demonstrate with
        symbols = await db.symbols.get_all()
        if not symbols:
            print("❌ No symbols found in database")
            return

        # Use the first symbol for demonstration
        symbol = symbols[0]
        exchange_name = symbol.cat_exchange.name
        symbol_str = symbol.symbol

        print(f"📊 Demonstrating with: {exchange_name}:{symbol_str}")
        print(f"   Backtest period: {symbol.backtest} days")
        print()

        # Check for existing data
        print("1️⃣  Checking for existing OHLCV data...")
        print("-" * 50)

        async with CandleRepository(exchange_name, symbol_str) as repo:
            latest_timestamp = await repo.get_latest_timestamp()

            if latest_timestamp:
                # Data exists - will resume from here
                latest_dt = latest_timestamp.datetime
                days_ago = (datetime.now(UTC) - latest_dt).days

                print(f"✅ Found existing data!")
                print(f"   Latest timestamp: {latest_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"   That's {days_ago} days ago")
                print()
                print("📍 The collector will RESUME from this point")
                print(f"   It will NOT re-collect the {days_ago} days of existing data")
                print(f"   This saves time and reduces API calls!")

                # Calculate time saved
                if symbol.backtest > days_ago:
                    saved_days = days_ago
                    remaining_days = symbol.backtest - days_ago
                    print()
                    print(f"⏱️  Time Savings:")
                    print(f"   - Skipping {saved_days} days of existing data")
                    print(f"   - Only collecting {remaining_days} days of new data")
                    print(f"   - Estimated time saved: ~{saved_days * 2} minutes")
            else:
                # No data exists - will start from backtest
                print("ℹ️  No existing data found")
                print(f"   The collector will start from {symbol.backtest} days ago")
                print("   This is normal for the first run")

        print()
        print("2️⃣  How the Resume Logic Works:")
        print("-" * 50)
        print("""
The enhanced historic collector now:

1. BEFORE collecting:
   - Checks CandleRepository for the latest timestamp
   - If data exists → Resume from (latest_timestamp + 1 second)
   - If no data → Start from backtest period

2. BENEFITS:
   ✅ No duplicate data collection
   ✅ Faster recovery after service restarts
   ✅ Reduced API rate limit consumption
   ✅ Can safely stop/start the service anytime
   ✅ Incremental data collection

3. LOGGING:
   - "Resuming collection from existing data" - when data exists
   - "Starting fresh collection from backtest period" - when no data
        """)

        print("3️⃣  Example Use Cases:")
        print("-" * 50)
        print("""
📍 Service Restart:
   Before: Re-collects 30 days of data (takes ~60 minutes)
   After: Resumes from last point (takes seconds to continue)

📍 Temporary Failure:
   Before: Loses progress, starts over from beginning
   After: Picks up exactly where it left off

📍 Adding New Symbol:
   Before: No change (starts from backtest)
   After: Same behavior (starts from backtest for new symbols)

📍 Maintenance Window:
   Before: Must wait for full re-collection after maintenance
   After: Instantly resumes from last collected timestamp
        """)

        print()
        print("=" * 70)
        print("✅ The historic collector is now resume-capable!")
        print("=" * 70)
        print()

        # Show how to manually trigger collection with resume
        print("To manually trigger collection (with automatic resume):")
        print("```python")
        print("from fullon_ohlcv_service.ohlcv.historic_collector import HistoricOHLCVCollector")
        print()
        print("collector = HistoricOHLCVCollector()")
        print("results = await collector.start_collection()")
        print("# or for specific symbol:")
        print("count = await collector.start_symbol(symbol)")
        print("```")


async def main():
    """Main entry point."""
    try:
        await demonstrate_resume_functionality()
    except KeyboardInterrupt:
        print("\n⚠️  Demonstration interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())