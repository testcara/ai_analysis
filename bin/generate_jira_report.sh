#!/bin/bash
#
# Generate Jira AI Impact Analysis Report
# Usage: ./generate_jira_report.sh [assignee] [options]
#
# Arguments:
#   assignee      Optional assignee email to filter issues
#
# Options:
#   --all-members     Generate reports for all team members from config
#   --combine-only    Combine existing TSV reports without regenerating
#
# Examples:
#   ./generate_jira_report.sh                       # Team overall report
#   ./generate_jira_report.sh wlin@redhat.com       # Specific assignee
#   ./generate_jira_report.sh --all-members         # Team + all individual members
#

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load shared report utilities
source "${SCRIPT_DIR}/lib/report_utils.sh"

# Setup colors and paths
setup_colors
setup_script_paths

# Load phase configuration
CONFIG_FILE="${PROJECT_ROOT}/config/jira_phases.conf"
load_and_validate_config "$CONFIG_FILE" "PHASES" || exit 1

# Parse arguments - command line overrides config file
ASSIGNEE=""
ALL_MEMBERS=false
COMBINE_ONLY=false

for arg in "$@"; do
    case $arg in
        --all-members)
            ALL_MEMBERS=true
            ;;
        --combine-only)
            COMBINE_ONLY=true
            ;;
        --*)
            echo -e "${RED}Error: Unknown option: $arg${NC}"
            echo "Valid options: --all-members, --combine-only"
            exit 1
            ;;
        *)
            # First non-flag argument is the assignee
            if [ -z "$ASSIGNEE" ]; then
                ASSIGNEE="$arg"
            fi
            ;;
    esac
done

# Handle --combine-only flag
if [ "$COMBINE_ONLY" = true ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Combining Existing Jira Reports${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    REPORTS_DIR="${PROJECT_ROOT}/reports/jira"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    COMBINED_FILE="${REPORTS_DIR}/combined_jira_report_${TIMESTAMP}.tsv"

    # Call shared combine function
    combine_reports_by_metric \
        "$REPORTS_DIR" \
        "jira_comparison_general_*.tsv" \
        "jira_comparison_*.tsv" \
        "jira_comparison_general_*" \
        "$COMBINED_FILE" \
        "Jira AI Impact Analysis" \
        's/jira_comparison_\([^_]*\).*/\1/' \
        "${PROJECT_ROOT}/config/jira_phases.conf" \
        "jira"

    # Check if combine was successful
    if [ $? -ne 0 ]; then
        exit 1
    fi

    # Check if Google Sheets upload is configured
    if [ -n "$GOOGLE_CREDENTIALS_FILE" ] && [ -n "$GOOGLE_SPREADSHEET_ID" ]; then
        echo -e "${YELLOW}Uploading to Google Sheets...${NC}"
        cd "$PROJECT_ROOT"
        python3 -m ai_impact_analysis.cli.upload_to_sheets --report "$COMBINED_FILE"
        echo ""
    else
        echo -e "${BLUE}Google Sheets upload not configured (optional)${NC}"
        echo "You can open this file in Google Sheets manually, or configure automatic upload:"
        echo "  export GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json"
        echo "  export GOOGLE_SPREADSHEET_ID=your_spreadsheet_id"
        echo ""
        echo "Or upload manually:"
        echo "  python3 -m ai_impact_analysis.cli.upload_to_sheets --report $COMBINED_FILE"
        echo ""
    fi

    echo -e "${GREEN}Done!${NC}"

    exit 0
fi

# Handle --all-members flag
if [ "$ALL_MEMBERS" = true ]; then
    TEAM_MEMBERS_FILE="${PROJECT_ROOT}/config/jira_team_members.conf"
    handle_all_members "$TEAM_MEMBERS_FILE" "$0" "assignee email" ""

    echo -e "${BLUE}To combine all reports into a single TSV, run:${NC}"
    echo -e "${BLUE}  ./bin/generate_jira_report.sh --combine-only${NC}"
    echo ""

    exit 0
fi

# Use assignee from command line or config default
if [ -z "$ASSIGNEE" ]; then
    ASSIGNEE="${DEFAULT_ASSIGNEE}"
    if [ -n "$ASSIGNEE" ]; then
        echo -e "${GREEN}Using default assignee from config: $ASSIGNEE${NC}"
    fi
else
    echo -e "${GREEN}Using assignee from command line: $ASSIGNEE${NC}"
fi

if [ -n "$ASSIGNEE" ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}AI Impact Analysis Report Generator${NC}"
    echo -e "${BLUE}Assignee: $ASSIGNEE${NC}"
    echo -e "${BLUE}========================================${NC}"
else
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}AI Impact Analysis Report Generator${NC}"
    echo -e "${BLUE}Team Overall Report${NC}"
    echo -e "${BLUE}========================================${NC}"
fi

echo ""

# Step 1: Clean up old generated files
echo -e "${YELLOW}Step 1: Cleaning up old files...${NC}"

# Determine identifier (username or general)
if [ -n "$ASSIGNEE" ]; then
    # Extract and normalize username:
    # 1. Remove @redhat.com suffix
    # 2. Remove rh-ee- prefix
    # 3. Remove -1, -2, etc. suffix
    USERNAME=$(echo "$ASSIGNEE" | cut -d'@' -f1 | sed 's/^rh-ee-//; s/-[0-9]*$//')
    IDENTIFIER="$USERNAME"
else
    IDENTIFIER="general"
fi
cleanup_old_reports "reports/jira" "$IDENTIFIER" "jira"

echo ""

# Step 2-N: Generate reports for all configured phases
STEP_NUM=2
for phase_config in "${PHASES[@]}"; do
    # Parse phase configuration (format: "Name|Start|End")
    IFS='|' read -r PHASE_NAME PHASE_START PHASE_END <<< "$phase_config"

    echo -e "${YELLOW}Step $STEP_NUM: Generating report for '$PHASE_NAME' ($PHASE_START to $PHASE_END)...${NC}"
    if [ -n "$ASSIGNEE" ]; then
        python3 -m ai_impact_analysis.cli.get_jira_metrics --start "$PHASE_START" --end "$PHASE_END" --assignee "$ASSIGNEE"
    else
        # For team report, limit to team members from config
        TEAM_MEMBERS_FILE="${PROJECT_ROOT}/config/jira_team_members.conf"
        if [ -f "$TEAM_MEMBERS_FILE" ]; then
            python3 -m ai_impact_analysis.cli.get_jira_metrics --start "$PHASE_START" --end "$PHASE_END" --limit-team-members "$TEAM_MEMBERS_FILE"
        else
            echo -e "${YELLOW}  Warning: Team members config not found, querying all project issues${NC}"
            python3 -m ai_impact_analysis.cli.get_jira_metrics --start "$PHASE_START" --end "$PHASE_END"
        fi
    fi
    echo -e "${GREEN}  ✓ '$PHASE_NAME' report generated${NC}"
    echo ""

    ((STEP_NUM++))
done

# Generate comparison report (step number continues from phase loop)
echo -e "${YELLOW}Step $STEP_NUM: Generating comparison report...${NC}"
if [ -n "$ASSIGNEE" ]; then
    python3 -m ai_impact_analysis.cli.generate_jira_comparison_report --assignee "$ASSIGNEE"
else
    python3 -m ai_impact_analysis.cli.generate_jira_comparison_report
fi
echo ""

# Show results
COMPARISON_FILE=$(display_report_results "reports/jira" "$IDENTIFIER" "jira" 20 | tail -1)

# Upload to Google Sheets if configured
cd "$PROJECT_ROOT"
upload_to_google_sheets "$COMPARISON_FILE"

echo -e "${GREEN}Done!${NC}"
