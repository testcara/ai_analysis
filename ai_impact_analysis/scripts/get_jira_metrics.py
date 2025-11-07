#!/usr/bin/env python3
"""
CLI script to fetch and analyze Jira metrics.

This is a thin wrapper around the core business logic in
ai_impact_analysis.core.jira_metrics_calculator
"""

import argparse
import sys

from ai_impact_analysis.core.jira_metrics_calculator import JiraMetricsCalculator
from ai_impact_analysis.core.jira_report_generator import JiraReportGenerator


def main():
    """Main entry point for Jira metrics CLI."""
    parser = argparse.ArgumentParser(description="Analyze Jira issue state transitions and closure time")
    parser.add_argument(
        "--start", type=str, help="Start date (format: YYYY-MM-DD)", required=False, default=None
    )
    parser.add_argument(
        "--end", type=str, help="End date (format: YYYY-MM-DD)", required=False, default=None
    )
    parser.add_argument("--status", type=str, help="Issue status (default: Done)", default="Done")
    parser.add_argument("--project", type=str, help="Project key (overrides PROJECT_KEY in config)", default=None)
    parser.add_argument(
        "--assignee", type=str, help="Specify assignee (username or email)", default=None
    )
    parser.add_argument(
        "--limit-team-members",
        type=str,
        help="Path to team members config file. When set without --assignee, limits team report to only these members",
        default=None,
    )

    args = parser.parse_args()

    # Initialize calculator and report generator
    calculator = JiraMetricsCalculator(project_key=args.project)
    report_gen = JiraReportGenerator()

    # Build JQL query
    jql_query, team_members = calculator.build_jql_query(
        project_key=args.project,
        assignee=args.assignee,
        team_members_file=args.limit_team_members,
        start_date=args.start,
        end_date=args.end,
        status=args.status,
    )

    print(f"\nUsing JQL query: {jql_query}\n")

    # Fetch all issues
    all_issues = calculator.fetch_all_issues(jql_query)

    if not all_issues:
        print("No issues found matching the criteria.")
        # Generate empty report
        metrics = calculator._empty_metrics()
    else:
        # Calculate metrics
        metrics = calculator.calculate_metrics(all_issues)

    # Generate text report
    report_text = report_gen.generate_text_report(
        metrics,
        jql_query,
        args.project or calculator.project_key,
        assignee=args.assignee
    )

    # Print report to console
    print(report_text)

    # Save text report
    report_filename = report_gen.save_text_report(report_text, assignee=args.assignee)
    print(f"\nReport saved to: {report_filename}")

    # Generate and save JSON output (if dates are provided)
    if args.start and args.end:
        # Calculate velocity
        velocity_stats = calculator.calculate_velocity(
            args.project or calculator.project_key,
            start_date=args.start,
            end_date=args.end
        )

        print("\n--- Velocity Calculation (Based on Story Points) ---")
        print(f"Completed Stories Count: {velocity_stats['total_stories']}")
        print(f"Stories with Story Points: {velocity_stats['stories_with_points']}")
        print(f"Total Story Points: {velocity_stats['total_story_points']}")
        if velocity_stats['stories_with_points'] > 0:
            print(f"Average Points per Story: {velocity_stats['avg_points_per_story']:.2f}")

        # Generate JSON output
        json_output = report_gen.generate_json_output(
            metrics,
            jql_query,
            args.project or calculator.project_key,
            args.start,
            args.end,
            assignee=args.assignee,
            velocity_stats=velocity_stats
        )

        # Save JSON output
        json_filename = report_gen.save_json_output(
            json_output,
            args.start,
            args.end,
            assignee=args.assignee
        )
        print(f"Analysis results saved to: {json_filename}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
