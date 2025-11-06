#!/usr/bin/env python3
"""
Compare REST API vs GraphQL API results to validate data consistency.

Usage:
    python3 bin/compare_apis.py reports/github/test_rest_api.json reports/github/test_graphql_api.json
"""

import json
import sys
from collections import defaultdict


def load_report(filepath):
    """Load a PR metrics report."""
    with open(filepath, 'r') as f:
        return json.load(f)


def compare_reports(rest_report, graphql_report):
    """Compare two PR reports and show differences."""

    print("=" * 80)
    print("REST API vs GraphQL API Comparison")
    print("=" * 80)
    print()

    # Compare basic statistics
    print("📊 Basic Statistics:")
    print("-" * 80)

    rest_stats = rest_report['statistics']
    gql_stats = graphql_report['statistics']

    metrics = [
        ('Total PRs', 'total_prs'),
        ('AI-Assisted PRs', 'ai_assisted_prs'),
        ('Non-AI PRs', 'non_ai_prs'),
        ('AI Adoption Rate', 'ai_adoption_rate'),
    ]

    for label, key in metrics:
        rest_val = rest_stats.get(key, 'N/A')
        gql_val = gql_stats.get(key, 'N/A')
        match = "✓" if rest_val == gql_val else "✗"
        print(f"{match} {label:30s} REST: {rest_val:15} GraphQL: {gql_val:15}")

    print()

    # Compare PRs by number
    print("📋 PR-by-PR Comparison:")
    print("-" * 80)

    rest_prs = {pr['pr_number']: pr for pr in rest_report['prs']}
    gql_prs = {pr['pr_number']: pr for pr in graphql_report['prs']}

    rest_only = set(rest_prs.keys()) - set(gql_prs.keys())
    gql_only = set(gql_prs.keys()) - set(rest_prs.keys())
    common = set(rest_prs.keys()) & set(gql_prs.keys())

    print(f"PRs in REST only: {len(rest_only)}")
    if rest_only:
        print(f"  {sorted(rest_only)}")

    print(f"PRs in GraphQL only: {len(gql_only)}")
    if gql_only:
        print(f"  {sorted(gql_only)}")

    print(f"PRs in both: {len(common)}")
    print()

    # Compare individual PR metrics for common PRs
    print("🔍 Detailed Comparison (first 5 PRs):")
    print("-" * 80)

    differences = defaultdict(list)

    for pr_num in sorted(common)[:5]:
        rest_pr = rest_prs[pr_num]
        gql_pr = gql_prs[pr_num]

        print(f"\nPR #{pr_num}: {rest_pr['title'][:60]}")

        fields = [
            ('Total Commits', 'total_commits'),
            ('AI Assistance', 'has_ai_assistance'),
            ('Time to Merge (days)', 'time_to_merge_days'),
            ('Additions', 'additions'),
            ('Deletions', 'deletions'),
            ('Changed Files', 'changed_files'),
            ('Reviewers Count', 'reviewers_count'),
        ]

        for label, field in fields:
            rest_val = rest_pr.get(field)
            gql_val = gql_pr.get(field)

            if rest_val != gql_val:
                match = "✗"
                differences[field].append(pr_num)
                print(f"  {match} {label:30s} REST: {rest_val:15} GraphQL: {gql_val:15}")
            else:
                match = "✓"
                print(f"  {match} {label:30s} {rest_val}")

    # Summary of differences
    print()
    print("=" * 80)
    print("📈 Summary of Differences:")
    print("-" * 80)

    if differences:
        for field, pr_nums in differences.items():
            print(f"⚠️  {field}: {len(pr_nums)} PRs differ")
            print(f"   Affected PRs: {pr_nums}")
    else:
        print("✅ No differences found in common PRs!")

    print()

    # Overall assessment
    print("=" * 80)
    print("🎯 Overall Assessment:")
    print("-" * 80)

    total_checks = len(common) * len(fields) if common else 1
    total_diffs = sum(len(v) for v in differences.values())
    accuracy = ((total_checks - total_diffs) / total_checks * 100) if total_checks > 0 else 0

    print(f"Total PRs compared: {len(common)}")
    print(f"Total fields checked: {len(fields)}")
    print(f"Total checks: {total_checks}")
    print(f"Differences found: {total_diffs}")
    print(f"Accuracy: {accuracy:.2f}%")

    if accuracy >= 99:
        print("\n✅ GraphQL API is highly accurate and ready for production!")
    elif accuracy >= 95:
        print("\n⚠️  GraphQL API has minor differences. Review and fix.")
    else:
        print("\n❌ GraphQL API has significant differences. Investigation required.")

    print("=" * 80)


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 bin/compare_apis.py <rest_report.json> <graphql_report.json>")
        sys.exit(1)

    rest_file = sys.argv[1]
    graphql_file = sys.argv[2]

    rest_report = load_report(rest_file)
    graphql_report = load_report(graphql_file)

    compare_reports(rest_report, graphql_report)


if __name__ == '__main__':
    main()
