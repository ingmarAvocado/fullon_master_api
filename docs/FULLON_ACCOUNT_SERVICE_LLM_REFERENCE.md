# Fullon Account Service - Complete LLM Reference

**A lightweight async daemon (~500-700 lines) for monitoring cryptocurrency account data (balances, orders, positions, trades) across exchanges with adaptive collection strategies.**

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Architecture](#core-architecture)
3. [Collection Strategies](#collection-strategies)
4. [API Reference](#api-reference)
5. [Usage Patterns](#usage-patterns)
6. [Integration Examples](#integration-examples)
7. [Testing Patterns](#testing-patterns)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Installation

```bash
poetry add git+ssh://git@github.com/ingmarAvocado/fullon_account_service.git
```

### Essential Imports

```python
from fullon_account_service import AccountDaemon
from fullon_orm import DatabaseContext
from fullon_orm.models import Exchange
from fullon_cache import AccountCache, ProcessCache
from fullon_log import get_component_logger
```

### Basic Usage - Full Daemon Startup

```python
import asyncio
from fullon_account_service import AccountDaemon

async def main():
    """Start daemon to monitor ALL exchanges from ALL users."""
    daemon = AccountDaemon()

    # Start monitoring (blocks until shutdown signal)
    await daemon.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### Basic Usage - Single Exchange Monitoring

```python
import asyncio
from fullon_account_service import AccountDaemon
from fullon_orm import DatabaseContext

async def main():
    """Monitor a single exchange dynamically."""
    # Get exchange from database
    async with DatabaseContext() as db:
        exchanges = await db.exchanges.get_user_exchanges(uid=1)
        exchange = exchanges[0]  # Select first exchange

    # Create daemon and process single exchange
    daemon = AccountDaemon()
    await daemon.process_exchange(exchange)

    # Monitor for 30 seconds
    await asyncio.sleep(30)

    # Stop gracefully
    await daemon.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Core Architecture

### Component Overview

The service follows the **LRRS Architecture** (Little, Responsible, Reusable, Separate):

```
fullon_account_service/
├── daemon.py                    # Main orchestrator (100-150 lines)
│   └── AccountDaemon           # Coordinates all components
├── account/
│   ├── live_collector.py       # WebSocket collection (150-200 lines)
│   │   └── LiveAccountCollector
│   └── rest_poller.py          # REST polling fallback (100-150 lines)
│       └── RestAccountPoller
└── utils/
    └── capability_detector.py  # Exchange capability detection (50-100 lines)
        └── CapabilityDetector
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      AccountDaemon                          │
│  (Discovers exchanges from database, coordinates lifecycle) │
└─────────┬───────────────────────────────────┬───────────────┘
          │                                   │
          ▼                                   ▼
┌─────────────────────┐           ┌─────────────────────────┐
│ LiveAccountCollector│           │   RestAccountPoller     │
│  (WebSocket streams)│           │   (REST API polling)    │
└─────────┬───────────┘           └─────────┬───────────────┘
          │                                   │
          │ Balance, Orders, Positions        │ Balance, Orders,
          │ (real-time)                       │ Positions, Trades
          │                                   │ (60s intervals)
          ▼                                   ▼
┌─────────────────────────────────────────────────────────────┐
│                       Storage Layer                         │
│  • Redis (AccountCache) - Balances (ephemeral, latest)     │
│  • Redis (AccountCache) - Positions (ephemeral, latest)    │
│  • PostgreSQL (fullon_orm) - Orders (persistent, history)  │
│  • PostgreSQL (fullon_orm) - Trades (persistent + PnL)     │
└─────────────────────────────────────────────────────────────┘
```

### Three-Way State Check Pattern

The daemon uses a **three-way state check** in `process_exchange()` to support both dynamic addition and fresh startup:

```python
if self.live_collector and self.rest_poller:
    # State 1: Daemon fully running - add exchange dynamically
    if self.live_collector.is_collecting(exchange):
        return  # Already collecting
    await self.live_collector.start_exchange(exchange)

elif not self.live_collector and not self.rest_poller:
    # State 2: Daemon not running - start fresh for single exchange
    self.live_collector = LiveAccountCollector()
    self.rest_poller = RestAccountPoller()
    await self._start_exchange_with_strategy(exchange)

else:
    # State 3: Partially running - inconsistent state (error)
    self.logger.error("Daemon in inconsistent state")
    return
```

---

## Collection Strategies

The service **automatically adapts** to exchange capabilities using three strategies:

### Strategy 1: FULL_WEBSOCKET
**Exchanges**: BitMEX (balance, orders, positions via WebSocket)

**Pattern**:
- **WebSocket**: Balance, orders, positions (real-time)
- **REST**: Trades only (60s intervals)

**When to Use**: Exchange has complete WebSocket support for account data

```python
# Automatic detection - no manual configuration needed
detector = CapabilityDetector()
strategy = await detector.detect_strategy(exchange)
# Returns: CollectionStrategy.FULL_WEBSOCKET

# Internally applies:
# - handler.subscribe_balance(callback)
# - handler.subscribe_orders(callback)
# - handler.subscribe_positions(callback)
# - REST polling for trades only
```

### Strategy 2: PARTIAL_WEBSOCKET
**Exchanges**: Kraken (balance via WebSocket, orders/positions via REST)

**Pattern**:
- **WebSocket**: Balance only (real-time)
- **REST**: Orders, positions, trades (60s intervals)

**When to Use**: Exchange has WebSocket support for balance only

```python
# Automatic detection
strategy = await detector.detect_strategy(exchange)
# Returns: CollectionStrategy.PARTIAL_WEBSOCKET

# Internally applies:
# - handler.subscribe_balance(callback)
# - REST polling for orders, positions, trades
```

### Strategy 3: REST_ONLY
**Exchanges**: Exchanges without WebSocket account data support

**Pattern**:
- **REST**: Balance, orders, positions, trades (60s intervals)

**When to Use**: Exchange has no WebSocket account data support

```python
# Automatic detection
strategy = await detector.detect_strategy(exchange)
# Returns: CollectionStrategy.REST_ONLY

# Internally applies:
# - REST polling for balance, orders, positions, trades
```

### Capability Detection

The service **automatically detects** exchange capabilities using `CapabilityDetector`:

```python
from fullon_account_service.utils.capability_detector import (
    CapabilityDetector,
    CollectionStrategy
)

detector = CapabilityDetector()

# Detect strategy
strategy = await detector.detect_strategy(exchange)
print(f"Strategy: {strategy.name}")  # FULL_WEBSOCKET, PARTIAL_WEBSOCKET, or REST_ONLY

# Get detailed capabilities
capabilities = await detector.get_capabilities(exchange)
print(f"Balance: {capabilities['balance']}")      # True/False
print(f"Orders: {capabilities['orders']}")        # True/False
print(f"Positions: {capabilities['positions']}")  # True/False
```

**Validated Capability Strings**:
- `'balance'` - Account balance updates
- `'orders'` - Order status updates
- `'positions'` - Position updates (derivatives)
- `'my_trades'` - User trade updates (not used - always REST)

---

## API Reference

### AccountDaemon

**Main orchestrator for cryptocurrency account monitoring.**

#### Constructor

```python
daemon = AccountDaemon()
```

**Parameters**: None (follows fullon_ticker_service pattern)

**Behavior**:
- Discovers ALL exchanges from ALL users (database-driven)
- No hardcoded configuration required
- Component-specific logging: `fullon.account.daemon`

#### Methods

##### `start() -> None`

Start the account monitoring daemon for all exchanges.

**Behavior**:
1. Discovers all active exchanges from database (all users)
2. Initializes `LiveAccountCollector` and `RestAccountPoller`
3. Starts monitoring all discovered exchanges with appropriate strategies
4. Registers processes in ProcessCache for health monitoring
5. Blocks until shutdown signal received

**Example**:
```python
daemon = AccountDaemon()
await daemon.start()  # Blocks until SIGTERM/SIGINT
```

**Logs**:
```
INFO: Starting AccountDaemon
INFO: AccountDaemon started successfully exchange_count=3 exchanges=['kraken', 'bitmex', 'hyperliquid']
```

##### `process_exchange(exchange: Exchange) -> None`

Process a single exchange for account monitoring.

**Parameters**:
- `exchange` (Exchange): Exchange model instance from fullon_orm

**Behavior** (Three-Way State Check):
- **Daemon running**: Adds exchange dynamically to existing collectors
- **Daemon not running**: Starts minimal collectors for single exchange
- **Partially running**: Logs error and returns

**Example**:
```python
async with DatabaseContext() as db:
    exchanges = await db.exchanges.get_user_exchanges(uid=1)
    exchange = exchanges[0]

daemon = AccountDaemon()
await daemon.process_exchange(exchange)  # Starts collection for this exchange
```

**Logs**:
```
INFO: Starting account collection for single exchange exchange_id=1 exchange=kraken
INFO: Starting account collector for exchange exchange_id=1
INFO: Applying collection strategy exchange_id=1 exchange_name=kraken strategy=PARTIAL_WEBSOCKET
```

##### `stop() -> None`

Stop the account monitoring daemon gracefully.

**Behavior**:
1. Updates all processes to STOPPED status
2. Stops all collectors (LiveAccountCollector + RestAccountPoller)
3. Cleans up resources (handlers, process_ids, state)
4. Resets daemon state

**Example**:
```python
await daemon.stop()
```

**Logs**:
```
INFO: Stopping AccountDaemon
INFO: AccountDaemon stopped successfully
```

##### `get_health() -> Dict[str, Any]`

Get daemon health status.

**Returns**: Dictionary with health information
```python
{
    "service": "fullon_account_service",
    "is_running": True,
    "uptime_seconds": 123.45,
    "exchanges_monitored": 3,
    "last_health_check": 1634567890.123,
    "live_collector": "active",    # or "inactive"
    "rest_poller": "active"         # or "inactive"
}
```

**Example**:
```python
health = await daemon.get_health()
print(f"Uptime: {health['uptime_seconds']}s")
print(f"Monitoring {health['exchanges_monitored']} exchanges")
```

---

### LiveAccountCollector

**Collects live account data via WebSocket streams.**

#### Constructor

```python
# For bulk startup (daemon initialization)
collector = LiveAccountCollector(exchanges=exchange_list)

# For single-exchange startup (dynamic addition)
collector = LiveAccountCollector()
```

**Parameters**:
- `exchanges` (List[Exchange], optional): List of exchanges to collect from (bulk startup)

#### Methods

##### `start_collection() -> None`

Start live account data collection for all configured exchanges.

**Use Case**: Bulk startup during daemon initialization

**Example**:
```python
collector = LiveAccountCollector(exchanges=all_exchanges)
await collector.start_collection()
```

##### `start_exchange(exchange: Exchange) -> None`

Start live account data collection for a single exchange.

**Use Case**: Dynamic addition or single-exchange monitoring

**Parameters**:
- `exchange` (Exchange): Exchange to start collecting from

**Behavior**:
1. Checks if already collecting (idempotent)
2. Gets WebSocket handler via ExchangeQueue
3. Registers callbacks based on capabilities
4. Subscribes to available streams
5. Registers process in ProcessCache

**Example**:
```python
collector = LiveAccountCollector()
await collector.start_exchange(exchange)
```

##### `is_collecting(exchange: Exchange) -> bool`

Check if currently collecting data from the given exchange.

**Returns**: True if collecting from this exchange

**Example**:
```python
if collector.is_collecting(exchange):
    print("Already collecting from this exchange")
```

##### `stop_collection() -> None`

Stop live account data collection for all exchanges.

##### `stop_exchange(exchange: Exchange) -> None`

Stop live account data collection for a single exchange.

#### Callback Handlers

These methods are **automatically called** by WebSocket streams:

##### `on_balance_update(exchange: Exchange, balances: Dict[str, Balance]) -> None`

Handle incoming balance update from WebSocket.

**Storage**: Redis (AccountCache) - latest values only

**Format**:
```python
balances = {
    "BTC": Balance(total=1.5, free=1.2, used=0.3),
    "USDT": Balance(total=10000, free=8500, used=1500)
}
```

##### `on_order_update(exchange: Exchange, orders: List[Order]) -> None`

Handle incoming order update from WebSocket.

**Storage**: PostgreSQL (fullon_orm) - persistent history

##### `on_position_update(exchange: Exchange, position: Position) -> None`

Handle incoming position update from WebSocket.

**Storage**: Redis (AccountCache) - latest values only

---

### RestAccountPoller

**Polls account data via REST API at fixed intervals.**

#### Constructor

```python
# For bulk startup
poller = RestAccountPoller(exchanges=exchange_list, poll_interval=60)

# For single-exchange startup
poller = RestAccountPoller(poll_interval=60)
```

**Parameters**:
- `exchanges` (List[Exchange], optional): List of exchanges to poll
- `poll_interval` (int): Polling interval in seconds (default 60)

#### Methods

##### `start_polling() -> None`

Start periodic REST polling for all configured exchanges.

##### `start_exchange(exchange: Exchange) -> None`

Start REST polling for a single exchange.

**Behavior**:
1. Creates unified polling loop (single task per exchange)
2. Polls balance, orders, positions, trades based on strategy
3. Uses single sleep cycle (not 4 separate sleeps)

**Example**:
```python
poller = RestAccountPoller(poll_interval=60)
await poller.start_exchange(exchange)
```

##### `is_polling(exchange: Exchange) -> bool`

Check if currently polling data for the given exchange.

##### `stop_polling() -> None`

Stop REST polling for all exchanges.

##### `stop_exchange(exchange: Exchange) -> None`

Stop REST polling for a single exchange.

---

### CapabilityDetector

**Detects exchange WebSocket capabilities and determines collection strategy.**

#### Constructor

```python
detector = CapabilityDetector()
```

#### Methods

##### `detect_strategy(exchange: Exchange) -> CollectionStrategy`

Detect which collection strategy to use based on exchange capabilities.

**Returns**:
- `CollectionStrategy.FULL_WEBSOCKET` - All capabilities via WebSocket
- `CollectionStrategy.PARTIAL_WEBSOCKET` - Balance via WebSocket, others via REST
- `CollectionStrategy.REST_ONLY` - All data via REST polling

**Example**:
```python
detector = CapabilityDetector()
strategy = await detector.detect_strategy(exchange)

if strategy == CollectionStrategy.FULL_WEBSOCKET:
    print("Using full WebSocket support")
elif strategy == CollectionStrategy.PARTIAL_WEBSOCKET:
    print("Using partial WebSocket support")
else:
    print("Using REST-only polling")
```

##### `get_capabilities(exchange: Exchange) -> Dict[str, bool]`

Get detailed capability information for an exchange.

**Returns**:
```python
{
    "balance": True,     # WebSocket balance support
    "orders": True,      # WebSocket orders support
    "positions": False   # No WebSocket positions support
}
```

**Example**:
```python
capabilities = await detector.get_capabilities(exchange)
print(f"Balance support: {capabilities['balance']}")
print(f"Orders support: {capabilities['orders']}")
print(f"Positions support: {capabilities['positions']}")
```

---

## Usage Patterns

### Pattern 1: Full Daemon Startup (Production)

**Use Case**: Monitor all exchanges from all users (like fullon_ticker_service monitors all symbols)

```python
import asyncio
from fullon_account_service import AccountDaemon

async def main():
    daemon = AccountDaemon()

    # Start daemon (blocks until shutdown)
    await daemon.start()

if __name__ == "__main__":
    asyncio.run(main())
```

**What Happens**:
1. Discovers ALL exchanges from ALL users via database query
2. Registers each exchange in ProcessCache for health monitoring
3. Applies appropriate collection strategy per exchange
4. Starts LiveAccountCollector and RestAccountPoller
5. Monitors continuously until SIGTERM/SIGINT

### Pattern 2: Single Exchange Monitoring (Development)

**Use Case**: Monitor specific exchange dynamically

```python
import asyncio
from fullon_account_service import AccountDaemon
from fullon_orm import DatabaseContext

async def main():
    # Get exchange from database
    async with DatabaseContext() as db:
        exchanges = await db.exchanges.get_user_exchanges(uid=1)
        exchange = exchanges[0]

    # Create daemon and process single exchange
    daemon = AccountDaemon()
    await daemon.process_exchange(exchange)

    # Monitor for 30 seconds
    await asyncio.sleep(30)

    # Stop gracefully
    await daemon.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

**What Happens**:
1. Creates empty collectors (no bulk startup)
2. Detects exchange capabilities
3. Starts appropriate collection strategy
4. Monitors for specified duration
5. Cleans up resources

### Pattern 3: Reading Balance Data

**Use Case**: Read collected balance data from Redis

```python
from fullon_cache import AccountCache

async def get_exchange_balances(exchange_id: int):
    """Get all balances for an exchange."""
    async with AccountCache() as cache:
        all_accounts = await cache.get_all_accounts()
        balances_raw = all_accounts.get(str(exchange_id))

        # Handle JSON string (if stored as string)
        if isinstance(balances_raw, str):
            import json
            balances = json.loads(balances_raw)
        else:
            balances = balances_raw

    # Filter positive balances
    positive_balances = {
        currency: data
        for currency, data in balances.items()
        if isinstance(data, dict) and data.get("total", 0.0) > 0
    }

    return positive_balances

# Usage
balances = await get_exchange_balances(exchange_id=1)
for currency, balance_data in balances.items():
    print(f"{currency}: {balance_data['total']:.6f}")
```

### Pattern 4: Reading Position Data

**Use Case**: Read collected position data from Redis

```python
from fullon_cache import AccountCache

async def get_exchange_positions(exchange_id: int):
    """Get all positions for an exchange."""
    async with AccountCache() as cache:
        all_positions = await cache.get_positions(exchange_id)

        # Filter to only positions for this exchange
        positions = [
            p for p in all_positions
            if getattr(p, "ex_id", "") == str(exchange_id)
        ]

    return positions

# Usage
positions = await get_exchange_positions(exchange_id=1)
for position in positions:
    print(f"{position.symbol}: vol={position.volume:.6f} @ ${position.price:.2f}")
```

### Pattern 5: Reading Orders from Database

**Use Case**: Query order history from PostgreSQL

```python
from fullon_orm import DatabaseContext

async def get_exchange_orders(exchange_id: int, limit: int = 10):
    """Get recent orders for an exchange."""
    async with DatabaseContext() as db:
        # Use fullon_orm repositories
        orders = await db.orders.get_exchange_orders(
            exchange_id=exchange_id,
            limit=limit
        )

    return orders

# Usage
orders = await get_exchange_orders(exchange_id=1, limit=10)
for order in orders:
    print(f"Order {order.order_id}: {order.status} - {order.symbol}")
```

### Pattern 6: Reading Trades with Automatic PnL

**Use Case**: Query trades with automatically calculated PnL from PostgreSQL

```python
from fullon_orm import DatabaseContext

async def get_exchange_trades_with_pnl(exchange_id: int, limit: int = 10):
    """Get recent trades with automatic PnL calculation."""
    async with DatabaseContext() as db:
        # fullon_orm automatically calculates PnL via FIFO matching
        trades = await db.trades.get_exchange_trades(
            exchange_id=exchange_id,
            limit=limit
        )

    return trades

# Usage
trades = await get_exchange_trades_with_pnl(exchange_id=1, limit=10)
for trade in trades:
    print(f"Trade {trade.trade_id}: {trade.symbol} - PnL: ${trade.pnl:.2f}")
```

**CRITICAL**: Trade storage automatically calculates PnL via FIFO matching:
- Automatic ROI calculations with leverage
- Fee tracking and average cost basis
- Closing PnL for realized positions
- **DO NOT** manually calculate PnL - fullon_orm handles this (lines 307-500 in trade.py)

### Pattern 7: Health Monitoring

**Use Case**: Monitor service health via ProcessCache

```python
from fullon_cache import ProcessCache

async def check_account_service_health():
    """Check health of account monitoring processes."""
    async with ProcessCache() as cache:
        processes = await cache.get_active_processes()

        account_processes = [
            p for p in processes
            if "account" in str(p.get("component", "")).lower()
        ]

        for process in account_processes:
            component = process.get("component", "unknown")
            status = process.get("status", "unknown")
            print(f"{component}: {status}")

        return len(account_processes)

# Usage
active_count = await check_account_service_health()
print(f"Active account monitoring processes: {active_count}")
```

---

## Integration Examples

### Example 1: Complete Pipeline with Daemon

**File**: `examples/run_example_pipeline.py`

```python
#!/usr/bin/env python3
"""
Example: Full Account Service Pipeline with Daemon

Demonstrates the complete account monitoring pipeline using the daemon.
Tests both capability detection and adaptive collection strategies.
"""

import asyncio
from fullon_account_service.daemon import AccountDaemon
from fullon_log import get_component_logger

logger = get_component_logger("fullon.account.pipeline.test")

async def run_pipeline():
    """Run the complete pipeline using the daemon."""
    daemon = None
    try:
        # Create daemon instance
        daemon = AccountDaemon()

        # Start daemon (monitors all user exchanges)
        daemon_task = asyncio.create_task(daemon.start())

        # Let it run for 30 seconds to collect account data
        await asyncio.sleep(30)

        # Cancel daemon task gracefully
        daemon_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await daemon_task

    except Exception as e:
        logger.exception("Pipeline failed")
    finally:
        if daemon:
            await daemon.stop()

if __name__ == "__main__":
    asyncio.run(run_pipeline())
```

### Example 2: Single User Process with Dynamic Exchange

**File**: `examples/single_user_process.py`

```python
#!/usr/bin/env python3
"""
Single User Process Example - Account Monitoring

Demonstrates collecting exactly 10 balance updates then exiting:
1. Get exchange from database
2. Create AccountDaemon
3. Start processing exchange using process_exchange()
4. Collect and count balance updates until we reach 10
5. Stop the daemon and clean up
"""

import asyncio
import signal
from fullon_account_service import AccountDaemon
from fullon_cache import AccountCache
from fullon_log import get_component_logger
from fullon_orm import DatabaseContext

logger = get_component_logger("fullon.account.examples.single_user_process")

async def main():
    """Simple account monitoring example."""
    daemon = None

    try:
        # Get exchange from database
        async with DatabaseContext() as db:
            user_exchanges = await db.exchanges.get_user_exchanges(uid=1)
            if not user_exchanges:
                logger.error("No exchanges found in database")
                return 1

            exchange = user_exchanges[0]

        # Create daemon and process single exchange
        daemon = AccountDaemon()
        await daemon.process_exchange(exchange=exchange)

        logger.info("Account monitoring started! Collecting 10 balance updates...")

        # Main loop: read from cache and print until we get 10 balance updates
        update_count = 0
        while update_count < 10:
            async with AccountCache() as cache:
                all_accounts = await cache.get_all_accounts()
                balances_raw = all_accounts.get(str(exchange.ex_id))

                if balances_raw:
                    if isinstance(balances_raw, str):
                        import json
                        balances = json.loads(balances_raw)
                    else:
                        balances = balances_raw

                    if balances:
                        update_count += 1
                        logger.info(
                            "Balance update received",
                            update_number=update_count,
                            total_expected=10
                        )

                        if update_count >= 10:
                            break

            await asyncio.sleep(3)

        return 0

    except Exception as e:
        logger.error("Error in main", error=str(e), exc_info=True)
        return 1
    finally:
        if daemon:
            await daemon.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Example 3: Custom Collection Strategy

```python
"""
Example: Manual strategy selection based on exchange type
"""

import asyncio
from fullon_account_service import AccountDaemon
from fullon_account_service.utils.capability_detector import (
    CapabilityDetector,
    CollectionStrategy
)
from fullon_orm import DatabaseContext

async def monitor_with_custom_strategy():
    """Monitor exchange with explicit strategy check."""
    async with DatabaseContext() as db:
        exchanges = await db.exchanges.get_user_exchanges(uid=1)
        exchange = exchanges[0]

    # Detect capabilities
    detector = CapabilityDetector()
    strategy = await detector.detect_strategy(exchange)
    capabilities = await detector.get_capabilities(exchange)

    print(f"Exchange: {exchange.cat_exchange.name}")
    print(f"Strategy: {strategy.name}")
    print(f"Capabilities: {capabilities}")

    # Start monitoring
    daemon = AccountDaemon()
    await daemon.process_exchange(exchange)

    # Run for 60 seconds
    await asyncio.sleep(60)
    await daemon.stop()

if __name__ == "__main__":
    asyncio.run(monitor_with_custom_strategy())
```

---

## Testing Patterns

### Test 1: Daemon Start/Stop

```python
import pytest
from fullon_account_service.daemon import AccountDaemon

@pytest.mark.asyncio
async def test_daemon_start_stop():
    """Test daemon lifecycle."""
    daemon = AccountDaemon()

    # Should not be running initially
    assert not daemon.is_running

    # Start should set is_running to True
    # (Note: start() blocks, so we'd use process_exchange() in tests)

    # Stop should clean up
    await daemon.stop()
    assert not daemon.is_running
    assert daemon.live_collector is None
    assert daemon.rest_poller is None
```

### Test 2: Capability Detection

```python
import pytest
from unittest.mock import AsyncMock
from fullon_account_service.utils.capability_detector import (
    CapabilityDetector,
    CollectionStrategy
)

@pytest.mark.asyncio
async def test_capability_detection_partial_websocket():
    """Test detection of partial WebSocket support."""
    # Mock exchange
    exchange = AsyncMock()
    exchange.ex_id = 1
    exchange.cat_exchange.name = "kraken"

    # Mock handler capabilities
    handler = AsyncMock()
    handler.supports_capability.side_effect = lambda cap: cap == "balance"

    # Manually inject handler (for testing)
    from fullon_exchange.queue import ExchangeQueue
    ExchangeQueue.get_websocket_handler = AsyncMock(return_value=handler)

    # Test detection
    detector = CapabilityDetector()
    strategy = await detector.detect_strategy(exchange)

    assert strategy == CollectionStrategy.PARTIAL_WEBSOCKET
```

### Test 3: Balance Update Storage

```python
import pytest
from fullon_cache import AccountCache
from fullon_orm.models import Balance

@pytest.mark.asyncio
async def test_balance_update_storage():
    """Test balance data storage in Redis."""
    exchange_id = 1

    # Create test balance data
    balance_data = {
        "BTC": {"total": 1.5, "free": 1.2, "used": 0.3},
        "USDT": {"total": 10000, "free": 8500, "used": 1500}
    }

    # Store in cache
    async with AccountCache() as cache:
        success = await cache.upsert_user_account(exchange_id, balance_data)

    assert success

    # Retrieve from cache
    async with AccountCache() as cache:
        all_accounts = await cache.get_all_accounts()
        balances = all_accounts.get(str(exchange_id))

    assert balances is not None
    assert "BTC" in balances
    assert balances["BTC"]["total"] == 1.5
```

### Test 4: Process Cache Health Monitoring

```python
import pytest
from fullon_cache import ProcessCache
from fullon_cache.process_cache import ProcessStatus, ProcessType

@pytest.mark.asyncio
async def test_process_cache_registration():
    """Test process registration in ProcessCache."""
    async with ProcessCache() as cache:
        # Register process
        process_id = await cache.register_process(
            process_type=ProcessType.BOT,
            component="account_monitor_test",
            params={"exchange_id": 1},
            message="Test registration",
            status=ProcessStatus.RUNNING
        )

    assert process_id is not None

    # Verify registration
    async with ProcessCache() as cache:
        processes = await cache.get_active_processes()
        test_processes = [
            p for p in processes
            if p.get("component") == "account_monitor_test"
        ]

    assert len(test_processes) == 1
    assert test_processes[0]["status"] == ProcessStatus.RUNNING.value
```

---

## Troubleshooting

### Issue 1: No Balance Data in Cache

**Symptom**: Balance data not appearing in AccountCache

**Diagnosis**:
```python
from fullon_cache import AccountCache

async with AccountCache() as cache:
    all_accounts = await cache.get_all_accounts()
    print(f"All accounts: {all_accounts}")  # Empty dict?
```

**Solutions**:
1. **Check exchange capabilities**: Exchange may not support WebSocket balance
   ```python
   detector = CapabilityDetector()
   capabilities = await detector.get_capabilities(exchange)
   print(f"Balance support: {capabilities['balance']}")
   ```

2. **Check collection strategy**: May be using REST-only (60s polling)
   ```python
   strategy = await detector.detect_strategy(exchange)
   print(f"Strategy: {strategy.name}")  # Should be PARTIAL_WEBSOCKET or FULL_WEBSOCKET
   ```

3. **Check ProcessCache logs**: Look for errors in collection
   ```python
   from fullon_cache import ProcessCache

   async with ProcessCache() as cache:
       processes = await cache.get_active_processes()
       for p in processes:
           if "account" in p.get("component", "").lower():
               print(f"{p['component']}: {p['status']} - {p.get('message', '')}")
   ```

### Issue 2: Daemon Not Starting

**Symptom**: `daemon.start()` returns immediately without starting

**Diagnosis**:
```python
daemon = AccountDaemon()
health = await daemon.get_health()
print(f"Running: {health['is_running']}")
print(f"Exchanges monitored: {health['exchanges_monitored']}")
```

**Solutions**:
1. **Check database for exchanges**:
   ```python
   from fullon_orm import DatabaseContext

   async with DatabaseContext() as db:
       users = await db.users.get_all()
       print(f"Users: {len(users)}")

       for user in users:
           exchanges = await db.exchanges.get_user_exchanges(uid=user.uid)
           print(f"User {user.uid}: {len(exchanges)} exchanges")
   ```

2. **Check logs for errors**:
   ```python
   from fullon_log import get_component_logger

   logger = get_component_logger("fullon.account.daemon")
   logger.setLevel("DEBUG")  # Enable debug logging
   ```

### Issue 3: REST Polling Not Working

**Symptom**: No data updates with REST-only strategy

**Diagnosis**:
```python
poller = RestAccountPoller()
status = poller.get_status()
print(f"Polling exchanges: {status['polling_exchanges']}")
print(f"Poll tasks: {status['poll_tasks']}")
print(f"Poll interval: {status['poll_interval']}s")
```

**Solutions**:
1. **Check polling interval**: Default is 60s, may need to wait
   ```python
   # Wait at least 60s for first poll
   await asyncio.sleep(60)
   ```

2. **Check exchange credentials**: REST requires valid API keys
   ```python
   from fullon_exchange.queue import ExchangeQueue

   try:
       handler = await ExchangeQueue.get_rest_handler(exchange)
       balances = await handler.get_balance()
       print(f"Balances: {balances}")
   except Exception as e:
       print(f"Error: {e}")  # Check for auth errors
   ```

### Issue 4: High Redis Write Load

**Symptom**: Excessive Redis writes causing performance issues

**Diagnosis**:
```bash
# Monitor Redis commands
redis-cli monitor | grep account
```

**Solutions**:
1. **Rate limiting is automatic**: ProcessCache updates limited to 30s intervals
2. **Check implementation**: Ensure using rate-limited methods
   ```python
   # ✅ CORRECT: Rate-limited update
   await self._update_process_with_rate_limit(exchange)

   # ❌ WRONG: Direct update (not rate-limited)
   await cache.update_process(process_id, status, message)
   ```

### Issue 5: Trade PnL Not Calculated

**Symptom**: Trades stored but PnL is None/zero

**Solution**: **NO MANUAL CALCULATION NEEDED!** fullon_orm handles PnL automatically:

```python
# ✅ CORRECT: fullon_orm calculates PnL automatically
from fullon_orm import DatabaseContext

async with DatabaseContext() as db:
    # save_trades() internally calls _calculate_closing_pnl_batch()
    success = await db.trades.save_trades(trades)
    await db.commit()

# PnL is calculated automatically via FIFO matching:
# - Automatic ROI calculations with leverage
# - Fee tracking and average cost basis
# - Closing PnL for realized positions

# ❌ WRONG: Manual PnL calculation (redundant, do NOT do this!)
# pnl = calculate_pnl(trades)  # This is WRONG - fullon_orm handles it
```

**CRITICAL**: Do NOT reimplement PnL calculation - fullon_orm's trade.py (lines 307-500) handles:
- FIFO position matching
- ROI calculations with leverage
- Fee tracking
- Average cost basis
- Closing PnL for realized positions

---

## Environment Configuration

Required environment variables:

```bash
# Database for fullon_orm
DB_HOST=localhost
DB_PORT=5432
DB_USER=fullon
DB_PASSWORD=your_password
DB_NAME=fullon2

# Redis for fullon_cache
CACHE_HOST=localhost
CACHE_PORT=6379
CACHE_DB=0

# Google Cloud Secrets Manager (Production)
GOOGLE_SECRET=your-gcp-secret-name
GOOGLE_CREDENTIALS=/path/to/service-account-key.json

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=beautiful
LOG_CONSOLE=true

# Account daemon specific
ACCOUNT_POLL_INTERVAL=60  # REST polling interval in seconds
ACCOUNT_RECONNECT_DELAY=5
ACCOUNT_MAX_RETRIES=3
```

---

## Performance Characteristics

### ProcessCache Rate Limiting

**Pattern**: Rate-limit ProcessCache updates to once per 30 seconds per exchange

**Impact**:
- **Before**: 1200+ Redis writes/hour per exchange
- **After**: 120 Redis writes/hour per exchange
- **Reduction**: 90% fewer Redis writes

**Why 30 seconds**: Health monitoring remains effective (2× faster than 60s standard)

### REST Polling Intervals

**Frequency**: 60 seconds (all data types: balance, orders, positions, trades)

**Rationale**:
- ✅ Matches proven legacy behavior
- ✅ Acceptable latency for account monitoring
- ✅ API-friendly (~240 calls/hour per exchange = 4 endpoints × 60s)
- ✅ Prevents API throttling
- ✅ Well within exchange rate limits

### Storage Strategy

| Data Type | Storage | Type | Frequency |
|-----------|---------|------|-----------|
| Balance | Redis (AccountCache) | Ephemeral (latest) | Real-time (WS) or 60s (REST) |
| Positions | Redis (AccountCache) | Ephemeral (latest) | Real-time (WS) or 60s (REST) |
| Orders | PostgreSQL (fullon_orm) | Persistent (history) | Real-time (WS) or 60s (REST) |
| Trades | PostgreSQL (fullon_orm) | Persistent + PnL | 60s (always REST) |

---

## Dependencies

**CRITICAL**: Use fullon_orm models as input/output throughout.

### Core Libraries

```python
from fullon_orm import DatabaseContext, init_db
from fullon_orm.models import Exchange, Order, Position, Trade, Balance
from fullon_cache import AccountCache, ProcessCache
from fullon_exchange.queue import ExchangeQueue
from fullon_log import get_component_logger
from fullon_credentials import fullon_credentials
```

### Documentation References

- 📖 **docs/FULLON_ORM_LLM_METHOD_REFERENCE.md** - Complete method reference for all repositories
- 📖 **docs/FULLON_CACHE_LLM_QUICKSTART.md** - AccountCache, ProcessCache integration patterns
- 📖 **docs/FULLON_LOG_LLM_README.md** - Component logging patterns
- 📖 **docs/11_FULLON_EXCHANGE_LLM_README.md** - Unified exchange API with WebSocket/REST
- 📖 **docs/FULLON_CREDENTIALS_LLM_README.md** - Secure credential resolver

---

## Key Differences from Other Services

### Unique to Account Service

1. **Adaptive Collection**: Must detect and adapt to exchange capabilities
2. **Mixed Storage**: Redis (balances, positions) + PostgreSQL (orders, trades)
3. **Three Collection Strategies**: Full WebSocket, Partial WebSocket, REST-only
4. **Exchange-Based Tracking**: Tracks by exchange.ex_id, not by symbol
5. **Automatic PnL Calculation**: Leverages fullon_orm's built-in FIFO matching

### Comparison with Other Services

| Aspect | Ticker Service | OHLCV Service | Account Service |
|--------|---------------|---------------|-----------------|
| **Storage** | Redis (TickCache) | PostgreSQL (hypertables) | Redis + PostgreSQL |
| **Data Type** | Ephemeral (latest) | Historical (time-series) | Mixed |
| **Daemon Method** | `process_ticker(symbol)` | `process_symbol(symbol)` | `process_exchange(exchange)` |
| **Tracking** | By symbol | By symbol | By exchange |
| **Initialization** | None | `add_all_symbols()` | None |
| **Collection** | Always WebSocket | WebSocket + REST | Adaptive (WS/REST) |

### Shared Patterns

- ✅ Three-way state check in daemon
- ✅ Empty constructor for single-item startup
- ✅ `start_exchange()` / `is_collecting()` methods
- ✅ Rate-limited ProcessCache updates (30 seconds)
- ✅ Component-specific logging
- ✅ Async/await throughout
- ✅ Database-driven configuration (no hardcoded lists)

---

## What NOT to Build

The service integrates with fullon ecosystem - **DO NOT** reimplement:

1. ❌ **Manual PnL calculation** - fullon_orm handles this automatically via FIFO matching
2. ❌ **Exchange connection management** - fullon_exchange handles WebSocket/REST connections
3. ❌ **Symbol discovery** - Database-driven via fullon_orm
4. ❌ **Credential management** - fullon_credentials handles secure credential resolution
5. ❌ **Database connection pooling** - fullon_orm handles connection lifecycle
6. ❌ **WebSocket reconnection logic** - fullon_exchange handles auto-reconnect with backoff
7. ❌ **Custom logging infrastructure** - Use fullon_log component logging

---

## Additional Resources

### Example Files

- `examples/run_example_pipeline.py` - Full daemon with all exchanges
- `examples/single_user_process.py` - Single exchange monitoring
- `examples/demo_data.py` - Test data setup utilities

### Running Examples

```bash
# Full pipeline test
poetry run python examples/run_example_pipeline.py

# Single exchange monitoring
poetry run python examples/single_user_process.py kraken

# With specific exchange
poetry run python examples/single_user_process.py bitmex
```

### Development Workflow

```bash
# Setup
poetry install
poetry run pre-commit install

# Run daemon (production)
poetry run python -m fullon_account_service.daemon start

# Stop daemon
poetry run python -m fullon_account_service.daemon stop

# Monitor single exchange
poetry run python -m fullon_account_service.daemon process --exchange-id=1

# Run tests
poetry run pytest

# Code quality
poetry run black .
poetry run ruff .
poetry run mypy src/
```

---

## Summary

The fullon_account_service is a **lightweight async daemon** (~500-700 lines) that:

1. **Automatically discovers** all exchanges from database (no hardcoded config)
2. **Adapts collection strategies** based on exchange WebSocket capabilities
3. **Stores data efficiently**: Redis for ephemeral (balances, positions), PostgreSQL for persistent (orders, trades)
4. **Calculates PnL automatically**: Leverages fullon_orm's FIFO matching (no manual calculation)
5. **Follows ecosystem patterns**: Three-way state check, rate-limited ProcessCache, component logging
6. **Integrates seamlessly**: Works with fullon_exchange, fullon_orm, fullon_cache, fullon_log

**Use Cases**:
- Production monitoring of all user exchanges
- Development testing with single exchanges
- Real-time balance tracking
- Historical trade analysis with PnL
- Position monitoring for derivatives
- Order status tracking

**Key Benefits**:
- Zero manual configuration (database-driven)
- Automatic strategy adaptation per exchange
- 90% reduction in Redis writes via rate limiting
- Built-in health monitoring via ProcessCache
- Automatic PnL calculation via fullon_orm

For detailed architectural patterns, see **CLAUDE.md** in the project root.
