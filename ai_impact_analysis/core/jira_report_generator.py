"""
Jira Report Generator

Generates text and JSON reports from Jira metrics.
Extracted from cli/get_jira_metrics.py and cli/generate_jira_comparison_report.py
"""

import os
import json
import re
from datetime import datetime

from ai_impact_analysis.utils.report_utils import (
    normalize_username,
    calculate_percentage_change,
    format_metric_changes,
    add_metric_change,
)


class JiraReportGenerator:
    """Generates reports from Jira metrics data."""


    def generate_text_report(self, metrics, jql_query, project_key, assignee=None,
                            start_date=None, end_date=None, leave_days=0, capacity=1.0):
        """
        Generate human-readable text report from metrics.

        Args:
            metrics: Metrics dictionary from JiraMetricsCalculator
            jql_query: JQL query used
            project_key: Project key
            assignee: Optional assignee filter
            start_date: Phase start date (YYYY-MM-DD) for Data Span calculation
            end_date: Phase end date (YYYY-MM-DD) for Data Span calculation
            leave_days: Number of leave days
            capacity: Work capacity (0.0 to 1.0, default 1.0 = full time)

        Returns:
            String report
        """
        report_lines = []
        report_lines.append("=" * 100)
        if assignee:
            report_lines.append(f"JIRA Data Analysis Report - {assignee}")
        else:
            report_lines.append("JIRA Data Analysis Report")
        report_lines.append("=" * 100)
        report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Project: {project_key}")
        if assignee:
            report_lines.append(f"Assignee: {assignee}")
        report_lines.append(f"JQL Query: {jql_query}\n")

        # Data Time Range
        report_lines.append("\n--- Data Time Range ---")

        if start_date and end_date:
            # Show phase configuration dates
            report_lines.append(f"Start: {start_date}")
            report_lines.append(f"End: {end_date}")

            # Calculate phase days
            phase_start = datetime.strptime(start_date, '%Y-%m-%d')
            phase_end = datetime.strptime(end_date, '%Y-%m-%d')
            phase_days = (phase_end - phase_start).days + 1  # Inclusive

            # Show leave days info
            if leave_days > 0:
                report_lines.append(f"Leave Days: {leave_days} days")
            else:
                report_lines.append(f"Leave Days: 0 days")

            # Show capacity
            report_lines.append(f"Capacity: {capacity}")

            # Data Span is always END - START (inclusive)
            report_lines.append(f"Data Span: {phase_days} days")
        else:
            # Fallback when no phase dates provided
            report_lines.append("Start: N/A")
            report_lines.append("End: N/A")
            report_lines.append("Leave Days: 0 days")
            report_lines.append("Capacity: 1.0")
            report_lines.append("Data Span: N/A")

        # Issue type statistics
        report_lines.append("\n--- Issue Type Statistics ---")
        total_issues = metrics.get("total_issues", 0)
        issue_types = metrics.get("issue_types", {})

        report_lines.append(f"Total: {total_issues} issues")
        if issue_types:
            sorted_types = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
            for issue_type, count in sorted_types:
                percentage = (count / total_issues) * 100 if total_issues > 0 else 0
                report_lines.append(f"  {issue_type:<20} {count:>5} ({percentage:>5.1f}%)")

        # Task Closure Time Statistics
        closing_times = metrics.get("closing_times", [])
        report_lines.append("\n--- Task Closure Time Statistics ---")

        if closing_times:
            avg_closing_time_seconds = sum(closing_times) / len(closing_times)
            avg_closing_time_days = avg_closing_time_seconds / (24 * 3600)
            avg_closing_time_hours = avg_closing_time_seconds / 3600
            min_time_days = min(closing_times) / (24 * 3600)
            max_time_days = max(closing_times) / (24 * 3600)

            report_lines.append(f"Successfully analyzed issues: {len(closing_times)}")
            report_lines.append(
                f"Average Closure Time: {avg_closing_time_days:.2f} days ({avg_closing_time_hours:.2f} hours)"
            )
            report_lines.append(f"Shortest Closure Time: {min_time_days:.2f} days")
            report_lines.append(f"Longest Closure Time: {max_time_days:.2f} days")
        else:
            report_lines.append("Successfully analyzed issues: 0")
            report_lines.append("Average Closure Time: N/A")
            report_lines.append("Shortest Closure Time: N/A")
            report_lines.append("Longest Closure Time: N/A")

        # State Duration Analysis
        report_lines.append("\n--- State Duration Analysis ---")
        state_stats = metrics.get("state_stats", {})

        if state_stats:
            sorted_states = sorted(
                state_stats.items(),
                key=lambda x: x[1]["total_seconds"] / x[1]["issue_count"],
                reverse=True,
            )

            report_lines.append(f"\nAnalyzed {total_issues} issues state transitions")
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

            # Detailed State Analysis
            report_lines.append("\n--- Detailed State Analysis ---")
            for state, stats in sorted_states:
                avg_transitions = stats["total_count"] / stats["issue_count"]
                report_lines.append(f"\n{state}:")
                report_lines.append(f"  - {stats['issue_count']} issues experienced this state")
                report_lines.append(f"  - Average times per issue entering this state {avg_transitions:.2f} times")
                if avg_transitions > 1.5:
                    report_lines.append("  ⚠️  Warning: This state was entered multiple times, indicating possible back-and-forth transitions")
        else:
            report_lines.append("\nAnalyzed 0 issues state transitions")
            report_lines.append(
                f"\n{'State':<20} {'Occurrences':<12} {'Issues Affected':<15} {'Avg Duration':<20} {'Total Duration':<20}"
            )
            report_lines.append("=" * 100)
            report_lines.append("(No state data available)")
            report_lines.append("\n--- Detailed State Analysis ---")
            report_lines.append("\n(No detailed state data available - 0 issues analyzed)")

        return "\n".join(report_lines)

    def generate_json_output(self, metrics, jql_query, project_key, start_date, end_date,
                            assignee=None, velocity_stats=None):
        """
        Generate JSON output from metrics.

        Args:
            metrics: Metrics dictionary
            jql_query: JQL query used
            project_key: Project key
            start_date: Start date string
            end_date: End date string
            assignee: Optional assignee
            velocity_stats: Optional velocity statistics

        Returns:
            Dictionary suitable for JSON serialization
        """
        closing_times = metrics.get("closing_times", [])

        output_data = {
            "analysis_date": datetime.now().isoformat(),
            "project_key": project_key,
            "query_parameters": {
                "start_date": start_date,
                "end_date": end_date,
                "assignee": assignee,
            },
            "jql_queries": {
                "main_analysis": jql_query,
            },
            "jql_query": jql_query,
            "total_issues_analyzed": metrics.get("total_issues", 0),
            "closing_time_stats": {},
            "state_statistics": {},
            "velocity_stats": velocity_stats or {},
        }

        # Add closing time stats
        if closing_times:
            avg_closing_time_seconds = sum(closing_times) / len(closing_times)
            output_data["closing_time_stats"] = {
                "average_days": avg_closing_time_seconds / (24 * 3600),
                "average_hours": avg_closing_time_seconds / 3600,
                "min_days": min(closing_times) / (24 * 3600),
                "max_days": max(closing_times) / (24 * 3600),
            }

        # Add state statistics
        state_stats = metrics.get("state_stats", {})
        for state, stats in state_stats.items():
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

        return output_data

    def save_text_report(self, report_text, assignee=None, output_dir="reports/jira"):
        """
        Save text report to file.

        Args:
            report_text: Report text content
            assignee: Optional assignee (for filename)
            output_dir: Output directory

        Returns:
            Output filename
        """
        os.makedirs(output_dir, exist_ok=True)

        if assignee:
            username = normalize_username(assignee)
            filename = os.path.join(
                output_dir, f'jira_report_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            )
        else:
            filename = os.path.join(
                output_dir, f'jira_report_general_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
            )

        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_text)

        return filename

    def save_json_output(self, output_data, start_date, end_date, assignee=None,
                        output_dir="reports/jira"):
        """
        Save JSON output to file.

        Args:
            output_data: Data dictionary
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            assignee: Optional assignee
            output_dir: Output directory

        Returns:
            Output filename
        """
        os.makedirs(output_dir, exist_ok=True)

        start_formatted = start_date.replace("-", "")
        end_formatted = end_date.replace("-", "")

        if assignee:
            identifier = normalize_username(assignee)
        else:
            identifier = "general"

        filename = os.path.join(
            output_dir, f'jira_metrics_{identifier}_{start_formatted}_{end_formatted}.json'
        )

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return filename

    def parse_jira_report(self, filename):
        """
        Parse a Jira report file and extract key metrics.

        Args:
            filename: Path to text report file

        Returns:
            Dictionary with extracted metrics
        """
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
        }

        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split("\n")

        # Extract basic info
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
            elif line.startswith("Start:"):
                data["time_range"]["start_date"] = line.split(":", 1)[1].strip()
            elif line.startswith("End:"):
                data["time_range"]["end_date"] = line.split(":", 1)[1].strip()
            elif line.startswith("Leave Days:"):
                match = re.search(r"Leave Days:\s*([\d.]+)\s*days?", line)
                if match:
                    data["time_range"]["leave_days"] = float(match.group(1))
            elif line.startswith("Capacity:"):
                match = re.search(r"Capacity:\s*([\d.]+)", line)
                if match:
                    data["time_range"]["capacity"] = float(match.group(1))
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
        for line in lines:
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

        # Parse state times
        in_state_analysis = False
        for line in lines:
            if "State" in line and "Occurrences" in line and "Avg Duration" in line:
                in_state_analysis = True
                continue
            if in_state_analysis:
                if line.startswith("---"):
                    break
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith("State") and not line_stripped.startswith("="):
                    match = re.match(
                        r"^(\S+(?:\s+\S+)?)\s+(\d+)\s+(\d+)\s+([-\d.]+)\s*(days|hours)", line_stripped
                    )
                    if match:
                        state_name = match.group(1).strip()
                        avg_time = float(match.group(4))
                        time_unit = match.group(5)
                        avg_days = avg_time / 24.0 if time_unit == "hours" else avg_time
                        if avg_days > 0:
                            data["state_times"][state_name] = avg_days

        # Parse re-entry rates
        current_state = None
        for line in lines:
            if line.strip().endswith(":") and not line.startswith("-"):
                state_candidate = line.strip().rstrip(":")
                if state_candidate in ["To Do", "In Progress", "Review", "New", "Waiting", "Release Pending"]:
                    current_state = state_candidate
            elif current_state and "Average times per issue entering this state" in line:
                match = re.search(r"([\d.]+)\s*times", line)
                if match:
                    data["state_reentry"][current_state] = float(match.group(1))

        return data

    def generate_comparison_tsv(self, reports, phase_names, assignee=None,
                                phase_configs=None):
        """
        Generate TSV comparison report from multiple phase reports.

        Args:
            reports: List of parsed report dictionaries
            phase_names: List of phase names
            assignee: Optional assignee
            phase_configs: Optional list of (name, start_date, end_date) tuples from config (for displaying phase dates)

        Returns:
            TSV format string
        """
        lines = []

        # Header
        if assignee:
            lines.append(f"AI Impact Analysis Report - {assignee}")
        else:
            lines.append("AI Impact Analysis Report - Team Overall")
        lines.append(f"Report Generated: {datetime.now().strftime('%B %d, %Y')}")
        lines.append("Project: Konflux UI")
        lines.append("")

        # Add description for multi-phase analysis
        if len(reports) >= 2:
            lines.append("This report analyzes development data across multiple periods to evaluate")
            lines.append("the impact of AI tools on team efficiency:")
            lines.append("")

        # Phase info with date ranges
        for i, (name, report) in enumerate(zip(phase_names, reports), 1):
            start_date = report["time_range"].get("start_date", "N/A")
            end_date = report["time_range"].get("end_date", "N/A")
            lines.append(f"Phase {i}: {name} ({start_date} to {end_date})")
        lines.append("")

        # Metrics table header
        header = "Metric\t" + "\t".join(phase_names)
        lines.append(header)

        # Period duration (always use Data Span from individual reports)
        periods = []
        for r in reports:
            span_days = r["time_range"].get("span_days")
            if span_days is not None:
                periods.append(f"{span_days}d")
            else:
                periods.append("N/A")
        lines.append("Analysis Period\t" + "\t".join(periods))

        # Leave days
        leave_days_list = []
        for r in reports:
            leave_days = r["time_range"].get("leave_days", 0)
            # Format as int if it's a whole number, otherwise as float
            if isinstance(leave_days, float) and leave_days == int(leave_days):
                leave_days_list.append(str(int(leave_days)))
            else:
                leave_days_list.append(str(leave_days))
        lines.append("Leave Days\t" + "\t".join(leave_days_list))

        # Capacity
        capacity_list = []
        for r in reports:
            capacity = r["time_range"].get("capacity", 1.0)
            capacity_list.append(str(capacity))
        lines.append("Capacity\t" + "\t".join(capacity_list))

        # Total issues
        issues = [str(r["total_issues"]) for r in reports]
        lines.append("Total Issues Completed\t" + "\t".join(issues))

        # Average closure time
        avg_times = [r["closure_stats"].get("avg_days", 0) for r in reports]
        lines.append("Average Closure Time\t" + "\t".join(f"{t:.2f}d" for t in avg_times))

        # Longest closure time
        max_times = [r["closure_stats"].get("max_days", 0) for r in reports]
        lines.append("Longest Closure Time\t" + "\t".join(f"{t:.2f}d" for t in max_times))

        # Daily throughput (skip leave days) = Total Issues / (Analysis Period - Leave Days)
        throughputs_skip_leave = []
        for i, report in enumerate(reports):
            period = periods[i]
            if period != "N/A" and period.endswith("d"):
                analysis_days = int(period.replace("d", ""))
                leave_days = report["time_range"].get("leave_days", 0)
                effective_days = analysis_days - leave_days
                throughput = report["total_issues"] / effective_days if effective_days > 0 else 0
                throughputs_skip_leave.append(f"{throughput:.2f}/d")
            else:
                throughputs_skip_leave.append("N/A")
        lines.append("Daily Throughput (skip leave days)\t" + "\t".join(throughputs_skip_leave))

        # Daily throughput (based on capacity) = Total Issues / (Analysis Period × Capacity)
        throughputs_capacity = []
        for i, report in enumerate(reports):
            period = periods[i]
            if period != "N/A" and period.endswith("d"):
                analysis_days = int(period.replace("d", ""))
                capacity = report["time_range"].get("capacity", 1.0)
                effective_days = analysis_days * capacity
                throughput = report["total_issues"] / effective_days if effective_days > 0 else 0
                throughputs_capacity.append(f"{throughput:.2f}/d")
            else:
                throughputs_capacity.append("N/A")
        lines.append("Daily Throughput (based on capacity)\t" + "\t".join(throughputs_capacity))

        # Daily throughput (considering leave days + capacity) = Total Issues / ((Analysis Period - Leave Days) × Capacity)
        throughputs_both = []
        for i, report in enumerate(reports):
            period = periods[i]
            if period != "N/A" and period.endswith("d"):
                analysis_days = int(period.replace("d", ""))
                leave_days = report["time_range"].get("leave_days", 0)
                capacity = report["time_range"].get("capacity", 1.0)
                effective_days = (analysis_days - leave_days) * capacity
                throughput = report["total_issues"] / effective_days if effective_days > 0 else 0
                throughputs_both.append(f"{throughput:.2f}/d")
            else:
                throughputs_both.append("N/A")
        lines.append("Daily Throughput (considering leave days + capacity)\t" + "\t".join(throughputs_both))

        # Daily throughput = Total Issues / Analysis Period
        throughputs = []
        for i, report in enumerate(reports):
            period = periods[i]
            if period != "N/A" and period.endswith("d"):
                analysis_days = int(period.replace("d", ""))
                throughput = report["total_issues"] / analysis_days if analysis_days > 0 else 0
                throughputs.append(f"{throughput:.2f}/d")
            else:
                throughputs.append("N/A")
        lines.append("Daily Throughput\t" + "\t".join(throughputs))

        # State times
        state_names = ["New", "To Do", "In Progress", "Review", "Release Pending", "Waiting"]
        for state in state_names:
            values = []
            for report in reports:
                time = report["state_times"].get(state, 0)
                values.append(f"{time:.2f}d" if time > 0 else "N/A")
            lines.append(f"{state} State Avg Time\t" + "\t".join(values))

        # Re-entry rates
        reentry_states = ["To Do", "In Progress", "Review", "Waiting"]
        for state in reentry_states:
            values = []
            for report in reports:
                rate = report["state_reentry"].get(state, 0)
                values.append(f"{rate:.2f}x" if rate > 0 else "N/A")
            lines.append(f"{state} Re-entry Rate\t" + "\t".join(values))

        # Issue types
        issue_types = ["Story", "Task", "Bug", "Epic"]
        for itype in issue_types:
            values = []
            for report in reports:
                if itype in report["issue_types"]:
                    values.append(f"{report['issue_types'][itype]['percentage']:.2f}%")
                else:
                    values.append("0.00%")
            lines.append(f"{itype} Percentage\t" + "\t".join(values))

        lines.append("")
        lines.append("Note: N/A values indicate no issues entered that workflow state during the period.")
        lines.append("This can be positive (e.g., no blocked issues) or indicate the state isn't used in your workflow.")

        # Calculate metric changes (first phase vs last phase) - only if we have 2+ reports
        if len(reports) >= 2:
            lines.append("")
            lines.append("Key Changes:")

            first_report = reports[0]
            last_report = reports[-1]

            # Collect all metric changes using shared utility functions
            metric_changes = []

            # Average closure time
            first_avg = first_report["closure_stats"].get("avg_days", 0)
            last_avg = last_report["closure_stats"].get("avg_days", 0)
            add_metric_change(metric_changes, "Average Closure Time", first_avg, last_avg, "d")

            # State times
            for state in state_names:
                first_time = first_report["state_times"].get(state, 0)
                last_time = last_report["state_times"].get(state, 0)
                add_metric_change(metric_changes, f"{state} State", first_time, last_time, "d")

            # Re-entry rates
            for state in reentry_states:
                first_rate = first_report["state_reentry"].get(state, 0)
                last_rate = last_report["state_reentry"].get(state, 0)
                add_metric_change(metric_changes, f"{state} Re-entry Rate", first_rate, last_rate, "x")

            # Format and append the top changes using shared utility
            formatted_changes = format_metric_changes(metric_changes, top_n=5)
            lines.extend(formatted_changes)

        lines.append("")
        lines.append("For detailed metric explanations, see:")
        lines.append("https://github.com/testcara/ai_impact_analysis#jira-report-metrics")

        return "\n".join(lines)
