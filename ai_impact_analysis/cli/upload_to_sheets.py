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
import csv
from datetime import datetime
from pathlib import Path

try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Error: Google Sheets API libraries not installed.")
    print(
        "Please install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )
    sys.exit(1)


# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_credentials(credentials_file=None, token_file="tmp/google_sheets_token.json"):
    """
    Get Google Sheets API credentials.

    Supports two authentication methods:
    1. Service Account (for automated/server use)
    2. OAuth 2.0 (for interactive use)

    Args:
        credentials_file: Path to credentials JSON file
        token_file: Path to store OAuth token

    Returns:
        Credentials object
    """
    creds = None

    if not credentials_file:
        credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")

    if not credentials_file or not os.path.exists(credentials_file):
        print("Error: Google credentials file not found.")
        print("\nSetup instructions:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create a project and enable Google Sheets API")
        print("3. Create credentials (Service Account or OAuth 2.0)")
        print("4. Download the JSON file")
        print("5. Set environment variable:")
        print("   export GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json")
        print("\nOr use --credentials flag:")
        print(
            "   python3 bin/upload_to_sheets.py --credentials /path/to/credentials.json --report report.tsv"
        )
        sys.exit(1)

    # Try Service Account first
    try:
        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=SCOPES
        )
        print("✓ Using Service Account authentication")
        return creds
    except Exception:
        pass

    # Fall back to OAuth 2.0
    # The token.json stores the user's access and refresh tokens
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        os.makedirs(os.path.dirname(token_file), exist_ok=True)
        with open(token_file, "w") as token:
            token.write(creds.to_json())
        print(f"✓ Using OAuth 2.0 authentication (token saved to {token_file})")

    return creds


def read_tsv_report(filepath):
    """
    Read TSV/CSV report file and return as list of rows.

    Args:
        filepath: Path to TSV or CSV file

    Returns:
        List of lists (rows)
    """
    rows = []

    # Detect delimiter
    delimiter = "\t" if filepath.endswith(".tsv") else ","

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            rows.append(row)

    return rows


def create_spreadsheet(service, title):
    """
    Create a new Google Spreadsheet.

    Args:
        service: Google Sheets API service
        title: Title for the spreadsheet

    Returns:
        Spreadsheet ID
    """
    spreadsheet = {"properties": {"title": title}}

    spreadsheet = service.spreadsheets().create(body=spreadsheet, fields="spreadsheetId").execute()

    return spreadsheet.get("spreadsheetId")


def get_existing_sheets(service, spreadsheet_id):
    """
    Get list of existing sheet names in a spreadsheet.

    Args:
        service: Google Sheets API service
        spreadsheet_id: ID of the spreadsheet

    Returns:
        List of sheet names
    """
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        sheets = spreadsheet.get("sheets", [])
        return [sheet["properties"]["title"] for sheet in sheets]
    except HttpError:
        return []


def create_new_sheet_tab(service, spreadsheet_id, sheet_name):
    """
    Create a new sheet tab in the spreadsheet.

    Args:
        service: Google Sheets API service
        spreadsheet_id: ID of the spreadsheet
        sheet_name: Name for the new sheet tab

    Returns:
        Sheet ID of the newly created tab
    """
    request_body = {"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]}

    response = (
        service.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body=request_body)
        .execute()
    )

    # Get the newly created sheet ID
    sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]
    return sheet_id


def upload_data_to_sheet(service, spreadsheet_id, data, sheet_name="Sheet1", create_new_tab=True):
    """
    Upload data to a Google Sheet.

    Args:
        service: Google Sheets API service
        spreadsheet_id: ID of the spreadsheet
        data: List of lists (rows)
        sheet_name: Base name of the sheet tab
        create_new_tab: If True, always create a new tab with timestamp

    Returns:
        tuple: (final_sheet_name, sheet_id)
    """
    # Get existing sheets
    existing_sheets = get_existing_sheets(service, spreadsheet_id)

    # Determine final sheet name
    if create_new_tab or sheet_name in existing_sheets:
        # Add timestamp to create unique name
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        final_sheet_name = f"{sheet_name} - {timestamp}"

        # If it's the first sheet and it's named "Sheet1", rename it
        if len(existing_sheets) == 1 and existing_sheets[0] == "Sheet1":
            try:
                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={
                        "requests": [
                            {
                                "updateSheetProperties": {
                                    "properties": {"sheetId": 0, "title": final_sheet_name},
                                    "fields": "title",
                                }
                            }
                        ]
                    },
                ).execute()
                sheet_id = 0
                print(f"✓ Renamed default sheet to '{final_sheet_name}'")
            except HttpError:
                # If rename fails, create new tab
                sheet_id = create_new_sheet_tab(service, spreadsheet_id, final_sheet_name)
                print(f"✓ Created new sheet tab '{final_sheet_name}'")
        else:
            # Create new tab
            sheet_id = create_new_sheet_tab(service, spreadsheet_id, final_sheet_name)
            print(f"✓ Created new sheet tab '{final_sheet_name}'")
    else:
        # Use the provided name (new spreadsheet case)
        final_sheet_name = sheet_name
        sheet_id = 0

    # Upload data
    range_name = f"'{final_sheet_name}'!A1"
    body = {"values": data}

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name, valueInputOption="RAW", body=body
    ).execute()

    print(f"✓ Uploaded {len(data)} rows to sheet '{final_sheet_name}'")

    return final_sheet_name, sheet_id


def format_sheet(service, spreadsheet_id, sheet_id=0):
    """
    Apply formatting to the sheet (header bold, freeze first row, etc).

    Args:
        service: Google Sheets API service
        spreadsheet_id: ID of the spreadsheet
        sheet_id: ID of the sheet tab (default 0)
    """
    requests = [
        # Freeze first row
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
        # Bold header row
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                "fields": "userEnteredFormat.textFormat.bold",
            }
        },
        # Auto-resize columns
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 10,
                }
            }
        },
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={"requests": requests}
    ).execute()

    print("✓ Applied formatting (frozen header, bold text, auto-resize)")


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

        # Check if it's a PR report
        if filename.startswith("pr_comparison_"):
            parts = filename.replace("pr_comparison_", "").split("_")
            if parts[0] == "general":
                args.sheet_name = "PR Report - Team"
            else:
                args.sheet_name = f"PR Report - {parts[0]}"
        # Otherwise it's a Jira report
        else:
            parts = filename.replace("comparison_report_", "").split("_")
            if parts[0] == "general":
                args.sheet_name = "Jira Report - Team"
            else:
                args.sheet_name = f"Jira Report - {parts[0]}"

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
        service = build("sheets", "v4", credentials=creds)
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
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
