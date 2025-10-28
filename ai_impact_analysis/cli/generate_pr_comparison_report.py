#!/usr/bin/env python3
"""
Generate PR Comparison Report across multiple time periods.

This script compares GitHub PR metrics across different phases to show AI impact over time.

Usage:
    # Team comparison (uses last 3 reports in reports/github/ directory)
    python3 bin/generate_pr_comparison_report.py

    # Individual comparison
    python3 bin/generate_pr_comparison_report.py --author wlin
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime


def parse_phase_config(config_path="config/github_phases.conf"):
    """
    Parse phase configuration file to extract phase names and date ranges.

    Args:
        config_path: Path to config file

    Returns:
        List of tuples: [(phase_name, start_date, end_date), ...]
    """
    phases = []

    if not os.path.exists(config_path):
        return phases

    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find the GITHUB_PHASES array (skip commented lines)
    in_array = False
    array_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("#"):
            continue

        # Start of array
        if "GITHUB_PHASES=(" in line and not stripped.startswith("#"):
            in_array = True
            # Get content after GITHUB_PHASES=(
            array_start = line.split("GITHUB_PHASES=(", 1)[1]
            array_lines.append(array_start)
            # Check if array closes on same line
            if ")" in array_start:
                break
            continue

        # Inside array
        if in_array:
            array_lines.append(line)
            if ")" in line:
                break

    # Join all array lines and extract phase entries
    array_content = "".join(array_lines)

    # Extract phase entries (quoted strings)
    phase_pattern = r'"([^"]+)"'
    phase_entries = re.findall(phase_pattern, array_content)

    for entry in phase_entries:
        # Parse format: "Phase Name|Start Date|End Date"
        parts = entry.split("|")
        if len(parts) == 3:
            phase_name = parts[0].strip()
            start_date = parts[1].strip()
            end_date = parts[2].strip()
            phases.append((phase_name, start_date, end_date))

    return phases


def get_phase_name_for_report(report, phase_config):
    """
    Match a report to its phase name from config based on dates.

    Args:
        report: Report dictionary with start_date and end_date
        phase_config: List of phase tuples from parse_phase_config()

    Returns:
        Phase name string or None if no match
    """
    report_start = report["start_date"]
    report_end = report["end_date"]

    for phase_name, config_start, config_end in phase_config:
        # Match if report dates align with config dates
        if report_start == config_start and report_end == config_end:
            return phase_name

    # If no exact match, return None (will use fallback naming)
    return None


def calculate_overall_metrics(prs):
    """
    Calculate overall metrics from all PRs (combining AI and non-AI).

    Args:
        prs: List of PR dictionaries

    Returns:
        Dictionary with calculated metrics
    """
    if not prs:
        return {}

    # Filter out None values for each metric
    merge_times = [
        pr["time_to_merge_days"] for pr in prs if pr.get("time_to_merge_days") is not None
    ]
    review_times = [
        pr["time_to_first_review_hours"]
        for pr in prs
        if pr.get("time_to_first_review_hours") is not None
    ]
    changes = [
        pr["changes_requested_count"] for pr in prs if pr.get("changes_requested_count") is not None
    ]
    commits = [pr["total_commits"] for pr in prs if pr.get("total_commits") is not None]
    reviewers = [pr["reviewers_count"] for pr in prs if pr.get("reviewers_count") is not None]
    comments = [
        pr["total_comments_count"] for pr in prs if pr.get("total_comments_count") is not None
    ]
    additions = [pr["additions"] for pr in prs if pr.get("additions") is not None]
    deletions = [pr["deletions"] for pr in prs if pr.get("deletions") is not None]
    files = [pr["changed_files"] for pr in prs if pr.get("changed_files") is not None]

    # Human-only metrics (excluding bots like CodeRabbit)
    human_reviewers = [
        pr["human_reviewers_count"] for pr in prs if pr.get("human_reviewers_count") is not None
    ]
    human_comments = [
        pr["human_total_comments_count"]
        for pr in prs
        if pr.get("human_total_comments_count") is not None
    ]

    # Substantive comments (excluding approval-only comments and bots)
    human_substantive_comments = [
        pr["human_substantive_comments_count"]
        for pr in prs
        if pr.get("human_substantive_comments_count") is not None
    ]

    return {
        "avg_time_to_merge_days": sum(merge_times) / len(merge_times) if merge_times else 0,
        "avg_time_to_first_review_hours": (
            sum(review_times) / len(review_times) if review_times else 0
        ),
        "avg_changes_requested": sum(changes) / len(changes) if changes else 0,
        "avg_commits": sum(commits) / len(commits) if commits else 0,
        "avg_reviewers": sum(reviewers) / len(reviewers) if reviewers else 0,
        "avg_comments": sum(comments) / len(comments) if comments else 0,
        "avg_additions": sum(additions) / len(additions) if additions else 0,
        "avg_deletions": sum(deletions) / len(deletions) if deletions else 0,
        "avg_files_changed": sum(files) / len(files) if files else 0,
        # Human-only metrics
        "avg_human_reviewers": (
            sum(human_reviewers) / len(human_reviewers) if human_reviewers else 0
        ),
        "avg_human_comments": sum(human_comments) / len(human_comments) if human_comments else 0,
        "avg_human_substantive_comments": (
            sum(human_substantive_comments) / len(human_substantive_comments)
            if human_substantive_comments
            else 0
        ),
    }


def parse_pr_report(filename):
    """
    Parse a PR metrics JSON file and extract key statistics.

    Args:
        filename: Path to JSON file

    Returns:
        Dictionary with extracted metrics
    """
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = data.get("statistics", {})
    period = data.get("period", {})
    prs = data.get("prs", [])

    # Calculate overall metrics from all PRs
    overall_metrics = calculate_overall_metrics(prs)

    return {
        "filename": filename,
        "start_date": period.get("start_date"),
        "end_date": period.get("end_date"),
        "total_prs": stats.get("total_prs", 0),
        "ai_prs": stats.get("ai_assisted_prs", 0),
        "non_ai_prs": stats.get("non_ai_prs", 0),
        "ai_adoption_rate": stats.get("ai_adoption_rate", 0),
        "claude_prs": stats.get("claude_prs", 0),
        "cursor_prs": stats.get("cursor_prs", 0),
        "ai_stats": stats.get("ai_stats", {}),
        "non_ai_stats": stats.get("non_ai_stats", {}),
        "overall_metrics": overall_metrics,
        "comparison": stats.get("comparison", {}),
    }


def generate_tsv_report(reports, author=None):
    """
    Generate TSV format comparison report.

    Args:
        reports: List of parsed report dictionaries
        author: Optional author name

    Returns:
        String report in TSV format
    """
    if len(reports) < 2:
        print(f"Error: Need at least 2 reports for comparison, found {len(reports)}")
        return None

    # Sort reports by date
    reports = sorted(reports, key=lambda x: x["start_date"])

    # Parse phase configuration
    phase_config = parse_phase_config()

    if not phase_config:
        print("Error: Could not parse phase configuration from config/github_phases.conf")
        print("Please ensure the config file exists and has valid GITHUB_PHASES entries.")
        return None

    # Determine phase names from config
    phase_names = []
    for i, report in enumerate(reports):
        phase_name = get_phase_name_for_report(report, phase_config)
        if not phase_name:
            print(f"Error: No matching phase found in config for report {i+1}")
            print(f"  Report dates: {report['start_date']} to {report['end_date']}")
            print(f"  Report file: {report['filename']}")
            print("\nAvailable phases in config:")
            for name, start, end in phase_config:
                print(f"  - {name}: {start} to {end}")
            print("\nPlease ensure report dates match phase dates in config/github_phases.conf")
            return None
        phase_names.append(phase_name)

    output = []

    # Header
    if author:
        output.append(f"GitHub PR Analysis - AI Impact Report - {author}")
    else:
        output.append("GitHub PR Analysis - AI Impact Report - Team Overall")

    output.append(f"Report Generated: {datetime.now().strftime('%B %d, %Y')}")
    repo = f"{os.getenv('GITHUB_REPO_OWNER', 'N/A')}/{os.getenv('GITHUB_REPO_NAME', 'N/A')}"
    output.append(f"Repository: {repo}")
    output.append("")

    output.append("This report compares GitHub PR metrics across different time periods")
    output.append("to evaluate the impact of AI tools (Claude, Cursor) on development workflow.")
    output.append("")

    # Phase information
    for i, (phase, report) in enumerate(zip(phase_names, reports)):
        output.append(f"Phase {i+1}: {phase} ({report['start_date']} to {report['end_date']})")

    output.append("")
    output.append("")

    # Metrics table (TSV format) - single clean table with overall metrics
    header = "Metric\t" + "\t".join(phase_names)
    output.append(header)

    # Total PRs (excluding bot-authored PRs)
    total_prs = [r["total_prs"] for r in reports]
    output.append("Total PRs Merged (excl. bot-authored)\t" + "\t".join(str(n) for n in total_prs))

    # AI adoption
    ai_adoption = [r["ai_adoption_rate"] for r in reports]
    output.append("AI Adoption Rate\t" + "\t".join(f"{rate:.1f}%" for rate in ai_adoption))

    # AI PRs
    ai_prs = [r["ai_prs"] for r in reports]
    output.append("AI-Assisted PRs\t" + "\t".join(str(n) for n in ai_prs))

    # Non-AI PRs
    non_ai_prs = [r["non_ai_prs"] for r in reports]
    output.append("Non-AI PRs\t" + "\t".join(str(n) for n in non_ai_prs))

    # Tool breakdown
    claude_prs = [r["claude_prs"] for r in reports]
    output.append("Claude PRs\t" + "\t".join(str(n) for n in claude_prs))

    cursor_prs = [r["cursor_prs"] for r in reports]
    output.append("Cursor PRs\t" + "\t".join(str(n) for n in cursor_prs))

    # Overall metrics (combining all PRs - AI and non-AI)
    metrics = [
        ("Avg Time to Merge (days)", "avg_time_to_merge_days", "d"),
        ("Avg Time to First Review (hours)", "avg_time_to_first_review_hours", "h"),
        ("Avg Changes Requested", "avg_changes_requested", ""),
        ("Avg Commits per PR", "avg_commits", ""),
        ("Avg Reviewers", "avg_reviewers", ""),
        ("Avg Reviewers (excl. bots)", "avg_human_reviewers", ""),
        ("Avg Comments", "avg_comments", ""),
        ("Avg Comments (excl. bots & approvals)", "avg_human_substantive_comments", ""),
        ("Avg Lines Added", "avg_additions", ""),
        ("Avg Lines Deleted", "avg_deletions", ""),
        ("Avg Files Changed", "avg_files_changed", ""),
    ]

    for metric_name, key, unit in metrics:
        values = []
        for r in reports:
            if r["overall_metrics"]:
                val = r["overall_metrics"].get(key, 0)
                values.append(f"{val:.2f}{unit}")
            else:
                values.append("N/A")
        output.append(f"{metric_name}\t" + "\t".join(values))

    output.append("")
    output.append("")
    output.append("")
    output.append("")
    output.append("")

    # Key trends based on metrics shown in the table above
    output.append("Key Trends:")
    output.append("")

    # AI adoption trend
    if len(ai_adoption) >= 2:
        adoption_change = ai_adoption[-1] - ai_adoption[0]
        output.append(
            f"AI Adoption: {ai_adoption[0]:.1f}% → {ai_adoption[-1]:.1f}% ({adoption_change:+.1f}% change)"
        )

    # Overall merge time trend
    merge_times = [
        r["overall_metrics"].get("avg_time_to_merge_days", 0)
        for r in reports
        if r["overall_metrics"]
    ]
    if len(merge_times) >= 2:
        first_merge = merge_times[0]
        last_merge = merge_times[-1]
        merge_change = ((last_merge - first_merge) / first_merge * 100) if first_merge > 0 else 0
        output.append(
            f"Avg Time to Merge: {first_merge:.2f}d → {last_merge:.2f}d ({merge_change:+.1f}% change)"
        )

    # Review speed trend
    review_times = [
        r["overall_metrics"].get("avg_time_to_first_review_hours", 0)
        for r in reports
        if r["overall_metrics"]
    ]
    if len(review_times) >= 2:
        first_review = review_times[0]
        last_review = review_times[-1]
        review_change = (
            ((last_review - first_review) / first_review * 100) if first_review > 0 else 0
        )
        output.append(
            f"Avg Time to First Review: {first_review:.2f}h → {last_review:.2f}h ({review_change:+.1f}% change)"
        )

    # Human reviewers trend
    human_reviewers = [
        r["overall_metrics"].get("avg_human_reviewers", 0) for r in reports if r["overall_metrics"]
    ]
    if len(human_reviewers) >= 2:
        reviewer_change = (
            ((human_reviewers[-1] - human_reviewers[0]) / human_reviewers[0] * 100)
            if human_reviewers[0] > 0
            else 0
        )
        output.append(
            f"Avg Reviewers (excl. bots): {human_reviewers[0]:.2f} → {human_reviewers[-1]:.2f} ({reviewer_change:+.1f}% change)"
        )

    # Human substantive comments trend
    human_comments = [
        r["overall_metrics"].get("avg_human_substantive_comments", 0)
        for r in reports
        if r["overall_metrics"]
    ]
    if len(human_comments) >= 2:
        comment_change = (
            ((human_comments[-1] - human_comments[0]) / human_comments[0] * 100)
            if human_comments[0] > 0
            else 0
        )
        output.append(
            f"Avg Comments (excl. bots & approvals): {human_comments[0]:.2f} → {human_comments[-1]:.2f} ({comment_change:+.1f}% change)"
        )

    output.append("")
    output.append("For detailed metric explanations, see:")
    output.append("https://github.com/testcara/ai_impact_analysis#understanding-report-metrics")
    output.append("")

    # Summary based on trends
    output.append("Summary:")
    if len(merge_times) >= 2:
        productivity_improved = merge_times[-1] < merge_times[0]
        if ai_adoption[-1] > 50:
            output.append(f"Strong AI adoption ({ai_adoption[-1]:.1f}% of PRs).")
            if productivity_improved:
                output.append("Merge times trending downward - positive productivity signal.")
        elif ai_adoption[-1] > 20:
            output.append(f"Moderate AI adoption ({ai_adoption[-1]:.1f}% of PRs).")
        else:
            output.append(f"Early stage AI adoption ({ai_adoption[-1]:.1f}% of PRs).")

    return "\n".join(output)


def find_pr_reports(author=None):
    """
    Find all matching PR report JSON files.

    Args:
        author: Optional author filter

    Returns:
        List of file paths
    """
    reports_dir = "reports/github"
    if not os.path.exists(reports_dir):
        return []

    files = []
    for filename in os.listdir(reports_dir):
        if not filename.startswith("pr_metrics_"):
            continue
        if not filename.endswith(".json"):
            continue

        if author:
            # Look for author-specific reports
            if f"pr_metrics_{author}_" in filename:
                files.append(os.path.join(reports_dir, filename))
        else:
            # Look for general reports
            if "pr_metrics_general_" in filename:
                files.append(os.path.join(reports_dir, filename))

    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description="Generate PR comparison report across multiple time periods"
    )
    parser.add_argument(
        "--author", type=str, help="Filter by author (GitHub username)", default=None
    )
    parser.add_argument(
        "--output", type=str, help="Output filename (default: auto-generated)", default=None
    )

    args = parser.parse_args()

    # Find matching reports
    report_files = find_pr_reports(args.author)

    if len(report_files) == 0:
        if args.author:
            print(f"Error: No PR reports found for author '{args.author}'")
            print(f"\nLooking for files matching: reports/github/pr_metrics_{args.author}_*.json")
        else:
            print("Error: No general PR reports found")
            print("\nLooking for files matching: reports/github/pr_metrics_general_*.json")
        return 1

    if len(report_files) < 2:
        print(f"Warning: Found only {len(report_files)} report(s), need at least 2 for comparison")
        print(f"Found: {', '.join(report_files)}")
        return 1

    # Use all reports if <= 4, otherwise use most recent 4
    if len(report_files) > 4:
        print(f"Found {len(report_files)} reports, using the 4 most recent for comparison:")
        report_files = sorted(report_files)[-4:]
    else:
        report_files = sorted(report_files)

    print(f"Analyzing {len(report_files)} PR reports:")
    for i, f in enumerate(report_files, 1):
        print(f"  Phase {i}: {f}")
    print()

    # Parse reports
    reports = []
    for filename in report_files:
        print(f"Parsing {filename}...")
        data = parse_pr_report(filename)
        reports.append(data)

    # Generate comparison report
    print("\nGenerating comparison report...")
    report_text = generate_tsv_report(reports, args.author)

    if not report_text:
        return 1

    # Create output directory
    output_dir = "reports/github"
    os.makedirs(output_dir, exist_ok=True)

    # Determine output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        output_file = args.output
    else:
        if args.author:
            output_file = os.path.join(output_dir, f"pr_comparison_{args.author}_{timestamp}.tsv")
        else:
            output_file = os.path.join(output_dir, f"pr_comparison_general_{timestamp}.tsv")

    # Write output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\n✓ Comparison report generated: {output_file}")
    print("\nYou can now:")
    print(f"  1. Open {output_file} in any text editor")
    print("  2. Copy all content (Ctrl+A, Ctrl+C)")
    print("  3. Paste directly into Google Sheets")
    print("  4. Or upload using: python3 bin/upload_to_sheets.py --report {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
