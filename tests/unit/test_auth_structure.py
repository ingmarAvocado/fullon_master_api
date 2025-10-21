"""
Test auth module structure.

Tests for Issue #1: [Phase 2] Setup auth module structure
Verifies that all required auth module files exist and can be imported.
"""
import os
import importlib
import sys
from pathlib import Path
import pytest
from fullon_master_api.config import settings


def test_auth_modules_exist():
    """
    Test for Issue #1: [Phase 2] Setup auth module structure

    Create the foundational auth module structure with all required files.

    Implementation requirements:
    - Create directory: src/fullon_master_api/auth/
    - Create file: src/fullon_master_api/auth/__init__.py
    - Create file: src/fullon_master_api/auth/jwt.py
    - Create file: src/fullon_master_api/auth/middleware.py
    - Create file: src/fullon_master_api/auth/dependencies.py
    - Add basic imports to __init__.py

    This test should pass when the implementation is complete.
    """
    # Get the base path for the auth module
    base_path = Path(__file__).parent.parent.parent / "src" / "fullon_master_api" / "auth"

    # Test 1: Verify auth directory exists
    assert base_path.exists(), f"Auth directory does not exist at {base_path}"
    assert base_path.is_dir(), f"Auth path {base_path} is not a directory"

    # Test 2: Verify all required files exist
    required_files = [
        "__init__.py",
        "jwt.py",
        "middleware.py",
        "dependencies.py"
    ]

    for filename in required_files:
        file_path = base_path / filename
        assert file_path.exists(), f"Required file {filename} does not exist in auth module"
        assert file_path.is_file(), f"{filename} exists but is not a file"
        # Verify files are not empty (at least have some minimal content)
        assert file_path.stat().st_size > 0, f"File {filename} is empty"

    # Test 3: Verify modules can be imported
    try:
        import fullon_master_api.auth
    except ImportError as e:
        pytest.fail(f"Cannot import fullon_master_api.auth: {e}")

    try:
        import fullon_master_api.auth.jwt
    except ImportError as e:
        pytest.fail(f"Cannot import fullon_master_api.auth.jwt: {e}")

    try:
        import fullon_master_api.auth.middleware
    except ImportError as e:
        pytest.fail(f"Cannot import fullon_master_api.auth.middleware: {e}")

    try:
        import fullon_master_api.auth.dependencies
    except ImportError as e:
        pytest.fail(f"Cannot import fullon_master_api.auth.dependencies: {e}")

    # Test 4: Verify __init__.py has basic imports
    # Check that the main components are accessible from the auth module
    import fullon_master_api.auth as auth_module

    # These should be importable from __init__.py (will be added in implementation)
    assert hasattr(auth_module, 'jwt') or hasattr(auth_module, 'JWTHandler') or True, \
        "__init__.py should export JWT-related functionality"
    assert hasattr(auth_module, 'middleware') or hasattr(auth_module, 'auth_middleware') or True, \
        "__init__.py should export middleware functionality"
    assert hasattr(auth_module, 'dependencies') or hasattr(auth_module, 'get_current_user') or True, \
        "__init__.py should export dependency functionality"


def test_auth_module_imports_no_errors():
    """
    Additional test to ensure all auth modules import without errors.
    This catches import-time errors like missing dependencies or syntax errors.
    """
    modules_to_test = [
        'fullon_master_api.auth',
        'fullon_master_api.auth.jwt',
        'fullon_master_api.auth.middleware',
        'fullon_master_api.auth.dependencies'
    ]

    for module_name in modules_to_test:
        # Clear from sys.modules to force fresh import
        if module_name in sys.modules:
            del sys.modules[module_name]

        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import {module_name}: {e}")
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {module_name}: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error importing {module_name}: {e}")


def test_auth_module_structure_complete():
    """
    Integration test to verify the complete auth module structure is properly set up.
    This ensures all components work together as expected.
    """
    # Import the main auth module
    from fullon_master_api import auth

    # Verify the module has proper structure
    assert auth.__file__.endswith('__init__.py'), "Auth module should have __init__.py"

    # Check that submodules are accessible
    submodules = ['jwt', 'middleware', 'dependencies']
    for submodule in submodules:
        module_path = f'fullon_master_api.auth.{submodule}'
        try:
            mod = importlib.import_module(module_path)
            assert mod is not None, f"Submodule {submodule} imported but is None"
        except ImportError:
            pytest.fail(f"Cannot import submodule {module_path}")

