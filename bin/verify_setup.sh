#!/bin/bash
#
# Quick setup verification script
# This script verifies that the AI Analysis tool is properly configured
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI Analysis Setup Verification${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    echo -e "${GREEN}✓ Python $PYTHON_VERSION (>= 3.11)${NC}"
else
    echo -e "${RED}✗ Python $PYTHON_VERSION (requires >= 3.11)${NC}"
    exit 1
fi

# Check PYTHONPATH
echo -e "${YELLOW}Checking PYTHONPATH...${NC}"
if [ -z "$PYTHONPATH" ] || [[ "$PYTHONPATH" != *"ai-analysis"* ]]; then
    echo -e "${YELLOW}⚠ PYTHONPATH not set or doesn't include project root${NC}"
    echo "  Run: export PYTHONPATH=."
else
    echo -e "${GREEN}✓ PYTHONPATH configured${NC}"
fi

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
python3 -c "import requests" 2>/dev/null && echo -e "${GREEN}✓ requests${NC}" || echo -e "${RED}✗ requests (run: pip install -r requirements.txt)${NC}"

# Check module imports
echo -e "${YELLOW}Checking module imports...${NC}"
export PYTHONPATH=.
python3 -c "from ai_impact_analysis.jira_client import JiraClient" 2>/dev/null && echo -e "${GREEN}✓ JiraClient${NC}" || echo -e "${RED}✗ JiraClient import failed${NC}"
python3 -c "from ai_impact_analysis.github_client import GitHubClient" 2>/dev/null && echo -e "${GREEN}✓ GitHubClient${NC}" || echo -e "${RED}✗ GitHubClient import failed${NC}"
python3 -c "from ai_impact_analysis.utils import convert_date_to_jql" 2>/dev/null && echo -e "${GREEN}✓ utils${NC}" || echo -e "${RED}✗ utils import failed${NC}"

# Check configuration files
echo -e "${YELLOW}Checking configuration files...${NC}"
[ -f "config/jira_phases.conf" ] && echo -e "${GREEN}✓ config/jira_phases.conf${NC}" || echo -e "${RED}✗ config/jira_phases.conf missing${NC}"
[ -f "config/github_phases.conf" ] && echo -e "${GREEN}✓ config/github_phases.conf${NC}" || echo -e "${RED}✗ config/github_phases.conf missing${NC}"

# Check Jira environment variables
echo -e "${YELLOW}Checking Jira configuration...${NC}"
[ -n "$JIRA_URL" ] && echo -e "${GREEN}✓ JIRA_URL set${NC}" || echo -e "${YELLOW}⚠ JIRA_URL not set${NC}"
[ -n "$JIRA_API_TOKEN" ] && echo -e "${GREEN}✓ JIRA_API_TOKEN set${NC}" || echo -e "${YELLOW}⚠ JIRA_API_TOKEN not set${NC}"
[ -n "$JIRA_PROJECT_KEY" ] && echo -e "${GREEN}✓ JIRA_PROJECT_KEY set${NC}" || echo -e "${YELLOW}⚠ JIRA_PROJECT_KEY not set${NC}"

# Check GitHub environment variables
echo -e "${YELLOW}Checking GitHub configuration...${NC}"
[ -n "$GITHUB_TOKEN" ] && echo -e "${GREEN}✓ GITHUB_TOKEN set${NC}" || echo -e "${YELLOW}⚠ GITHUB_TOKEN not set${NC}"
[ -n "$GITHUB_REPO_OWNER" ] && echo -e "${GREEN}✓ GITHUB_REPO_OWNER set${NC}" || echo -e "${YELLOW}⚠ GITHUB_REPO_OWNER not set${NC}"
[ -n "$GITHUB_REPO_NAME" ] && echo -e "${GREEN}✓ GITHUB_REPO_NAME set${NC}" || echo -e "${YELLOW}⚠ GITHUB_REPO_NAME not set${NC}"

# Check scripts
echo -e "${YELLOW}Checking scripts...${NC}"
[ -x "bin/generate_jira_report.sh" ] && echo -e "${GREEN}✓ bin/generate_jira_report.sh executable${NC}" || echo -e "${YELLOW}⚠ bin/generate_jira_report.sh not executable (run: chmod +x bin/generate_jira_report.sh)${NC}"
[ -x "bin/generate_pr_report.sh" ] && echo -e "${GREEN}✓ bin/generate_pr_report.sh executable${NC}" || echo -e "${YELLOW}⚠ bin/generate_pr_report.sh not executable (run: chmod +x bin/generate_pr_report.sh)${NC}"

# Test script help
echo -e "${YELLOW}Testing script help messages...${NC}"
python3 -m ai_impact_analysis.cli.get_jira_metrics --help > /dev/null 2>&1 && echo -e "${GREEN}✓ get_jira_metrics.py${NC}" || echo -e "${RED}✗ get_jira_metrics.py failed${NC}"
python3 -m ai_impact_analysis.cli.get_pr_metrics --help > /dev/null 2>&1 && echo -e "${GREEN}✓ get_pr_metrics.py${NC}" || echo -e "${RED}✗ get_pr_metrics.py failed${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ -n "$JIRA_URL" ] && [ -n "$JIRA_API_TOKEN" ]; then
    echo -e "${GREEN}✓ Jira analysis ready${NC}"
    echo "  Run: bash bin/generate_jira_report.sh"
else
    echo -e "${YELLOW}⚠ Jira analysis not configured${NC}"
    echo "  Set: JIRA_URL, JIRA_API_TOKEN, JIRA_PROJECT_KEY"
fi

if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO_OWNER" ]; then
    echo -e "${GREEN}✓ GitHub analysis ready${NC}"
    echo "  Run: bash bin/generate_pr_report.sh"
else
    echo -e "${YELLOW}⚠ GitHub analysis not configured${NC}"
    echo "  Set: GITHUB_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME"
fi

echo ""
echo -e "${BLUE}For detailed setup instructions, see README.md${NC}"
echo ""
