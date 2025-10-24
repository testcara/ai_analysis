#!/bin/bash
#
# Generate GitHub PR Analysis Report
# Usage: ./generate_pr_report.sh [author]
#   e.g., ./generate_pr_report.sh wlin
#   or:   ./generate_pr_report.sh  (for team overall report)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load phase configuration
CONFIG_FILE="${PROJECT_ROOT}/config/github_phases.conf"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}"
    echo "Please create config/github_phases.conf with phase definitions."
    exit 1
fi

source "$CONFIG_FILE"

# Validate configuration
if [ ${#GITHUB_PHASES[@]} -eq 0 ]; then
    echo -e "${RED}Error: No phases defined in $CONFIG_FILE${NC}"
    echo "Please add at least one phase to the GITHUB_PHASES array."
    exit 1
fi

echo -e "${GREEN}Loaded ${#GITHUB_PHASES[@]} phase(s) from configuration${NC}"

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

# Parse arguments - command line overrides config file
if [ -n "$1" ]; then
    AUTHOR="$1"
    echo -e "${GREEN}Using author from command line: $AUTHOR${NC}"
else
    AUTHOR="${DEFAULT_GITHUB_AUTHOR}"
    if [ -n "$AUTHOR" ]; then
        echo -e "${GREEN}Using default author from config: $AUTHOR${NC}"
    fi
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

# Create reports directory if it doesn't exist
mkdir -p reports/github

# Remove old PR reports
if [ -n "$AUTHOR" ]; then
    rm -f reports/github/pr_metrics_${AUTHOR}_*.json 2>/dev/null || true
    rm -f reports/github/pr_report_${AUTHOR}_*.txt 2>/dev/null || true
    rm -f reports/github/pr_comparison_${AUTHOR}_*.tsv 2>/dev/null || true
    echo "  ✓ Removed old reports for $AUTHOR"
else
    rm -f reports/github/pr_metrics_general_*.json 2>/dev/null || true
    rm -f reports/github/pr_report_general_*.txt 2>/dev/null || true
    rm -f reports/github/pr_comparison_general_*.tsv 2>/dev/null || true
    echo "  ✓ Removed old general team reports"
fi

echo ""

# Step 2-N: Generate reports for all configured phases
STEP_NUM=2
for phase_config in "${GITHUB_PHASES[@]}"; do
    # Parse phase configuration (format: "Name|Start|End")
    IFS='|' read -r PHASE_NAME PHASE_START PHASE_END <<< "$phase_config"

    echo -e "${YELLOW}Step $STEP_NUM: Generating PR metrics for '$PHASE_NAME' ($PHASE_START to $PHASE_END)...${NC}"

    # Change to project root to ensure Python can find modules
    cd "$PROJECT_ROOT"

    if [ -n "$AUTHOR" ]; then
        python3 -m ai_impact_analysis.cli.get_pr_metrics --start "$PHASE_START" --end "$PHASE_END" --author "$AUTHOR"
    else
        python3 -m ai_impact_analysis.cli.get_pr_metrics --start "$PHASE_START" --end "$PHASE_END"
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
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All reports generated successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}Generated files:${NC}"
if [ -n "$AUTHOR" ]; then
    ls -lh reports/github/pr_metrics_${AUTHOR}_*.json 2>/dev/null || echo "  (no PR metrics found)"
    ls -lh reports/github/pr_report_${AUTHOR}_*.txt 2>/dev/null || echo "  (no PR reports found)"
    ls -lh reports/github/pr_comparison_${AUTHOR}_*.tsv 2>/dev/null || echo "  (no comparison report found)"
else
    ls -lh reports/github/pr_metrics_general_*.json 2>/dev/null || echo "  (no PR metrics found)"
    ls -lh reports/github/pr_report_general_*.txt 2>/dev/null || echo "  (no PR reports found)"
    ls -lh reports/github/pr_comparison_general_*.tsv 2>/dev/null || echo "  (no comparison report found)"
fi

echo ""

# Get the comparison file
if [ -n "$AUTHOR" ]; then
    COMPARISON_FILE=$(ls -t reports/github/pr_comparison_${AUTHOR}_*.tsv 2>/dev/null | head -1)
else
    COMPARISON_FILE=$(ls -t reports/github/pr_comparison_general_*.tsv 2>/dev/null | head -1)
fi

if [ -f "$COMPARISON_FILE" ]; then
    echo -e "${BLUE}Preview of comparison report ($COMPARISON_FILE):${NC}"
    echo "----------------------------------------"
    head -25 "$COMPARISON_FILE"
    echo "----------------------------------------"
    echo "(showing first 25 lines)"
    echo ""
fi

# Check if Google Sheets upload is configured
if [ -n "$GOOGLE_CREDENTIALS_FILE" ] && [ -n "$GOOGLE_SPREADSHEET_ID" ]; then
    if [ -f "$COMPARISON_FILE" ]; then
        echo -e "${YELLOW}Uploading to Google Sheets...${NC}"
        python3 -m ai_impact_analysis.cli.upload_to_sheets --report "$COMPARISON_FILE"
        echo ""
    fi
else
    echo -e "${BLUE}Google Sheets upload not configured (optional)${NC}"
    if [ -f "$COMPARISON_FILE" ]; then
        echo "To upload manually, run:"
        echo "  python3 -m ai_impact_analysis.cli.upload_to_sheets --report $COMPARISON_FILE"
        echo ""
        echo "Or configure automatic upload:"
        echo "  export GOOGLE_CREDENTIALS_FILE=/path/to/credentials.json"
        echo "  export GOOGLE_SPREADSHEET_ID=your_spreadsheet_id"
    fi
    echo ""
fi

echo -e "${GREEN}Done!${NC}"
