"""
PR Metrics Calculator

Core business logic for calculating GitHub PR metrics.
Extracted from cli/get_pr_metrics.py
"""

from datetime import datetime


class PRMetricsCalculator:
    """Calculator for GitHub PR metrics and statistics."""

    def calculate_statistics(self, prs_with_metrics):
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

    def calculate_overall_metrics(self, prs_with_metrics):
        """
        Calculate overall metrics combining all PRs.

        Args:
            prs_with_metrics: List of PR dictionaries

        Returns:
            Dictionary with overall metrics
        """
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

        return {
            "avg_time_to_merge_days": avg(merge_times),
            "avg_time_to_first_review_hours": avg(review_times),
            "avg_changes_requested": avg(changes),
            "avg_commits": avg(commits),
            "avg_reviewers": avg(reviewers),
            "avg_human_reviewers": avg(human_reviewers),
            "avg_comments": avg(comments),
            "avg_human_substantive_comments": avg(human_substantive_comments),
            "avg_additions": avg(additions),
            "avg_deletions": avg(deletions),
            "avg_files_changed": avg(files),
        }
