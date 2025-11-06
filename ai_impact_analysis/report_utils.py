"""
Shared utilities for report generation.

This module provides common functions used across different report generators
to avoid code duplication.
"""

import re


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
