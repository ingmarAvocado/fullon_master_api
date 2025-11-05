#!/usr/bin/env python3
"""
Cleanup Old Yahoo Symbols - Remove GC=F and ^GSPC from database

This script removes the old Yahoo API format symbols so demo_data_beta1.py
can insert the new clean format symbols (GOLD, SPX).
"""

import os
import asyncio
from dotenv import load_dotenv
from fullon_orm.database_context import DatabaseContext
from fullon_log import get_component_logger

logger = get_component_logger("fullon.cleanup.yahoo_symbols")


async def cleanup_yahoo_symbols(db_name: str = None):
    """Remove old Yahoo API format symbols from database"""
    load_dotenv()

    # Use specified database or check environment
    if db_name:
        original_db = os.environ.get("DB_NAME")
        os.environ["DB_NAME"] = db_name
        logger.info(f"Using database: {db_name}")
    else:
        db_name = os.environ.get("DB_NAME", "fullon2")
        logger.info(f"Using database from environment: {db_name}")
    
    old_symbols = ["GC=F", "^GSPC", "GOLD", "SPX"]  # Remove both old and new just in case
    
    async with DatabaseContext() as db:
        # Get yahoo exchange ID
        cat_exchanges = await db.exchanges.get_cat_exchanges()
        yahoo_cat_ex_id = None
        for ce in cat_exchanges:
            if ce.name == "yahoo":
                yahoo_cat_ex_id = ce.cat_ex_id
                break

        if not yahoo_cat_ex_id:
            logger.info("No yahoo exchange found - nothing to clean")
            return

        logger.info(f"Found yahoo exchange with cat_ex_id={yahoo_cat_ex_id}")
        
        # Delete each symbol
        for symbol_name in old_symbols:
            try:
                existing = await db.symbols.get_by_symbol(symbol_name, cat_ex_id=yahoo_cat_ex_id)
                if existing:
                    # Delete the symbol
                    await db.symbols.delete_symbol(existing.symbol_id)
                    logger.info(f"Deleted symbol: {symbol_name}")
                else:
                    logger.info(f"Symbol not found (already clean): {symbol_name}")
            except Exception as e:
                logger.warning(f"Could not delete {symbol_name}: {e}")
    
    logger.info("✅ Yahoo symbols cleanup complete")
    logger.info("Now run: python examples/demo_data_beta1.py")


if __name__ == "__main__":
    import sys
    db_name = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(cleanup_yahoo_symbols(db_name))
