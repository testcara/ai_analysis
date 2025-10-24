"""Unit tests for GitHubClient."""

import os
import pytest
from unittest.mock import Mock, patch
from ai_impact_analysis.github_client import GitHubClient


class TestGitHubClient:
    """Test cases for GitHubClient class."""

    def test_init_with_params(self):
        """Test initialization with parameters."""
        client = GitHubClient(token="test_token", repo_owner="test_owner", repo_name="test_repo")
        assert client.token == "test_token"
        assert client.repo_owner == "test_owner"
        assert client.repo_name == "test_repo"

    def test_init_with_env_vars(self):
        """Test initialization with environment variables."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "env_token",
                "GITHUB_REPO_OWNER": "env_owner",
                "GITHUB_REPO_NAME": "env_repo",
            },
        ):
            client = GitHubClient()
            assert client.token == "env_token"
            assert client.repo_owner == "env_owner"
            assert client.repo_name == "env_repo"

    def test_init_missing_token(self):
        """Test initialization fails without token."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GitHub token is required"):
                GitHubClient(repo_owner="owner", repo_name="repo")

    def test_init_missing_repo_info(self):
        """Test initialization fails without repo info."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Repository owner and name are required"):
                GitHubClient(token="token")

    @patch("ai_impact_analysis.github_client.requests.get")
    def test_fetch_merged_prs_success(self, mock_get):
        """Test fetching merged PRs successfully."""
        # Mock first page with one PR
        mock_response_page1 = Mock()
        mock_response_page1.status_code = 200
        mock_response_page1.json.return_value = [
            {
                "number": 1,
                "title": "Test PR",
                "user": {"login": "testuser"},
                "merged_at": "2024-10-15T10:00:00Z",
                "created_at": "2024-10-14T10:00:00Z",
                "updated_at": "2024-10-15T10:00:00Z",
            }
        ]

        # Mock second page (empty to end pagination)
        mock_response_page2 = Mock()
        mock_response_page2.status_code = 200
        mock_response_page2.json.return_value = []

        # Set side_effect to return first page, then empty page
        mock_get.side_effect = [mock_response_page1, mock_response_page2]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        prs = client.fetch_merged_prs("2024-10-01", "2024-10-31")

        assert len(prs) == 1
        assert prs[0]["number"] == 1
        assert prs[0]["title"] == "Test PR"

    @patch("ai_impact_analysis.github_client.requests.get")
    def test_fetch_merged_prs_http_error(self, mock_get):
        """Test fetching PRs with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP Error")
        mock_get.return_value = mock_response

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")

        with pytest.raises(Exception, match="HTTP Error"):
            client.fetch_merged_prs("2024-10-01", "2024-10-31")

    @patch("ai_impact_analysis.github_client.requests.get")
    def test_get_pr_commits(self, mock_get):
        """Test getting PR commits."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"sha": "abc123", "commit": {"message": "Fix bug\n\nAssisted-by: Claude"}}
        ]
        mock_get.return_value = mock_response

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        commits = client.get_pr_commits(1)

        assert len(commits) == 1
        assert commits[0]["sha"] == "abc123"

    @patch("ai_impact_analysis.github_client.requests.get")
    def test_get_pr_reviews(self, mock_get):
        """Test getting PR reviews."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 1,
                "user": {"login": "reviewer"},
                "state": "APPROVED",
                "submitted_at": "2024-10-15T12:00:00Z",
            }
        ]
        mock_get.return_value = mock_response

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        reviews = client.get_pr_reviews(1)

        assert len(reviews) == 1
        assert reviews[0]["state"] == "APPROVED"

    @patch("ai_impact_analysis.github_client.requests.get")
    def test_get_pr_comments(self, mock_get):
        """Test getting PR comments."""
        # Mock review comments
        mock_review_response = Mock()
        mock_review_response.status_code = 200
        mock_review_response.json.return_value = [
            {"id": 1, "body": "Review comment", "user": {"login": "reviewer"}}
        ]

        # Mock issue comments
        mock_issue_response = Mock()
        mock_issue_response.status_code = 200
        mock_issue_response.json.return_value = [
            {"id": 2, "body": "Issue comment", "user": {"login": "commenter"}}
        ]

        # Mock reviews (for identifying approval-only comments)
        mock_reviews_response = Mock()
        mock_reviews_response.status_code = 200
        mock_reviews_response.json.return_value = [{"id": 3, "state": "APPROVED", "body": "LGTM"}]

        # get_pr_comments makes 3 API calls: review comments, issue comments, reviews
        mock_get.side_effect = [mock_review_response, mock_issue_response, mock_reviews_response]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        comments = client.get_pr_comments(1)

        assert comments["total_comments"] == 2
        assert len(comments["review_comments"]) == 1
        assert len(comments["issue_comments"]) == 1
        assert len(comments["approval_review_ids"]) == 1

    @patch.object(GitHubClient, "get_pr_commits")
    def test_detect_ai_assistance_claude(self, mock_get_commits):
        """Test detecting Claude AI assistance."""
        mock_get_commits.return_value = [
            {
                "commit": {
                    "message": "Fix authentication\n\nAssisted-by: Claude <noreply@anthropic.com>"
                }
            }
        ]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        result = client.detect_ai_assistance(1)

        assert result["has_ai_assistance"] is True
        assert "Claude" in result["ai_tools"]
        assert result["ai_commits_count"] == 1
        assert result["total_commits"] == 1

    @patch.object(GitHubClient, "get_pr_commits")
    def test_detect_ai_assistance_cursor(self, mock_get_commits):
        """Test detecting Cursor AI assistance."""
        mock_get_commits.return_value = [
            {"commit": {"message": "Implement feature\n\nAssisted-by: Cursor"}}
        ]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        result = client.detect_ai_assistance(1)

        assert result["has_ai_assistance"] is True
        assert "Cursor" in result["ai_tools"]

    @patch.object(GitHubClient, "get_pr_commits")
    def test_detect_ai_assistance_both_tools(self, mock_get_commits):
        """Test detecting both Claude and Cursor."""
        mock_get_commits.return_value = [
            {"commit": {"message": "First commit\n\nAssisted-by: Claude"}},
            {"commit": {"message": "Second commit\n\nAssisted-by: Cursor"}},
        ]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        result = client.detect_ai_assistance(1)

        assert result["has_ai_assistance"] is True
        assert "Claude" in result["ai_tools"]
        assert "Cursor" in result["ai_tools"]
        assert result["ai_commits_count"] == 2

    @patch.object(GitHubClient, "get_pr_commits")
    def test_detect_ai_assistance_none(self, mock_get_commits):
        """Test detecting no AI assistance."""
        mock_get_commits.return_value = [{"commit": {"message": "Regular commit without AI"}}]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        result = client.detect_ai_assistance(1)

        assert result["has_ai_assistance"] is False
        assert len(result["ai_tools"]) == 0
        assert result["ai_commits_count"] == 0

    @patch.object(GitHubClient, "get_pr_commits")
    def test_detect_ai_assistance_case_insensitive(self, mock_get_commits):
        """Test AI detection is case insensitive."""
        mock_get_commits.return_value = [{"commit": {"message": "Fix bug\n\nassisted-by: claude"}}]

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        result = client.detect_ai_assistance(1)

        assert result["has_ai_assistance"] is True
        assert "Claude" in result["ai_tools"]

    @patch.object(GitHubClient, "detect_ai_assistance")
    @patch.object(GitHubClient, "get_pr_reviews")
    @patch.object(GitHubClient, "get_pr_comments")
    @patch.object(GitHubClient, "get_pr_details")
    def test_get_pr_detailed_metrics(self, mock_pr_details, mock_comments, mock_reviews, mock_ai):
        """Test getting detailed PR metrics."""
        # Mock AI detection
        mock_ai.return_value = {
            "has_ai_assistance": True,
            "ai_tools": ["Claude"],
            "ai_commits_count": 2,
            "total_commits": 3,
            "ai_percentage": 66.67,
        }

        # Mock reviews
        mock_reviews.return_value = [
            {
                "user": {"login": "reviewer1"},
                "state": "APPROVED",
                "submitted_at": "2024-10-15T12:00:00Z",
            },
            {
                "user": {"login": "reviewer2"},
                "state": "CHANGES_REQUESTED",
                "submitted_at": "2024-10-15T10:00:00Z",
            },
        ]

        # Mock comments
        mock_comments.return_value = {
            "review_comments": [{"id": 1}],
            "issue_comments": [{"id": 2}],
            "total_comments": 2,
        }

        # Mock full PR details (returned by get_pr_details)
        mock_pr_details.return_value = {
            "number": 1,
            "title": "Test PR",
            "user": {"login": "author"},
            "created_at": "2024-10-14T10:00:00Z",
            "merged_at": "2024-10-15T14:00:00Z",
            "html_url": "https://github.com/owner/repo/pull/1",
            "additions": 100,
            "deletions": 50,
            "changed_files": 5,
        }

        # Mock PR data (from list endpoint, may have limited data)
        pr_data = {
            "number": 1,
            "title": "Test PR",
            "user": {"login": "author"},
            "created_at": "2024-10-14T10:00:00Z",
            "merged_at": "2024-10-15T14:00:00Z",
            "html_url": "https://github.com/owner/repo/pull/1",
            "additions": 0,  # List endpoint may not have this
            "deletions": 0,  # List endpoint may not have this
            "changed_files": 0,  # List endpoint may not have this
        }

        client = GitHubClient(token="token", repo_owner="owner", repo_name="repo")
        metrics = client.get_pr_detailed_metrics(pr_data)

        assert metrics["pr_number"] == 1
        assert metrics["has_ai_assistance"] is True
        assert "Claude" in metrics["ai_tools"]
        assert metrics["changes_requested_count"] == 1
        assert metrics["approvals_count"] == 1
        assert metrics["reviewers_count"] == 2
        assert metrics["total_comments_count"] == 2
        assert metrics["time_to_merge_days"] > 0
        # Verify size metrics come from full PR details
        assert metrics["additions"] == 100
        assert metrics["deletions"] == 50
        assert metrics["changed_files"] == 5


class TestPRComparisonReport:
    """Test cases for PR comparison report generation."""

    @patch("ai_impact_analysis.cli.generate_pr_comparison_report.parse_phase_config")
    def test_generate_tsv_report_with_no_ai_prs(self, mock_parse_config):
        """Test generating report when there are no AI-assisted PRs."""
        # Import here to avoid circular dependency
        from ai_impact_analysis.cli.generate_pr_comparison_report import generate_tsv_report

        # Mock phase config
        mock_parse_config.return_value = [
            ("Phase 1", "2024-10-01", "2024-10-31"),
            ("Phase 2", "2024-11-01", "2024-11-30"),
        ]

        # Mock reports with only non-AI PRs (need at least 2 for comparison)
        reports = [
            {
                "filename": "test1.json",
                "start_date": "2024-10-01",
                "end_date": "2024-10-31",
                "total_prs": 10,
                "ai_prs": 0,
                "non_ai_prs": 10,
                "ai_adoption_rate": 0.0,
                "claude_prs": 0,
                "cursor_prs": 0,
                "overall_metrics": {
                    "count": 10,
                    "avg_time_to_merge_days": 3.5,
                    "avg_time_to_first_review_hours": 6.0,
                    "avg_changes_requested": 1.2,
                    "avg_commits": 4.0,
                    "avg_reviewers": 2.0,
                    "avg_human_reviewers": 1.5,
                    "avg_comments": 7.0,
                    "avg_human_substantive_comments": 3.0,
                    "avg_additions": 120.0,
                    "avg_deletions": 60.0,
                    "avg_files_changed": 4.0,
                },
            },
            {
                "filename": "test2.json",
                "start_date": "2024-11-01",
                "end_date": "2024-11-30",
                "total_prs": 12,
                "ai_prs": 0,
                "non_ai_prs": 12,
                "ai_adoption_rate": 0.0,
                "claude_prs": 0,
                "cursor_prs": 0,
                "overall_metrics": {
                    "count": 12,
                    "avg_time_to_merge_days": 3.2,
                    "avg_time_to_first_review_hours": 5.5,
                    "avg_changes_requested": 1.0,
                    "avg_commits": 3.8,
                    "avg_reviewers": 2.1,
                    "avg_human_reviewers": 1.6,
                    "avg_comments": 6.5,
                    "avg_human_substantive_comments": 2.8,
                    "avg_additions": 110.0,
                    "avg_deletions": 55.0,
                    "avg_files_changed": 3.8,
                },
            },
        ]

        # This should not raise UnboundLocalError
        report_text = generate_tsv_report(reports, None)

        assert report_text is not None
        assert "GitHub PR Analysis" in report_text

    @patch("ai_impact_analysis.cli.generate_pr_comparison_report.parse_phase_config")
    def test_generate_tsv_report_with_only_ai_prs(self, mock_parse_config):
        """Test generating report when there are only AI-assisted PRs."""
        from ai_impact_analysis.cli.generate_pr_comparison_report import generate_tsv_report

        # Mock phase config
        mock_parse_config.return_value = [
            ("Phase 1", "2024-10-01", "2024-10-31"),
            ("Phase 2", "2024-11-01", "2024-11-30"),
        ]

        # Mock reports with only AI PRs (need at least 2 for comparison)
        reports = [
            {
                "filename": "test1.json",
                "start_date": "2024-10-01",
                "end_date": "2024-10-31",
                "total_prs": 10,
                "ai_prs": 10,
                "non_ai_prs": 0,
                "ai_adoption_rate": 100.0,
                "claude_prs": 5,
                "cursor_prs": 5,
                "overall_metrics": {
                    "count": 10,
                    "avg_time_to_merge_days": 2.5,
                    "avg_time_to_first_review_hours": 4.0,
                    "avg_changes_requested": 0.8,
                    "avg_commits": 3.0,
                    "avg_reviewers": 2.0,
                    "avg_human_reviewers": 1.8,
                    "avg_comments": 5.0,
                    "avg_human_substantive_comments": 2.5,
                    "avg_additions": 100.0,
                    "avg_deletions": 50.0,
                    "avg_files_changed": 3.0,
                },
            },
            {
                "filename": "test2.json",
                "start_date": "2024-11-01",
                "end_date": "2024-11-30",
                "total_prs": 12,
                "ai_prs": 12,
                "non_ai_prs": 0,
                "ai_adoption_rate": 100.0,
                "claude_prs": 6,
                "cursor_prs": 6,
                "overall_metrics": {
                    "count": 12,
                    "avg_time_to_merge_days": 2.2,
                    "avg_time_to_first_review_hours": 3.5,
                    "avg_changes_requested": 0.7,
                    "avg_commits": 2.8,
                    "avg_reviewers": 2.1,
                    "avg_human_reviewers": 1.9,
                    "avg_comments": 4.8,
                    "avg_human_substantive_comments": 2.3,
                    "avg_additions": 95.0,
                    "avg_deletions": 48.0,
                    "avg_files_changed": 2.9,
                },
            },
        ]

        # This should not raise UnboundLocalError
        report_text = generate_tsv_report(reports, None)

        assert report_text is not None
        assert "GitHub PR Analysis" in report_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
