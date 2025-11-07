#!/usr/bin/env python3
"""
Upload Jira comparison reports to Google Sheets.

This script uploads TSV/CSV comparison reports to Google Sheets for easy sharing and visualization.

Usage:
    python3 bin/upload_to_sheets.py --report reports/comparison_report_wlin_*.tsv
    python3 bin/upload_to_sheets.py --report reports/comparison_report_general_*.tsv --sheet-name "Team Report"

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Setup (Recommended - Manual Spreadsheet):
    1. Create Service Account at https://console.cloud.google.com
       - Create project and enable Google Sheets API
       - Create Service Account credentials
       - Download JSON key file
       - Note the Service Account email (client_email in JSON)

    2. Create Google Spreadsheet manually
       - Go to https://sheets.google.com
       - Create new spreadsheet (e.g., "Jira Analysis - wlin")
       - Click "Share" and add Service Account email with Editor permission
       - Copy Spreadsheet ID from URL

    3. Set environment variables:
       export GOOGLE_CREDENTIALS_FILE=/path/to/service-account-key.json
       export GOOGLE_SPREADSHEET_ID=1ABCdef...  # From spreadsheet URL

    Each upload creates a new tab with timestamp, preserving all history.
"""

import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.sheets_client import (
    get_credentials,
    build_service,
    create_spreadsheet,
    upload_data_to_sheet,
    format_sheet,
    get_service_account_email,
)
from utils.core_utils import read_tsv_report, normalize_username

try:
    from googleapiclient.errors import HttpError
    import socket
except ImportError:
    print("Error: Google Sheets API libraries not installed.")
    print(
        "Please install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Upload Jira comparison reports to Google Sheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # First time: Upload to new spreadsheet (creates new file)
  python3 bin/upload_to_sheets.py --report reports/comparison_report_wlin_20251022.tsv
  # Output will show: Spreadsheet ID: 1ABCdef...

  # Set environment variable for subsequent uploads
  export GOOGLE_SPREADSHEET_ID="1ABCdef..."

  # Future uploads: automatically append to same spreadsheet
  python3 bin/upload_to_sheets.py --report reports/comparison_report_wlin_20251024.tsv

  # Override env var with specific spreadsheet ID
  python3 bin/upload_to_sheets.py --report report.tsv --spreadsheet-id "1XYZ..."

  # Upload with custom sheet name
  python3 bin/upload_to_sheets.py --report reports/comparison_report_general.tsv --sheet-name "Team Report"

Environment Variables:
  GOOGLE_CREDENTIALS_FILE - Path to Google credentials JSON file
  GOOGLE_SPREADSHEET_ID   - Default spreadsheet ID for updates (optional)

Note:
  When using --spreadsheet-id or GOOGLE_SPREADSHEET_ID, a NEW TAB will be created
  with timestamp (e.g., "wlin Report - 2025-10-24 14:30").
  All previous tabs are preserved, allowing you to keep historical data in one spreadsheet.
        """,
    )

    parser.add_argument(
        "--report", type=str, required=True, help="Path to TSV/CSV report file to upload"
    )
    parser.add_argument(
        "--credentials",
        type=str,
        help="Path to Google credentials JSON file (or set GOOGLE_CREDENTIALS_FILE env var)",
    )
    parser.add_argument(
        "--spreadsheet-id",
        type=str,
        help="Existing spreadsheet ID to update (or set GOOGLE_SPREADSHEET_ID env var)",
    )
    parser.add_argument(
        "--sheet-name", type=str, help="Name for the sheet tab (default: derived from filename)"
    )
    parser.add_argument(
        "--no-format", action="store_true", help="Skip formatting (frozen header, bold, etc)"
    )

    args = parser.parse_args()

    # Get spreadsheet ID from env var if not provided
    if not args.spreadsheet_id:
        args.spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")

    # Validate report file exists
    if not os.path.exists(args.report):
        print(f"Error: Report file not found: {args.report}")
        sys.exit(1)

    # Derive sheet name from filename if not provided
    if not args.sheet_name:
        filename = Path(args.report).stem
        # Remove timestamp from filename for cleaner name
        # e.g., "comparison_report_wlin_20251022_111614" -> "Jira Report - wlin"
        # e.g., "pr_comparison_wlin_20251022_111614" -> "PR Report - wlin"
        # e.g., "combined_pr_report_20251022_111614" -> "PR Report - Combined"
        # e.g., "combined_jira_report_20251022_111614" -> "Jira Report - Combined"

        # Check if it's a combined PR report
        if filename.startswith("combined_pr_report"):
            args.sheet_name = "PR Report - Combined"
        # Check if it's a combined Jira report
        elif filename.startswith("combined_jira_report"):
            args.sheet_name = "Jira Report - Combined"
        # Check if it's a PR comparison report
        elif filename.startswith("pr_comparison_"):
            parts = filename.replace("pr_comparison_", "").split("_")
            if parts[0] == "general":
                args.sheet_name = "PR Report - Team"
            else:
                normalized = normalize_username(parts[0])
                args.sheet_name = f"PR Report - {normalized}"
        # Check if it's a Jira comparison report
        elif filename.startswith("jira_comparison_"):
            parts = filename.replace("jira_comparison_", "").split("_")
            if parts[0] == "general":
                args.sheet_name = "Jira Report - Team"
            else:
                normalized = normalize_username(parts[0])
                args.sheet_name = f"Jira Report - {normalized}"
        # Fallback for old comparison_report_* naming (for backwards compatibility)
        else:
            parts = filename.replace("comparison_report_", "").split("_")
            if parts[0] == "general":
                args.sheet_name = "Jira Report - Team"
            else:
                normalized = normalize_username(parts[0])
                args.sheet_name = f"Jira Report - {normalized}"

    print("\n📊 Uploading report to Google Sheets...")
    print(f"Report: {args.report}")
    print(f"Sheet name: {args.sheet_name}")

    if args.spreadsheet_id:
        env_source = (
            " (from GOOGLE_SPREADSHEET_ID)"
            if os.getenv("GOOGLE_SPREADSHEET_ID") == args.spreadsheet_id
            else ""
        )
        print(f"Target: Existing spreadsheet{env_source}")

    # Get credentials
    try:
        creds = get_credentials(args.credentials)
    except Exception as e:
        print(f"Error getting credentials: {e}")
        sys.exit(1)

    # Build service
    try:
        service = build_service(creds)
    except Exception as e:
        print(f"Error building Google Sheets service: {e}")
        sys.exit(1)

    # Read report data
    print("\n📖 Reading report file...")
    try:
        data = read_tsv_report(args.report)
        print(f"✓ Read {len(data)} rows")
    except Exception as e:
        print(f"Error reading report file: {e}")
        sys.exit(1)

    # Create or use existing spreadsheet
    try:
        if args.spreadsheet_id:
            spreadsheet_id = args.spreadsheet_id
            print(f"\n📝 Updating existing spreadsheet: {spreadsheet_id}")
        else:
            # Create new spreadsheet with timestamp
            title = f"Jira AI Analysis - {args.sheet_name} - {datetime.now().strftime('%Y-%m-%d')}"
            print(f"\n📝 Creating new spreadsheet: {title}")
            spreadsheet_id = create_spreadsheet(service, title)
            print(f"✓ Created spreadsheet: {spreadsheet_id}")

        # Upload data (create new tab if updating existing spreadsheet)
        create_new_tab = bool(args.spreadsheet_id)
        final_sheet_name, sheet_id = upload_data_to_sheet(
            service, spreadsheet_id, data, args.sheet_name, create_new_tab
        )

        # Format sheet
        if not args.no_format:
            format_sheet(service, spreadsheet_id, sheet_id)

        # Print success with URL
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        print("\n✅ Success! Report uploaded to Google Sheets")
        print(f"📋 Sheet tab: '{final_sheet_name}'")
        print(f"🔗 Open here: {url}")

        if args.spreadsheet_id:
            print("\n💡 Tip: All previous reports are preserved in other tabs")
        else:
            print("\n💡 Tip: To append future reports to this spreadsheet:")
            print(f"   Spreadsheet ID: {spreadsheet_id}")
            print("\n   Set environment variable (recommended):")
            print(f'   export GOOGLE_SPREADSHEET_ID="{spreadsheet_id}"')
            print("\n   Or use --spreadsheet-id flag each time:")
            print(
                f'   python3 bin/upload_to_sheets.py --report ... --spreadsheet-id "{spreadsheet_id}"'
            )

    except HttpError as error:
        print(f"\n❌ Google Sheets API error: {error}")
        if error.resp.status == 403:
            print("\n💡 Permission Issue:")
            print("   If using a service account, you must share the spreadsheet with:")
            sa_email = get_service_account_email()
            if sa_email:
                print(f"   {sa_email}")
            else:
                print("   The service account email (found in your credentials JSON file)")
            print("\n   Steps:")
            print("   1. Open the spreadsheet in Google Sheets")
            print("   2. Click 'Share' button")
            print("   3. Add the service account email with 'Editor' permission")
        elif error.resp.status == 404:
            print("\n💡 Spreadsheet not found. Please check GOOGLE_SPREADSHEET_ID.")
        sys.exit(1)
    except socket.timeout as e:
        print(f"\n❌ Timeout error: {e}")
        print("\n💡 Possible causes:")
        print("   1. Network connectivity issues")
        print("   2. Spreadsheet permission issues (see below)")
        print("   3. Large data upload taking too long")
        print("\n💡 If using a service account with GOOGLE_SPREADSHEET_ID:")
        print("   Share the spreadsheet with your service account email:")
        sa_email = get_service_account_email()
        if sa_email:
            print(f"   {sa_email}")
        else:
            print("   (Found in 'client_email' field of your credentials JSON)")
        sys.exit(1)
    except ValueError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
