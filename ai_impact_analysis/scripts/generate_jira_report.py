#!/usr/bin/env python3
"""
Generate Jira AI Impact Analysis Report.

This script orchestrates the complete Jira report generation workflow:
1. Load configuration
2. Generate reports for each configured phase
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


def generate_phase_report(
    phase_name: str,
    start_date: str,
    end_date: str,
    assignee: Optional[str] = None,
    limit_team_members: Optional[Path] = None
) -> bool:
    """Generate report for a single phase."""
    args = [
        sys.executable, "-m", "ai_impact_analysis.scripts.get_jira_metrics",
        "--start", start_date,
        "--end", end_date,
    ]

    if assignee:
        args.extend(["--assignee", assignee])
    elif limit_team_members and limit_team_members.exists():
        args.extend(["--limit-team-members", str(limit_team_members)])

    try:
        subprocess.run(args, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def generate_comparison_report(assignee: Optional[str] = None) -> bool:
    """Generate comparison report from phase reports."""
    args = [
        sys.executable, "-m", "ai_impact_analysis.scripts.generate_jira_comparison_report",
    ]

    if assignee:
        args.extend(["--assignee", assignee])

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
        description="Generate Jira AI Impact Analysis Report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m ai_impact_analysis.script.generate_jira_report                      # Team overall
  python3 -m ai_impact_analysis.script.generate_jira_report wlin@redhat.com     # Individual
  python3 -m ai_impact_analysis.script.generate_jira_report --all-members        # All members
  python3 -m ai_impact_analysis.script.generate_jira_report --combine-only       # Combine only
        """
    )

    parser.add_argument(
        "assignee",
        nargs="?",
        help="Assignee email to filter issues (optional)",
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
        "--no-upload",
        action="store_true",
        help="Skip uploading report to Google Sheets",
    )

    args = parser.parse_args()

    project_root = get_project_root()
    config_file = project_root / "config" / "jira_report_config.yaml"
    reports_dir = project_root / "reports" / "jira"

    # Handle --combine-only flag
    if args.combine_only:
        from ai_impact_analysis.utils.report_utils import combine_comparison_reports

        print_header("Combining Existing Jira Reports")

        try:
            output_file = combine_comparison_reports(
                reports_dir=str(reports_dir),
                report_type="jira",
                title="Jira AI Impact Analysis - Combined Report (Grouped by Metric)"
            )
            print(f"{Colors.GREEN}✓ Combined report generated: {output_file.name}{Colors.NC}")
            print()
            if not args.no_upload:
                upload_to_google_sheets(output_file)
        except Exception as e:
            print(f"{Colors.RED}Error combining reports: {e}{Colors.NC}")
            import traceback
            traceback.print_exc()
            return 1

        return 0

    # Handle --all-members flag
    if args.all_members:
        return generate_all_members_reports(
            config_file,  # Use same config file for team members
            "ai_impact_analysis.scripts.generate_jira_report"
        )

    # Load configuration
    try:
        phases, default_assignee = load_config_file(config_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"{Colors.RED}Error loading config: {e}{Colors.NC}")
        return 1

    # Determine assignee
    assignee = args.assignee or default_assignee or None

    if assignee:
        print_header("AI Impact Analysis Report Generator", f"Assignee: {assignee}")
    else:
        print_header("AI Impact Analysis Report Generator", "Team Overall Report")

    print()

    # Step 1: Cleanup old reports
    print(f"{Colors.YELLOW}Step 1: Cleaning up old files...{Colors.NC}")
    identifier = normalize_username(assignee) if assignee else "general"
    cleanup_old_reports(reports_dir, identifier, "jira")
    print()

    # Step 2-N: Generate reports for each phase
    step_num = 2
    limit_team_file = config_file if not assignee else None

    for phase_name, start_date, end_date in phases:
        print(f"{Colors.YELLOW}Step {step_num}: Generating report for '{phase_name}' ({start_date} to {end_date})...{Colors.NC}")

        success = generate_phase_report(
            phase_name,
            start_date,
            end_date,
            assignee=assignee,
            limit_team_members=limit_team_file
        )

        if success:
            print(f"{Colors.GREEN}  ✓ '{phase_name}' report generated{Colors.NC}")
        else:
            print(f"{Colors.RED}  ✗ Failed to generate '{phase_name}' report{Colors.NC}")
            return 1

        print()
        step_num += 1

    # Generate comparison report
    print(f"{Colors.YELLOW}Step {step_num}: Generating comparison report...{Colors.NC}")
    if not generate_comparison_report(assignee=assignee):
        print(f"{Colors.RED}  ✗ Failed to generate comparison report{Colors.NC}")
        return 1
    print()

    # Find and upload the latest comparison report
    comparison_file = find_latest_comparison_report(reports_dir, identifier, "jira")
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
