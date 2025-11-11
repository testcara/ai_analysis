"""
Jira Metrics Calculator

Core business logic for fetching Jira data and calculating metrics.
Extracted from cli/get_jira_metrics.py
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

from ai_impact_analysis.utils.report_utils import normalize_username
from ai_impact_analysis.utils.workflow_utils import load_team_members_from_yaml


class JiraMetricsCalculator:
    """
    Calculator for Jira issue metrics including closure times,
    state durations, and velocity.
    """

    def __init__(self, jira_url=None, jira_token=None, project_key=None):
        """
        Initialize the Jira metrics calculator.

        Args:
            jira_url: Jira instance URL (default: from JIRA_URL env var)
            jira_token: Jira API token (default: from JIRA_API_TOKEN env var)
            project_key: Project key (default: from JIRA_PROJECT_KEY env var)
        """
        self.jira_url = jira_url or os.getenv("JIRA_URL", "https://issues.redhat.com")
        self.jira_token = jira_token or os.getenv("JIRA_API_TOKEN")
        self.project_key = project_key or os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

        # Setup authentication headers
        self.headers = {"Accept": "application/json", "authorization": f"Bearer {self.jira_token}"}

    def fetch_jira_data(self, jql_query, start_at=0, max_results=50, expand=None):
        """
        Generic function for fetching Jira issue data with pagination.

        Args:
            jql_query: JQL query string
            start_at: Pagination start index
            max_results: Maximum results per page
            expand: Fields to expand (e.g., "changelog")

        Returns:
            JSON response data or None on error
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

    def calculate_state_durations(self, issue):
        """
        Calculate the time spent in each state for an issue and the number of occurrences.

        Args:
            issue: Jira issue dict with changelog data

        Returns:
            Dictionary containing total time (seconds) and occurrence count for each state
        """
        state_stats = {}

        changelog = issue.get("changelog", {})
        histories = changelog.get("histories", [])

        created_str = issue["fields"].get("created")
        current_status = issue["fields"].get("status", {}).get("name", "Unknown")
        resolution_str = issue["fields"].get("resolutiondate")

        if not created_str:
            return {}

        try:
            created_date = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            try:
                created_date = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return {}

        # Build status transition history
        status_transitions = []

        for history in histories:
            history_created = history.get("created")
            if not history_created:
                continue

            try:
                transition_date = datetime.strptime(history_created, "%Y-%m-%dT%H:%M:%S.%f%z")
            except ValueError:
                try:
                    transition_date = datetime.strptime(history_created, "%Y-%m-%dT%H:%M:%S%z")
                except ValueError:
                    continue

            for item in history.get("items", []):
                if item.get("field") == "status":
                    from_status = item.get("fromString")
                    to_status = item.get("toString")
                    status_transitions.append(
                        {"date": transition_date, "from": from_status, "to": to_status}
                    )

        status_transitions.sort(key=lambda x: x["date"])

        # Determine initial status
        if status_transitions:
            initial_status = status_transitions[0]["from"]
        else:
            initial_status = current_status

        # Calculate time spent in each state
        current_state = initial_status
        current_state_start = created_date

        if current_state:
            if current_state not in state_stats:
                state_stats[current_state] = {"total_seconds": 0, "count": 0}
            state_stats[current_state]["count"] += 1

        for transition in status_transitions:
            if current_state:
                duration = (transition["date"] - current_state_start).total_seconds()
                state_stats[current_state]["total_seconds"] += duration

            current_state = transition["to"]
            current_state_start = transition["date"]

            if current_state not in state_stats:
                state_stats[current_state] = {"total_seconds": 0, "count": 0}
            state_stats[current_state]["count"] += 1

        # Calculate time for last state
        if current_state:
            if resolution_str:
                try:
                    end_date = datetime.strptime(resolution_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                except ValueError:
                    try:
                        end_date = datetime.strptime(resolution_str, "%Y-%m-%dT%H:%M:%S%z")
                    except ValueError:
                        end_date = datetime.now(current_state_start.tzinfo)
            else:
                end_date = datetime.now(current_state_start.tzinfo)

            duration = (end_date - current_state_start).total_seconds()
            state_stats[current_state]["total_seconds"] += duration

        return state_stats

    def convert_date_to_jql(self, date_str):
        """
        Convert YYYY-MM-DD format date to Jira JQL relative time expression.

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            JQL time expression (e.g., "-300d")
        """
        if not date_str:
            return None

        try:
            input_date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now()
            days_diff = (today - input_date).days

            if days_diff == 0:
                return "startOfDay()"
            elif days_diff > 0:
                return f'"-{days_diff}d"'
            else:
                return f'"{abs(days_diff)}d"'
        except ValueError:
            return f'"{date_str}"'

    def build_jql_query(
        self,
        project_key=None,
        assignee=None,
        team_members_file=None,
        start_date=None,
        end_date=None,
        status=None,
    ):
        """
        Build JQL query based on filters.

        Args:
            project_key: Jira project key
            assignee: Single assignee to filter by
            team_members_file: Path to team members config file
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            status: Issue status

        Returns:
            Tuple of (jql_query, team_members_list)
        """
        project_key = project_key or self.project_key
        jql_parts = [f'project = "{project_key}"']

        team_members = []

        # Add assignee filter
        if assignee:
            jql_parts.append(f'assignee = "{assignee}"')
            print(f"Filtering by assignee: {assignee}")
        elif team_members_file:
            # Load team members from config file using YAML parser
            try:
                team_members = load_team_members_from_yaml(Path(team_members_file))

                if team_members:
                    assignee_conditions = " OR ".join(
                        [f'assignee = "{member}"' for member in team_members]
                    )
                    jql_parts.append(f"({assignee_conditions})")
                    print(f"Limiting to team members from config: {len(team_members)} members")
                    print(f"Team members: {', '.join(team_members)}")
                else:
                    print("Warning: No team members found in config file")
            except Exception as e:
                print(f"Warning: Error reading team members file: {e}")

        # Add date filters
        if start_date or end_date:
            if start_date:
                start_jql = self.convert_date_to_jql(start_date)
                jql_parts.append(f"resolved >= {start_jql}")
                print(f"Start date {start_date} converted to: {start_jql}")

            if end_date:
                end_jql = self.convert_date_to_jql(end_date)
                jql_parts.append(f"resolved <= {end_jql}")
                print(f"End date {end_date} converted to: {end_jql}")
        else:
            # Only use status when no date filter
            if status:
                jql_parts.append(f'status = "{status}"')

        return " AND ".join(jql_parts), team_members

    def fetch_all_issues(self, jql_query, batch_size=50):
        """
        Fetch all issues matching JQL query with pagination.

        Args:
            jql_query: JQL query string
            batch_size: Results per page

        Returns:
            List of all issues with changelog data
        """
        # Get total count
        initial_data = self.fetch_jira_data(jql_query, max_results=1)
        total_issues = initial_data.get("total", 0) if initial_data else 0

        print(f"Total issues found for analysis: {total_issues}")

        if total_issues == 0:
            return []

        all_issues = []
        for start_at in range(0, total_issues, batch_size):
            print(f"Fetching issues {start_at} to {min(start_at + batch_size, total_issues)}...")
            data = self.fetch_jira_data(
                jql_query, start_at=start_at, max_results=batch_size, expand="changelog"
            )
            if data and "issues" in data:
                all_issues.extend(data["issues"])
            else:
                print(f"Failed to fetch batch starting at {start_at}")
                break

        return all_issues

    def calculate_metrics(self, issues):
        """
        Calculate comprehensive metrics from issues.

        Args:
            issues: List of Jira issues

        Returns:
            Dictionary containing all calculated metrics
        """
        if not issues:
            return self._empty_metrics()

        closing_times = []
        created_dates = []
        resolution_dates = []
        issue_types = {}

        # Calculate basic metrics
        for issue in issues:
            try:
                created_str = issue["fields"].get("created")
                resolution_str = issue["fields"].get("resolutiondate")
                issue_type = issue["fields"].get("issuetype", {}).get("name", "Unknown")

                if issue_type not in issue_types:
                    issue_types[issue_type] = 0
                issue_types[issue_type] += 1

                if created_str and resolution_str:
                    created_date = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                    resolution_date = datetime.strptime(resolution_str, "%Y-%m-%dT%H:%M:%S.%f%z")

                    created_dates.append(created_date)
                    resolution_dates.append(resolution_date)

                    time_diff = (resolution_date - created_date).total_seconds()
                    closing_times.append(time_diff)
            except Exception as e:
                print(f"Error processing issue {issue.get('key', 'unknown')}: {e}")

        # Calculate state durations
        all_states_aggregated = {}
        for issue in issues:
            state_stats = self.calculate_state_durations(issue)

            for state, stats in state_stats.items():
                if state not in all_states_aggregated:
                    all_states_aggregated[state] = {
                        "total_seconds": 0,
                        "total_count": 0,
                        "issue_count": 0,
                    }
                all_states_aggregated[state]["total_seconds"] += stats["total_seconds"]
                all_states_aggregated[state]["total_count"] += stats["count"]
                all_states_aggregated[state]["issue_count"] += 1

        return {
            "total_issues": len(issues),
            "issue_types": issue_types,
            "closing_times": closing_times,
            "created_dates": created_dates,
            "resolution_dates": resolution_dates,
            "state_stats": all_states_aggregated,
        }

    def _empty_metrics(self):
        """Return empty metrics structure."""
        return {
            "total_issues": 0,
            "issue_types": {},
            "closing_times": [],
            "created_dates": [],
            "resolution_dates": [],
            "state_stats": {},
        }

    def calculate_velocity(self, project_key, start_date=None, end_date=None, batch_size=50):
        """
        Calculate velocity based on story points.

        Args:
            project_key: Jira project key
            start_date: Start date filter
            end_date: End date filter
            batch_size: Batch size for pagination

        Returns:
            Dictionary with velocity statistics
        """
        jql_stories_parts = [f'project = "{project_key}"', "issuetype = Story"]

        if start_date:
            start_jql = self.convert_date_to_jql(start_date)
            jql_stories_parts.append(f"resolved >= {start_jql}")

        if end_date:
            end_jql = self.convert_date_to_jql(end_date)
            jql_stories_parts.append(f"resolved <= {end_jql}")

        jql_stories = " AND ".join(jql_stories_parts)

        print(f"\n[DEBUG] Story query JQL: {jql_stories}\n")

        story_data = self.fetch_jira_data(jql_stories, max_results=1)
        total_stories = story_data.get("total", 0) if story_data else 0

        if total_stories == 0:
            return {
                "total_stories": 0,
                "stories_with_points": 0,
                "total_story_points": 0,
                "avg_points_per_story": 0,
            }

        all_stories = []
        for start_at in range(0, total_stories, batch_size):
            data = self.fetch_jira_data(
                jql_stories, start_at=start_at, max_results=batch_size, expand="changelog"
            )
            if data and "issues" in data:
                all_stories.extend(data["issues"])

        total_story_points = 0
        stories_with_points = 0

        for story in all_stories:
            story_points = story["fields"].get("customfield_12310243")
            if story_points:
                total_story_points += float(story_points)
                stories_with_points += 1

        return {
            "total_stories": total_stories,
            "stories_with_points": stories_with_points,
            "total_story_points": total_story_points,
            "avg_points_per_story": (
                total_story_points / stories_with_points if stories_with_points > 0 else 0
            ),
        }
