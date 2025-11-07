#!/usr/bin/env python3
"""
Quick setup verification script.

This script verifies that the AI Analysis tool is properly configured.
"""

import os
import sys
import subprocess
from pathlib import Path

from ai_impact_analysis.utils.logger import Colors, print_header, print_status, print_section


def check_python_version() -> bool:
    """Check if Python version is >= 3.11."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major >= 3 and version.minor >= 11:
        print_status(True, f"Python {version_str} (>= 3.11)")
        return True
    else:
        print_status(False, f"Python {version_str} (requires >= 3.11)")
        return False


def check_pythonpath() -> bool:
    """Check if PYTHONPATH is set correctly by trying to import the package."""
    # The best way to check is to try importing the package
    try:
        import ai_impact_analysis
        print_status(True, "PYTHONPATH configured (package can be imported)")
        return True
    except ImportError:
        print_status(False, "PYTHONPATH not set or doesn't include project root", warning=True)
        print("  Run: export PYTHONPATH=. (or PYTHONPATH=. before your command)")
        return False


def check_dependency(module_name: str) -> bool:
    """Check if a Python module can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def check_dependencies() -> bool:
    """Check if required dependencies are installed."""
    dependencies = ["requests", "argparse"]
    all_installed = True

    for dep in dependencies:
        if check_dependency(dep):
            print_status(True, dep)
        else:
            print_status(False, f"{dep} (run: pip install -r requirements.txt)")
            all_installed = False

    return all_installed


def check_module_imports() -> bool:
    """Check if project modules can be imported."""
    # Ensure PYTHONPATH includes current directory
    sys.path.insert(0, str(Path.cwd()))

    modules = [
        ("ai_impact_analysis.clients.jira_client", "JiraClient"),
        ("ai_impact_analysis.clients.github_client", "GitHubClient"),
        ("ai_impact_analysis.utils.report_utils", "normalize_username"),
    ]
    all_imported = True
    for module_path, name in modules:
        try:
            __import__(module_path)
            print_status(True, name)
        except Exception:
            all_imported = False
            print_status(False, f"{name} import failed")
    return all_imported


def check_config_files() -> bool:
    """Check if configuration files exist."""
    config_files = [
        "config/jira_phases.conf",
        "config/github_phases.conf",
        "config/jira_team_members.conf",
        "config/github_team_members.conf",
    ]
    all_configured = True

    for config_file in config_files:
        if Path(config_file).exists():
            print_status(True, config_file)
        else:
            all_configured = False
            print_status(False, f"{config_file} missing", warning=True)
    return all_configured

def check_env_var(var_name: str, required: bool = False) -> bool:
    """Check if an environment variable is set."""
    value = os.getenv(var_name)

    if value:
        print_status(True, f"{var_name} set")
        return True
    else:
        print_status(False, f"{var_name} not set", warning=not required)
        return False


def check_jira_config() -> bool:
    """Check Jira configuration and test connection."""
    url_set = check_env_var("JIRA_URL")
    token_set = check_env_var("JIRA_API_TOKEN")
    project_set = check_env_var("JIRA_PROJECT_KEY")

    if not (url_set and token_set and project_set):
        return False

    # Test actual connection
    try:
        from ai_impact_analysis.clients.jira_client import JiraClient

        jira_url = os.getenv("JIRA_URL")
        api_token = os.getenv("JIRA_API_TOKEN")
        project_key = os.getenv("JIRA_PROJECT_KEY")

        client = JiraClient(jira_url, api_token)
        # Try a simple JQL query to verify connection and project access
        test_jql = f'project = "{project_key}"'
        client.fetch_jira_data(test_jql, max_results=1)
        print_status(True, "Jira connection successful")
        return True
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            print_status(False, "Jira authentication failed (invalid token)")
        elif "404" in error_msg or "Not Found" in error_msg:
            print_status(False, "Jira project not found")
        else:
            print_status(False, f"Jira connection failed: {str(e)[:50]}")
        return False


def check_github_config() -> bool:
    """Check GitHub configuration and test connection."""
    token_set = check_env_var("GITHUB_TOKEN")
    owner_set = check_env_var("GITHUB_REPO_OWNER")
    repo_set = check_env_var("GITHUB_REPO_NAME")

    if not (token_set and owner_set and repo_set):
        return False

    # Test actual connection
    try:
        import requests

        token = os.getenv("GITHUB_TOKEN")
        repo_owner = os.getenv("GITHUB_REPO_OWNER")
        repo_name = os.getenv("GITHUB_REPO_NAME")

        # Try to get repository info
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        print_status(True, "GitHub connection successful")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print_status(False, "GitHub authentication failed (invalid token)")
        elif e.response.status_code == 404:
            print_status(False, "GitHub repository not found")
        else:
            print_status(False, f"GitHub connection failed: HTTP {e.response.status_code}")
        return False
    except Exception as e:
        print_status(False, f"GitHub connection failed: {str(e)[:50]}")
        return False


def check_googlesheet_config() -> bool:
    """Check Google Sheets configuration and test authentication."""
    creds_set = check_env_var("GOOGLE_CREDENTIALS_FILE")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID")
    has_spreadsheet_id = check_env_var("GOOGLE_SPREADSHEET_ID", required=False)  # Optional

    if not creds_set:
        return False

    # Test actual authentication
    try:
        from ai_impact_analysis.clients.sheets_client import (
            get_credentials,
            build_service,
            get_existing_sheets,
            get_service_account_email,
        )

        # Try to authenticate
        creds = get_credentials()

        # Try to build the service (this validates credentials)
        service = build_service(creds)

        print_status(True, "Google Sheets authentication successful")

        # Show service account email if available
        sa_email = get_service_account_email()
        if sa_email:
            print(f"  Service account: {sa_email}")
            print(f"  Share spreadsheets with this email to grant access")

        # If spreadsheet ID is set, test access to it
        if has_spreadsheet_id and spreadsheet_id:
            try:
                get_existing_sheets(service, spreadsheet_id)
                print_status(True, f"Spreadsheet access verified: {spreadsheet_id[:20]}...")
            except ValueError as ve:
                print_status(False, "Spreadsheet access failed", warning=True)
                print(f"  {str(ve)}")
                return False
            except Exception as e:
                print_status(False, f"Spreadsheet access failed: {str(e)[:50]}", warning=True)
                return False

        return True
    except Exception as e:
        error_msg = str(e)
        if "credentials" in error_msg.lower() or "json" in error_msg.lower():
            print_status(False, "Google Sheets credentials file invalid")
        else:
            print_status(False, f"Google Sheets auth failed: {str(e)[:50]}")
        return False


def check_scripts() -> bool:
    """Check if Python CLI scripts work."""
    scripts = [
        "ai_impact_analysis.scripts.get_jira_metrics",
        "ai_impact_analysis.scripts.get_pr_metrics",
        "ai_impact_analysis.scripts.generate_jira_report",
        "ai_impact_analysis.scripts.generate_pr_report",
        "ai_impact_analysis.scripts.generate_jira_comparison_report",
        "ai_impact_analysis.scripts.generate_pr_comparison_report",
        "ai_impact_analysis.scripts.upload_to_sheets"
    ]

    all_scripts_ready = True
    
    for script in scripts:
        try:
            result = subprocess.run(
                [sys.executable, "-m", script, "--help"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                print_status(True, f"{script.split('.')[-1]}.py")
            else:
                all_scripts_ready = False
                print_status(False, f"{script.split('.')[-1]}.py failed")
        except Exception:
            all_scripts_ready = False
            print_status(False, f"{script.split('.')[-1]}.py failed")
    return all_scripts_ready


def print_summary(jira_ready: bool, github_ready: bool, sheets_ready: bool) -> None:
    """Print verification summary."""
    print()
    print_header("Verification Summary")
    print()


    if jira_ready:
        print_status(True, "Jira connection verified - ready for analysis")
        print("  Run: python3 -m ai_impact_analysis.scripts.generate_jira_report -h")
    else:
        print_status(False, "Jira connection failed or not configured", warning=True)
        print("  Check: JIRA_URL, JIRA_API_TOKEN, JIRA_PROJECT_KEY")
        print("  Verify: Credentials are valid and project exists")

    if github_ready:
        print_status(True, "GitHub connection verified - ready for analysis")
        print("  Run: python3 -m ai_impact_analysis.scripts.generate_pr_report -h")
    else:
        print_status(False, "GitHub connection failed or not configured", warning=True)
        print("  Check: GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME")
        print("  Verify: Token is valid and repository exists")

    if sheets_ready:
        print_status(True, "Google Sheets authentication verified - ready for upload")
        print("  Run: python3 -m ai_impact_analysis.scripts.upload_to_sheets -h")
    else:
        print_status(False, "Google Sheets authentication failed or not configured", warning=True)
        print("  Check: GOOGLE_CREDENTIALS_FILE points to valid JSON credentials")
        print("  Optional: GOOGLE_SPREADSHEET_ID (for updating existing spreadsheets)")

    print()
    print(f"{Colors.BLUE}For detailed setup instructions, see README.md{Colors.NC}")
    print()


def main() -> int:
    """Run all verification checks."""
    print_header("AI Analysis Setup Verification")

    # Check Python version
    print_section("Checking Python version")
    if not check_python_version():
        return 1

    # Check PYTHONPATH
    print_section("Checking PYTHONPATH")
    if not check_pythonpath():
        return 1

    # Check dependencies
    print_section("Checking dependencies")
    if not check_dependencies():
        return 1

    # Check module imports
    print_section("Checking module imports")
    if not check_module_imports():
        return 1

    # Check configuration files
    print_section("Checking configuration files")
    if not check_config_files():
        return 1

    # Check Jira configuration and connection
    print_section("Testing Jira connection")
    jira_ready = check_jira_config()

    # Check GitHub configuration and connection
    print_section("Testing GitHub connection")
    github_ready = check_github_config()

    # Check Google Sheets configuration and authentication
    print_section("Testing Google Sheets authentication")
    sheets_ready = check_googlesheet_config()

    # Check scripts
    print_section("Testing script help messages")
    if not check_scripts():
        return 1

    # Print summary
    print_summary(jira_ready, github_ready, sheets_ready)

    return 0


if __name__ == "__main__":
    sys.exit(main())
