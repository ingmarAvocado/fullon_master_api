#!/usr/bin/env python3
"""
Generate GitHub Issues from Phase Manifest

Creates granular, testable GitHub issues based on phase manifest JSON files.
Uses `gh` CLI to create issues with proper labels, dependencies, and formatting.

Usage:
    python scripts/generate_phase_issues.py --phase 2
    python scripts/generate_phase_issues.py --phase 2 --dry-run
"""
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
ISSUES_DIR = PROJECT_ROOT / "issues"


def load_phase_manifest(phase: int) -> Dict[str, Any]:
    """
    Load phase manifest JSON file.

    Args:
        phase: Phase number (e.g., 2 for Phase 2)

    Returns:
        Dict containing phase data and issues
    """
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

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r") as f:
        return json.load(f)


def format_issue_body(issue: Dict[str, Any]) -> str:
    """
    Format issue data into GitHub issue markdown body.

    Args:
        issue: Issue data from manifest

    Returns:
        Formatted markdown string
    """
    body = []

    # Description
    body.append("## Description")
    body.append(issue["description"])
    body.append("")

    # Example Reference (if exists)
    if issue.get("example_file"):
        body.append("## Example Reference")
        body.append(f"Related to: `{issue['example_file']}`")
        if issue.get("example_lines"):
            body.append(f"Lines: {issue['example_lines']}")
        body.append("")

        # Expected behavior (if exists)
        if issue.get("expected_behavior"):
            body.append("**Expected behavior:**")
            body.append("```json")
            body.append(json.dumps(issue["expected_behavior"], indent=2))
            body.append("```")
            body.append("")

        if issue.get("expected_response"):
            body.append("**Expected response:**")
            body.append("```json")
            body.append(json.dumps(issue["expected_response"], indent=2))
            body.append("```")
            body.append("")

    # Test Criteria
    body.append("## Test Criteria")
    if issue.get("test_file") and issue.get("test_function"):
        body.append(
            f"✅ Test passes: `{issue['test_file']}::{issue['test_function']}`"
        )
    body.append("")

    # Implementation Guidance
    if issue.get("implementation_guidance"):
        body.append("## Implementation Guidance")
        for i, step in enumerate(issue["implementation_guidance"], 1):
            body.append(f"{i}. {step}")
        body.append("")

    # Acceptance Criteria
    if issue.get("acceptance_criteria"):
        body.append("## Acceptance Criteria")
        for criterion in issue["acceptance_criteria"]:
            body.append(f"- [ ] {criterion}")
        body.append("")

    # Dependencies
    body.append("## Dependencies")
    if issue.get("depends_on"):
        for dep in issue["depends_on"]:
            body.append(f"- **Depends on:** #{dep}")
    else:
        body.append("None (can start immediately)")

    if issue.get("blocks"):
        for blocked in issue["blocks"]:
            body.append(f"- **Blocks:** #{blocked}")
    body.append("")

    # Labels
    body.append("## Labels")
    if issue.get("labels"):
        labels_str = ", ".join(f"`{label}`" for label in issue["labels"])
        body.append(labels_str)

    return "\n".join(body)


def create_github_issue(
    title: str, body: str, labels: List[str], dry_run: bool = False
) -> bool:
    """
    Create GitHub issue using `gh` CLI.

    Args:
        title: Issue title
        body: Issue body (markdown)
        labels: List of label names
        dry_run: If True, print instead of creating

    Returns:
        bool: True if successful
    """
    if dry_run:
        print(f"\n{'='*60}")
        print(f"TITLE: {title}")
        print(f"LABELS: {', '.join(labels)}")
        print(f"{'='*60}")
        print(body)
        print(f"{'='*60}\n")
        return True

    try:
        # Build gh command
        cmd = ["gh", "issue", "create", "--title", title, "--body", body]

        # Add labels
        for label in labels:
            cmd.extend(["--label", label])

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        print(f"✅ Created: {title}")
        print(f"   URL: {result.stdout.strip()}")

        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create issue: {title}")
        print(f"   Error: {e.stderr}")
        return False


def generate_phase_issues(phase: int, dry_run: bool = False):
    """
    Generate all issues for a phase.

    Args:
        phase: Phase number
        dry_run: If True, print issues instead of creating
    """
    print(f"{'='*60}")
    print(f"Generating Issues for Phase {phase}")
    print(f"{'='*60}\n")

    # Load manifest
    manifest = load_phase_manifest(phase)

    print(f"Phase: {manifest['name']}")
    print(f"Issues: {len(manifest['issues'])}")
    print(f"Dry run: {dry_run}\n")

    # Create issues in order
    created = 0
    failed = 0

    for issue_data in manifest["issues"]:
        title = issue_data["title"]
        body = format_issue_body(issue_data)
        labels = issue_data.get("labels", [])

        # Create issue
        success = create_github_issue(title, body, labels, dry_run=dry_run)

        if success:
            created += 1
        else:
            failed += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    print(f"Created: {created}")
    print(f"Failed:  {failed}")
    print(f"Total:   {created + failed}")

    if dry_run:
        print("\n💡 This was a dry run. Use without --dry-run to create issues.")

    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate GitHub issues from phase manifest"
    )

    parser.add_argument(
        "--phase", type=int, required=True, help="Phase number (e.g., 2)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print issues instead of creating them",
    )

    args = parser.parse_args()

    try:
        generate_phase_issues(args.phase, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
