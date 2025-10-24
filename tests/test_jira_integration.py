"""Integration tests using real Jira credentials.

These tests require environment variables to be set:
- JIRA_URL
- JIRA_API_TOKEN
- JIRA_PROJECT_KEY

Run with: pytest tests/test_integration.py -v
Skip with: pytest tests/ --ignore=tests/test_integration.py
"""

import os
import pytest
from ai_impact_analysis.jira_client import JiraClient
from ai_impact_analysis.utils import build_jql_query


@pytest.mark.skipif(
    not os.getenv("JIRA_API_TOKEN"), reason="JIRA_API_TOKEN not set - skipping integration tests"
)
class TestJiraIntegration:
    """Integration tests with real Jira instance."""

    def test_jira_connection(self):
        """Test connection to Jira."""
        client = JiraClient()

        # Simple query to test connection
        project_key = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")
        jql = f'project = "{project_key}"'

        result = client.fetch_jira_data(jql, max_results=1)

        assert result is not None, "Failed to connect to Jira"
        assert "total" in result, "Response missing 'total' field"
        assert "issues" in result, "Response missing 'issues' field"
        print("\n✓ Successfully connected to Jira")
        print(f"  Project: {project_key}")
        print(f"  Total issues found: {result['total']}")

    def test_fetch_with_date_filter(self):
        """Test fetching issues with date filters."""
        client = JiraClient()
        project_key = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

        # Test with a recent date range
        jql = build_jql_query(
            project_key=project_key, start_date="2025-10-01", end_date="2025-10-20"
        )

        result = client.fetch_jira_data(jql, max_results=5)

        assert result is not None, "Query failed"
        print("\n✓ Date filter query successful")
        print(f"  JQL: {jql}")
        print(f"  Issues found: {result['total']}")

        if result["issues"]:
            issue = result["issues"][0]
            print(f"  Sample issue: {issue['key']}")

    def test_fetch_with_assignee(self):
        """Test fetching issues for specific assignee."""
        client = JiraClient()
        project_key = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

        # Get current user's email from environment if available
        assignee = os.getenv("JIRA_USER_EMAIL")

        if not assignee:
            pytest.skip("JIRA_USER_EMAIL not set")

        jql = build_jql_query(project_key=project_key, assignee=assignee)

        result = client.fetch_jira_data(jql, max_results=5)

        assert result is not None, "Query failed"
        print("\n✓ Assignee filter query successful")
        print(f"  Assignee: {assignee}")
        print(f"  Issues found: {result['total']}")

    def test_fetch_all_issues_pagination(self):
        """Test pagination with real data."""
        client = JiraClient()
        project_key = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

        # Use small batch size to test pagination
        jql = f'project = "{project_key}"'
        issues = client.fetch_all_issues(jql, batch_size=10, expand=None)

        assert isinstance(issues, list), "Should return a list"
        print("\n✓ Pagination test successful")
        print(f"  Total issues fetched: {len(issues)}")

        if issues:
            print(f"  First issue: {issues[0]['key']}")
            print(f"  Last issue: {issues[-1]['key']}")

    def test_changelog_expansion(self):
        """Test fetching issues with changelog expansion."""
        client = JiraClient()
        project_key = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

        jql = build_jql_query(
            project_key=project_key, start_date="2025-10-01", end_date="2025-10-20"
        )

        result = client.fetch_jira_data(jql, max_results=1, expand="changelog")

        assert result is not None, "Query failed"

        if result["issues"]:
            issue = result["issues"][0]
            assert "changelog" in issue, "Changelog not expanded"
            print("\n✓ Changelog expansion successful")
            print(f"  Issue: {issue['key']}")

            if "histories" in issue.get("changelog", {}):
                histories = issue["changelog"]["histories"]
                print(f"  History entries: {len(histories)}")
        else:
            print("\n⚠ No issues found in date range")


if __name__ == "__main__":
    # Allow running directly with: python tests/test_integration.py
    pytest.main([__file__, "-v"])
