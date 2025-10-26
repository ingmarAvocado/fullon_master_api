# Fix E2E Test Failures - Database Isolation & Server Connection Issues

**Date**: 2025-10-26
**Status**: ACTIVE
**Priority**: HIGH
**Affected Files**: `tests/e2e/test_example_orm_routes.py`, `tests/e2e/test_example_ohlcv_routes.py`

---

## Executive Summary

### Problem

E2E tests are failing while integration tests and examples work perfectly:

1. **Database Pollution**: Hardcoded email `"e2e_test@example.com"` persists in production database (`fullon2`), causing `UniqueViolationError` on subsequent test runs
2. **No Database Isolation**: E2E tests use production/development database instead of isolated test databases
3. **Server Connection Issues**: Some tests cannot connect to localhost:8000
4. **Cleanup Failure**: Test cleanup comment says "E2E tests typically don't clean up" - this is WRONG for our architecture

### Root Cause

E2E tests **do NOT follow the proven pattern** from `examples/` directory:
- ❌ Use production database (`fullon2`)
- ❌ Hardcoded non-unique email addresses
- ❌ No cleanup
- ❌ No database isolation

Meanwhile, **examples work perfectly** because they:
- ✅ Create isolated test databases with UUID: `test_example_{uuid}`
- ✅ Use UUID-based unique emails
- ✅ Use `demo_data.py` utilities (`create_dual_test_databases`, `drop_dual_test_databases`)
- ✅ Proper cleanup with try/finally blocks

### The Solution

**Run actual example scripts as E2E tests:**

E2E tests execute the example scripts from `examples/` directory as subprocesses. This approach:
- ✅ **Zero duplication** - examples already work perfectly
- ✅ **Validates examples** - ensures examples are runnable standalone
- ✅ **Inherits all safety** - database isolation, cleanup, UUID uniqueness
- ✅ **Simple implementation** - just subprocess.run() each example (~2 hours)
- ✅ **Easier maintenance** - fix once in example, E2E test works

**Key Principle**: Examples are source of truth. E2E tests validate examples work.

---

## Problem Analysis

### Issue 1: Database Pollution (UniqueViolationError)

**Symptom**:
```
asyncpg.exceptions.UniqueViolationError: duplicate key value violates unique constraint "users_mail_key"
DETAIL: Key (mail)=(e2e_test@example.com) already exists.
```

**Root Cause**: `test_example_orm_routes.py` line 62:
```python
user = User(
    mail="e2e_test@example.com",  # ❌ HARDCODED - persists across runs!
    name="E2E",
    lastname="Test",
    ...
)
```

**Why This Fails**:
1. First test run creates user with `e2e_test@example.com` in `fullon2` database
2. Test finishes but NO CLEANUP (line 82: "E2E tests typically don't clean up")
3. User persists in production database
4. Second test run tries to create same user → UniqueViolationError

**Working Example** (`example_orm_routes.py`):
```python
# Line 45-55: Generate UNIQUE test database name
def generate_test_db_name() -> str:
    """Generate unique test database name."""
    import random
    import string
    return "fullon2_test_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

test_db_base = generate_test_db_name()
test_db_orm = test_db_base
test_db_ohlcv = f"{test_db_base}_ohlcv"

# Line 58-60: Set environment BEFORE imports
os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv
os.environ["DB_TEST_NAME"] = test_db_orm

# Line 356-376: Setup with isolated database
async def setup_test_environment():
    print(f"\n1. Creating dual test databases:")
    print(f"   ORM DB:   {test_db_orm}")
    print(f"   OHLCV DB: {test_db_ohlcv}")

    orm_db_name, ohlcv_db_name = await create_dual_test_databases(test_db_base)
    # ... setup data ...

# Line 457-468: ALWAYS cleanup
finally:
    print("\n" + "=" * 60)
    print("Cleaning up test databases...")
    print("=" * 60)
    try:
        await drop_dual_test_databases(test_db_orm, test_db_ohlcv)
        print("✅ Test databases cleaned up successfully")
    except Exception as cleanup_error:
        print(f"⚠️  Error during cleanup: {cleanup_error}")
```

### Issue 2: No Database Isolation

**Current E2E Pattern** (WRONG):
```python
# tests/e2e/test_example_orm_routes.py line 71
async with DatabaseContext() as db:
    created_user = await db.users.add_user(user)
```

This uses **whatever database is configured** in environment (likely `fullon2` production DB).

**Correct Pattern** (from examples):
```python
# 1. Generate unique DB name FIRST
test_db_base = generate_test_db_name()
test_db_orm = test_db_base
test_db_ohlcv = f"{test_db_base}_ohlcv"

# 2. Set environment BEFORE imports
os.environ["DB_NAME"] = test_db_orm
os.environ["DB_OHLCV_NAME"] = test_db_ohlcv

# 3. Create databases
await create_dual_test_databases(test_db_base)
await init_db()
await install_demo_data()

# 4. Use database
async with DatabaseContext() as db:
    # Now this uses test_db_orm, NOT fullon2!
    created_user = await db.users.add_user(user)

# 5. Cleanup
await drop_dual_test_databases(test_db_orm, test_db_ohlcv)
```

### Issue 3: Server Connection Failures

**Symptom** (`test_example_ohlcv_routes.py`):
```
httpx.ConnectError: All connection attempts failed
```

**Possible Causes**:
1. Server not running on localhost:8000
2. Server started but not ready (needs longer wait time)
3. Port conflict (another service on 8000)
4. Server crashes immediately after start

**Current Server Fixture** (INSUFFICIENT):
```python
@pytest.fixture(scope="module")
def server_process():
    """Start server for E2E testing."""
    process = subprocess.Popen(
        ["poetry", "run", "uvicorn", "fullon_master_api.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(3)  # ❌ Fixed delay, no retry logic

    # Verify server is running
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5.0)
        assert response.status_code == 200
    except Exception as e:
        process.kill()
        raise RuntimeError(f"Server failed to start: {e}")

    yield process

    process.kill()
    process.wait()
```

**Issues**:
- No retry logic for server startup
- No logging of server stdout/stderr
- No graceful shutdown
- Module scope means shared server across tests (state leakage potential)

**Better Pattern** (examples start their own server):
Examples like `example_orm_routes.py` handle server lifecycle internally, ensuring proper isolation.

### Issue 4: No Cleanup

**Current Code** (line 82-83):
```python
yield (created_user, token)

# Note: E2E tests typically don't clean up to avoid interfering with other tests
```

**This is WRONG for our architecture!**

In our project:
- ✅ Integration tests use database-per-worker isolation (savepoint rollback)
- ✅ Examples use isolated test databases with cleanup
- ❌ E2E tests pollute shared database with no cleanup

**Result**: Database pollution, flaky tests, UniqueViolationError on re-runs.

**Correct Approach**: E2E tests should:
1. Create isolated test database (or use examples that do this)
2. Run tests
3. **ALWAYS** cleanup test database in finally block

---

## The Solution: Run Example Scripts as E2E Tests

### Concept

E2E tests execute actual example scripts from `examples/` directory as subprocesses.

### Why This Works

**Examples are already perfect**:
- ✅ Isolated test databases with UUID names
- ✅ Complete setup → operation → validation → cleanup workflow
- ✅ Real HTTP requests to localhost:8000
- ✅ Proper error handling
- ✅ Production-ready patterns

**E2E tests become validators**:
- Run example script via subprocess
- Check exit code (0 = success)
- Check output for errors
- That's it!

### Benefits

1. **Zero Duplication**: Don't repeat pattern in E2E tests
2. **Validates Examples**: Ensures examples are runnable standalone
3. **Inherits Safety**: Database isolation, cleanup, uniqueness
4. **Simple Implementation**: Just `subprocess.run()`
5. **Easy Maintenance**: Fix once in example, E2E test works
6. **Fast to Implement**: ~2 hours total

---

## Implementation Steps

### Step 1: Create New E2E Test Structure

Create `tests/e2e/test_run_examples.py`:

```python
"""
E2E Tests: Run Example Scripts

Validates that all example scripts run successfully without errors.
This ensures examples are production-ready and self-contained.
"""
import subprocess
import sys
from pathlib import Path
import pytest
from fullon_log import get_component_logger

logger = get_component_logger("fullon.master_api.tests.e2e.run_examples")

# Path to examples directory
EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"


class TestExampleScripts:
    """Test that example scripts run successfully."""

    def test_example_health_check(self):
        """Test example_health_check.py runs without errors."""
        script = EXAMPLES_DIR / "example_health_check.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Log output for debugging
        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_health_check.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_jwt_login(self):
        """Test example_jwt_login.py runs without errors."""
        script = EXAMPLES_DIR / "example_jwt_login.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_jwt_login.py",
                stdout=result.stdout[-500:],
                stderr=result.stderr[-500:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_orm_routes(self):
        """Test example_orm_routes.py runs without errors."""
        script = EXAMPLES_DIR / "example_orm_routes.py"

        # This example creates its own server, DB, and cleans up
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60  # Longer timeout for full example
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_orm_routes.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_ohlcv_routes(self):
        """Test example_ohlcv_routes.py runs without errors."""
        script = EXAMPLES_DIR / "example_ohlcv_routes.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_ohlcv_routes.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_bot_management(self):
        """Test example_bot_management.py runs without errors."""
        script = EXAMPLES_DIR / "example_bot_management.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_bot_management.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_trade_analytics(self):
        """Test example_trade_analytics.py runs without errors."""
        script = EXAMPLES_DIR / "example_trade_analytics.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_trade_analytics.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    def test_example_exchange_catalog(self):
        """Test example_exchange_catalog.py runs without errors."""
        script = EXAMPLES_DIR / "example_exchange_catalog.py"

        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(
                "Example failed",
                script="example_exchange_catalog.py",
                stdout=result.stdout[-1000:],
                stderr=result.stderr[-1000:]
            )

        assert result.returncode == 0, f"Example failed:\n{result.stderr}"

    @pytest.mark.slow
    def test_run_all_examples(self):
        """Test run_all_examples.py script (comprehensive test)."""
        script = EXAMPLES_DIR / "run_all_examples.py"

        result = subprocess.run(
            [sys.executable, str(script), "--skip-websocket"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for full suite
        )

        if result.returncode != 0:
            logger.error(
                "run_all_examples failed",
                stdout=result.stdout[-2000:],
                stderr=result.stderr[-2000:]
            )

        # Check for summary in output
        assert "Example Results Summary" in result.stdout or "All examples passed" in result.stdout

        # Exit code 0 means all examples passed
        assert result.returncode == 0, f"Some examples failed:\n{result.stdout[-1000:]}"
```

### Step 2: Run New E2E Tests

```bash
# Run new E2E tests
pytest tests/e2e/test_run_examples.py -v

# Expected output:
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_health_check PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_jwt_login PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_orm_routes PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_ohlcv_routes PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_bot_management PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_trade_analytics PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_example_exchange_catalog PASSED
# tests/e2e/test_run_examples.py::TestExampleScripts::test_run_all_examples PASSED
```

### Step 3: Mark Old E2E Tests as Deprecated

Add to `tests/e2e/test_example_orm_routes.py` at top:

```python
"""
DEPRECATED: This E2E test pattern is deprecated.

Issues:
- Uses production database (no isolation)
- Hardcoded emails cause UniqueViolationError on re-runs
- No cleanup
- Violates project's database isolation principles

Use tests/e2e/test_run_examples.py instead, which runs actual
example scripts that follow proper isolation patterns.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Deprecated - use test_run_examples.py")

# ... existing code ...
```

Similarly for `tests/e2e/test_example_ohlcv_routes.py` and other old E2E test files.

### Step 4: Update CI/CD Pipeline

Update `.github/workflows/test.yml` or equivalent:

```yaml
- name: Run E2E Tests
  run: |
    # New approach: Run example scripts as E2E tests
    pytest tests/e2e/test_run_examples.py -v

    # Or run examples directly
    python examples/run_all_examples.py --skip-websocket
```

### Step 5: Update Documentation

Add to `CLAUDE.md` Section 6 (Testing Patterns):

```markdown
### E2E Tests

**Purpose**: Validate complete workflows by running actual example scripts.

**Pattern**: E2E tests execute example scripts as subprocesses:

```python
def test_example_orm_routes():
    """Test example_orm_routes.py runs successfully."""
    script = Path("examples/example_orm_routes.py")

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        timeout=60
    )

    assert result.returncode == 0
```

**Why**: Examples already have perfect isolation, cleanup, and validation.

**Characteristics**: Real server, real database (isolated), complete workflow, validates examples are production-ready.
```

---

## Verification Steps

### Verify New E2E Tests Work

```bash
# 1. Run new E2E test suite
pytest tests/e2e/test_run_examples.py -v

# 2. Verify all tests pass
# Expected: 8 passed (or more depending on examples)

# 3. Check no database pollution
psql -U postgres -c "\l" | grep "fullon2_test"
# Expected: Empty (all test databases cleaned up)

# 4. Run multiple times to verify no UniqueViolationError
pytest tests/e2e/test_run_examples.py -v
pytest tests/e2e/test_run_examples.py -v
pytest tests/e2e/test_run_examples.py -v
# Expected: All runs pass, no errors

# 5. Verify examples still work standalone
python examples/example_orm_routes.py
python examples/example_ohlcv_routes.py
# Expected: Both complete successfully with cleanup
```

### Verify No Database Pollution

```bash
# Check production database NOT affected
psql -U postgres -d fullon2 -c "SELECT mail FROM users WHERE mail LIKE 'e2e_test%';"
# Expected: Empty (E2E tests use isolated databases via examples)

# Check all test databases cleaned up
psql -U postgres -c "\l" | grep "test"
# Expected: Only permanent test databases (like those from conftest.py)
# Should NOT see: fullon2_test_e2e_*, test_example_*

# Verify examples clean up too
python examples/example_orm_routes.py
psql -U postgres -c "\l" | grep "test_example"
# Expected: Empty (example cleaned up its database)
```

### Verify Old Tests Are Skipped

```bash
# Check old tests are marked as skipped
pytest tests/e2e/test_example_orm_routes.py -v

# Expected output:
# tests/e2e/test_example_orm_routes.py::test_example_get_current_user SKIPPED (Deprecated - use test_run_examples.py)
# tests/e2e/test_example_orm_routes.py::test_example_list_users SKIPPED
# ...
```

---

## Implementation Timeline

### Week 1: Implement Solution

**Day 1-2** (4 hours):
1. ✅ Create `tests/e2e/test_run_examples.py`
2. ✅ Add test for each example script
3. ✅ Run tests and verify they pass
4. ✅ Fix any failing examples

**Day 3-4** (2 hours):
1. ✅ Mark old E2E tests as deprecated
2. ✅ Verify old tests are skipped
3. ✅ Update CI/CD pipeline
4. ✅ Run full test suite (unit + integration + e2e)

**Day 5** (2 hours):
1. ✅ Update documentation (CLAUDE.md, README.md)
2. ✅ Add E2E testing section
3. ✅ Create GitHub issue documenting the fix
4. ✅ Close related issues

### Week 2: Monitor and Cleanup

**Day 1-3** (monitoring):
1. ✅ Monitor test stability in CI/CD
2. ✅ Verify no database pollution
3. ✅ Verify examples run reliably
4. ✅ Address any edge cases

**Day 4-5** (cleanup):
1. ✅ Remove deprecated E2E test files (or keep with skip markers)
2. ✅ Clean up any leftover test databases
3. ✅ Add automated cleanup script if needed
4. ✅ Final documentation review

---

## Rollback Strategy

If issues arise:

### Option 1: Revert Changes (Quick)

```bash
# Revert to old pattern (NOT RECOMMENDED - has bugs)
git revert <commit-hash>
```

### Option 2: Temporary Fix (Quick)

```bash
# Manual cleanup before running old tests
cat > cleanup.sql << 'EOF'
DELETE FROM users WHERE mail LIKE 'e2e_test%';
EOF

psql -U postgres -d fullon2 -f cleanup.sql
```

### Option 3: Skip E2E Tests (Safe)

```bash
# Run only integration and unit tests
pytest tests/integration/ tests/unit/ -v

# Skip E2E until fixed
pytest tests/ -v --ignore=tests/e2e/
```

### Option 4: Fix Forward (Best)

If specific examples fail:
1. Fix the failing example
2. Verify example works standalone
3. E2E test will automatically pass

---

## Common Issues and Solutions

### Issue: "Example script failed with exit code 1"

**Symptom**:
```
AssertionError: Example failed:
Traceback (most recent call last):
  File "examples/example_orm_routes.py", line 123
  ...
```

**Solution**: Fix the example script itself
```bash
# Run example directly to debug
python examples/example_orm_routes.py

# Check output for errors
# Fix example
# E2E test will automatically pass
```

### Issue: "Server already running on port 8000"

**Symptom**:
```
OSError: [Errno 48] Address already in use
```

**Solution**: Check for running server
```bash
# Find process using port 8000
lsof -ti:8000

# Kill it
lsof -ti:8000 | xargs kill -9

# Run test again
pytest tests/e2e/test_run_examples.py -v
```

### Issue: "Test databases not cleaned up"

**Symptom**: Lots of `fullon2_test_*` databases remain

**Solution**: Manual cleanup script
```bash
# Create cleanup script
cat > cleanup_test_dbs.sh << 'EOF'
#!/bin/bash
psql -U postgres -c "
SELECT 'DROP DATABASE \"' || datname || '\";'
FROM pg_database
WHERE datname LIKE 'fullon2_test_%'
   OR datname LIKE 'test_example_%'
   OR datname LIKE '%_test_e2e_%'
" | grep DROP | psql -U postgres
EOF

chmod +x cleanup_test_dbs.sh
./cleanup_test_dbs.sh
```

### Issue: "Timeout waiting for example to complete"

**Symptom**:
```
subprocess.TimeoutExpired: Command '[python, examples/example_orm_routes.py]' timed out after 60 seconds
```

**Solution**: Increase timeout or debug example
```python
# Increase timeout in test
result = subprocess.run(
    [sys.executable, str(script)],
    capture_output=True,
    text=True,
    timeout=120  # Increase from 60 to 120
)

# Or debug example directly
python examples/example_orm_routes.py
# Find what's slow and optimize
```

---

## Next Steps

### Immediate Actions (Today)

1. ✅ **Review this document** with team
2. ✅ **Create GitHub issue** referencing this document
3. ✅ **Start implementation** - create test_run_examples.py
4. ✅ **Test locally** - verify new tests pass

### This Week

1. ✅ Implement `test_run_examples.py`
2. ✅ Verify all examples pass
3. ✅ Mark old E2E tests as deprecated
4. ✅ Update CI/CD pipeline
5. ✅ Update documentation

### Next Week

1. ✅ Monitor test stability in CI/CD
2. ✅ Address any edge cases
3. ✅ Remove deprecated test files
4. ✅ Close related GitHub issues

### Ongoing

1. ✅ Add new examples for new features
2. ✅ Ensure all examples follow isolation pattern
3. ✅ Run examples as part of pre-release checklist
4. ✅ Keep examples as source of truth for API usage

---

## References

### Working Examples (Source of Truth)

- `examples/example_orm_routes.py` - Perfect database isolation pattern (lines 45-468)
- `examples/demo_data.py` - Database lifecycle utilities
- `examples/run_all_examples.py` - Example test runner
- `tests/integration/conftest.py` - Integration test isolation pattern

### Broken E2E Tests (To Be Fixed)

- `tests/e2e/test_example_orm_routes.py` - Database pollution, hardcoded emails (will be deprecated)
- `tests/e2e/test_example_ohlcv_routes.py` - Server connection issues (will be deprecated)

### Documentation

- `CLAUDE.md` Section 2 - Examples-Driven Development
- `CLAUDE.md` Section 3 - Test Isolation Pattern
- `CLAUDE.md` Section 6 - Testing Patterns

### Related Issues

- GitHub Issue #45 - Fix E2E Test Failures
- Database isolation principles (conftest.py)
- Examples-driven development workflow

---

## Conclusion

**E2E test failures are caused by violating the project's proven database isolation pattern.**

**The Fix**: Run actual example scripts as E2E tests.

**Why This Works**:
- ✅ Examples already have perfect isolation
- ✅ Examples already clean up properly
- ✅ Examples already use unique database names
- ✅ Examples already demonstrate production patterns
- ✅ Zero code duplication

**Implementation Time**: ~8 hours total over 2 weeks

**Key Principle**: **Examples are source of truth. E2E tests validate examples work.**

---

**Questions? See CLAUDE.md Section 2 (Examples-Driven Development) and Section 6 (Testing Patterns).**
