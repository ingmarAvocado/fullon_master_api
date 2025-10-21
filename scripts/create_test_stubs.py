#!/usr/bin/env python3
"""
Create Test Stubs from Phase Manifest

Generates test files with stub tests for each issue in a phase manifest.
Tests initially fail, providing clear TDD workflow.

Usage:
    python scripts/create_test_stubs.py --phase 2
    python scripts/create_test_stubs.py --phase 2 --overwrite
"""
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
ISSUES_DIR = PROJECT_ROOT / "issues"
TESTS_DIR = PROJECT_ROOT / "tests"


def load_phase_manifest(phase: int) -> Dict[str, Any]:
    """Load phase manifest JSON file."""
    manifest_files = {
        2: "phase-2-jwt-auth.json",
        3: "phase-3-orm-routes.json",
        4: "phase-4-ohlcv-routes.json",
        5: "phase-5-cache-websocket.json",
        6: "phase-6-health-monitoring.json",
    }

    if phase not in manifest_files:
        raise ValueError(f"No manifest for phase {phase}")

    manifest_path = ISSUES_DIR / manifest_files[phase]

    with open(manifest_path, "r") as f:
        return json.load(f)


def group_tests_by_file(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """
    Group issues by test file.

    Args:
        issues: List of issue data

    Returns:
        Dict mapping test file path to list of issues
    """
    grouped = defaultdict(list)

    for issue in issues:
        test_file = issue.get("test_file")
        if test_file:
            grouped[test_file].append(issue)

    return dict(grouped)


def generate_test_stub(issue: Dict[str, Any]) -> str:
    """
    Generate test stub code for an issue.

    Args:
        issue: Issue data

    Returns:
        Python test function code
    """
    test_function = issue.get("test_function", "test_placeholder")
    description = issue.get("description", "")
    issue_number = issue.get("number", "?")
    title = issue.get("title", "")

    stub = f'''
def {test_function}():
    """
    Test for Issue #{issue_number}: {title}

    {description}

    Implementation requirements:
'''

    # Add implementation guidance as comments
    if issue.get("implementation_guidance"):
        for step in issue["implementation_guidance"]:
            stub += f"    - {step}\n"

    stub += '''
    This test should pass when the implementation is complete.
    """
    # TODO: Implement test
    pytest.skip("Test not yet implemented - Issue #''' + str(issue_number) + '''")

'''

    return stub


def create_test_file(
    test_file_path: str, issues: List[Dict[str, Any]], overwrite: bool = False
) -> bool:
    """
    Create test file with stubs for all issues.

    Args:
        test_file_path: Path to test file (e.g., "tests/unit/test_jwt.py")
        issues: List of issues for this test file
        overwrite: If True, overwrite existing file

    Returns:
        bool: True if file was created
    """
    file_path = PROJECT_ROOT / test_file_path

    # Check if exists
    if file_path.exists() and not overwrite:
        print(f"⏭️  Skipping {test_file_path} (already exists)")
        print(f"   Use --overwrite to replace")
        return False

    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate file header
    header = f'''"""
Test stubs for {file_path.name}

Auto-generated from phase manifest.
Each test corresponds to a GitHub issue.

Tests initially use pytest.skip() and should be implemented
as part of the TDD workflow.
"""
import pytest
from fullon_master_api.config import settings

# Import modules under test
# TODO: Add imports as implementation progresses

'''

    # Generate test stubs
    test_stubs = [generate_test_stub(issue) for issue in issues]

    # Write file
    content = header + "\n".join(test_stubs)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"✅ Created {test_file_path}")
    print(f"   Tests: {len(test_stubs)}")

    return True


def create_test_stubs(phase: int, overwrite: bool = False):
    """
    Create all test stub files for a phase.

    Args:
        phase: Phase number
        overwrite: If True, overwrite existing files
    """
    print(f"{'='*60}")
    print(f"Creating Test Stubs for Phase {phase}")
    print(f"{'='*60}\n")

    # Load manifest
    manifest = load_phase_manifest(phase)

    print(f"Phase: {manifest['name']}")
    print(f"Issues: {len(manifest['issues'])}")
    print(f"Overwrite: {overwrite}\n")

    # Group by test file
    test_files = group_tests_by_file(manifest["issues"])

    print(f"Test files to create: {len(test_files)}\n")

    # Create each test file
    created = 0
    skipped = 0

    for test_file_path, issues in sorted(test_files.items()):
        success = create_test_file(test_file_path, issues, overwrite=overwrite)

        if success:
            created += 1
        else:
            skipped += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    print(f"Created:  {created} test files")
    print(f"Skipped:  {skipped} (already exist)")
    print(f"Total:    {created + skipped}")
    print(f"{'='*60}\n")

    # Next steps
    print("💡 Next steps:")
    print("   1. Run tests: pytest -v")
    print("   2. All tests should be skipped initially")
    print("   3. Implement code to make each test pass")
    print("   4. Remove pytest.skip() as tests are implemented")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create test stub files from phase manifest"
    )

    parser.add_argument(
        "--phase", type=int, required=True, help="Phase number (e.g., 2)"
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing test files",
    )

    args = parser.parse_args()

    try:
        create_test_stubs(args.phase, overwrite=args.overwrite)
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
