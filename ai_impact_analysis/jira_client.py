"""Jira API client for fetching issue data."""

import requests
import os


class JiraClient:
    """Client for interacting with Jira REST API."""

    def __init__(self, jira_url=None, api_token=None):
        """Initialize Jira client with URL and API token."""
        self.jira_url = jira_url or os.getenv("JIRA_URL", "https://issues.redhat.com")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")

        self.headers = {"Accept": "application/json", "authorization": f"Bearer {self.api_token}"}

    def fetch_jira_data(self, jql_query, start_at=0, max_results=50, expand=None):
        """
        Fetch Jira Issue data with pagination support.

        Args:
            jql_query: JQL query string
            start_at: Starting index for pagination
            max_results: Maximum results per request
            expand: Optional fields to expand (e.g., 'changelog')

        Returns:
            JSON response from Jira API or None on error
        """
        url = f"{self.jira_url}/rest/api/2/search"

        params = {
            "jql": jql_query,
            "fields": "created,resolutiondate,status,issuetype,timeoriginalestimate,timetracking",
            "startAt": start_at,
            "maxResults": max_results,
        }

        if expand:
            params["expand"] = expand

        print("\n[DEBUG] === Jira API Request ===")
        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] JQL Query: {jql_query}")
        print("[DEBUG] Parameters:")
        for key, value in params.items():
            print(f"[DEBUG]   {key}: {value}")
        print("[DEBUG] =========================\n")

        try:
            response = requests.get(url, headers=self.headers, params=params)

            print(f"[DEBUG] Response Status Code: {response.status_code}")
            print(f"[DEBUG] Response URL: {response.url}")

            if not response.ok:
                print(f"[DEBUG] Error Response: {response.text}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Jira data: {e}")
            print(f"[DEBUG] Request failed with exception: {type(e).__name__}")
            if hasattr(e, "response") and e.response is not None:
                print(f"[DEBUG] Response text: {e.response.text}")
            return None

    def fetch_all_issues(self, jql_query, batch_size=50, expand=None):
        """
        Fetch all issues matching a JQL query with automatic pagination.

        Args:
            jql_query: JQL query string
            batch_size: Number of issues per request
            expand: Optional fields to expand

        Returns:
            List of all issues matching the query
        """
        initial_data = self.fetch_jira_data(jql_query, max_results=1)
        total_issues = initial_data.get("total", 0) if initial_data else 0

        print(f"Total issues found: {total_issues}")

        all_issues = []
        if total_issues > 0:
            for start_at in range(0, total_issues, batch_size):
                print(
                    f"Fetching issues {start_at} to {min(start_at + batch_size, total_issues)}..."
                )
                data = self.fetch_jira_data(
                    jql_query, start_at=start_at, max_results=batch_size, expand=expand
                )
                if data and "issues" in data:
                    all_issues.extend(data["issues"])
                else:
                    print(f"Failed to fetch batch starting at {start_at}")
                    break

        return all_issues
