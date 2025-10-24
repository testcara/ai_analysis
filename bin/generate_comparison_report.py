#!/usr/bin/env python3
"""
Generate AI Impact Comparison Report from Jira Reports
Compares three time periods to show AI tools impact
"""

import os
import re
import argparse
from datetime import datetime
from collections import defaultdict


def parse_jira_report(filename):
    """Parse a Jira report file and extract key metrics"""
    data = {
        'filename': filename,
        'assignee': None,
        'jql_query': None,
        'time_range': {},
        'issue_types': {},
        'total_issues': 0,
        'closure_stats': {},
        'state_times': {},
        'state_reentry': {}
    }

    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    # Extract assignee if present
    for line in lines:
        if line.startswith('分配人:'):
            data['assignee'] = line.split(':', 1)[1].strip()
        elif line.startswith('JQL查询:'):
            data['jql_query'] = line.split(':', 1)[1].strip()
        elif line.startswith('总计:'):
            match = re.search(r'总计:\s*(\d+)', line)
            if match:
                data['total_issues'] = int(match.group(1))
        elif line.startswith('平均关闭时间:'):
            match = re.search(r'平均关闭时间:\s*([\d.]+)\s*天', line)
            if match:
                data['closure_stats']['avg_days'] = float(match.group(1))
        elif line.startswith('最长关闭时间:'):
            match = re.search(r'最长关闭时间:\s*([\d.]+)\s*天', line)
            if match:
                data['closure_stats']['max_days'] = float(match.group(1))
        elif line.startswith('最早创建时间:'):
            data['time_range']['earliest_created'] = line.split(':', 1)[1].strip()
        elif line.startswith('最早解决时间:'):
            data['time_range']['earliest_resolved'] = line.split(':', 1)[1].strip()
        elif line.startswith('最晚解决时间:'):
            data['time_range']['latest_resolved'] = line.split(':', 1)[1].strip()
        elif line.startswith('数据跨度:'):
            match = re.search(r'数据跨度:\s*(\d+)\s*天', line)
            if match:
                data['time_range']['span_days'] = int(match.group(1))

    # Parse issue types
    in_issue_types = False
    for i, line in enumerate(lines):
        if line.startswith('--- Issue 类型统计 ---'):
            in_issue_types = True
            continue
        if in_issue_types:
            if line.startswith('---'):
                break
            match = re.match(r'\s*(Story|Task|Bug|Epic|Sub-task)\s+(\d+)\s*\(\s*([\d.]+)%\)', line)
            if match:
                issue_type, count, percentage = match.groups()
                data['issue_types'][issue_type] = {
                    'count': int(count),
                    'percentage': float(percentage)
                }

    # Parse state times and re-entry rates
    in_state_analysis = False
    for i, line in enumerate(lines):
        if '状态                   出现次数' in line:
            in_state_analysis = True
            continue
        if in_state_analysis:
            if line.startswith('---'):
                break
            # Parse state time line - need to handle multi-word state names
            # Line format: "State Name      count1      count2      avg_time      total_time"
            # Extract state name from the beginning (before the numeric columns)
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('状态') and not line_stripped.startswith('='):
                # Use regex to extract state name and average time
                # Match pattern: state_name (any text) followed by numbers, then avg time in days
                match = re.match(r'^(\S+(?:\s+\S+)?)\s+(\d+)\s+(\d+)\s+([\d.]+)\s*天', line_stripped)
                if match:
                    state_name = match.group(1).strip()
                    avg_days = float(match.group(4))
                    data['state_times'][state_name] = avg_days

    # Parse re-entry rates from detailed analysis
    current_state = None
    for line in lines:
        if line.strip().endswith(':') and not line.startswith('-'):
            state_candidate = line.strip().rstrip(':')
            if state_candidate in ['To Do', 'In Progress', 'Review', 'New', 'Waiting',
                                   'Release Pending', 'Backlog', 'Closed', 'Code Review', 'Refinement']:
                current_state = state_candidate
        elif current_state and '平均每个issue进入此状态' in line:
            match = re.search(r'([\d.]+)\s*次', line)
            if match:
                data['state_reentry'][current_state] = float(match.group(1))

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
    if len(reports) < 2:
        print(f"Error: Need at least 2 reports for comparison, found {len(reports)}")
        return

    # Sort reports by time period (oldest to newest based on filename timestamp)
    reports = sorted(reports, key=lambda x: x['filename'])

    # Determine phases based on number of reports
    if len(reports) == 2:
        phase_names = ["Before AI", "After AI"]
    elif len(reports) == 3:
        phase_names = ["No AI", "Cursor", "Comprehensive AI Tools"]
    else:
        # For 4+ reports, use generic labels
        phase_names = [f"Phase {i+1}" for i in range(len(reports))]

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

    for i, (phase, report) in enumerate(zip(phase_names, reports)):
        # Use resolved dates (earliest resolved to latest resolved) as the phase period
        earliest = report['time_range'].get('earliest_resolved', 'N/A')
        latest = report['time_range'].get('latest_resolved', 'N/A')

        # Extract just the date part
        if earliest != 'N/A':
            earliest_date = earliest.split()[0]
        else:
            earliest_date = 'N/A'

        if latest != 'N/A':
            latest_date = latest.split()[0]
        else:
            latest_date = 'N/A'

        # Calculate period days from the resolved date range
        if earliest != 'N/A' and latest != 'N/A':
            try:
                start = datetime.strptime(earliest_date, '%Y-%m-%d')
                end = datetime.strptime(latest_date, '%Y-%m-%d')
                period_days = (end - start).days
                period_info = f"{period_days} days"
            except:
                period_info = "N/A"
        else:
            period_info = "N/A"

        output.append(f"Phase {i+1}: {phase} ({earliest_date} to {latest_date}, {period_info})")

    output.append("")
    output.append("")

    # Metrics table (using tabs for TSV format)
    header = "Metric\t" + "\t".join(phase_names)
    output.append(header)

    # Period duration - calculate from resolved dates
    periods = []
    for r in reports:
        earliest = r['time_range'].get('earliest_resolved', 'N/A')
        latest = r['time_range'].get('latest_resolved', 'N/A')
        if earliest != 'N/A' and latest != 'N/A':
            try:
                start = datetime.strptime(earliest.split()[0], '%Y-%m-%d')
                end = datetime.strptime(latest.split()[0], '%Y-%m-%d')
                period_days = (end - start).days
                periods.append(f"{period_days}d")
            except:
                periods.append("N/A")
        else:
            periods.append("N/A")

    output.append("Analysis Period\t" + "\t".join(periods))

    # Total issues
    issues = [r['total_issues'] for r in reports]
    output.append("Total Issues Completed\t" + "\t".join(str(i) for i in issues))

    # Average closure time
    avg_times = [r['closure_stats'].get('avg_days', 0) for r in reports]
    output.append("Average Closure Time\t" + "\t".join(f"{t:.2f}d" for t in avg_times))

    # Longest closure time
    max_times = [r['closure_stats'].get('max_days', 0) for r in reports]
    output.append("Longest Closure Time\t" + "\t".join(f"{t:.2f}d" for t in max_times))

    # Daily throughput
    throughputs = []
    for i, report in enumerate(reports):
        period = periods[i]
        if period != "N/A" and period.endswith("d"):
            days = int(period.replace("d", ""))
            throughput = report['total_issues'] / days if days > 0 else 0
            throughputs.append(f"{throughput:.2f}/d")
        else:
            throughputs.append("N/A")
    output.append("Daily Throughput\t" + "\t".join(throughputs))

    # State times
    state_names = ['New', 'To Do', 'In Progress', 'Review', 'Release Pending', 'Waiting']
    for state in state_names:
        values = []
        for report in reports:
            time = report['state_times'].get(state, 0)
            if time > 0:
                values.append(f"{time:.2f}d")
            else:
                values.append("N/A")
        output.append(f"{state} State Avg Time\t" + "\t".join(values))

    # Re-entry rates
    reentry_states = ['To Do', 'In Progress', 'Review', 'Waiting']
    for state in reentry_states:
        values = []
        for report in reports:
            rate = report['state_reentry'].get(state, 0)
            if rate > 0:
                values.append(f"{rate:.2f}x")
            else:
                values.append("N/A")
        output.append(f"{state} Re-entry Rate\t" + "\t".join(values))

    # Issue types
    issue_types = ['Story', 'Task', 'Bug', 'Epic']
    for itype in issue_types:
        values = []
        for report in reports:
            if itype in report['issue_types']:
                values.append(f"{report['issue_types'][itype]['percentage']:.2f}%")
            else:
                values.append("0.00%")
        output.append(f"{itype} Percentage\t" + "\t".join(values))

    output.append("")
    output.append("")

    # Key conclusions - compare first and last reports
    output.append("Key Conclusions:")

    improvement = 0
    if len(avg_times) >= 2 and avg_times[0] > 0:
        improvement = ((avg_times[0] - avg_times[-1]) / avg_times[0]) * 100
        output.append(f"• Average Task Closure Time: {avg_times[0]:.2f}d → {avg_times[-1]:.2f}d ({improvement:+.1f}% change)")

    # To Do improvement
    todo_times = [r['state_times'].get('To Do', 0) for r in reports]
    if len(todo_times) >= 2 and todo_times[0] > 0 and todo_times[-1] > 0:
        todo_improvement = ((todo_times[0] - todo_times[-1]) / todo_times[0]) * 100
        output.append(f"• To Do State: {todo_times[0]:.2f}d → {todo_times[-1]:.2f}d ({todo_improvement:+.1f}% change)")

    # In Progress
    ip_times = [r['state_times'].get('In Progress', 0) for r in reports]
    if len(ip_times) >= 2 and ip_times[0] > 0 and ip_times[-1] > 0:
        ip_improvement = ((ip_times[0] - ip_times[-1]) / ip_times[0]) * 100
        output.append(f"• In Progress State: {ip_times[0]:.2f}d → {ip_times[-1]:.2f}d ({ip_improvement:+.1f}% change)")

    # Review
    review_times = [r['state_times'].get('Review', 0) for r in reports]
    if len(review_times) >= 2 and review_times[0] > 0 and review_times[-1] > 0:
        review_improvement = ((review_times[0] - review_times[-1]) / review_times[0]) * 100
        output.append(f"• Review State: {review_times[0]:.2f}d → {review_times[-1]:.2f}d ({review_improvement:+.1f}% change)")

    output.append("")

    # Final summary
    if improvement > 0:
        output.append("Summary: The comparison shows a quantifiably positive outcome,")
        output.append("with improvements in core efficiency metrics and a more stable workflow.")
    else:
        output.append("Summary: The data shows mixed results. Further investigation recommended.")

    return '\n'.join(output)


def find_reports(assignee=None):
    """Find all matching Jira report files"""
    files = []

    # Look in reports directory
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        return files

    for filename in os.listdir(reports_dir):
        if not filename.startswith('jira_report_'):
            continue
        if not filename.endswith('.txt'):
            continue

        if assignee:
            # Extract username part (before @)
            username = assignee.split('@')[0]
            # Look for assignee-specific reports using just username
            # Pattern: jira_report_username_YYYYMMDD_HHMMSS.txt
            if f'jira_report_{username}_' in filename:
                files.append(os.path.join(reports_dir, filename))
        else:
            # Look for general reports
            # Pattern: jira_report_general_YYYYMMDD_HHMMSS.txt
            if 'jira_report_general_' in filename:
                files.append(os.path.join(reports_dir, filename))

    return sorted(files)


def main():
    parser = argparse.ArgumentParser(
        description='Generate AI Impact Comparison Report from Jira reports'
    )
    parser.add_argument(
        '--assignee',
        type=str,
        help='Filter by assignee (e.g., sbudhwar or sbudhwar@redhat.com)',
        default=None
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output filename (default: auto-generated)',
        default=None
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
            username = args.assignee.split('@')[0]
            print(f"  reports/jira_report_{username}_*.txt")
        else:
            print("  reports/jira_report_general_*.txt")
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
    # Create output directory
    output_dir = 'reports'
    os.makedirs(output_dir, exist_ok=True)

    if args.output:
        output_file = args.output
    else:
        # Extract timestamp from the last (most recent) report file to maintain consistency
        last_report_file = os.path.basename(report_files[-1])
        # Extract timestamp from filename pattern: jira_report_{username}_{timestamp}.txt
        timestamp_match = re.search(r'_(\d{8}_\d{6})\.txt$', last_report_file)
        if timestamp_match:
            timestamp = timestamp_match.group(1)
        else:
            # Fallback to current time if pattern doesn't match
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if args.assignee:
            username = args.assignee.split('@')[0]
            output_file = os.path.join(output_dir, f'comparison_report_{username}_{timestamp}.tsv')
        else:
            output_file = os.path.join(output_dir, f'comparison_report_general_{timestamp}.tsv')

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report_text)

    print(f"\n✓ Report generated: {output_file}")
    print("\nYou can now:")
    print(f"  1. Open {output_file} in any text editor")
    print("  2. Copy all content (Ctrl+A, Ctrl+C)")
    print("  3. Paste directly into Google Sheets (no need to split columns)")
    print("  4. The data will automatically be placed in separate columns")

    return 0


if __name__ == '__main__':
    exit(main())
