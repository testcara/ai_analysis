#!/usr/bin/env python3
"""
Collect GitHub PR metrics for AI impact analysis.
...
"""

import os
import sys
import json
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai_impact_analysis.github_client import GitHubClient
from ai_impact_analysis.logger import logger


def calculate_statistics(prs_with_metrics):
    """
    Calculate aggregated statistics from PR metrics.

    Args:
        prs_with_metrics: List of PR dictionaries with metrics

    Returns:
        Dictionary with aggregated statistics
    """
    if not prs_with_metrics:
        return {"total_prs": 0, "ai_assisted_prs": 0, "non_ai_prs": 0, "ai_adoption_rate": 0}

    # Separate AI and non-AI PRs
    ai_prs = [pr for pr in prs_with_metrics if pr["has_ai_assistance"]]
    non_ai_prs = [pr for pr in prs_with_metrics if not pr["has_ai_assistance"]]

    # Count by AI tool
    claude_prs = [pr for pr in ai_prs if "Claude" in pr["ai_tools"]]
    cursor_prs = [pr for pr in ai_prs if "Cursor" in pr["ai_tools"]]
    both_prs = [pr for pr in ai_prs if len(pr["ai_tools"]) > 1]

    def avg(values):
        """Calculate average, handling empty lists."""
        return sum(values) / len(values) if values else 0

    # Calculate AI metrics
    ai_stats = {}
    if ai_prs:
        ai_stats = {
            "count": len(ai_prs),
            "avg_time_to_merge_days": avg([pr["time_to_merge_days"] for pr in ai_prs]),
            "avg_time_to_first_review_hours": avg(
                [
                    pr["time_to_first_review_hours"]
                    for pr in ai_prs
                    if pr["time_to_first_review_hours"]
                ]
            ),
            "avg_changes_requested": avg([pr["changes_requested_count"] for pr in ai_prs]),
            "avg_commits": avg([pr["total_commits"] for pr in ai_prs]),
            "avg_reviewers": avg([pr["reviewers_count"] for pr in ai_prs]),
            "avg_comments": avg([pr["total_comments_count"] for pr in ai_prs]),
            "avg_additions": avg([pr["additions"] for pr in ai_prs]),
            "avg_deletions": avg([pr["deletions"] for pr in ai_prs]),
            "avg_files_changed": avg([pr["changed_files"] for pr in ai_prs]),
        }

    # Calculate non-AI metrics
    non_ai_stats = {}
    if non_ai_prs:
        non_ai_stats = {
            "count": len(non_ai_prs),
            "avg_time_to_merge_days": avg([pr["time_to_merge_days"] for pr in non_ai_prs]),
            "avg_time_to_first_review_hours": avg(
                [
                    pr["time_to_first_review_hours"]
                    for pr in non_ai_prs
                    if pr["time_to_first_review_hours"]
                ]
            ),
            "avg_changes_requested": avg([pr["changes_requested_count"] for pr in non_ai_prs]),
            "avg_commits": avg([pr["total_commits"] for pr in non_ai_prs]),
            "avg_reviewers": avg([pr["reviewers_count"] for pr in non_ai_prs]),
            "avg_comments": avg([pr["total_comments_count"] for pr in non_ai_prs]),
            "avg_additions": avg([pr["additions"] for pr in non_ai_prs]),
            "avg_deletions": avg([pr["deletions"] for pr in non_ai_prs]),
            "avg_files_changed": avg([pr["changed_files"] for pr in non_ai_prs]),
        }

    return {
        "total_prs": len(prs_with_metrics),
        "ai_assisted_prs": len(ai_prs),
        "non_ai_prs": len(non_ai_prs),
        "ai_adoption_rate": (len(ai_prs) / len(prs_with_metrics) * 100) if prs_with_metrics else 0,
        # By tool
        "claude_prs": len(claude_prs),
        "cursor_prs": len(cursor_prs),
        "both_tools_prs": len(both_prs),
        # AI stats
        "ai_stats": ai_stats,
        # Non-AI stats
        "non_ai_stats": non_ai_stats,
        # Comparison (improvement %)
        "comparison": {
            "merge_time_improvement": (
                (
                    (
                        non_ai_stats.get("avg_time_to_merge_days", 0)
                        - ai_stats.get("avg_time_to_merge_days", 0)
                    )
                    / non_ai_stats.get("avg_time_to_merge_days", 1)
                    * 100
                )
                if non_ai_stats.get("avg_time_to_merge_days", 0) > 0
                else 0
            ),
            "changes_requested_reduction": (
                (
                    (
                        non_ai_stats.get("avg_changes_requested", 0)
                        - ai_stats.get("avg_changes_requested", 0)
                    )
                    / non_ai_stats.get("avg_changes_requested", 1)
                    * 100
                )
                if non_ai_stats.get("avg_changes_requested", 0) > 0
                else 0
            ),
        },
    }


def generate_text_report(stats, prs_with_metrics, start_date, end_date, author=None):
    """
    Generate human-readable text report for a single period.

    Args:
        stats: Statistics dictionary
        prs_with_metrics: List of PR dictionaries
        start_date: Start date string
        end_date: End date string
        author: Optional author filter

    Returns:
        String report
    """
    lines = []
    lines.append("=" * 80)
    lines.append("GitHub PR Metrics Report")
    lines.append("=" * 80)
    lines.append(f"Period: {start_date} to {end_date}")
    lines.append(f"Repository: {os.getenv('GITHUB_REPO_OWNER')}/{os.getenv('GITHUB_REPO_NAME')}")
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


def main():
    parser = argparse.ArgumentParser(
        description="Collect GitHub PR metrics for AI impact analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  GITHUB_TOKEN       - GitHub personal access token (required)
  GITHUB_REPO_OWNER  - Repository owner/organization (required)
  GITHUB_REPO_NAME   - Repository name (required)

Examples:
  # Get PRs for October 2024
  python3 bin/get_pr_metrics.py --start 2024-10-01 --end 2024-10-31

  # Get PRs for specific author
  python3 bin/get_pr_metrics.py --start 2024-10-01 --end 2024-10-31 --author wlin

  # Custom output file
  python3 bin/get_pr_metrics.py --start 2024-10-01 --end 2024-10-31 --output my_report.json
        """,
    )

    parser.add_argument("--start", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--author", type=str, help="Filter by PR author (GitHub username)")
    parser.add_argument(
        "--output", type=str, help="Output JSON file path (default: auto-generated)"
    )

    args = parser.parse_args()

    # Validate dates
    try:
        datetime.strptime(args.start, "%Y-%m-%d")
        datetime.strptime(args.end, "%Y-%m-%d")
    except ValueError:
        print("Error: Dates must be in YYYY-MM-DD format")
        return 1

    print("\n📊 Collecting GitHub PR metrics...")
    print(f"Period: {args.start} to {args.end}")
    if args.author:
        print(f"Author: {args.author}")

    # Initialize GitHub client
    try:
        client = GitHubClient()
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nPlease set the following environment variables:")
        print("  export GITHUB_TOKEN='your_token'")
        print("  export GITHUB_REPO_OWNER='owner'")
        print("  export GITHUB_REPO_NAME='repo'")
        return 1

    # Fetch merged PRs
    print("\n📥 Fetching merged PRs...")
    try:
        prs = client.fetch_merged_prs(args.start, args.end)
    except Exception as e:
        print(f"Error fetching PRs: {e}")
        return 1

    # Filter by author if specified
    if args.author:
        prs = [pr for pr in prs if pr["user"]["login"] == args.author]
        print(f"✓ Filtered to {len(prs)} PRs by author '{args.author}'")

    if not prs:
        print("\n⚠ No merged PRs found for the specified period")
        return 0

    # Get detailed metrics for each PR (with concurrent processing)
    print(f"\n📈 Analyzing {len(prs)} PRs (using concurrent processing)...")
    prs_with_metrics = []

    def analyze_single_pr(pr):
        """Analyze a single PR with error handling."""
        try:
            return client.get_pr_detailed_metrics(pr)
        except Exception as e:
            logger.error(f"Error analyzing PR #{pr['number']}: {e}")
            return None

    # Use ThreadPoolExecutor for concurrent processing
    # Limit workers to avoid rate limiting (GitHub allows ~5000 requests/hour)
    max_workers = min(10, len(prs))  # Use up to 10 concurrent workers

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all PR analysis tasks
        future_to_pr = {executor.submit(analyze_single_pr, pr): pr for pr in prs}

        # Process completed tasks as they finish
        completed = 0
        for future in as_completed(future_to_pr):
            pr = future_to_pr[future]
            completed += 1

            try:
                metrics = future.result()
                if metrics:
                    prs_with_metrics.append(metrics)
                    print(f"  ✓ [{completed}/{len(prs)}] PR #{pr['number']}: {pr['title'][:60]}")
                else:
                    print(f"  ✗ [{completed}/{len(prs)}] PR #{pr['number']}: Failed to analyze")
            except Exception as e:
                print(f"  ✗ [{completed}/{len(prs)}] PR #{pr['number']}: {e}")

    print(f"\n✓ Successfully analyzed {len(prs_with_metrics)}/{len(prs)} PRs")

    # Calculate statistics
    print("\n📊 Calculating statistics...")
    stats = calculate_statistics(prs_with_metrics)

    # Generate text report
    text_report = generate_text_report(stats, prs_with_metrics, args.start, args.end, args.author)

    # Prepare JSON output
    output_data = {
        "analysis_date": datetime.now().isoformat(),
        "period": {"start_date": args.start, "end_date": args.end},
        "repository": {"owner": client.repo_owner, "name": client.repo_name},
        "filter": {"author": args.author},
        "statistics": stats,
        "prs": prs_with_metrics,
    }

    # Create output directory
    output_dir = "reports/github"
    os.makedirs(output_dir, exist_ok=True)

    # Determine output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.output:
        json_file = args.output
    else:
        if args.author:
            json_file = f"{output_dir}/pr_metrics_{args.author}_{timestamp}.json"
            txt_file = f"{output_dir}/pr_report_{args.author}_{timestamp}.txt"
        else:
            json_file = f"{output_dir}/pr_metrics_general_{timestamp}.json"
            txt_file = f"{output_dir}/pr_report_general_{timestamp}.txt"

    # Save JSON output
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Save text report
    if not args.output:  # Only save txt if using auto-generated filenames
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(text_report)

    # Display report
    print("\n" + text_report)

    print("\n✅ Analysis complete!")
    print(f"📄 JSON output: {json_file}")
    if not args.output:
        print(f"📄 Text report: {txt_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
