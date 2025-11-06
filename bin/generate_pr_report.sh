#!/bin/bash
#
# Generate GitHub PR Analysis Report
# Usage: ./generate_pr_report.sh [author] [options]
#
# Arguments:
#   author        Optional GitHub username to filter PRs
#
# Options:
#   --no-cache        Disable caching
#   --clear-cache     Clear cache before fetching
#   --incremental     Only fetch PRs updated since last run
#   --use-rest        Use REST API instead of GraphQL (slower)
#   --all-members     Generate reports for all team members from config
#   --combine-only    Combine existing TSV reports without regenerating
#
# Examples:
#   ./generate_pr_report.sh                    # Team overall report
#   ./generate_pr_report.sh wlin               # Specific author
#   ./generate_pr_report.sh --clear-cache      # Force re-fetch all data
#   ./generate_pr_report.sh wlin --incremental # Incremental update for author
#   ./generate_pr_report.sh --all-members      # Team + all individual members
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
CONFIG_FILE="${PROJECT_ROOT}/config/github_phases.conf"
load_and_validate_config "$CONFIG_FILE" "GITHUB_PHASES" || exit 1

# Check environment variables
if [ -z "$GITHUB_TOKEN" ]; then
    echo -e "${RED}Error: GITHUB_TOKEN environment variable not set${NC}"
    echo "Please set: export GITHUB_TOKEN='your_token'"
    exit 1
fi

if [ -z "$GITHUB_REPO_OWNER" ] || [ -z "$GITHUB_REPO_NAME" ]; then
    echo -e "${RED}Error: GitHub repository not configured${NC}"
    echo "Please set:"
    echo "  export GITHUB_REPO_OWNER='your_org'"
    echo "  export GITHUB_REPO_NAME='your_repo'"
    exit 1
fi

# Parse arguments
AUTHOR=""
EXTRA_FLAGS=""
ALL_MEMBERS=false
COMBINE_ONLY=false

# Parse all arguments
for arg in "$@"; do
    case $arg in
        --no-cache|--clear-cache|--incremental|--use-rest)
            EXTRA_FLAGS="$EXTRA_FLAGS $arg"
            ;;
        --all-members)
            ALL_MEMBERS=true
            ;;
        --combine-only)
            COMBINE_ONLY=true
            ;;
        --*)
            echo -e "${RED}Error: Unknown option: $arg${NC}"
            echo "Valid options: --no-cache, --clear-cache, --incremental, --use-rest, --all-members, --combine-only"
            exit 1
            ;;
        *)
            # First non-flag argument is the author
            if [ -z "$AUTHOR" ]; then
                AUTHOR="$arg"
            fi
            ;;
    esac
done

# Handle --combine-only flag
if [ "$COMBINE_ONLY" = true ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Combining Existing PR Reports${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    REPORTS_DIR="${PROJECT_ROOT}/reports/github"
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    COMBINED_FILE="${REPORTS_DIR}/combined_pr_report_${TIMESTAMP}.tsv"

    # Call shared combine function
    combine_reports_by_metric \
        "$REPORTS_DIR" \
        "pr_comparison_general_*.tsv" \
        "pr_comparison_*.tsv" \
        "pr_comparison_general_*" \
        "$COMBINED_FILE" \
        "GitHub PR Analysis" \
        's/pr_comparison_\([^_]*\).*/\1/' \
        "${PROJECT_ROOT}/config/github_phases.conf" \
        "pr"

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
    TEAM_MEMBERS_FILE="${PROJECT_ROOT}/config/github_team_members.conf"
    handle_all_members "$TEAM_MEMBERS_FILE" "$0" "GitHub username" "$EXTRA_FLAGS"

    echo -e "${BLUE}To combine all reports into a single TSV, run:${NC}"
    echo -e "${BLUE}  ./bin/generate_pr_report.sh --combine-only${NC}"
    echo ""

    exit 0
fi

# Use default author from config if not specified
if [ -z "$AUTHOR" ]; then
    AUTHOR="${DEFAULT_GITHUB_AUTHOR}"
fi

# Display selected options
if [ -n "$AUTHOR" ]; then
    echo -e "${GREEN}Author: $AUTHOR${NC}"
fi
if [ -n "$EXTRA_FLAGS" ]; then
    echo -e "${GREEN}Options:$EXTRA_FLAGS${NC}"
fi

if [ -n "$AUTHOR" ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}GitHub PR Analysis Report Generator${NC}"
    echo -e "${BLUE}Author: $AUTHOR${NC}"
    echo -e "${BLUE}========================================${NC}"
    PATTERN="*${AUTHOR}*"
else
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}GitHub PR Analysis Report Generator${NC}"
    echo -e "${BLUE}Team Overall Report${NC}"
    echo -e "${BLUE}========================================${NC}"
    PATTERN="pr_metrics_general_*"
fi

echo -e "${BLUE}Repository: ${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}${NC}"
echo ""

# Step 1: Clean up old generated files
echo -e "${YELLOW}Step 1: Cleaning up old files...${NC}"

# Determine identifier (author or general)
IDENTIFIER="${AUTHOR:-general}"
cleanup_old_reports "reports/github" "$IDENTIFIER" "pr"

echo ""

# Step 2-N: Generate reports for all configured phases
STEP_NUM=2
for phase_config in "${GITHUB_PHASES[@]}"; do
    # Parse phase configuration (format: "Name|Start|End")
    IFS='|' read -r PHASE_NAME PHASE_START PHASE_END <<< "$phase_config"

    echo -e "${YELLOW}Step $STEP_NUM: Generating PR metrics for '$PHASE_NAME' ($PHASE_START to $PHASE_END)...${NC}"

    # Change to project root to ensure Python can find modules
    cd "$PROJECT_ROOT"

    # Build command with extra flags
    if [ -n "$AUTHOR" ]; then
        python3 -m ai_impact_analysis.cli.get_pr_metrics --start "$PHASE_START" --end "$PHASE_END" --author "$AUTHOR" $EXTRA_FLAGS
    else
        python3 -m ai_impact_analysis.cli.get_pr_metrics --start "$PHASE_START" --end "$PHASE_END" $EXTRA_FLAGS
    fi

    echo -e "${GREEN}  ✓ '$PHASE_NAME' PR metrics collected${NC}"
    echo ""

    ((STEP_NUM++))
done

# Generate comparison report (step number continues from phase loop)
echo -e "${YELLOW}Step $STEP_NUM: Generating PR comparison report...${NC}"
if [ -n "$AUTHOR" ]; then
    python3 -m ai_impact_analysis.cli.generate_pr_comparison_report --author "$AUTHOR"
else
    python3 -m ai_impact_analysis.cli.generate_pr_comparison_report
fi
echo ""

# Show results
COMPARISON_FILE=$(display_report_results "reports/github" "$IDENTIFIER" "pr" 25 | tail -1)

# Upload to Google Sheets if configured
cd "$PROJECT_ROOT"
upload_to_google_sheets "$COMPARISON_FILE"

echo -e "${GREEN}Done!${NC}"
