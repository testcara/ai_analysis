"""
PR Report Generator

Generates text and JSON reports from PR metrics.
Extracted from cli/get_pr_metrics.py
"""

import os
import json
from datetime import datetime

from ai_impact_analysis.utils.report_utils import (
    add_metric_change,
    format_metric_changes,
)


class PRReportGenerator:
    """Generates reports from PR metrics data."""

    def generate_text_report(self, stats, prs_with_metrics, start_date, end_date,
                            repo_owner, repo_name, author=None):
        """
        Generate human-readable text report for a single period.

        Args:
            stats: Statistics dictionary
            prs_with_metrics: List of PR dictionaries
            start_date: Start date string
            end_date: End date string
            repo_owner: Repository owner
            repo_name: Repository name
            author: Optional author filter

        Returns:
            String report
        """
        lines = []
        lines.append("=" * 80)
        lines.append("GitHub PR Metrics Report")
        lines.append("=" * 80)
        lines.append(f"Period: {start_date} to {end_date}")
        lines.append(f"Repository: {repo_owner}/{repo_name}")
        if author:
            lines.append(f"Author: {author}")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        lines.append("--- PR Summary ---")
        lines.append(f"Total PRs Merged (excl. bot-authored): {stats['total_prs']}")
        lines.append(f"AI Adoption Rate: {stats['ai_adoption_rate']:.1f}%")
        lines.append(f"AI-Assisted PRs: {stats['ai_assisted_prs']}")
        lines.append(f"Non-AI PRs: {stats['non_ai_prs']}")
        lines.append("")

        if stats["ai_assisted_prs"] > 0:
            lines.append("--- AI Tool Distribution ---")
            lines.append(f"Claude PRs: {stats['claude_prs']}")
            lines.append(f"Cursor PRs: {stats['cursor_prs']}")
            if stats["both_tools_prs"] > 0:
                lines.append(f"Both Tools: {stats['both_tools_prs']}")
            lines.append("")

        # Calculate overall metrics (combining AI and non-AI PRs)
        def avg(values):
            return sum(values) / len(values) if values else 0

        merge_times = [
            pr["time_to_merge_days"]
            for pr in prs_with_metrics
            if pr.get("time_to_merge_days") is not None
        ]
        review_times = [
            pr["time_to_first_review_hours"]
            for pr in prs_with_metrics
            if pr.get("time_to_first_review_hours") is not None
        ]
        changes = [
            pr["changes_requested_count"]
            for pr in prs_with_metrics
            if pr.get("changes_requested_count") is not None
        ]
        commits = [
            pr["total_commits"] for pr in prs_with_metrics if pr.get("total_commits") is not None
        ]
        reviewers = [
            pr["reviewers_count"] for pr in prs_with_metrics if pr.get("reviewers_count") is not None
        ]
        comments = [
            pr["total_comments_count"]
            for pr in prs_with_metrics
            if pr.get("total_comments_count") is not None
        ]
        additions = [pr["additions"] for pr in prs_with_metrics if pr.get("additions") is not None]
        deletions = [pr["deletions"] for pr in prs_with_metrics if pr.get("deletions") is not None]
        files = [pr["changed_files"] for pr in prs_with_metrics if pr.get("changed_files") is not None]

        # Human-only metrics (excluding bots like CodeRabbit)
        human_reviewers = [
            pr["human_reviewers_count"]
            for pr in prs_with_metrics
            if pr.get("human_reviewers_count") is not None
        ]
        human_substantive_comments = [
            pr["human_substantive_comments_count"]
            for pr in prs_with_metrics
            if pr.get("human_substantive_comments_count") is not None
        ]

        lines.append("--- Overall Metrics ---")
        lines.append(f"Avg Time to Merge: {avg(merge_times):.2f} days")
        lines.append(f"Avg Time to First Review: {avg(review_times):.2f} hours")
        lines.append(f"Avg Changes Requested: {avg(changes):.2f}")
        lines.append(f"Avg Commits per PR: {avg(commits):.2f}")
        lines.append(f"Avg Reviewers: {avg(reviewers):.2f}")
        lines.append(f"Avg Reviewers (excl. bots): {avg(human_reviewers):.2f}")
        lines.append(f"Avg Comments: {avg(comments):.2f}")
        lines.append(f"Avg Comments (excl. bots & approvals): {avg(human_substantive_comments):.2f}")
        lines.append(f"Avg Lines Added: {avg(additions):.2f}")
        lines.append(f"Avg Lines Deleted: {avg(deletions):.2f}")
        lines.append(f"Avg Files Changed: {avg(files):.2f}")
        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_json_output(self, stats, prs_with_metrics, start_date, end_date,
                            repo_owner, repo_name, author=None):
        """
        Generate JSON output.

        Args:
            stats: Statistics dictionary
            prs_with_metrics: List of PR dictionaries
            start_date: Start date
            end_date: End date
            repo_owner: Repository owner
            repo_name: Repository name
            author: Optional author filter

        Returns:
            Dictionary suitable for JSON serialization
        """
        return {
            "analysis_date": datetime.now().isoformat(),
            "period": {"start_date": start_date, "end_date": end_date},
            "repository": {"owner": repo_owner, "name": repo_name},
            "filter": {"author": author},
            "statistics": stats,
            "prs": prs_with_metrics,
        }

    def save_json_output(self, output_data, start_date, end_date, author=None,
                        output_dir="reports/github"):
        """
        Save JSON output to file.

        Args:
            output_data: Data dictionary
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            author: Optional author
            output_dir: Output directory

        Returns:
            Output filename
        """
        os.makedirs(output_dir, exist_ok=True)

        date_range = f"{start_date}_{end_date}".replace("-", "")

        if author:
            filename = f"{output_dir}/pr_metrics_{author}_{date_range}.json"
        else:
            filename = f"{output_dir}/pr_metrics_general_{date_range}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return filename

    def save_text_report(self, report_text, start_date, end_date, author=None,
                        output_dir="reports/github"):
        """
        Save text report to file.

        Args:
            report_text: Report text content
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            author: Optional author
            output_dir: Output directory

        Returns:
            Output filename
        """
        os.makedirs(output_dir, exist_ok=True)

        date_range = f"{start_date}_{end_date}".replace("-", "")

        if author:
            filename = f"{output_dir}/pr_report_{author}_{date_range}.txt"
        else:
            filename = f"{output_dir}/pr_report_general_{date_range}.txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_text)

        return filename

    def parse_pr_report(self, filename):
        """
        Parse a PR metrics JSON file and extract key metrics.

        Args:
            filename: Path to JSON report file

        Returns:
            Dictionary with extracted metrics
        """
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        stats = data.get("statistics", {})
        period = data.get("period", {})

        # Extract overall metrics from non_ai_stats if available, otherwise from ai_stats,
        # otherwise calculate from all PRs
        overall_stats = {}
        if stats.get("non_ai_stats"):
            overall_stats = stats["non_ai_stats"]
        elif stats.get("ai_stats"):
            overall_stats = stats["ai_stats"]

        # Check if human-specific metrics exist (they were added later)
        has_human_metrics = (
            "avg_human_reviewers" in overall_stats or
            "avg_human_substantive_comments" in overall_stats
        )

        # Calculate totals from individual PRs
        all_prs = data.get("prs", [])
        total_additions = sum(pr.get("additions", 0) for pr in all_prs)
        total_deletions = sum(pr.get("deletions", 0) for pr in all_prs)
        total_files_changed = sum(pr.get("changed_files", 0) for pr in all_prs)

        return {
            "filename": filename,
            "period": period,
            "total_prs": stats.get("total_prs", 0),
            "ai_adoption_rate": stats.get("ai_adoption_rate", 0),
            "ai_assisted_prs": stats.get("ai_assisted_prs", 0),
            "non_ai_prs": stats.get("non_ai_prs", 0),
            "claude_prs": stats.get("claude_prs", 0),
            "cursor_prs": stats.get("cursor_prs", 0),
            "avg_time_to_merge_days": overall_stats.get("avg_time_to_merge_days", 0),
            "avg_time_to_first_review_hours": overall_stats.get("avg_time_to_first_review_hours", 0),
            "avg_changes_requested": overall_stats.get("avg_changes_requested", 0),
            "avg_commits": overall_stats.get("avg_commits", 0),
            "avg_reviewers": overall_stats.get("avg_reviewers", 0),
            "avg_comments": overall_stats.get("avg_comments", 0),
            "avg_additions": overall_stats.get("avg_additions", 0),
            "avg_deletions": overall_stats.get("avg_deletions", 0),
            "avg_files_changed": overall_stats.get("avg_files_changed", 0),
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "total_files_changed": total_files_changed,
            "avg_human_reviewers": overall_stats.get("avg_human_reviewers", 0),
            "avg_human_substantive_comments": overall_stats.get("avg_human_substantive_comments", 0),
            "has_human_metrics": has_human_metrics,
        }

    def generate_comparison_tsv(self, reports, phase_names, author=None):
        """
        Generate TSV comparison report from multiple phase reports.

        Args:
            reports: List of parsed report dictionaries
            phase_names: List of phase names
            author: Optional author

        Returns:
            TSV format string
        """
        lines = []

        # Header
        if author:
            lines.append(f"PR AI Impact Analysis Report - {author}")
        else:
            lines.append("PR AI Impact Analysis Report - Team Overall")
        lines.append(f"Report Generated: {datetime.now().strftime('%B %d, %Y')}")
        lines.append("Repository: konflux-ci/konflux-ui")
        lines.append("")

        # Add description for multi-phase analysis
        if len(reports) >= 2:
            lines.append("This report analyzes PR data across multiple periods to evaluate")
            lines.append("the impact of AI tools on development efficiency:")
            lines.append("")

        # Phase info with date ranges
        for i, (name, report) in enumerate(zip(phase_names, reports), 1):
            period = report.get("period", {})
            start_date = period.get("start_date", "N/A")
            end_date = period.get("end_date", "N/A")
            lines.append(f"Phase {i}: {name} ({start_date} to {end_date})")
        lines.append("")

        # Metrics table header
        header = "Metric\t" + "\t".join(phase_names)
        lines.append(header)

        # Total PRs
        total_prs = [str(r["total_prs"]) for r in reports]
        lines.append("Total PRs Merged (excl. bot-authored)\t" + "\t".join(total_prs))

        # AI Adoption Rate
        ai_rates = [f"{r['ai_adoption_rate']:.1f}%" for r in reports]
        lines.append("AI Adoption Rate\t" + "\t".join(ai_rates))

        # AI Assisted PRs
        ai_prs = [str(r["ai_assisted_prs"]) for r in reports]
        lines.append("AI-Assisted PRs\t" + "\t".join(ai_prs))

        # Non-AI PRs
        non_ai_prs = [str(r["non_ai_prs"]) for r in reports]
        lines.append("Non-AI PRs\t" + "\t".join(non_ai_prs))

        # AI Tool breakdown
        claude_prs = [str(r.get("claude_prs", 0)) for r in reports]
        lines.append("Claude PRs\t" + "\t".join(claude_prs))

        cursor_prs = [str(r.get("cursor_prs", 0)) for r in reports]
        lines.append("Cursor PRs\t" + "\t".join(cursor_prs))

        # Time to Merge
        merge_times = [f"{r['avg_time_to_merge_days']:.2f}d" for r in reports]
        lines.append("Avg Time to Merge per PR (days)\t" + "\t".join(merge_times))

        # Time to First Review
        review_times = [f"{r['avg_time_to_first_review_hours']:.2f}h" for r in reports]
        lines.append("Avg Time to First Review per PR (hours)\t" + "\t".join(review_times))

        # Changes Requested
        changes = [f"{r['avg_changes_requested']:.2f}" for r in reports]
        lines.append("Avg Changes Requested per PR\t" + "\t".join(changes))

        # Commits
        commits = [f"{r['avg_commits']:.2f}" for r in reports]
        lines.append("Avg Commits per PR\t" + "\t".join(commits))

        # Reviewers
        reviewers = [f"{r['avg_reviewers']:.2f}" for r in reports]
        lines.append("Avg Reviewers per PR\t" + "\t".join(reviewers))

        # Human Reviewers (excluding bots) - only show if all reports have this data
        if all(r.get("has_human_metrics", False) for r in reports):
            human_reviewers = [f"{r['avg_human_reviewers']:.2f}" for r in reports]
            lines.append("Avg Reviewers per PR (excl. bots)\t" + "\t".join(human_reviewers))

        # Comments
        comments = [f"{r['avg_comments']:.2f}" for r in reports]
        lines.append("Avg Comments per PR\t" + "\t".join(comments))

        # Human Substantive Comments - only show if all reports have this data
        if all(r.get("has_human_metrics", False) for r in reports):
            human_comments = [f"{r['avg_human_substantive_comments']:.2f}" for r in reports]
            lines.append("Avg Comments per PR (excl. bots & approvals)\t" + "\t".join(human_comments))

        # Code Changes - Average per PR
        additions = [f"{r['avg_additions']:.0f}" for r in reports]
        lines.append("Avg Lines Added per PR\t" + "\t".join(additions))

        deletions = [f"{r['avg_deletions']:.0f}" for r in reports]
        lines.append("Avg Lines Deleted per PR\t" + "\t".join(deletions))

        files = [f"{r['avg_files_changed']:.2f}" for r in reports]
        lines.append("Avg Files Changed per PR\t" + "\t".join(files))

        # Code Changes - Totals
        total_additions = [str(r.get('total_additions', 0)) for r in reports]
        lines.append("Total Lines Added\t" + "\t".join(total_additions))

        total_deletions = [str(r.get('total_deletions', 0)) for r in reports]
        lines.append("Total Lines Deleted\t" + "\t".join(total_deletions))

        total_files = [str(r.get('total_files_changed', 0)) for r in reports]
        lines.append("Total Files Changed\t" + "\t".join(total_files))

        lines.append("")
        lines.append("Note: N/A values indicate insufficient data for that metric in the period.")

        # Calculate metric changes (first phase vs last phase) - only if we have 2+ reports
        if len(reports) >= 2:
            lines.append("")
            lines.append("Key Changes:")

            first_report = reports[0]
            last_report = reports[-1]

            # Collect all metric changes using shared utility functions
            metric_changes = []

            # Time to merge
            add_metric_change(metric_changes, "Avg Time to Merge per PR",
                            first_report["avg_time_to_merge_days"],
                            last_report["avg_time_to_merge_days"], "d")

            # Time to first review
            add_metric_change(metric_changes, "Avg Time to First Review per PR",
                            first_report["avg_time_to_first_review_hours"],
                            last_report["avg_time_to_first_review_hours"], "h")

            # Changes requested
            add_metric_change(metric_changes, "Avg Changes Requested per PR",
                            first_report["avg_changes_requested"],
                            last_report["avg_changes_requested"], "")

            # Commits
            add_metric_change(metric_changes, "Avg Commits per PR",
                            first_report["avg_commits"],
                            last_report["avg_commits"], "")

            # Reviewers
            add_metric_change(metric_changes, "Avg Reviewers per PR",
                            first_report["avg_reviewers"],
                            last_report["avg_reviewers"], "")

            # Comments
            add_metric_change(metric_changes, "Avg Comments per PR",
                            first_report["avg_comments"],
                            last_report["avg_comments"], "")

            # Code changes
            add_metric_change(metric_changes, "Avg Lines Added per PR",
                            first_report["avg_additions"],
                            last_report["avg_additions"], "")

            add_metric_change(metric_changes, "Avg Lines Deleted per PR",
                            first_report["avg_deletions"],
                            last_report["avg_deletions"], "")

            add_metric_change(metric_changes, "Avg Files Changed per PR",
                            first_report["avg_files_changed"],
                            last_report["avg_files_changed"], "")

            # AI Adoption Rate (special case - absolute change if starting from 0)
            first_ai_rate = first_report["ai_adoption_rate"]
            last_ai_rate = last_report["ai_adoption_rate"]
            if first_ai_rate == 0 and last_ai_rate > 0:
                add_metric_change(metric_changes, "AI Adoption Rate",
                                first_ai_rate, last_ai_rate, "%", is_absolute=True)
            elif first_ai_rate > 0:
                add_metric_change(metric_changes, "AI Adoption Rate",
                                first_ai_rate, last_ai_rate, "%")

            # Format and append the top changes using shared utility
            formatted_changes = format_metric_changes(metric_changes, top_n=5)
            lines.extend(formatted_changes)

        lines.append("")
        lines.append("For detailed metric explanations, see:")
        lines.append("https://github.com/testcara/ai_impact_analysis#pr-report-metrics")

        return "\n".join(lines)
