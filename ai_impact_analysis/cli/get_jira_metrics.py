import requests
import json
import argparse
import os
from datetime import datetime

from ai_impact_analysis.report_utils import normalize_username

# --- Configuration (read from environment variables) ---
JIRA_URL = os.getenv("JIRA_URL", "https://issues.redhat.com")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "Konflux UI")

# Use Bearer Token authentication (matching test_auth.py approach)
headers = {"Accept": "application/json", "authorization": f"Bearer {JIRA_API_TOKEN}"}


def fetch_jira_data(jql_query, start_at=0, max_results=50, expand=None):
    """
    Generic function for fetching Jira issue data with pagination.
    """
    url = f"{JIRA_URL}/rest/api/2/search"

    # Build query parameters
    params = {
        "jql": jql_query,
        "fields": "created,resolutiondate,status,issuetype,timeoriginalestimate,timetracking",  # Fields to fetch
        "startAt": start_at,
        "maxResults": max_results,
    }

    if expand:
        params["expand"] = expand

    # DEBUG: Print full request information
    print("\n[DEBUG] === Jira API Request ===")
    print(f"[DEBUG] URL: {url}")
    print(f"[DEBUG] JQL Query: {jql_query}")
    print("[DEBUG] Parameters:")
    for key, value in params.items():
        print(f"[DEBUG]   {key}: {value}")
    print("[DEBUG] =========================\n")

    try:
        response = requests.get(url, headers=headers, params=params)

        # DEBUG: Print response status
        print(f"[DEBUG] Response Status Code: {response.status_code}")
        print(f"[DEBUG] Response URL: {response.url}")

        if not response.ok:
            print(f"[DEBUG] Error Response: {response.text}")

        response.raise_for_status()  # Check for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Jira data: {e}")
        print(f"[DEBUG] Request failed with exception: {type(e).__name__}")
        if hasattr(e, "response") and e.response is not None:
            print(f"[DEBUG] Response text: {e.response.text}")
        return None


def calculate_state_durations(issue):
    """
    Calculate the time spent in each state for an issue and the number of occurrences.
    Returns a dictionary containing total time (seconds) and occurrence count for each state.
    """
    state_stats = {}

    # Get changelog
    changelog = issue.get("changelog", {})
    histories = changelog.get("histories", [])

    # Get creation time and current status
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

    # Find all status changes
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

    # Sort by time
    status_transitions.sort(key=lambda x: x["date"])

    # Determine initial status (from status of first transition, or current status if no transitions)
    if status_transitions:
        initial_status = status_transitions[0]["from"]
    else:
        initial_status = current_status

    # Calculate time spent in each state
    current_state = initial_status
    current_state_start = created_date

    # Initialize first state
    if current_state:
        if current_state not in state_stats:
            state_stats[current_state] = {"total_seconds": 0, "count": 0}
        state_stats[current_state]["count"] += 1

    # Process all state transitions
    for transition in status_transitions:
        if current_state:
            duration = (transition["date"] - current_state_start).total_seconds()
            state_stats[current_state]["total_seconds"] += duration

        current_state = transition["to"]
        current_state_start = transition["date"]

        # Record new state
        if current_state not in state_stats:
            state_stats[current_state] = {"total_seconds": 0, "count": 0}
        state_stats[current_state]["count"] += 1

    # Calculate time for last state (to resolution time or current time)
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


# --- Parse command line arguments ---
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

# Use command line argument or value from config file
project_key = args.project if args.project else PROJECT_KEY


def convert_date_to_jql(date_str):
    """
    Convert YYYY-MM-DD format date to Jira JQL relative time expression.
    Example: 2024-01-15 -> "-300d" (if 300 days ago)
    """
    if not date_str:
        return None

    try:
        input_date = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now()

        # Calculate day difference
        days_diff = (today - input_date).days

        if days_diff == 0:
            return "startOfDay()"
        elif days_diff > 0:
            # Past date, use -Xd format
            return f'"-{days_diff}d"'
        else:
            # Future date (although uncommon)
            return f'"{abs(days_diff)}d"'
    except ValueError:
        # If format is incorrect, return original string
        return f'"{date_str}"'


# Build JQL query
jql_parts = [f'project = "{project_key}"']

# Add assignee filter
if args.assignee:
    jql_parts.append(f'assignee = "{args.assignee}"')
    print(f"Filtering by assignee: {args.assignee}")
elif args.limit_team_members:
    # Load team members from config file and build OR query
    team_members = []
    try:
        with open(args.limit_team_members, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    # Remove trailing comma if present
                    member = line.rstrip(',').strip()
                    if member:
                        team_members.append(member)

        if team_members:
            # Build OR query: (assignee = "user1" OR assignee = "user2" OR ...)
            assignee_conditions = ' OR '.join([f'assignee = "{member}"' for member in team_members])
            jql_parts.append(f'({assignee_conditions})')
            print(f"Limiting to team members from config: {len(team_members)} members")
            print(f"Team members: {', '.join(team_members)}")
        else:
            print("Warning: No team members found in config file, querying all issues")
    except FileNotFoundError:
        print(f"Warning: Team members file not found: {args.limit_team_members}")
        print("Continuing without team member filter")
    except Exception as e:
        print(f"Warning: Error reading team members file: {e}")
        print("Continuing without team member filter")

# Use resolved field (resolution date) to filter completed tasks
# Note: If resolved date filter is specified, no need to specify status, as issues with resolved dates are already resolved
if args.start or args.end:
    # When resolved date filter is present, don't add status condition
    if args.start:
        start_jql = convert_date_to_jql(args.start)
        jql_parts.append(f"resolved >= {start_jql}")
        print(f"Start date {args.start} converted to: {start_jql}")

    if args.end:
        end_jql = convert_date_to_jql(args.end)
        jql_parts.append(f"resolved <= {end_jql}")
        print(f"End date {args.end} converted to: {end_jql}")
else:
    # Only use status parameter when no resolved date filter
    if args.status:
        jql_parts.append(f'status = "{args.status}"')

JQL_DONE_ISSUES = " AND ".join(jql_parts)

print(f"\nUsing JQL query: {JQL_DONE_ISSUES}\n")

# First request to get total count
initial_data = fetch_jira_data(JQL_DONE_ISSUES, max_results=1)
total_issues = initial_data.get("total", 0) if initial_data else 0

# Loop to fetch all data, then calculate time difference (resolutiondate - created)
all_issues = []
batch_size = 50

print(f"Total issues found for analysis: {total_issues}")

if total_issues > 0:
    for start_at in range(0, total_issues, batch_size):
        print(f"Fetching issues {start_at} to {min(start_at + batch_size, total_issues)}...")
        # Add changelog expansion to get status transition history
        data = fetch_jira_data(
            JQL_DONE_ISSUES, start_at=start_at, max_results=batch_size, expand="changelog"
        )
        if data and "issues" in data:
            all_issues.extend(data["issues"])
        else:
            print(f"Failed to fetch batch starting at {start_at}")
            break

    # Collect data overview information
    closing_times = []
    created_dates = []
    resolution_dates = []
    issue_types = {}

    for issue in all_issues:
        try:
            created_str = issue["fields"].get("created")
            resolution_str = issue["fields"].get("resolutiondate")
            issue_type = issue["fields"].get("issuetype", {}).get("name", "Unknown")

            # Count issue types
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

    # Start generating report content
    report_lines = []
    report_lines.append("=" * 100)
    if args.assignee:
        report_lines.append(f"JIRA Data Analysis Report - {args.assignee}")
    else:
        report_lines.append("JIRA Data Analysis Report")
    report_lines.append("=" * 100)
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Project: {project_key}")
    if args.assignee:
        report_lines.append(f"Assignee: {args.assignee}")
    report_lines.append(f"JQL Query: {JQL_DONE_ISSUES}\n")

    # Data Time Range
    report_lines.append("\n--- Data Time Range ---")
    if created_dates and resolution_dates:
        earliest_created = min(created_dates)
        latest_created = max(created_dates)
        earliest_resolved = min(resolution_dates)
        latest_resolved = max(resolution_dates)

        report_lines.append(f"Earliest Created: {earliest_created.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Latest Created: {latest_created.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Earliest Resolved: {earliest_resolved.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Latest Resolved: {latest_resolved.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Data Span: {(latest_resolved - earliest_created).days} days")

    # Issue type statistics
    report_lines.append("\n--- Issue Type Statistics ---")
    report_lines.append(f"Total: {len(all_issues)} issues")
    sorted_types = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
    for issue_type, count in sorted_types:
        percentage = (count / len(all_issues)) * 100
        report_lines.append(f"  {issue_type:<20} {count:>5} ({percentage:>5.1f}%)")

    if closing_times:
        avg_closing_time_seconds = sum(closing_times) / len(closing_times)
        avg_closing_time_days = avg_closing_time_seconds / (24 * 3600)
        avg_closing_time_hours = avg_closing_time_seconds / 3600

        # Calculate min and max values
        min_time_days = min(closing_times) / (24 * 3600)
        max_time_days = max(closing_times) / (24 * 3600)

        report_lines.append("\n--- Task Closure Time Statistics ---")
        report_lines.append(f"Successfully analyzed issues: {len(closing_times)}")
        report_lines.append(
            f"Average Closure Time: {avg_closing_time_days:.2f} days ({avg_closing_time_hours:.2f} hours)"
        )
        report_lines.append(f"Shortest Closure Time: {min_time_days:.2f} days")
        report_lines.append(f"Longest Closure Time: {max_time_days:.2f} days")
    else:
        report_lines.append("\nNo valid closing time data found.")

    # Analyze State Duration
    report_lines.append("\n--- State Duration Analysis ---")
    all_states_aggregated = {}

    for issue in all_issues:
        issue_key = issue.get("key", "unknown")
        state_stats = calculate_state_durations(issue)

        # Aggregate status data from all issues
        for state, stats in state_stats.items():
            if state not in all_states_aggregated:
                all_states_aggregated[state] = {
                    "total_seconds": 0,
                    "total_count": 0,
                    "issue_count": 0,  # How many issues have been through this state
                }
            all_states_aggregated[state]["total_seconds"] += stats["total_seconds"]
            all_states_aggregated[state]["total_count"] += stats["count"]
            all_states_aggregated[state]["issue_count"] += 1

    if all_states_aggregated:
        # Sort by average duration
        sorted_states = sorted(
            all_states_aggregated.items(),
            key=lambda x: x[1]["total_seconds"] / x[1]["issue_count"],
            reverse=True,
        )

        report_lines.append(f"\nAnalyzed {len(all_issues)} issues state transitions")
        report_lines.append(
            f"\n{'State':<20} {'Occurrences':<12} {'Issues Affected':<15} {'Avg Duration':<20} {'Total Duration':<20}"
        )
        report_lines.append("=" * 100)

        for state, stats in sorted_states:
            avg_seconds = stats["total_seconds"] / stats["issue_count"]
            avg_days = avg_seconds / (24 * 3600)
            avg_hours = avg_seconds / 3600
            total_days = stats["total_seconds"] / (24 * 3600)
            total_hours = stats["total_seconds"] / 3600

            # Format time display
            if avg_days >= 1:
                avg_time_str = f"{avg_days:.2f} days"
            else:
                avg_time_str = f"{avg_hours:.2f} hours"

            if total_days >= 1:
                total_time_str = f"{total_days:.2f} days"
            else:
                total_time_str = f"{total_hours:.2f} hours"

            report_lines.append(
                f"{state:<20} {stats['total_count']:<12} {stats['issue_count']:<15} {avg_time_str:<20} {total_time_str:<20}"
            )

        # Output detailed state transitions analysis
        report_lines.append("\n--- Detailed State Analysis ---")
        for state, stats in sorted_states:
            avg_transitions = stats["total_count"] / stats["issue_count"]
            report_lines.append(f"\n{state}:")
            report_lines.append(f"  - {stats['issue_count']} issues experienced this state")
            report_lines.append(f"  - Average times per issue entering this state {avg_transitions:.2f} times")
            if avg_transitions > 1.5:
                report_lines.append("  ⚠️  Warning: This state was entered multiple times, indicating possible back-and-forth transitions")
    else:
        report_lines.append("Unable to retrieve state transition data")

    # Print all reports to console
    for line in report_lines:
        print(line)

    # Save report to text file
    # Create output directory
    import os

    # Match PR report structure: reports/jira/ (like reports/github/)
    output_dir = "reports/jira"
    os.makedirs(output_dir, exist_ok=True)

    if args.assignee:
        # Normalize username for filename
        username = normalize_username(args.assignee)
        report_filename = os.path.join(
            output_dir, f'jira_report_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )
    else:
        report_filename = os.path.join(
            output_dir, f'jira_report_general_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )

    try:
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"\nReport saved to: {report_filename}")
    except Exception as e:
        print(f"\nError saving report: {e}")
else:
    print("No issues found matching the criteria.")

    # Generate report with N/A values for 0 issues
    report_lines = []
    report_lines.append("=" * 100)
    if args.assignee:
        report_lines.append(f"JIRA Data Analysis Report - {args.assignee}")
    else:
        report_lines.append("JIRA Data Analysis Report")
    report_lines.append("=" * 100)
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Project: {project_key}")
    if args.assignee:
        report_lines.append(f"Assignee: {args.assignee}")
    report_lines.append(f"JQL Query: {JQL_DONE_ISSUES}\n")

    # Data Time Range
    report_lines.append("\n--- Data Time Range ---")
    report_lines.append("Earliest Created: N/A")
    report_lines.append("Latest Created: N/A")
    report_lines.append("Earliest Resolved: N/A")
    report_lines.append("Latest Resolved: N/A")
    report_lines.append("Data Span: 0 days")

    # Issue type statistics
    report_lines.append("\n--- Issue Type Statistics ---")
    report_lines.append("Total: 0 issues")

    # Task Closure Time Statistics
    report_lines.append("\n--- Task Closure Time Statistics ---")
    report_lines.append("Successfully analyzed issues: 0")
    report_lines.append("Average Closure Time: N/A")
    report_lines.append("Shortest Closure Time: N/A")
    report_lines.append("Longest Closure Time: N/A")

    # State Duration Analysis
    report_lines.append("\n--- State Duration Analysis ---")
    report_lines.append("\nAnalyzed 0 issues state transitions")
    report_lines.append(
        f"\n{'State':<20} {'Occurrences':<12} {'Issues Affected':<15} {'Avg Duration':<20} {'Total Duration':<20}"
    )
    report_lines.append("=" * 100)
    report_lines.append("(No state data available)")

    # Detailed State Analysis
    report_lines.append("\n--- Detailed State Analysis ---")
    report_lines.append("\n(No detailed state data available - 0 issues analyzed)")

    # Print to console
    for line in report_lines:
        print(line)

    # Save report to text file
    import os

    output_dir = "reports/jira"
    os.makedirs(output_dir, exist_ok=True)

    if args.assignee:
        username = normalize_username(args.assignee)
        report_filename = os.path.join(
            output_dir, f'jira_report_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )
    else:
        report_filename = os.path.join(
            output_dir, f'jira_report_general_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        )

    try:
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"\nReport saved to: {report_filename}")
    except Exception as e:
        print(f"\nError saving report: {e}")

# --- Example: Calculate Velocity (requires extraction from Sprint data, may need specific Jira Software API endpoints) ---
# Velocity retrieval typically requires specific Jira Software API, more complex than general search, may need specific permissions.
print("\n--- Velocity Calculation (Based on Story Points) ---")
# Get completed Stories and count Story Points
jql_stories_parts = [f'project = "{project_key}"', "issuetype = Story"]

if args.start:
    start_jql = convert_date_to_jql(args.start)
    jql_stories_parts.append(f"resolved >= {start_jql}")

if args.end:
    end_jql = convert_date_to_jql(args.end)
    jql_stories_parts.append(f"resolved <= {end_jql}")

JQL_STORIES = " AND ".join(jql_stories_parts)

print(f"\n[DEBUG] Story query JQL: {JQL_STORIES}\n")

story_data = fetch_jira_data(JQL_STORIES, max_results=1)
total_stories = story_data.get("total", 0) if story_data else 0

if total_stories > 0:
    all_stories = []
    for start_at in range(0, total_stories, batch_size):
        data = fetch_jira_data(
            JQL_STORIES, start_at=start_at, max_results=batch_size, expand="changelog"
        )
        if data and "issues" in data:
            all_stories.extend(data["issues"])

    # Try to extract Story Points (field name may vary by configuration, commonly customfield_xxxxx)
    # You need to check the Story Points field name in your Jira instance
    total_story_points = 0
    stories_with_points = 0

    for story in all_stories:
        story_points = story["fields"].get("customfield_12310243")
        if story_points:
            total_story_points += float(story_points)
            stories_with_points += 1

    print(f"Completed Stories Count: {total_stories}")
    print(f"Stories with Story Points: {stories_with_points}")
    print(f"Total Story Points: {total_story_points}")
    if stories_with_points > 0:
        print(f"Average Points per Story: {total_story_points / stories_with_points:.2f}")
else:
    print("No stories found matching the criteria.")

# --- Save analysis results to JSON file ---
print("\n--- Save Analysis Results ---")
try:
    output_data = {
        "analysis_date": datetime.now().isoformat(),
        "project_key": project_key,
        "query_parameters": {
            "start_date": args.start,
            "end_date": args.end,
            "status": args.status,
            "assignee": args.assignee,
        },
        "jql_queries": {
            "main_analysis": JQL_DONE_ISSUES,
            "velocity_calculation": JQL_STORIES if "JQL_STORIES" in locals() else None,
        },
        "jql_query": JQL_DONE_ISSUES,  # Kept for backward compatibility
        "total_issues_analyzed": len(all_issues) if "all_issues" in locals() else 0,
        "closing_time_stats": {
            "average_days": avg_closing_time_days if "avg_closing_time_days" in locals() else None,
            "average_hours": (
                avg_closing_time_hours if "avg_closing_time_hours" in locals() else None
            ),
            "min_days": min_time_days if "min_time_days" in locals() else None,
            "max_days": max_time_days if "max_time_days" in locals() else None,
        },
        "state_statistics": {},
        "velocity_stats": {
            "query_used": JQL_STORIES if "JQL_STORIES" in locals() else None,
            "total_stories": total_stories if "total_stories" in locals() else 0,
            "total_story_points": total_story_points if "total_story_points" in locals() else 0,
            "stories_with_points": stories_with_points if "stories_with_points" in locals() else 0,
        },
    }

    # Add state statistics
    if "all_states_aggregated" in locals():
        for state, stats in all_states_aggregated.items():
            avg_seconds = stats["total_seconds"] / stats["issue_count"]
            output_data["state_statistics"][state] = {
                "total_count": stats["total_count"],
                "issue_count": stats["issue_count"],
                "average_seconds": avg_seconds,
                "average_days": avg_seconds / (24 * 3600),
                "average_hours": avg_seconds / 3600,
                "total_seconds": stats["total_seconds"],
                "avg_transitions_per_issue": stats["total_count"] / stats["issue_count"],
            }

    # Create output directory for JSON files (matching PR report structure)
    json_output_dir = "reports/jira"
    os.makedirs(json_output_dir, exist_ok=True)

    # Build filename with assignee and date range (matching pr_metrics_* pattern)
    # Format dates from YYYY-MM-DD to YYYYMMDD
    start_formatted = args.start.replace("-", "")
    end_formatted = args.end.replace("-", "")

    if args.assignee:
        # Normalize username for identifier
        identifier = normalize_username(args.assignee)
    else:
        identifier = "general"

    output_filename = os.path.join(
        json_output_dir, f'jira_metrics_{identifier}_{start_formatted}_{end_formatted}.json'
    )
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"Analysis results saved to: {output_filename}")
except Exception as e:
    print(f"Error saving results: {e}")
