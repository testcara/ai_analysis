#!/bin/bash
#
# Generate AI Impact Analysis Report
# Usage: ./generate_report.sh [assignee]
#   e.g., ./generate_report.sh sbudhwar@redhat.com
#   or:   ./generate_report.sh  (for team overall report)
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PHASE1_START="2024-10-24"  # No AI period start
PHASE1_END="2025-05-30"    # No AI period end

PHASE2_START="2025-06-02"  # Cursor period start
PHASE2_END="2025-07-31"    # Cursor period end

PHASE3_START="2025-08-01"  # Full AI period start
PHASE3_END="2025-10-20"    # Full AI period end (yesterday to avoid today's incomplete data)

# Parse arguments
ASSIGNEE="${1:-}"

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
    rm -f reports/comparison_report_${USERNAME}_*.csv 2>/dev/null || true
    echo "  ✓ Removed old reports for $USERNAME"
else
    rm -f reports/jira_report_general_*.txt 2>/dev/null || true
    rm -f reports/comparison_report_general_*.csv 2>/dev/null || true
    echo "  ✓ Removed old general team reports"
fi

echo ""

# Step 2: Generate Phase 1 report (No AI period)
echo -e "${YELLOW}Step 2: Generating Phase 1 report (No AI: $PHASE1_START to $PHASE1_END)...${NC}"
if [ -n "$ASSIGNEE" ]; then
    python get_issues.py --start "$PHASE1_START" --end "$PHASE1_END" --assignee "$ASSIGNEE"
else
    python get_issues.py --start "$PHASE1_START" --end "$PHASE1_END"
fi
echo -e "${GREEN}  ✓ Phase 1 report generated${NC}"
echo ""

# Step 3: Generate Phase 2 report (Cursor period)
echo -e "${YELLOW}Step 3: Generating Phase 2 report (Cursor: $PHASE2_START to $PHASE2_END)...${NC}"
if [ -n "$ASSIGNEE" ]; then
    python get_issues.py --start "$PHASE2_START" --end "$PHASE2_END" --assignee "$ASSIGNEE"
else
    python get_issues.py --start "$PHASE2_START" --end "$PHASE2_END"
fi
echo -e "${GREEN}  ✓ Phase 2 report generated${NC}"
echo ""

# Step 4: Generate Phase 3 report (Full AI period)
echo -e "${YELLOW}Step 4: Generating Phase 3 report (Full AI: $PHASE3_START to $PHASE3_END)...${NC}"
if [ -n "$ASSIGNEE" ]; then
    python get_issues.py --start "$PHASE3_START" --end "$PHASE3_END" --assignee "$ASSIGNEE"
else
    python get_issues.py --start "$PHASE3_START" --end "$PHASE3_END"
fi
echo -e "${GREEN}  ✓ Phase 3 report generated${NC}"
echo ""

# Step 5: Generate comparison report
echo -e "${YELLOW}Step 5: Generating comparison report...${NC}"
if [ -n "$ASSIGNEE" ]; then
    python generate_comparison_report.py --assignee "$ASSIGNEE"
else
    python generate_comparison_report.py
fi
echo ""

# Step 6: Show results
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All reports generated successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}Generated files:${NC}"
if [ -n "$ASSIGNEE" ]; then
    ls -lh reports/jira_report_${USERNAME}_*.txt 2>/dev/null || echo "  (no Jira reports found)"
    ls -lh reports/comparison_report_${USERNAME}_*.csv 2>/dev/null || echo "  (no comparison report found)"
else
    ls -lh reports/jira_report_general_*.txt 2>/dev/null || echo "  (no Jira reports found)"
    ls -lh reports/comparison_report_general_*.csv 2>/dev/null || echo "  (no comparison report found)"
fi

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Open the comparison_report_*.csv file in reports/ directory"
echo "  2. Copy all content (Ctrl+A, Ctrl+C)"
echo "  3. Paste into Google Sheets"
echo "  4. The data will be automatically formatted"
echo ""

# Display a preview of the comparison report
if [ -n "$ASSIGNEE" ]; then
    COMPARISON_FILE=$(ls -t reports/comparison_report_${USERNAME}_*.csv 2>/dev/null | head -1)
else
    COMPARISON_FILE=$(ls -t reports/comparison_report_general_*.csv 2>/dev/null | head -1)
fi

if [ -f "$COMPARISON_FILE" ]; then
    echo -e "${BLUE}Preview of comparison report ($COMPARISON_FILE):${NC}"
    echo "----------------------------------------"
    head -20 "$COMPARISON_FILE"
    echo "----------------------------------------"
    echo "(showing first 20 lines)"
fi

echo ""
echo -e "${GREEN}Done!${NC}"
