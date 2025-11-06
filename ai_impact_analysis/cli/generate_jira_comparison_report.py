#!/usr/bin/env python3
"""
Generate AI Impact Comparison Report from Jira Reports
Compares three time periods to show AI tools impact
"""

import os
import re
import argparse
from datetime import datetime

from ai_impact_analysis.report_utils import (
    calculate_percentage_change,
    format_metric_changes,
    add_metric_change,
    normalize_username
)


def parse_phase_config(config_path="config/jira_phases.conf"):
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

    # Find the PHASES array (skip commented lines)
    in_array = False
    array_lines = []

    for line in lines:
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("#"):
            continue

        # Start of array
        if "PHASES=(" in line and not stripped.startswith("#"):
            in_array = True
            # Get content after PHASES=(
            array_start = line.split("PHASES=(", 1)[1]
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


def extract_dates_from_jql(jql_query):
    """
    Extract approximate start and end dates from JQL query.
    The JQL uses relative dates like 'resolved >= "-375d" AND resolved <= "-157d"'

    Args:
        jql_query: JQL query string

    Returns:
        tuple: (days_ago_start, days_ago_end) or (None, None) if not found
    """
    # Look for resolved date filters: resolved >= "-XXXd" AND resolved <= "-YYYd"
    start_match = re.search(r'resolved\s*>=\s*"-?(\d+)d"', jql_query, re.IGNORECASE)
    end_match = re.search(r'resolved\s*<=\s*"-?(\d+)d"', jql_query, re.IGNORECASE)

    if start_match and end_match:
        days_ago_start = int(start_match.group(1))
        days_ago_end = int(end_match.group(1))
        return (days_ago_start, days_ago_end)

    return (None, None)


def create_empty_jira_report(phase_name, start_date, end_date):
    """
    Create an empty Jira report structure with zero values for a phase with no data.

    Args:
        phase_name: Name of the phase
        start_date: Start date string
        end_date: End date string

    Returns:
        Dictionary with empty/zero report data
    """
    return {
        "filename": f"(no data for {phase_name})",
        "assignee": None,
        "jql_query": None,
        "time_range": {
            "earliest_created": "N/A",
            "earliest_resolved": "N/A",
            "latest_resolved": "N/A",
            "span_days": 0
        },
        "issue_types": {},
        "total_issues": 0,
        "closure_stats": {
            "avg_days": 0,
            "max_days": 0
        },
        "state_times": {},
        "state_reentry": {},
        "start_date": start_date,
        "end_date": end_date,
    }


def parse_jira_report(filename):
    """Parse a Jira report file and extract key metrics"""
    data = {
        "filename": filename,
        "assignee": None,
        "jql_query": None,
        "time_range": {},
        "issue_types": {},
        "total_issues": 0,
        "closure_stats": {},
        "state_times": {},
        "state_reentry": {},
        "start_date": None,
        "end_date": None,
    }

    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.split("\n")

    # Extract assignee if present
    for line in lines:
        if line.startswith("Assignee:"):
            data["assignee"] = line.split(":", 1)[1].strip()
        elif line.startswith("JQL Query:"):
            data["jql_query"] = line.split(":", 1)[1].strip()
        elif line.startswith("Total:"):
            match = re.search(r"Total:\s*(\d+)", line)
            if match:
                data["total_issues"] = int(match.group(1))
        elif line.startswith("Average Closure Time:"):
            match = re.search(r"Average Closure Time:\s*([\d.]+)\s*days", line)
            if match:
                data["closure_stats"]["avg_days"] = float(match.group(1))
        elif line.startswith("Longest Closure Time:"):
            match = re.search(r"Longest Closure Time:\s*([\d.]+)\s*days", line)
            if match:
                data["closure_stats"]["max_days"] = float(match.group(1))
        elif line.startswith("Earliest Created:"):
            data["time_range"]["earliest_created"] = line.split(":", 1)[1].strip()
        elif line.startswith("Earliest Resolved:"):
            data["time_range"]["earliest_resolved"] = line.split(":", 1)[1].strip()
        elif line.startswith("Latest Resolved:"):
            data["time_range"]["latest_resolved"] = line.split(":", 1)[1].strip()
        elif line.startswith("Data Span:"):
            match = re.search(r"Data Span:\s*(\d+)\s*days", line)
            if match:
                data["time_range"]["span_days"] = int(match.group(1))

    # Parse issue types
    in_issue_types = False
    for i, line in enumerate(lines):
        if line.startswith("--- Issue Type Statistics ---"):
            in_issue_types = True
            continue
        if in_issue_types:
            if line.startswith("---"):
                break
            match = re.match(r"\s*(Story|Task|Bug|Epic|Sub-task)\s+(\d+)\s*\(\s*([\d.]+)%\)", line)
            if match:
                issue_type, count, percentage = match.groups()
                data["issue_types"][issue_type] = {
                    "count": int(count),
                    "percentage": float(percentage),
                }

    # Parse state times and re-entry rates
    in_state_analysis = False
    for i, line in enumerate(lines):
        if "State" in line and "Occurrences" in line and "Avg Duration" in line:
            in_state_analysis = True
            continue
        if in_state_analysis:
            if line.startswith("---"):
                break
            # Parse state time line - need to handle multi-word state names
            # Line format: "State Name      count1      count2      avg_time      total_time"
            # Extract state name from the beginning (before the numeric columns)
            line_stripped = line.strip()
            if (
                line_stripped
                and not line_stripped.startswith("State")
                and not line_stripped.startswith("=")
            ):
                # Use regex to extract state name and average time
                # Match pattern: state_name (any text) followed by numbers, then avg time in days/hours
                match = re.match(
                    r"^(\S+(?:\s+\S+)?)\s+(\d+)\s+(\d+)\s+([-\d.]+)\s*(days|hours)", line_stripped
                )
                if match:
                    state_name = match.group(1).strip()
                    avg_time = float(match.group(4))
                    time_unit = match.group(5)
                    # Convert hours to days if needed
                    if time_unit == "hours":
                        avg_days = avg_time / 24.0
                    else:
                        avg_days = avg_time
                    # Only store positive values (skip negative times like "Closed" state)
                    if avg_days > 0:
                        data["state_times"][state_name] = avg_days

    # Parse re-entry rates from detailed analysis
    current_state = None
    for line in lines:
        if line.strip().endswith(":") and not line.startswith("-"):
            state_candidate = line.strip().rstrip(":")
            if state_candidate in [
                "To Do",
                "In Progress",
                "Review",
                "New",
                "Waiting",
                "Release Pending",
                "Backlog",
                "Closed",
                "Code Review",
                "Refinement",
            ]:
                current_state = state_candidate
        elif current_state and "Average times per issue entering this state" in line:
            match = re.search(r"([\d.]+)\s*times", line)
            if match:
                data["state_reentry"][current_state] = float(match.group(1))

    return data


def extract_period_info(jql_query):
    """Extract period information from JQL query"""
    # Look for resolved date filters
    start_match = re.search(r'resolved\s*>=\s*"?-(\d+)d"?', jql_query, re.IGNORECASE)
    end_match = re.search(r'resolved\s*<=\s*"?-(\d+)d"?', jql_query, re.IGNORECASE)

    if start_match and end_match:
        start_days = int(start_match.group(1))
        end_days = int(end_match.group(1))
        period_days = start_days - end_days
        return f"~{period_days} days"

    return "N/A"


def generate_csv_report(reports, assignee=None):
    """Generate a CSV format comparison report"""
    # Parse phase configuration - this is the source of truth for phases
    phase_config = parse_phase_config()

    if not phase_config:
        print("Error: Could not parse phase configuration from config/jira_phases.conf")
        print("Please ensure the config file exists and has valid PHASES entries.")
        return None

    # Build a dictionary of existing reports by their actual date ranges
    reports_by_dates = {}
    for report in reports:
        earliest = report["time_range"].get("earliest_resolved")
        latest = report["time_range"].get("latest_resolved")
        if earliest and latest:
            # Use the date range as key
            key = f"{earliest}_{latest}"
            reports_by_dates[key] = report

    # Create phase_reports list based on config phases
    # For each phase in config, use existing report if available, otherwise create empty
    phase_reports = []
    phase_names = []

    for phase_name, start_date, end_date in phase_config:
        # Try to find a matching report (simple check - if report exists, use it)
        # Since reports list is ordered by filename (which follows phase order),
        # we can try to match by index position as a heuristic
        matching_report = None
        phase_index = len(phase_reports)  # Current phase index

        if phase_index < len(reports):
            # Use the report at this index position
            matching_report = reports[phase_index]
            print(f"Using report data for phase '{phase_name}'")

        if matching_report:
            phase_reports.append(matching_report)
        else:
            # No report data for this phase - create empty report
            print(f"No data found for phase '{phase_name}', using zero values")
            phase_reports.append(create_empty_jira_report(phase_name, start_date, end_date))

        phase_names.append(phase_name)

    # Use phase_reports instead of reports for the rest of the function
    reports = phase_reports

    # Build output
    output = []

    # Header
    if assignee:
        output.append(f"AI Impact Analysis Report - {assignee}")
    else:
        output.append("AI Impact Analysis Report - Team Overall")
    output.append(f"Report Generated: {datetime.now().strftime('%B %d, %Y')}")
    output.append("Project: Konflux UI")
    output.append("")
    output.append("This report analyzes development data across three distinct periods to evaluate")
    output.append("the impact of AI tools on team efficiency:")
    output.append("")

    # Display phase information using config dates (source of truth)
    for i, (phase_name, start_date, end_date) in enumerate(phase_config):
        output.append(f"Phase {i+1}: {phase_name} ({start_date} to {end_date})")

    output.append("")

    # Metrics table (using tabs for TSV format)
    header = "Metric\t" + "\t".join(phase_names)
    output.append(header)

    # Period duration - calculate from resolved dates
    periods = []
    for r in reports:
        earliest = r["time_range"].get("earliest_resolved", "N/A")
        latest = r["time_range"].get("latest_resolved", "N/A")
        if earliest != "N/A" and latest != "N/A":
            try:
                start = datetime.strptime(earliest.split()[0], "%Y-%m-%d")
                end = datetime.strptime(latest.split()[0], "%Y-%m-%d")
                period_days = (end - start).days
                periods.append(f"{period_days}d")
            except Exception:
                periods.append("N/A")
        else:
            periods.append("N/A")

    output.append("Analysis Period\t" + "\t".join(periods))

    # Total issues
    issues = [r["total_issues"] for r in reports]
    output.append("Total Issues Completed\t" + "\t".join(str(i) for i in issues))

    # Average closure time
    avg_times = [r["closure_stats"].get("avg_days", 0) for r in reports]
    output.append("Average Closure Time\t" + "\t".join(f"{t:.2f}d" for t in avg_times))

    # Longest closure time
    max_times = [r["closure_stats"].get("max_days", 0) for r in reports]
    output.append("Longest Closure Time\t" + "\t".join(f"{t:.2f}d" for t in max_times))

    # Daily throughput
    throughputs = []
    for i, report in enumerate(reports):
        period = periods[i]
        if period != "N/A" and period.endswith("d"):
            days = int(period.replace("d", ""))
            throughput = report["total_issues"] / days if days > 0 else 0
            throughputs.append(f"{throughput:.2f}/d")
        else:
            throughputs.append("N/A")
    output.append("Daily Throughput\t" + "\t".join(throughputs))

    # State times
    state_names = ["New", "To Do", "In Progress", "Review", "Release Pending", "Waiting"]
    for state in state_names:
        values = []
        for report in reports:
            time = report["state_times"].get(state, 0)
            if time > 0:
                values.append(f"{time:.2f}d")
            else:
                values.append("N/A")
        output.append(f"{state} State Avg Time\t" + "\t".join(values))

    # Re-entry rates
    reentry_states = ["To Do", "In Progress", "Review", "Waiting"]
    for state in reentry_states:
        values = []
        for report in reports:
            rate = report["state_reentry"].get(state, 0)
            if rate > 0:
                values.append(f"{rate:.2f}x")
            else:
                values.append("N/A")
        output.append(f"{state} Re-entry Rate\t" + "\t".join(values))

    # Issue types
    issue_types = ["Story", "Task", "Bug", "Epic"]
    for itype in issue_types:
        values = []
        for report in reports:
            if itype in report["issue_types"]:
                values.append(f"{report['issue_types'][itype]['percentage']:.2f}%")
            else:
                values.append("0.00%")
        output.append(f"{itype} Percentage\t" + "\t".join(values))

    output.append("")
    output.append("Note: N/A values indicate no issues entered that workflow state during the period.")
    output.append("This can be positive (e.g., no blocked issues) or indicate the state isn't used in your workflow.")
    output.append("")

    # Key changes - objectively show top 5 increases and top 5 decreases
    # No subjective judgment of "positive" or "negative"
    output.append("Key Changes:")

    # Collect all metrics with valid data for comparison
    metric_changes = []

    # Average Closure Time
    if len(avg_times) >= 2 and avg_times[0] > 0:
        add_metric_change(metric_changes, "Average Closure Time",
                         avg_times[0], avg_times[-1], "d")

    # Daily Throughput
    if len(throughputs) >= 2:
        try:
            before_tp = float(throughputs[0].replace("/d", ""))
            after_tp = float(throughputs[-1].replace("/d", ""))
            if before_tp > 0:
                add_metric_change(metric_changes, "Daily Throughput",
                                 before_tp, after_tp, "/d")
        except (ValueError, AttributeError):
            pass

    # State times
    for state in ["New", "To Do", "In Progress", "Review", "Release Pending", "Waiting"]:
        state_vals = [r["state_times"].get(state, 0) for r in reports]
        if len(state_vals) >= 2 and state_vals[0] > 0:
            add_metric_change(metric_changes, f"{state} State",
                             state_vals[0], state_vals[-1], "d")

    # Re-entry rates
    for state in ["To Do", "In Progress", "Review", "Waiting"]:
        reentry_vals = [r["state_reentry"].get(state, 0) for r in reports]
        if len(reentry_vals) >= 2 and reentry_vals[0] > 0:
            add_metric_change(metric_changes, f"{state} Re-entry Rate",
                             reentry_vals[0], reentry_vals[-1], "x")

    # Format and display metric changes
    output.extend(format_metric_changes(metric_changes, top_n=5))

    output.append("")
    output.append("For detailed metric explanations, see:")
    output.append("https://github.com/testcara/ai_impact_analysis#jira-report-metrics")

    return "\n".join(output)


def find_reports(assignee=None):
    """Find all matching Jira report files"""
    files = []

    # Look in reports/jira directory (matching PR report structure)
    reports_dir = "reports/jira"
    if not os.path.exists(reports_dir):
        return files

    for filename in os.listdir(reports_dir):
        if not filename.startswith("jira_report_"):
            continue
        if not filename.endswith(".txt"):
            continue

        if assignee:
            # Normalize username for matching
            username = normalize_username(assignee)
            # Look for assignee-specific reports using normalized username
            # Pattern: jira_report_username_YYYYMMDD_HHMMSS.txt
            if f"jira_report_{username}_" in filename:
                files.append(os.path.join(reports_dir, filename))
        else:
            # Look for general reports
            # Pattern: jira_report_general_YYYYMMDD_HHMMSS.txt
            if "jira_report_general_" in filename:
                files.append(os.path.join(reports_dir, filename))

    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI Impact Comparison Report from Jira reports"
    )
    parser.add_argument(
        "--assignee",
        type=str,
        help="Filter by assignee (e.g., sbudhwar or sbudhwar@redhat.com)",
        default=None,
    )
    parser.add_argument(
        "--output", type=str, help="Output filename (default: auto-generated)", default=None
    )

    args = parser.parse_args()

    # Find matching reports
    report_files = find_reports(args.assignee)

    if len(report_files) == 0:
        if args.assignee:
            print(f"Error: No reports found for assignee '{args.assignee}'")
        else:
            print("Error: No general reports found")
        print("\nLooking for files matching pattern:")
        if args.assignee:
            username = normalize_username(args.assignee)
            print(f"  reports/jira/jira_report_{username}_*.txt")
        else:
            print("  reports/jira/jira_report_general_*.txt")
        return 1

    if len(report_files) < 2:
        print(f"Warning: Found only {len(report_files)} report(s), need at least 2 for comparison")
        print(f"Found: {', '.join(report_files)}")
        return 1

    # Use all reports if <= 4, otherwise use the most recent 4
    if len(report_files) > 4:
        print(f"Found {len(report_files)} reports, using the 4 most recent for comparison:")
        report_files = sorted(report_files)[-4:]
    else:
        report_files = sorted(report_files)

    print(f"Analyzing {len(report_files)} reports:")
    for i, f in enumerate(report_files, 1):
        print(f"  Phase {i}: {f}")
    print()

    # Parse reports
    reports = []
    for filename in report_files:
        print(f"Parsing {filename}...")
        data = parse_jira_report(filename)
        reports.append(data)

    # Generate comparison report
    print("\nGenerating comparison report...")
    report_text = generate_csv_report(reports, args.assignee)

    # Determine output filename
    # Create output directory (matching PR report structure)
    output_dir = "reports/jira"
    os.makedirs(output_dir, exist_ok=True)

    if args.output:
        output_file = args.output
    else:
        # Extract timestamp from the last (most recent) report file to maintain consistency
        last_report_file = os.path.basename(report_files[-1])
        # Extract timestamp from filename pattern: jira_report_{username}_{timestamp}.txt
        timestamp_match = re.search(r"_(\d{8}_\d{6})\.txt$", last_report_file)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
        else:
            # Fallback to current time if pattern doesn't match
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Use jira_comparison_* naming to match pr_comparison_* pattern
        if args.assignee:
            username = normalize_username(args.assignee)
            output_file = os.path.join(output_dir, f"jira_comparison_{username}_{timestamp}.tsv")
        else:
            output_file = os.path.join(output_dir, f"jira_comparison_general_{timestamp}.tsv")

    # Write output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    print(f"\n✓ Report generated: {output_file}")
    print("\nYou can now:")
    print(f"  1. Open {output_file} in any text editor")
    print("  2. Copy all content (Ctrl+A, Ctrl+C)")
    print("  3. Paste directly into Google Sheets (no need to split columns)")
    print("  4. The data will automatically be placed in separate columns")

    return 0


if __name__ == "__main__":
    exit(main())
