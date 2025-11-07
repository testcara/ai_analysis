"""
Google Sheets Client Library.

This module provides a client library for interacting with Google Sheets API.
It supports uploading data, creating spreadsheets, and formatting sheets.

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Setup:
    1. Create Service Account at https://console.cloud.google.com
       - Create project and enable Google Sheets API
       - Create Service Account credentials
       - Download JSON key file

    2. Set environment variable:
       export GOOGLE_CREDENTIALS_FILE=/path/to/service-account-key.json
"""

import os
import sys
from datetime import datetime

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
            "   python3 scripts/upload_to_sheets.py --credentials /path/to/credentials.json --report report.tsv"
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

    Raises:
        HttpError: If the spreadsheet doesn't exist or the service account lacks permission
    """
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        sheets = spreadsheet.get("sheets", [])
        return [sheet["properties"]["title"] for sheet in sheets]
    except HttpError as e:
        if e.resp.status == 404:
            raise ValueError(
                f"Spreadsheet not found: {spreadsheet_id}\n"
                "Please check the GOOGLE_SPREADSHEET_ID environment variable."
            )
        elif e.resp.status == 403:
            raise ValueError(
                f"Permission denied for spreadsheet: {spreadsheet_id}\n"
                "If using a service account, share the spreadsheet with the service account email.\n"
                "Service account email is found in the 'client_email' field of your credentials JSON."
            )
        else:
            raise


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


def get_service_account_email(credentials_file=None):
    """
    Get the service account email from credentials file.

    Args:
        credentials_file: Path to credentials JSON file

    Returns:
        Service account email address or None if not a service account
    """
    import json

    if not credentials_file:
        credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE")

    if not credentials_file or not os.path.exists(credentials_file):
        return None

    try:
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
            return creds_data.get("client_email")
    except Exception:
        return None


def build_service(credentials, timeout=60):
    """
    Build Google Sheets API service with timeout configuration.

    Args:
        credentials: Google API credentials
        timeout: Timeout in seconds for API requests (default: 60)

    Returns:
        Google Sheets API service object
    """
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp

    # Create HTTP client with timeout
    # httplib2 automatically uses HTTP_PROXY/HTTPS_PROXY environment variables
    http = httplib2.Http(timeout=timeout)

    # Create authorized HTTP client with credentials and proxy support
    authorized_http = AuthorizedHttp(credentials, http=http)

    # Build the service with the authorized HTTP client
    # This ensures both proxy settings and credentials are used correctly
    service = build("sheets", "v4", http=authorized_http)

    return service
