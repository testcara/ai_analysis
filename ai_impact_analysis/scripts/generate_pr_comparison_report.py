#!/usr/bin/env python3
"""
Generate PR AI Impact Comparison Report.

This script reads individual PR phase reports and generates a comparison
report showing metrics across multiple time periods.
"""

import os
import sys
import argparse
import re
from datetime import datetime
from pathlib import Path

from ai_impact_analysis.core.pr_report_generator import PRReportGenerator
from ai_impact_analysis.utils.report_utils import generate_comparison_report
from ai_impact_analysis.utils.workflow_utils import load_config_file, get_project_root


def parse_phase_config(config_path="config/github_phases.conf"):
    """Parse phase configuration file."""
    phases = []
    if not os.path.exists(config_path):
        return phases

    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_array = False
    array_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "GITHUB_PHASES=(" in line and not stripped.startswith("#"):
            in_array = True
            array_start = line.split("GITHUB_PHASES=(", 1)[1]
            array_lines.append(array_start)
            if ")" in array_start:
                break
            continue
        if in_array:
            array_lines.append(line)
            if ")" in line:
                break

    array_content = "".join(array_lines)
    phase_pattern = r'"([^"]+)"'
    phase_entries = re.findall(phase_pattern, array_content)

    for entry in phase_entries:
        parts = entry.split("|")
        if len(parts) == 3:
            phases.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))

    return phases


def find_reports(author=None, reports_dir="reports/github"):
    """Find all matching PR report files."""
    if not os.path.exists(reports_dir):
        return []

    files = []
    for filename in os.listdir(reports_dir):
        if not filename.startswith("pr_metrics_"):
            continue
        if not filename.endswith(".json"):
            continue

        if author:
            if f"pr_metrics_{author}_" in filename:
                files.append(os.path.join(reports_dir, filename))
        else:
            if "pr_metrics_general_" in filename:
                files.append(os.path.join(reports_dir, filename))

    return sorted(files)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate PR AI Impact Comparison Report from phase reports"
    )
    parser.add_argument(
        "--author",
        type=str,
        help="Filter by author (GitHub username)",
        default=None,
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output filename (default: auto-generated)",
        default=None,
    )

    args = parser.parse_args()

    # Load phase configuration to get phase names
    project_root = get_project_root()
    config_file = project_root / "config" / "pr_report_config.yaml"

    try:
        phases, _ = load_config_file(config_file)
        phase_names = [phase[0] for phase in phases]  # Extract phase names
    except Exception as e:
        print(f"Warning: Could not load phase names from config: {e}")
        phase_names = []

    # Find matching reports
    report_files = find_reports(args.author)

    if len(report_files) == 0:
        if args.author:
            print(f"Error: No reports found for author '{args.author}'")
        else:
            print("Error: No general reports found")
        print("\nLooking for files matching pattern:")
        if args.author:
            print(f"  reports/github/pr_metrics_{args.author}_*.json")
        else:
            print("  reports/github/pr_metrics_general_*.json")
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

    # Use phase names from config if available, otherwise use generic names
    if not phase_names or len(phase_names) < len(report_files):
        phase_names = [f"Phase {i+1}" for i in range(len(report_files))]

    # Generate comparison report using shared utility
    report_gen = PRReportGenerator()

    generate_comparison_report(
        report_files=report_files,
        report_generator=report_gen,
        phase_names=phase_names,
        identifier=args.author,
        output_dir="reports/github",
        output_file=args.output,
        report_type="pr",
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
