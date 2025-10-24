"""
Integration tests for GitHub PR analysis.

These tests require real GitHub credentials and will make actual API calls.
Set environment variables before running:
    export GITHUB_TOKEN="your_token"
    export GITHUB_REPO_OWNER="your_org"
    export GITHUB_REPO_NAME="your_repo"

Run with: pytest tests/test_github_integration.py -v
Or with tox: tox -e github-integration
"""

import os
import pytest
from datetime import datetime, timedelta

from ai_impact_analysis.github_client import GitHubClient


# Skip all tests if GitHub credentials not available
pytestmark = pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN")
    or not os.getenv("GITHUB_REPO_OWNER")
    or not os.getenv("GITHUB_REPO_NAME"),
    reason="GitHub credentials not set (GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME)",
)


class TestGitHubIntegration:
    """Integration tests with real GitHub API."""

    def test_github_client_initialization(self):
        """Test that client initializes with env vars."""
        client = GitHubClient()
        assert client.token is not None
        assert client.repo_owner is not None
        assert client.repo_name is not None
        print(f"\n✓ Connected to {client.repo_owner}/{client.repo_name}")

    def test_fetch_recent_merged_prs(self):
        """Test fetching recent merged PRs."""
        client = GitHubClient()

        # Fetch PRs from last 30 days
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        print(f"\n📥 Fetching PRs from {start_date} to {end_date}")

        prs = client.fetch_merged_prs(start_date, end_date)

        print(f"✓ Found {len(prs)} merged PRs")

        if prs:
            # Display first PR info
            pr = prs[0]
            print(f"  Example PR: #{pr['number']} - {pr['title']}")
            print(f"  Author: {pr['user']['login']}")
            print(f"  Merged: {pr['merged_at']}")

    def test_pr_detailed_metrics(self):
        """Test getting detailed metrics for a PR."""
        client = GitHubClient()

        # Fetch recent PRs
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        prs = client.fetch_merged_prs(start_date, end_date)

        if not prs:
            pytest.skip("No recent merged PRs found for testing")

        # Get detailed metrics for first PR
        pr = prs[0]
        print(f"\n📊 Analyzing PR #{pr['number']}: {pr['title']}")

        metrics = client.get_pr_detailed_metrics(pr)

        # Verify metrics structure
        assert "pr_number" in metrics
        assert "has_ai_assistance" in metrics
        assert "ai_tools" in metrics
        assert "time_to_merge_days" in metrics
        assert "total_commits" in metrics
        assert "reviewers_count" in metrics
        assert "total_comments_count" in metrics

        print(f"  AI Assisted: {metrics['has_ai_assistance']}")
        if metrics["has_ai_assistance"]:
            print(f"  AI Tools: {', '.join(metrics['ai_tools'])}")
        print(f"  Time to merge: {metrics['time_to_merge_days']:.2f} days")
        print(f"  Commits: {metrics['total_commits']}")
        print(f"  Reviewers: {metrics['reviewers_count']}")
        print(f"  Comments: {metrics['total_comments_count']}")
        print(f"  Changes requested: {metrics['changes_requested_count']}")

    def test_ai_detection(self):
        """Test AI assistance detection in commit messages."""
        client = GitHubClient()

        # Fetch recent PRs
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        prs = client.fetch_merged_prs(start_date, end_date)

        if not prs:
            pytest.skip("No recent merged PRs found for testing")

        print("\n🔍 Scanning PRs for AI assistance...")

        ai_assisted_count = 0
        for pr in prs[:10]:  # Check first 10 PRs
            ai_info = client.detect_ai_assistance(pr["number"])
            if ai_info["has_ai_assistance"]:
                ai_assisted_count += 1
                print(
                    f"  PR #{pr['number']}: {', '.join(ai_info['ai_tools'])} ({ai_info['ai_commits_count']}/{ai_info['total_commits']} commits)"
                )

        print(f"\n✓ Found {ai_assisted_count} AI-assisted PRs out of {min(len(prs), 10)} checked")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
