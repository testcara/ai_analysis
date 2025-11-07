"""
Shared utilities for report generation.

This module provides common functions used across different report generators
to avoid code duplication.
"""

import os
import re
from datetime import datetime
from typing import List, Optional, Any


def normalize_username(username):
    """
    Normalize username by removing common prefixes/suffixes.

    This ensures consistent identifiers across filenames, sheet names, and reports.

    Transformations:
    - Remove @redhat.com, @gmail.com, etc. (email domain)
    - Remove rh-ee- prefix (Red Hat employee prefix)
    - Remove -1, -2, etc. suffix (numeric suffixes)

    Examples:
        wlin@redhat.com    -> wlin
        sbudhwar-1         -> sbudhwar
        rh-ee-djanaki      -> djanaki
        rh-ee-mtakac       -> mtakac
        rakshett           -> rakshett

    Args:
        username: Username string to normalize

    Returns:
        Normalized username string
    """
    if not username:
        return username
    # Remove email domain
    username = username.split("@")[0]
    # Remove rh-ee- prefix
    if username.startswith("rh-ee-"):
        username = username[6:]  # len("rh-ee-") = 6
    # Remove -1, -2, etc. suffix
    username = re.sub(r'-\d+$', '', username)
    return username


def calculate_percentage_change(before, after):
    """
    Calculate percentage change between two values.

    Formula: (after - before) / before * 100
    - Positive % = increase
    - Negative % = decrease

    Args:
        before: Value from earlier period
        after: Value from later period

    Returns:
        Percentage change as float
    """
    if before == 0:
        return None  # Can't calculate percentage change from 0
    return ((after - before) / before) * 100


def format_metric_changes(metric_changes, top_n=5):
    """
    Format metric changes into increases and decreases sections.

    Args:
        metric_changes: List of metric change dictionaries with keys:
            - name: Metric name
            - before: Value before
            - after: Value after
            - change: Percentage change
            - unit: Unit string (e.g., "d", "h", "%")
            - is_absolute: (optional) If True, shows absolute change instead of %
        top_n: Number of top changes to show (default: 5)

    Returns:
        List of formatted output lines
    """
    output = []

    # Separate into increases and decreases based on percentage change
    increases = []
    decreases = []

    for metric in metric_changes:
        if metric["change"] > 0:
            increases.append(metric)
        elif metric["change"] < 0:
            decreases.append(metric)

    # Sort by absolute change magnitude (biggest changes first)
    increases.sort(key=lambda x: abs(x["change"]), reverse=True)
    decreases.sort(key=lambda x: abs(x["change"]), reverse=True)

    # Show top N increases
    output.append("")
    output.append(f"Top {top_n} Increases in Metrics:")
    if len(increases) > 0:
        for metric in increases[:top_n]:
            if metric.get("is_absolute"):
                # Special case for absolute changes (e.g., AI Adoption from 0%)
                output.append(
                    f"• {metric['name']}: {metric['before']:.2f}{metric['unit']} → "
                    f"{metric['after']:.2f}{metric['unit']} "
                    f"(+{metric['change']:.2f}{metric['unit']} absolute change)"
                )
            else:
                output.append(
                    f"• {metric['name']}: {metric['before']:.2f}{metric['unit']} → "
                    f"{metric['after']:.2f}{metric['unit']} ({metric['change']:+.1f}% change)"
                )
    else:
        output.append("• No increases detected")

    # Show top N decreases
    output.append("")
    output.append(f"Top {top_n} Decreases in Metrics:")
    if len(decreases) > 0:
        for metric in decreases[:top_n]:
            output.append(
                f"• {metric['name']}: {metric['before']:.2f}{metric['unit']} → "
                f"{metric['after']:.2f}{metric['unit']} ({metric['change']:+.1f}% change)"
            )
    else:
        output.append("• No decreases detected")

    return output


def add_metric_change(metric_changes, name, before, after, unit, is_absolute=False):
    """
    Helper to add a metric change to the list if valid.

    Args:
        metric_changes: List to append to
        name: Metric name
        before: Value from earlier period
        after: Value from later period
        unit: Unit string (e.g., "d", "h", "%")
        is_absolute: If True, shows absolute change instead of % (for 0 baseline)
    """
    if is_absolute:
        # For absolute changes (e.g., going from 0% to X%)
        metric_changes.append({
            "name": name,
            "before": before,
            "after": after,
            "change": after,  # Absolute change
            "unit": unit,
            "is_absolute": True
        })
    else:
        # Regular percentage change
        pct_change = calculate_percentage_change(before, after)
        if pct_change is not None:
            metric_changes.append({
                "name": name,
                "before": before,
                "after": after,
                "change": pct_change,
                "unit": unit,
                "is_absolute": False
            })


def generate_comparison_report(
    report_files: List[str],
    report_generator: Any,
    phase_names: List[str],
    identifier: Optional[str] = None,
    output_dir: str = "reports",
    output_file: Optional[str] = None,
    report_type: str = "jira"
) -> str:
    """
    Generate comparison report from multiple phase reports.

    This is a shared utility function used by both Jira and PR comparison scripts.

    Args:
        report_files: List of report file paths to compare
        report_generator: Report generator instance with parse and generate_comparison_tsv methods
        phase_names: List of phase names
        identifier: Optional identifier (assignee for Jira, author for PR)
        output_dir: Output directory for the comparison report
        output_file: Optional custom output filename
        report_type: "jira" or "pr" for file naming

    Returns:
        Path to generated comparison report file
    """
    # Parse all reports
    print("Parsing reports...")
    parsed_reports = []

    for report_file in report_files:
        print(f"  Parsing {os.path.basename(report_file)}...")
        if report_type == "jira":
            parsed = report_generator.parse_jira_report(report_file)
        else:  # pr
            parsed = report_generator.parse_pr_report(report_file)
        parsed_reports.append(parsed)

    # Generate comparison TSV
    print("\nGenerating comparison report...")
    comparison_tsv = report_generator.generate_comparison_tsv(
        parsed_reports, phase_names, identifier
    )

    # Determine output filename
    os.makedirs(output_dir, exist_ok=True)

    if output_file:
        output_path = output_file
    else:
        # Extract timestamp from the last (most recent) report file
        last_report_file = os.path.basename(report_files[-1])

        # Different timestamp patterns for different report types
        if report_type == "jira":
            # Pattern: jira_report_xxx_YYYYMMDD_HHMMSS.txt
            timestamp_match = re.search(r"_(\d{8}_\d{6})\.txt$", last_report_file)
        else:  # pr
            # Pattern: pr_metrics_xxx_YYYYMMDD_YYYYMMDD.json
            timestamp_match = re.search(r"_(\d{8}_\d{8})\.json$", last_report_file)

        if timestamp_match:
            timestamp = timestamp_match.group(1)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build filename
        if identifier:
            filename = f"{report_type}_comparison_{identifier}_{timestamp}.tsv"
        else:
            filename = f"{report_type}_comparison_general_{timestamp}.tsv"

        output_path = os.path.join(output_dir, filename)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(comparison_tsv)

    print(f"\n✓ Report generated: {output_path}")
    print("\nYou can now:")
    print(f"  1. Open {output_path} in any text editor")
    print("  2. Copy all content (Ctrl+A, Ctrl+C)")
    print("  3. Paste directly into Google Sheets (no need to split columns)")
    print("  4. The data will automatically be placed in separate columns")

    return output_path


def combine_comparison_reports(
    reports_dir: str,
    report_type: str = "jira",
    title: Optional[str] = None
) -> str:
    """
    Combine all individual member comparison reports into a single report grouped by metric.

    This creates a combined view where each metric shows all team members' values
    side-by-side for comparison.

    Args:
        reports_dir: Directory containing comparison reports
        report_type: "jira" or "pr"
        title: Optional title for the combined report

    Returns:
        Path to generated combined report file
    """
    import glob
    from pathlib import Path

    reports_dir = Path(reports_dir)

    # Find all individual comparison reports (exclude "general")
    if report_type == "jira":
        pattern = str(reports_dir / "jira_comparison_*_*.tsv")
    else:
        pattern = str(reports_dir / "pr_comparison_*_*.tsv")

    all_files = glob.glob(pattern)

    # Filter out general reports
    report_files = [f for f in all_files if "_general_" not in f]

    if not report_files:
        raise ValueError(f"No individual {report_type} comparison reports found in {reports_dir}")

    print(f"Found {len(report_files)} individual reports to combine")

    # Parse all reports and extract member names and metrics
    members_data = {}  # {member_name: {metric_name: [phase1_val, phase2_val, ...]}}
    phase_names = None

    for report_file in sorted(report_files):
        # Extract member name from filename
        # Pattern: jira_comparison_MEMBER_TIMESTAMP.tsv or pr_comparison_MEMBER_TIMESTAMP.tsv
        basename = os.path.basename(report_file)
        parts = basename.split("_")
        if len(parts) >= 3:
            member_name = parts[2]  # e.g., "wlin", "sbudhwar"
        else:
            continue

        print(f"  Processing {member_name}...")

        # Parse the report
        with open(report_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the metrics table
        metric_data = {}
        in_table = False

        for line in lines:
            line = line.rstrip('\n')

            # Skip until we find the header line with "Metric\t"
            if line.startswith("Metric\t"):
                in_table = True
                # Extract phase names from header
                if phase_names is None:
                    phase_names = line.split('\t')[1:]  # Skip "Metric" column
                continue

            if not in_table:
                continue

            # Stop at empty line or special sections
            if not line.strip() or line.startswith("Note:") or line.startswith("Key Changes:") or line.startswith("Top "):
                break

            # Parse metric line
            parts = line.split('\t')
            if len(parts) >= 2:
                metric_name = parts[0]
                values = parts[1:]
                metric_data[metric_name] = values

        members_data[member_name] = metric_data

    if not members_data or not phase_names:
        raise ValueError("Failed to parse comparison reports")

    # Get all unique metrics (use first member's metrics as template)
    first_member = next(iter(members_data.values()))
    all_metrics = list(first_member.keys())

    # Build combined report
    lines = []

    # Header
    if title:
        lines.append(title)
    else:
        lines.append(f"{report_type.upper()} AI Impact Analysis - Combined Report (Grouped by Metric)")

    lines.append(f"Generated: {datetime.now().strftime('%B %d, %Y')}")
    lines.append("Project: Konflux UI")
    lines.append("")
    lines.append(f"This report compares {report_type.upper()} metrics across different time periods")
    lines.append("to evaluate the impact of AI tools on development workflow.")
    lines.append("")

    # Add phase info (extract from phase names)
    for i, phase_name in enumerate(phase_names, 1):
        lines.append(f"Phase {i}: {phase_name}")
    lines.append("")
    lines.append("")

    # Sort members for consistent output
    sorted_members = sorted(members_data.keys())

    # Add "team" at the beginning if it exists
    if "general" in sorted_members:
        sorted_members.remove("general")
        sorted_members.insert(0, "team")

    # For each metric, create a section
    for metric in all_metrics:
        lines.append(f"=== {metric} ===")

        # Header: Phase + all members
        header = "Phase\t" + "\t".join(sorted_members)
        lines.append(header)

        # For each phase, gather all members' values
        for phase_idx, phase_name in enumerate(phase_names):
            row_values = [phase_name]

            for member in sorted_members:
                member_key = "general" if member == "team" else member
                member_data = members_data.get(member_key, {})
                metric_values = member_data.get(metric, [])

                # Get value for this phase
                if phase_idx < len(metric_values):
                    row_values.append(metric_values[phase_idx])
                else:
                    row_values.append("N/A")

            lines.append("\t".join(row_values))

        lines.append("")  # Empty line between sections

    # Determine output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = reports_dir / f"combined_{report_type}_report_{timestamp}.tsv"

    # Write output
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_file
