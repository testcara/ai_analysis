"""
Workflow utilities for report generation scripts.

This module contains shared functions used by Jira and GitHub report generation workflows.
"""

import os
import sys
import glob
import subprocess
import yaml
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from ai_impact_analysis.utils.logger import Colors


def get_project_root() -> Path:
    """
    Get the project root directory by searching for marker files.

    Searches upward from current file for .git directory or other markers.
    """
    current = Path(__file__).resolve()

    # Search upward for project markers
    for parent in [current, *current.parents]:
        # Check for common project root markers
        if any(
            [
                (parent / ".git").exists(),
                (parent / "pyproject.toml").exists(),
                (parent / "setup.py").exists(),
                (parent / "requirements.txt").exists() and (parent / "ai_impact_analysis").is_dir(),
            ]
        ):
            return parent

    # Fallback: assume current working directory
    return Path.cwd()


def merge_configs(default_config: Dict[str, Any], custom_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge custom configuration with default configuration.

    Custom config values override defaults. Missing values in custom config
    are taken from default config.

    Args:
        default_config: Default configuration dict
        custom_config: Custom configuration dict (overrides defaults)

    Returns:
        Merged configuration dict
    """
    merged = default_config.copy()

    # Override with custom values
    for key, value in custom_config.items():
        if value is not None:  # Only override if value is provided
            merged[key] = value

    return merged


def load_config_file(
    config_path: Path, custom_config_path: Optional[Path] = None
) -> Tuple[List[Tuple[str, str, str]], str]:
    """
    Load phase configuration from a YAML config file with optional custom config override.

    Args:
        config_path: Path to default YAML configuration file
        custom_config_path: Optional path to custom YAML config that overrides defaults

    Returns:
        Tuple of (phases list, default assignee/author)
        phases: List of (phase_name, start_date, end_date) tuples

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config format is invalid
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML format in {config_path}: {e}")

    if not config:
        raise ValueError(f"Empty config file: {config_path}")

    # Merge with custom config if provided
    if custom_config_path and custom_config_path.exists():
        try:
            with open(custom_config_path, "r") as f:
                custom_config = yaml.safe_load(f)
            if custom_config:
                config = merge_configs(config, custom_config)
                print(f"[INFO] Merged custom config from: {custom_config_path}")
        except yaml.YAMLError as e:
            print(f"[WARNING] Invalid YAML format in custom config {custom_config_path}: {e}")

    # Extract phases
    phases = []
    if "phases" in config and config["phases"]:
        for phase in config["phases"]:
            name = phase.get("name", "")
            start = phase.get("start", "")
            end = phase.get("end", "")
            if name and start and end:
                phases.append((name, start, end))

    if not phases:
        raise ValueError(f"No valid phases found in {config_path}")

    # Extract default assignee/author
    default_assignee = config.get("default_assignee", "")

    return phases, default_assignee


def load_team_members_from_yaml(config_path: Path, detailed: bool = False):
    """
    Load team members from YAML config file.

    Supports both formats:
    - team_members with 'email' field (for Jira)
    - team_members with 'name' field (for GitHub)

    Args:
        config_path: Path to YAML configuration file
        detailed: If True, return dict with full details (leave_days, capacity)
                  If False, return list of identifiers only

    Returns:
        If detailed=False: List of team member identifiers (emails or usernames)
        If detailed=True: Dict mapping identifier to member details:
            {
                'wlin@redhat.com': {
                    'member': 'wlin',
                    'email': 'wlin@redhat.com',
                    'leave_days': [...],
                    'capacity': 0.8
                },
                ...
            }

    Raises:
        FileNotFoundError: If config file doesn't exist
    """
    if not config_path.exists():
        return {} if detailed else []

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError:
        return {} if detailed else []

    if not config or "team_members" not in config:
        return {} if detailed else []

    if detailed:
        # Return detailed information
        members_details = {}
        for member in config["team_members"]:
            if isinstance(member, dict):
                identifier = member.get("email") or member.get("name")
                if identifier:
                    members_details[identifier] = {
                        "member": member.get("member", identifier),
                        "email": member.get("email"),
                        "name": member.get("name"),
                        "leave_days": member.get("leave_days") or [],
                        "capacity": member.get("capacity", 1.0),
                    }
        return members_details
    else:
        # Return simple list (backward compatible)
        members = []
        for member in config["team_members"]:
            if isinstance(member, dict):
                # Support both 'email' (Jira) and 'name' (GitHub)
                if "email" in member:
                    members.append(member["email"])
                elif "name" in member:
                    members.append(member["name"])
            elif isinstance(member, str):
                members.append(member)
        return members


def cleanup_old_reports(reports_dir: Path, identifier: str, report_type: str) -> None:
    """
    Clean up old report files for a given identifier.

    Args:
        reports_dir: Directory containing reports
        identifier: User identifier or "general"
        report_type: "jira" or "pr"
    """
    reports_dir.mkdir(parents=True, exist_ok=True)

    if report_type == "pr":
        patterns = [
            f"pr_metrics_{identifier}_*.json",
            f"pr_report_{identifier}_*.txt",
            f"pr_comparison_{identifier}_*.tsv",
        ]
    elif report_type == "jira":
        patterns = [
            f"jira_metrics_{identifier}_*.json",
            f"jira_report_{identifier}_*.txt",
            f"jira_comparison_{identifier}_*.tsv",
        ]
    else:
        raise ValueError(f"Unknown report type: {report_type}")

    removed_count = 0
    for pattern in patterns:
        for file_path in reports_dir.glob(pattern):
            file_path.unlink()
            removed_count += 1

    print(f"{Colors.GREEN}  ✓ Removed {removed_count} old report files for {identifier}{Colors.NC}")


def upload_to_google_sheets(report_file: Optional[Path]) -> None:
    """
    Upload report to Google Sheets if configured.

    Args:
        report_file: Path to report file to upload
    """
    if not report_file or not report_file.exists():
        return

    credentials = os.getenv("GOOGLE_CREDENTIALS_FILE")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")

    if credentials and spreadsheet_id:
        print(f"{Colors.YELLOW}Uploading to Google Sheets...{Colors.NC}")
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ai_impact_analysis.scripts.upload_to_sheets",
                    "--report",
                    str(report_file),
                ],
                check=True,
            )
            print()
        except subprocess.CalledProcessError:
            print(f"{Colors.RED}Error: Google Sheets upload failed{Colors.NC}")
    else:
        print(f"{Colors.BLUE}Google Sheets upload not configured (optional){Colors.NC}")
        print("You can open this file in Google Sheets manually, or configure automatic upload:")
        print("  export GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json")
        print("  export GOOGLE_SPREADSHEET_ID=your_spreadsheet_id")
        print()
        print("Or upload manually:")
        print(f"  python3 -m ai_impact_analysis.scripts.upload_to_sheets --report {report_file}")
        print()


def find_latest_comparison_report(
    reports_dir: Path, identifier: str, report_type: str
) -> Optional[Path]:
    """
    Find the most recent comparison report.

    Args:
        reports_dir: Directory containing reports
        identifier: User identifier or "general"
        report_type: "jira" or "pr"

    Returns:
        Path to latest report or None
    """
    if report_type == "jira":
        pattern = f"jira_comparison_{identifier}_*.tsv"
    elif report_type == "pr":
        pattern = f"pr_comparison_{identifier}_*.tsv"
    else:
        return None

    files = list(reports_dir.glob(pattern))
    if not files:
        return None

    # Sort by modification time, newest first
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def load_team_members(team_members_file: Path) -> List[str]:
    """
    Load team members from YAML configuration file.

    Args:
        team_members_file: Path to YAML team members config

    Returns:
        List of team member emails
    """
    return load_team_members_from_yaml(team_members_file)


def resolve_member_identifier(
    identifier: str, config_path: Path
) -> Tuple[Optional[str], Optional[Dict]]:
    """
    Resolve member identifier to email and details.

    Supports both short format (e.g., "wlin") and email format (e.g., "wlin@redhat.com").
    If short format is provided, looks up the member in team_members config.

    Args:
        identifier: Member identifier (short name or email)
        config_path: Path to YAML configuration file

    Returns:
        Tuple of (email, member_details) or (None, None) if not found
    """
    if not identifier:
        return None, None

    # Load all team members with details
    members_details = load_team_members_from_yaml(config_path, detailed=True)

    # Check if identifier is already an email in our config
    if identifier in members_details:
        return identifier, members_details[identifier]

    # Otherwise, try to find by short member name
    for email, details in members_details.items():
        member_name = details.get("member", "")
        if member_name == identifier:
            return email, details

    # Not found, return identifier as-is (for backward compatibility)
    return identifier, None


def run_report_for_member(
    script_path: Path, member: str, report_type: str, extra_args: Optional[List[str]] = None
) -> bool:
    """
    Run report generation for a single team member.

    Args:
        script_path: Path to this script (for recursive calls)
        member: Team member identifier
        report_type: "jira" or "pr"
        extra_args: Additional arguments to pass

    Returns:
        True if successful, False otherwise
    """
    args = [sys.executable, "-m"]

    if report_type == "jira":
        args.extend(["ai_impact_analysis.cli.generate_jira_report", member])
    elif report_type == "pr":
        args.extend(["ai_impact_analysis.cli.generate_pr_report", member])
    else:
        return False

    if extra_args:
        args.extend(extra_args)

    try:
        subprocess.run(args, check=True)
        return True
    except subprocess.CalledProcessError:
        print(f"{Colors.RED}  ✗ Failed to generate report for {member}{Colors.NC}")
        return False
