# Examples-Driven Issue Workflow

**TDD workflow where GitHub issues → pytest tests → implementation → passing tests**

## Overview

This project uses an **examples-driven, test-driven development** workflow where:

1. **Examples define WHAT** - Executable contracts showing expected behavior
2. **Tests define HOW we validate** - pytest tests that must pass
3. **Issues define incremental steps** - One function/method per issue
4. **GitHub tracks progress** - Issues, labels, dependencies

## Workflow

```
masterplan.md → issue manifest → GitHub issues → test stubs → TDD → passing tests
```

### Step 1: Generate Issues

```bash
# Generate all issues for Phase 2
python scripts/generate_phase_issues.py --phase 2

# Dry run (preview without creating)
python scripts/generate_phase_issues.py --phase 2 --dry-run
```

**Creates:**
- 13 GitHub issues for Phase 2
- Each issue has: description, example reference, test criteria, dependencies
- Labels: `phase-2-jwt`, `auth`, `baseline`, etc.

### Step 2: Generate Test Stubs

```bash
# Create test files with stub tests
python scripts/create_test_stubs.py --phase 2

# Overwrite existing test files
python scripts/create_test_stubs.py --phase 2 --overwrite
```

**Creates:**
- `tests/unit/test_jwt.py` (6 tests)
- `tests/unit/test_middleware.py` (1 test)
- `tests/integration/test_auth_endpoints.py` (2 tests)
- `tests/e2e/test_jwt_example.py` (1 test)
- More...

All tests initially use `pytest.skip()` and fail.

### Step 3: Verify Tests

```bash
# All tests should be skipped initially
poetry run pytest -v

# Output should show:
# ======================= 13 skipped =======================
```

### Step 4: TDD Implementation

Pick an issue and implement using TDD:

```bash
# 1. Pick Issue #1 (baseline)
# GitHub: https://github.com/ingmarAvocado/fullon_master_api/issues/1

# 2. Run the test (should skip/fail)
poetry run pytest tests/unit/test_auth_structure.py::test_auth_modules_exist -v

# 3. Remove pytest.skip() from test

# 4. Run test (should fail)
poetry run pytest tests/unit/test_auth_structure.py::test_auth_modules_exist -v

# 5. Implement the code (create auth module files)

# 6. Run test (should pass)
poetry run pytest tests/unit/test_auth_structure.py::test_auth_modules_exist -v

# 7. Close GitHub issue #1
gh issue close 1 -c "Test passing, auth module structure created"
```

### Step 5: Repeat for Each Issue

Work through issues in dependency order:
- Issue #1 (baseline) → #2, #5, #10, #11
- Issue #2 → #3, #8
- Issue #3 → #4
- etc.

## Issue Structure

Each issue has:

### Description
What needs to be implemented

### Example Reference
Points to specific example code showing expected behavior:
```python
# From examples/example_jwt_login.py:69-75
token_data = response.json()
# Returns: {"access_token": "...", "token_type": "bearer", "expires_in": 3600}
```

### Test Criteria
Specific test that must pass:
```python
✅ Test passes: tests/unit/test_jwt.py::test_generate_token
```

### Implementation Guidance
Step-by-step instructions:
1. Create JWTHandler class in src/fullon_master_api/auth/jwt.py
2. Implement generate_token(user_id, username) -> str
3. Use PyJWT library
4. etc.

### Acceptance Criteria
Checklist:
- [ ] Test passes
- [ ] Function signature matches spec
- [ ] Return value correct
- [ ] Error handling implemented

### Dependencies
- **Depends on:** #1 (must be done first)
- **Blocks:** #3, #8 (others waiting on this)

## Phase 2 Issue Breakdown

**13 Issues Total:**

| # | Title | Type | Depends On | Blocks | Test File |
|---|-------|------|------------|--------|-----------|
| 1 | Setup auth module structure | baseline | - | 2,5,10,11 | test_auth_structure.py |
| 2 | Implement JWTHandler.generate_token() | function | 1 | 3,8 | test_jwt.py |
| 3 | Implement JWTHandler.decode_token() | function | 2 | 4 | test_jwt.py |
| 4 | Implement JWTHandler.verify_token() | function | 3 | 9,10,11 | test_jwt.py |
| 5 | Implement hash_password() | function | 1 | 6 | test_jwt.py |
| 6 | Implement verify_password() | function | 5 | 7 | test_jwt.py |
| 7 | Implement authenticate_user() | function | 6 | 8 | test_jwt.py |
| 8 | POST /api/v1/auth/login endpoint | endpoint | 2,7 | 13 | test_auth_endpoints.py |
| 9 | GET /api/v1/auth/verify endpoint | endpoint | 4 | 13 | test_auth_endpoints.py |
| 10 | Implement JWTMiddleware class | middleware | 4 | 12 | test_middleware.py |
| 11 | Create get_current_user() dependency | dependency | 4 | 12 | test_dependencies.py |
| 12 | Integrate middleware into gateway | integration | 10,11 | 13 | test_gateway.py |
| 13 | Verify example_jwt_login.py works | e2e | 8,9,12 | - | test_jwt_example.py |

## Labels

Issues are labeled for filtering:

### Phase Labels
- `phase-2-jwt` - Phase 2: JWT Authentication
- `phase-3-orm` - Phase 3: ORM Routes
- `phase-4-ohlcv` - Phase 4: OHLCV Routes
- etc.

### Component Labels
- `auth` - Authentication/Authorization
- `middleware` - Middleware components
- `endpoint` - API endpoints
- `database` - Database operations
- `websocket` - WebSocket functionality
- `integration` - Integration tasks

### Priority Labels
- `baseline` - Foundation/baseline code (do first)
- `critical` - Critical functionality
- `dependency` - FastAPI dependencies

### Type Labels
- `function` - Function/method implementation
- `example-validation` - Example validation

## Tracking Progress

### GitHub Issues
```bash
# View all Phase 2 issues
gh issue list --label phase-2-jwt

# View open baseline issues
gh issue list --label baseline --state open

# View my assigned issues
gh issue list --assignee @me
```

### Test Progress
```bash
# Run all tests
poetry run pytest -v

# Show summary
poetry run pytest --co -q

# Run only Phase 2 tests
poetry run pytest tests/unit/test_jwt.py tests/integration/test_auth_endpoints.py -v
```

## Files Created

### Templates & Manifests
- `.github/ISSUE_TEMPLATE/function-implementation.md` - Issue template
- `issues/phase-2-jwt-auth.json` - Phase 2 manifest

### Scripts
- `scripts/generate_phase_issues.py` - Generate GitHub issues from manifest
- `scripts/create_test_stubs.py` - Generate test stub files
- `scripts/setup_github_labels.sh` - Setup GitHub labels

### Tests (Generated)
- `tests/unit/test_auth_structure.py`
- `tests/unit/test_jwt.py`
- `tests/unit/test_middleware.py`
- `tests/unit/test_dependencies.py`
- `tests/integration/test_auth_endpoints.py`
- `tests/integration/test_gateway.py`
- `tests/e2e/test_jwt_example.py`

## Benefits

✅ **No Ambiguity** - Examples show exact expected behavior
✅ **No Hallucination** - Tests must pass (concrete validation)
✅ **Incremental Progress** - Small, testable chunks
✅ **Clear Dependencies** - Issue graph shows what blocks what
✅ **Automated Tracking** - GitHub issues + pytest
✅ **Examples as Contracts** - Implementation matches examples

## Next Steps

1. ✅ Generated Phase 2 issues (13 total)
2. ✅ Created test stubs (7 test files, 13 tests)
3. ⏳ Implement Issue #1 (auth module structure)
4. ⏳ Implement remaining issues in dependency order
5. ⏳ Close issues as tests pass

## Example Session

```bash
# 1. View issues
gh issue list --label phase-2-jwt

# 2. Start with Issue #1
gh issue view 1

# 3. Run test
poetry run pytest tests/unit/test_auth_structure.py::test_auth_modules_exist -v
# SKIPPED (not implemented yet)

# 4. Edit test file, remove pytest.skip()

# 5. Run test again
poetry run pytest tests/unit/test_auth_structure.py::test_auth_modules_exist -v
# FAILED (no auth module)

# 6. Implement
mkdir -p src/fullon_master_api/auth
touch src/fullon_master_api/auth/{__init__.py,jwt.py,middleware.py,dependencies.py}

# 7. Run test
poetry run pytest tests/unit/test_auth_structure.py::test_auth_modules_exist -v
# PASSED ✅

# 8. Close issue
gh issue close 1 -c "✅ Test passing"

# 9. Move to next issue (#2, #5, #10, or #11 - all depend on #1)
```

---

**For more details, see:**
- [masterplan.md](masterplan.md) - Overall architecture and phases
- [README.md](README.md) - Project documentation
- [examples/](examples/) - Example code showing expected behavior
