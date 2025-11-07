#!/usr/bin/env python3
"""
Generate GitHub PR AI Impact Analysis Report.

This script orchestrates the complete GitHub PR report generation workflow:
1. Load configuration
2. Generate PR metrics for each configured phase
3. Create comparison report
4. Optionally upload to Google Sheets
"""

import sys
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional

from ai_impact_analysis.utils.workflow_utils import (
    Colors,
    get_project_root,
    load_config_file,
    cleanup_old_reports,
    upload_to_google_sheets,
    find_latest_comparison_report,
    load_team_members,
)
from ai_impact_analysis.utils.report_utils import normalize_username


def print_header(title: str, subtitle: Optional[str] = None) -> None:
    """Print formatted header."""
    print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}")
    print(f"{Colors.BLUE}{title}{Colors.NC}")
    if subtitle:
        print(f"{Colors.BLUE}{subtitle}{Colors.NC}")
    print(f"{Colors.BLUE}{'=' * 40}{Colors.NC}")
    print()


def generate_phase_metrics(
    phase_name: str,
    start_date: str,
    end_date: str,
    author: Optional[str] = None,
    incremental: bool = False
) -> bool:
    """Generate PR metrics for a single phase."""
    args = [
        sys.executable, "-m", "ai_impact_analysis.scripts.get_pr_metrics",
        "--start", start_date,
        "--end", end_date,
    ]

    if author:
        args.extend(["--author", author])

    if incremental:
        args.append("--incremental")

    try:
        subprocess.run(args, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def generate_comparison_report(author: Optional[str] = None) -> bool:
    """Generate comparison report from phase metrics."""
    args = [
        sys.executable, "-m", "ai_impact_analysis.scripts.generate_pr_comparison_report",
    ]

    if author:
        args.extend(["--author", author])

    try:
        subprocess.run(args, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def generate_all_members_reports(team_members_file: Path, script_name: str) -> int:
    """Generate reports for all team members."""
    print_header("Generating reports for all team members")

    members = load_team_members(team_members_file)
    if not members:
        print(f"{Colors.RED}Error: No team members found in {team_members_file}{Colors.NC}")
        return 1

    # Generate team overall report first
    print(f"{Colors.BLUE}>>> Generating Team Overall Report{Colors.NC}")
    print()
    result = subprocess.run([sys.executable, "-m", script_name])
    if result.returncode != 0:
        print(f"{Colors.RED}  ✗ Failed to generate team report{Colors.NC}")
        return 1
    print()
    print()

    # Generate individual reports for each member
    failed_members = []
    for member in members:
        print(f"{Colors.BLUE}>>> Generating Report for: {member}{Colors.NC}")
        print()
        result = subprocess.run([sys.executable, "-m", script_name, member])
        if result.returncode != 0:
            failed_members.append(member)
        print()
        print()

    # Summary
    print(f"{Colors.GREEN}{'=' * 40}{Colors.NC}")
    if failed_members:
        print(f"{Colors.YELLOW}⚠ All team member reports completed with {len(failed_members)} failures{Colors.NC}")
        print(f"{Colors.YELLOW}Failed: {', '.join(failed_members)}{Colors.NC}")
    else:
        print(f"{Colors.GREEN}✓ All team member reports completed successfully!{Colors.NC}")
    print(f"{Colors.GREEN}{'=' * 40}{Colors.NC}")
    print()

    print(f"{Colors.BLUE}To combine all reports into a single TSV, run:{Colors.NC}")
    print(f"{Colors.BLUE}  python3 -m {script_name} --combine-only{Colors.NC}")
    print()

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate GitHub PR AI Impact Analysis Report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m ai_impact_analysis.script.generate_pr_report                    # Team overall
  python3 -m ai_impact_analysis.script.generate_pr_report wlin              # Individual
  python3 -m ai_impact_analysis.script.generate_pr_report --all-members      # All members
  python3 -m ai_impact_analysis.script.generate_pr_report --combine-only     # Combine only
  python3 -m ai_impact_analysis.script.generate_pr_report --incremental      # Incremental mode
        """
    )

    parser.add_argument(
        "author",
        nargs="?",
        help="GitHub author username to filter PRs (optional)",
    )
    parser.add_argument(
        "--all-members",
        action="store_true",
        help="Generate reports for all team members from config",
    )
    parser.add_argument(
        "--combine-only",
        action="store_true",
        help="Combine existing TSV reports without regenerating",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only fetch new/updated PRs (faster for repeated runs)",
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip uploading report to Google Sheets",
    )

    args = parser.parse_args()

    project_root = get_project_root()
    config_file = project_root / "config" / "pr_report_config.yaml"
    reports_dir = project_root / "reports" / "github"

    # Handle --combine-only flag
    if args.combine_only:
        print_header("Combining Existing GitHub PR Reports")
        print(f"{Colors.YELLOW}Note: The combine feature requires the bash implementation.{Colors.NC}")
        print(f"{Colors.YELLOW}For now, please use: bash bin/generate_pr_report.sh --combine-only{Colors.NC}")
        print()
        return 0

    # Handle --all-members flag
    if args.all_members:
        return generate_all_members_reports(
            config_file,  # Use same config file for team members
            "ai_impact_analysis.scripts.generate_pr_report"
        )

    # Load configuration
    try:
        phases, default_author = load_config_file(config_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"{Colors.RED}Error loading config: {e}{Colors.NC}")
        return 1

    # Determine author
    author = args.author or default_author or None

    if author:
        print_header("GitHub PR Analysis Report Generator", f"Author: {author}")
    else:
        print_header("GitHub PR Analysis Report Generator", "Team Overall Report")

    print()

    # Step 1: Cleanup old reports
    print(f"{Colors.YELLOW}Step 1: Cleaning up old files...{Colors.NC}")
    identifier = normalize_username(author) if author else "general"
    cleanup_old_reports(reports_dir, identifier, "pr")
    print()

    # Step 2-N: Generate metrics for each phase
    step_num = 2

    for phase_name, start_date, end_date in phases:
        print(f"{Colors.YELLOW}Step {step_num}: Collecting PR metrics for '{phase_name}' ({start_date} to {end_date})...{Colors.NC}")

        success = generate_phase_metrics(
            phase_name,
            start_date,
            end_date,
            author=author,
            incremental=args.incremental
        )

        if success:
            print(f"{Colors.GREEN}  ✓ '{phase_name}' metrics collected{Colors.NC}")
        else:
            print(f"{Colors.RED}  ✗ Failed to collect '{phase_name}' metrics{Colors.NC}")
            return 1

        print()
        step_num += 1

    # Generate comparison report
    print(f"{Colors.YELLOW}Step {step_num}: Generating comparison report...{Colors.NC}")
    if not generate_comparison_report(author=author):
        print(f"{Colors.RED}  ✗ Failed to generate comparison report{Colors.NC}")
        return 1
    print()

    # Find and upload the latest comparison report
    comparison_file = find_latest_comparison_report(reports_dir, identifier, "pr")
    if comparison_file:
        print(f"{Colors.GREEN}✓ Report generated: {comparison_file.name}{Colors.NC}")
        print()
        if not args.no_upload:
            upload_to_google_sheets(comparison_file)
        else:
            print(f"{Colors.YELLOW}Skipping upload to Google Sheets (--no-upload specified){Colors.NC}")
            print()

    print(f"{Colors.GREEN}Done!{Colors.NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
