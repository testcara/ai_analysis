"""
Report generation orchestration.

This module contains the core business logic for orchestrating
multi-phase report generation workflows.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from ai_impact_analysis.models import Phase, AnalysisConfig
from ai_impact_analysis.utils import (
    Colors,
    cleanup_old_reports,
    find_latest_comparison_report,
    normalize_username,
)


class ReportOrchestrator:
    """Orchestrates the report generation workflow."""

    def __init__(self, config: AnalysisConfig, reports_dir: Path):
        """
        Initialize orchestrator.

        Args:
            config: Analysis configuration
            reports_dir: Directory to store reports
        """
        self.config = config
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_old_reports(self, identifier: str) -> None:
        """Clean up old reports for the given identifier."""
        cleanup_old_reports(self.reports_dir, identifier, self.config.report_type)

    def generate_phase_report(
        self,
        phase: Phase,
        assignee: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Generate report for a single phase.

        Args:
            phase: Phase configuration
            assignee: Optional assignee/author filter
            **kwargs: Additional arguments passed to the generator

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement generate_phase_report")

    def generate_comparison_report(self, assignee: Optional[str] = None) -> bool:
        """
        Generate comparison report from phase reports.

        Args:
            assignee: Optional assignee/author filter

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement generate_comparison_report")

    def run_workflow(
        self,
        assignee: Optional[str] = None,
        **kwargs
    ) -> Optional[Path]:
        """
        Run the complete report generation workflow.

        Args:
            assignee: Optional assignee/author filter
            **kwargs: Additional arguments passed to generators

        Returns:
            Path to generated comparison report, or None if failed
        """
        identifier = normalize_username(assignee) if assignee else "general"

        # Step 1: Cleanup
        print(f"{Colors.YELLOW}Step 1: Cleaning up old files...{Colors.NC}")
        self.cleanup_old_reports(identifier)
        print()

        # Step 2-N: Generate phase reports
        step_num = 2
        for phase in self.config.phases:
            print(
                f"{Colors.YELLOW}Step {step_num}: Generating report for "
                f"'{phase.name}' ({phase.start_date} to {phase.end_date})...{Colors.NC}"
            )

            success = self.generate_phase_report(phase, assignee=assignee, **kwargs)

            if success:
                print(f"{Colors.GREEN}  ✓ '{phase.name}' report generated{Colors.NC}")
            else:
                print(f"{Colors.RED}  ✗ Failed to generate '{phase.name}' report{Colors.NC}")
                return None

            print()
            step_num += 1

        # Final step: Generate comparison
        print(f"{Colors.YELLOW}Step {step_num}: Generating comparison report...{Colors.NC}")
        if not self.generate_comparison_report(assignee=assignee):
            print(f"{Colors.RED}  ✗ Failed to generate comparison report{Colors.NC}")
            return None
        print()

        # Find the generated report
        comparison_file = find_latest_comparison_report(
            self.reports_dir,
            identifier,
            self.config.report_type
        )

        if comparison_file:
            print(f"{Colors.GREEN}✓ Report generated: {comparison_file.name}{Colors.NC}")
            print()

        return comparison_file


class JiraReportOrchestrator(ReportOrchestrator):
    """Orchestrator for Jira report generation."""

    def __init__(self, config: AnalysisConfig, reports_dir: Path, limit_team_members: Optional[Path] = None):
        """
        Initialize Jira orchestrator.

        Args:
            config: Analysis configuration
            reports_dir: Directory to store reports
            limit_team_members: Optional path to team members config file
        """
        super().__init__(config, reports_dir)
        self.limit_team_members = limit_team_members

    def generate_phase_report(
        self,
        phase: Phase,
        assignee: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Generate Jira report for a single phase."""
        args = [
            sys.executable, "-m", "ai_impact_analysis.cli.get_jira_metrics",
            "--start", phase.start_date,
            "--end", phase.end_date,
        ]

        if assignee:
            args.extend(["--assignee", assignee])
        elif self.limit_team_members and self.limit_team_members.exists():
            args.extend(["--limit-team-members", str(self.limit_team_members)])

        try:
            subprocess.run(args, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def generate_comparison_report(self, assignee: Optional[str] = None) -> bool:
        """Generate Jira comparison report."""
        args = [
            sys.executable, "-m", "ai_impact_analysis.cli.generate_jira_comparison_report",
        ]

        if assignee:
            args.extend(["--assignee", assignee])

        try:
            subprocess.run(args, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


class GitHubReportOrchestrator(ReportOrchestrator):
    """Orchestrator for GitHub PR report generation."""

    def generate_phase_report(
        self,
        phase: Phase,
        assignee: Optional[str] = None,
        incremental: bool = False,
        **kwargs
    ) -> bool:
        """Generate GitHub PR metrics for a single phase."""
        args = [
            sys.executable, "-m", "ai_impact_analysis.cli.get_pr_metrics",
            "--start", phase.start_date,
            "--end", phase.end_date,
        ]

        if assignee:
            args.extend(["--author", assignee])

        if incremental:
            args.append("--incremental")

        try:
            subprocess.run(args, check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def generate_comparison_report(self, assignee: Optional[str] = None) -> bool:
        """Generate GitHub PR comparison report."""
        args = [
            sys.executable, "-m", "ai_impact_analysis.cli.generate_pr_comparison_report",
        ]

        if assignee:
            args.extend(["--author", assignee])

        try:
            subprocess.run(args, check=True)
            return True
        except subprocess.CalledProcessError:
            return False
