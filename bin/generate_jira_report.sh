#!/bin/bash
#
# Generate Jira AI Impact Analysis Report
# Usage: ./generate_jira_report.sh [assignee]
#   e.g., ./generate_jira_report.sh sbudhwar@redhat.com
#   or:   ./generate_jira_report.sh  (for team overall report)
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
CONFIG_FILE="${PROJECT_ROOT}/config/jira_phases.conf"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Configuration file not found: $CONFIG_FILE${NC}"
    echo "Please create config/jira_phases.conf with phase definitions."
    exit 1
fi

source "$CONFIG_FILE"

# Validate configuration
if [ ${#PHASES[@]} -eq 0 ]; then
    echo -e "${RED}Error: No phases defined in $CONFIG_FILE${NC}"
    echo "Please add at least one phase to the PHASES array."
    exit 1
fi

echo -e "${GREEN}Loaded ${#PHASES[@]} phase(s) from configuration${NC}"

# Parse arguments - command line overrides config file
if [ -n "$1" ]; then
    ASSIGNEE="$1"
    echo -e "${GREEN}Using assignee from command line: $ASSIGNEE${NC}"
else
    ASSIGNEE="${DEFAULT_ASSIGNEE}"
    if [ -n "$ASSIGNEE" ]; then
        echo -e "${GREEN}Using default assignee from config: $ASSIGNEE${NC}"
    fi
fi

if [ -n "$ASSIGNEE" ]; then
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}AI Impact Analysis Report Generator${NC}"
    echo -e "${BLUE}Assignee: $ASSIGNEE${NC}"
    echo -e "${BLUE}========================================${NC}"
    # Extract just the username part (before @)
    USERNAME=$(echo "$ASSIGNEE" | cut -d'@' -f1)
    PATTERN="*${USERNAME}*"
else
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}AI Impact Analysis Report Generator${NC}"
    echo -e "${BLUE}Team Overall Report${NC}"
    echo -e "${BLUE}========================================${NC}"
    PATTERN="jira_report_[0-9]*"
fi

echo ""

# Step 1: Clean up old generated files
echo -e "${YELLOW}Step 1: Cleaning up old files...${NC}"

# Create reports directory if it doesn't exist
mkdir -p reports

# Remove old Jira reports
if [ -n "$ASSIGNEE" ]; then
    rm -f reports/jira_report_${USERNAME}_*.txt 2>/dev/null || true
    rm -f reports/comparison_report_${USERNAME}_*.tsv 2>/dev/null || true
    echo "  ✓ Removed old reports for $USERNAME"
else
    rm -f reports/jira_report_general_*.txt 2>/dev/null || true
    rm -f reports/comparison_report_general_*.tsv 2>/dev/null || true
    echo "  ✓ Removed old general team reports"
fi

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
        python3 -m ai_impact_analysis.cli.get_jira_metrics --start "$PHASE_START" --end "$PHASE_END"
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
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All reports generated successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}Generated files:${NC}"
if [ -n "$ASSIGNEE" ]; then
    ls -lh reports/jira_report_${USERNAME}_*.txt 2>/dev/null || echo "  (no Jira reports found)"
    ls -lh reports/comparison_report_${USERNAME}_*.tsv 2>/dev/null || echo "  (no comparison report found)"
else
    ls -lh reports/jira_report_general_*.txt 2>/dev/null || echo "  (no Jira reports found)"
    ls -lh reports/comparison_report_general_*.tsv 2>/dev/null || echo "  (no comparison report found)"
fi

echo ""

# Get the comparison file
if [ -n "$ASSIGNEE" ]; then
    COMPARISON_FILE=$(ls -t reports/comparison_report_${USERNAME}_*.tsv 2>/dev/null | head -1)
else
    COMPARISON_FILE=$(ls -t reports/comparison_report_general_*.tsv 2>/dev/null | head -1)
fi

if [ -f "$COMPARISON_FILE" ]; then
    echo -e "${BLUE}Preview of comparison report ($COMPARISON_FILE):${NC}"
    echo "----------------------------------------"
    head -20 "$COMPARISON_FILE"
    echo "----------------------------------------"
    echo "(showing first 20 lines)"
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
