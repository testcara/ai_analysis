# AI Impact Analysis

- [Overview](#overview)
- [Usage](#usage)
  - [Quick start](#quick-start)
  - [Generate Jira reports](#generate-jira-reports)
  - [Manual usage](#manual-usage)
  - [Generate GitHub PR reports](#generate-github-pr-reports)
- [Understanding Report Metrics](#understanding-report-metrics)
  - [Basic Metrics](#basic-metrics)
  - [State Time Metrics](#state-time-metrics)
  - [Re-entry Rate Metrics](#re-entry-rate-metrics)
  - [Issue Type Distribution](#issue-type-distribution)
  - [Interpreting the Metrics](#interpreting-the-metrics)
- [Developer](#developer)
  - [Contributing](#contributing)
  - [Project structure](#project-structure)
- [Tests](#tests)
  - [Test Types](#test-types)
  - [Manual Testing](#manual-testing)
  - [Continuous Integration](#continuous-integration)
  - [Troubleshooting](#troubleshooting)
  - [Test Maintenance](#test-maintenance)

## Overview

AI Impact Analysis is a comprehensive Python tool to analyze the impact of AI tools on development efficiency through data-driven metrics. It provides two types of analysis:

1. **Jira Issue Analysis**: Compare issue closure times, state durations, and workflow metrics across different time periods
2. **GitHub PR Analysis**: Analyze pull request metrics to measure AI tool impact on code review and merge efficiency

### Key Features

- **Flexible Configuration**: Define custom analysis phases with configurable date ranges to match your AI adoption timeline
- **Team & Individual Analysis**: Generate reports for entire teams or individual contributors
- **Automated Workflows**: One-command report generation with automated phase-by-phase analysis
- **Comparative Insights**: Compare metrics across multiple time periods (e.g., Before AI, Cursor adoption, Full AI toolkit)
- **Google Sheets Integration**: Automatically upload reports for easy sharing and collaboration
- **Extensible Design**: Support for multiple AI tools (Claude, Cursor) with detection via Git commit trailers

The tool helps teams quantify the impact of AI coding assistants through objective metrics, enabling data-driven decisions about AI tool adoption and usage patterns.

## Usage

### Quick start

To start using the tool follow the procedure below:

1. Clone the repo: `git clone https://github.com/testcara/ai_impact_analysis.git`
2. Create a virtual environment with `python3 -m venv venv && source venv/bin/activate`
3. Install dependencies with `pip install -r requirements.txt`
4. Set the python app path to the repo root directory with `export PYTHONPATH=.`
5. Set environment variables:

```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_API_TOKEN="your_api_token_here"
export JIRA_PROJECT_KEY="Konflux UI"

# For GitHub PR analysis (optional)
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO_OWNER="your-org-or-username"
export GITHUB_REPO_NAME="your-repo-name"
```

6. **Verify your setup** (recommended):

```bash
python3 -m ai_impact_analysis.scripts.verify_setup
```

This will check:

- ✅ Python version (>= 3.11)
- ✅ Dependencies installed
- ✅ Configuration files exist
- ✅ Environment variables set
- ✅ Module imports working

### Generate Jira reports

**For team overall analysis:**

```bash
python3 -m ai_impact_analysis.scripts.generate_jira_report

# With custom config
python3 -m ai_impact_analysis.scripts.generate_jira_report --config my-custom-config.yaml
```

**For individual team member:**

```bash
# Option 1: Set default assignee in config/jira_report_config.yaml
# Then just run: python3 -m ai_impact_analysis.scripts.generate_jira_report

# Option 2: Specify assignee via command line (overrides config)
python3 -m ai_impact_analysis.scripts.generate_jira_report user@redhat.com

# Option 3: Use custom config with different default_assignee
python3 -m ai_impact_analysis.scripts.generate_jira_report --config my-config.yaml
```

**For all team members at once:**

```bash
python3 -m ai_impact_analysis.scripts.generate_jira_report --all-members

# With custom config (uses team_members from custom config)
python3 -m ai_impact_analysis.scripts.generate_jira_report --all-members --config my-config.yaml
```

The script will:

1. Load configuration from `config/jira_report_config.yaml` (phases + default assignee + team members)
2. Clean up old reports
3. Generate reports for all configured phases
4. Create a comparison TSV file in `reports/` directory
5. **Automatically upload to Google Sheets** (if configured, see below)

**Customize configuration:**

Edit `config/jira_report_config.yaml` to configure analysis periods, default assignee, and team members:

```yaml
# config/jira_report_config.yaml

# Define analysis phases (flexible: 1 to many)
phases:
  - name: "No AI Period"
    start: "2024-10-24"
    end: "2025-05-30"
  - name: "Cursor Period"
    start: "2025-06-02"
    end: "2025-07-31"
  - name: "Full AI Period"
    start: "2025-08-01"
    end: "2025-11-03"

# Default assignee (optional)
# - Set to "" for team overall reports (default)
# - Set to email for individual reports (e.g., "wlin@redhat.com")
# - Command line argument will override this value
default_assignee: ""

# Team members (optional, for --all-members mode)
team_members:
  - member: wlin
    email: wlin@redhat.com
    leave_days:
      - 26 # No AI Period
      - 20 # Cursor Period
      - 11.5 # Full AI Period
    capacity: 0.8
  - member: sbudhwar
    email: sbudhwar@redhat.com
    leave_days: 0
    capacity: 1.0
  - member: abhindas
    email: abhindas@redhat.com
    leave_days: 0
    capacity:
      - 1.0 # No AI Period (full time)
      - 1.0 # Cursor Period (full time)
      - 0.0 # Full AI Period (left team)
```

**Phase configuration:**

- Add as many phases as needed for your analysis
- Use descriptive names (e.g., "No AI Period", "Cursor Only", "Claude + Cursor")
- Dates must be in YYYY-MM-DD format

**Team members configuration:**

- `member`: Jira username
- `email`: Email address for filtering
- `leave_days`: Leave days for each phase
  - Can be a single number (applies to all phases): `leave_days: 0`
  - Or a list (one value per phase): `leave_days: [26, 20, 11.5]`
- `capacity`: Work capacity (0.0 to 1.0, where 1.0 = full time)
  - Can be a single number (applies to all phases): `capacity: 0.8`
  - Or a list (one value per phase): `capacity: [1.0, 1.0, 0.0]`
  - Use 0.0 to indicate member left team in that phase

**Assignee configuration:**

- Leave `default_assignee: ""` for team reports
- Set `default_assignee: "wlin@redhat.com"` to always generate reports for specific person
- Command line argument overrides config: `python3 -m ai_impact_analysis.scripts.generate_jira_report other@redhat.com`

**Using custom configuration:**

You can create a custom YAML file to override default settings. Only include the values you want to change:

```yaml
# my-config.yaml - Example custom config

# Override only phases (keep default team members)
phases:
  - name: "Q1 2024"
    start: "2024-01-01"
    end: "2024-03-31"
  - name: "Q2 2024"
    start: "2024-04-01"
    end: "2024-06-30"

# Or override only team members (keep default phases)
team_members:
  - member: alice
    email: alice@company.com
    leave_days: 5
    capacity: 1.0
  - member: bob
    email: bob@company.com
    leave_days: 0
    capacity: 0.5
```

Use custom config:

```bash
# For individual phase report
python3 -m ai_impact_analysis.scripts.get_jira_metrics --start 2024-01-01 --end 2024-03-31 --config my-config.yaml

# For full report workflow
python3 -m ai_impact_analysis.scripts.generate_jira_report --config my-config.yaml
```

**How config merging works:**

- Values in custom config override defaults from `config/jira_report_config.yaml`
- Missing values in custom config are taken from default config
- This allows you to change only what you need without duplicating entire config

**Understanding Leave Days and Capacity:**

These metrics help calculate more accurate throughput by accounting for time off and work capacity:

- **Leave Days**: Days the team member was on leave during the phase

  - Displayed in single reports and comparison reports
  - Can be specified per phase (list) or as single value
  - For team reports: sum of all members' leave days

- **Capacity**: Work capacity as percentage of full-time (0.0 to 1.0)

  - `1.0` = Full time (100%)
  - `0.8` = 80% time (e.g., 4 days/week)
  - `0.5` = Half time
  - `0.0` = Not on team (member left)
  - For team reports: sum of all members' capacity (total FTE)

- **Data Span**: Always calculated as Phase end date - Phase start date + 1
  ```bash
  # Example: Phase from 2024-01-01 to 2024-01-31
  # Data Span = 31 days (includes both start and end dates)
  ```

**How metrics use Leave Days and Capacity:**

Reports now include **four Daily Throughput metrics** to provide comprehensive analysis:

1. **Daily Throughput (skip leave days)** = Total Issues / (Analysis Period - Leave Days)

   - Accounts for vacation time

2. **Daily Throughput (based on capacity)** = Total Issues / (Analysis Period × Capacity)

   - Accounts for part-time work

3. **Daily Throughput (considering leave days + capacity)** = Total Issues / ((Analysis Period - Leave Days) × Capacity)

   - Most accurate: accounts for both vacation and capacity

4. **Daily Throughput** = Total Issues / Analysis Period
   - Baseline metric for comparison

### Manual usage

**Generate individual phase report:**

```bash
python3 -m ai_impact_analysis.scripts.get_jira_metrics --start 2024-10-24 --end 2025-05-30
python3 -m ai_impact_analysis.scripts.get_jira_metrics --start 2024-10-24 --end 2025-05-30 --assignee "user@redhat.com"

# Use custom config file
python3 -m ai_impact_analysis.scripts.get_jira_metrics --start 2024-10-24 --end 2025-05-30 --config my-custom-config.yaml
```

**Available parameters:**

- `--start` - Start date (YYYY-MM-DD)
- `--end` - End date (YYYY-MM-DD)
- `--status` - Issue status (default: Done)
- `--project` - Project key (overrides JIRA_PROJECT_KEY)
- `--assignee` - Assignee username or email
- `--config` - Path to custom config YAML file (overrides settings from default config)
- `--leave-days` - Number of leave days for this phase (e.g., '26' or '11.5')
- `--capacity` - Work capacity for this member (0.0 to 1.0, e.g., '0.8' for 80% time)

**Generate comparison report:**

```bash
# Team comparison (uses last 3 reports in reports/ directory)
python3 -m ai_impact_analysis.scripts.generate_jira_comparison_report

# Individual comparison
python3 -m ai_impact_analysis.scripts.generate_jira_comparison_report --assignee user@redhat.com
```

**Upload report to Google Sheets:**

```bash
# Upload the most recent Jira comparison report
python3 -m ai_impact_analysis.scripts.upload_to_sheets --report reports/comparison_report_*.tsv

# Upload a specific report
python3 -m ai_impact_analysis.scripts.upload_to_sheets --report reports/comparison_report_username_20241028_123456.tsv

# Note: Requires Google Sheets setup - see "Upload to Google Sheets" section below
```

### Generate GitHub PR reports

The GitHub PR analysis detects AI assistance by looking for "Assisted-by: Claude" or "Assisted-by: Cursor" in commit messages, then compares AI-assisted PRs with non-AI PRs.

**Setup GitHub access:**

```bash
# 1. Create GitHub Personal Access Token
#    Go to https://github.com/settings/tokens
#    Generate new token with 'repo' scope (or 'public_repo' for public repos only)

# 2. Set environment variables (add to ~/.bashrc for persistence)
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO_OWNER="your-org-name"  # e.g., "konflux-ci"
export GITHUB_REPO_NAME="your-repo-name"   # e.g., "konflux-ui"
```

**For team overall analysis:**

```bash
python3 -m ai_impact_analysis.scripts.generate_pr_report
```

**For individual team member:**

```bash
# Option 1: Set default author in config/pr_report_config.yaml
# Then just run: python3 -m ai_impact_analysis.scripts.generate_pr_report

# Option 2: Specify author via command line (overrides config)
python3 -m ai_impact_analysis.scripts.generate_pr_report wlin
```

**For all team members at once:**

```bash
python3 -m ai_impact_analysis.scripts.generate_pr_report --all-members
```

**For faster incremental updates:**

```bash
# Only fetch new/updated PRs since last run
python3 -m ai_impact_analysis.scripts.generate_pr_report --incremental
```

The script will:

1. Load configuration from `config/pr_report_config.yaml` (phases + default author + team members)
2. Clean up old reports
3. Collect PR metrics for all configured phases
4. Generate a comparison TSV file in `reports/github/` directory
5. **Automatically upload to Google Sheets** (if configured, see below)

**Customize time periods:**

Edit `config/pr_report_config.yaml` to change the analysis periods and team members:

```yaml
# config/pr_report_config.yaml

phases:
  - name: "No AI Period"
    start: "2024-10-24"
    end: "2025-05-30"
  - name: "Cursor Period"
    start: "2025-06-02"
    end: "2025-07-31"
  - name: "Full AI Period"
    start: "2025-08-01"
    end: "2025-11-03"

# Default author (optional)
# - Set to "" for team overall reports (default)
# - Set to GitHub username for individual reports (e.g., "wlin")
default_author: ""

# Team members (optional, for --all-members mode)
team_members:
  - name: testcara
  - name: wlin
  - name: sahil143
```

**Manual usage:**

If you prefer to run individual commands:

```bash
# Collect PR metrics for one period (uses optimized GraphQL API by default)
python3 -m ai_impact_analysis.scripts.get_pr_metrics --start 2024-10-01 --end 2024-10-31
python3 -m ai_impact_analysis.scripts.get_pr_metrics --start 2024-10-01 --end 2024-10-31 --author wlin

# For faster repeated runs, use incremental mode (only fetches new/updated PRs)
python3 -m ai_impact_analysis.scripts.get_pr_metrics --start 2024-10-01 --end 2024-10-31 --incremental

# Clear cache if needed (force re-fetch all data)
python3 -m ai_impact_analysis.scripts.get_pr_metrics --start 2024-10-01 --end 2024-10-31 --clear-cache

# Generate comparison report (requires multiple period reports)
python3 -m ai_impact_analysis.scripts.generate_pr_comparison_report
python3 -m ai_impact_analysis.scripts.generate_pr_comparison_report --author wlin

# Upload report to Google Sheets
python3 -m ai_impact_analysis.scripts.upload_to_sheets --report reports/github/pr_comparison_*.tsv
python3 -m ai_impact_analysis.scripts.upload_to_sheets --report reports/github/pr_comparison_wlin_*.tsv

# Note: Requires Google Sheets setup - see "Upload to Google Sheets" section below
```

**Performance Tips:**

- The tool uses GraphQL API by default, which is **20x faster** than the legacy REST API
- Built-in caching makes repeated runs nearly instant
- Use `--incremental` for daily/weekly reports to only fetch new data
- Use `--clear-cache` only when you need to force a complete refresh

**AI Detection in Commits:**

The tool detects AI assistance from Git commit trailers. Add these to your commit messages:

```bash
# For Claude assistance
git commit -m "Fix authentication bug

Assisted-by: Claude <noreply@anthropic.com>"

# For Cursor assistance
git commit -m "Implement new feature

Assisted-by: Cursor"

# Both tools (multiple commits in PR)
# Some commits with Claude, some with Cursor
```

**PR Metrics Collected:**

- Time to merge (PR creation → merged)
- Time to first review
- Review iterations (changes requested)
- Commits per PR
- Code size (additions, deletions, files changed)
- Review comments count
- AI vs non-AI comparison

**Note:** PRs created by bots (CodeRabbit, Dependabot, Renovate, GitHub Actions, red-hat-konflux, etc.) are automatically excluded from analysis to focus on human-authored code.

**Report outputs:**

- `reports/github/pr_metrics_YYYYMMDD_HHMMSS.json` - Team PR metrics (JSON)
- `reports/github/pr_report_YYYYMMDD_HHMMSS.txt` - Team PR metrics (human-readable)
- `reports/github/pr_metrics_{author}_YYYYMMDD_HHMMSS.json` - Individual PR metrics
- `reports/github/pr_comparison_general_YYYYMMDD_HHMMSS.tsv` - Team comparison report
- `reports/github/pr_comparison_{author}_YYYYMMDD_HHMMSS.tsv` - Individual comparison report

### Upload to Google Sheets (optional)

Reports can be **automatically uploaded** to Google Sheets if configured, or uploaded manually.

**Setup (one-time):**

```bash
# 1. Install Google Sheets dependencies
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

# 2. Create Service Account at https://console.cloud.google.com
#    - Create project and enable Google Sheets API
#    - Create Service Account credentials
#    - Download JSON key file
#    - Note the Service Account email (client_email in JSON)

# 3. Create Google Spreadsheet (recommended)
#    - Go to https://sheets.google.com and create new spreadsheet
#    - Name it like: "AI Analysis - wlin"
#    - Click "Share" and add Service Account email with Editor permission
#    - Copy Spreadsheet ID from URL: https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit

# 4. Configure environment variables for automatic upload
export GOOGLE_CREDENTIALS_FILE="/path/to/service-account-key.json"
export GOOGLE_SPREADSHEET_ID="1ABCdefGHI..."

# Add to ~/.bashrc for persistence
echo 'export GOOGLE_CREDENTIALS_FILE="/path/to/service-account-key.json"' >> ~/.bashrc
echo 'export GOOGLE_SPREADSHEET_ID="1ABCdefGHI..."' >> ~/.bashrc
```

**Usage:**

```bash
# Automatic upload (if environment variables configured)
python3 -m ai_impact_analysis.scripts.generate_jira_report    # Generates & auto-uploads Jira report
python3 -m ai_impact_analysis.scripts.generate_pr_report      # Generates & auto-uploads PR report

# Manual upload (if auto-upload not configured)
python3 -m ai_impact_analysis.scripts.upload_to_sheets --report reports/comparison_report_wlin_*.tsv
python3 -m ai_impact_analysis.scripts.upload_to_sheets --report reports/github/pr_comparison_wlin_*.tsv
```

**Features:**

- Each upload creates a new tab with timestamp (e.g., "wlin Report - 2025-10-24 14:30")
- All previous tabs are preserved for historical tracking
- You can use the same spreadsheet for both Jira and GitHub reports (different tabs)
- If auto-upload not configured, scripts show manual upload instructions

**Output files:**

Reports are saved in `reports/` directory:

- `jira_report_YYYYMMDD_HHMMSS.txt` - Team phase reports
- `jira_report_{assignee}_YYYYMMDD_HHMMSS.txt` - Individual phase reports
- `comparison_report_YYYYMMDD_HHMMSS.tsv` - Team comparison (TSV format)
- `comparison_report_{assignee}_YYYYMMDD_HHMMSS.tsv` - Individual comparison

**Report metrics** (see [Understanding Report Metrics](#understanding-report-metrics) for detailed explanations):

- Average closure time
- Daily throughput
- Time in each state (New, To Do, In Progress, Review, etc.)
- State re-entry rates (indication of rework)
- Issue type distribution (Story, Task, Bug, Epic)

## Understanding Report Metrics

This section explains what each metric means and how it's calculated.

### GitHub PR Report Metrics

GitHub PR reports analyze pull request activity and review efficiency. Below are detailed explanations of each metric.

**Total PRs Merged (excl. bot-authored)**

- **What it is**: Count of all human-authored pull requests that were merged during the analysis period
- **How it's calculated**: Direct count from GitHub API query filtering by merged status, date range, and excluding bot authors (CodeRabbit, Dependabot, Renovate, GitHub Actions, red-hat-konflux)
- **Example**: 25 PRs merged (bot-authored PRs like dependency updates are excluded)
- **Why it matters**: Indicates overall human code delivery volume; focuses analysis on developer work rather than automated PRs

**AI Adoption Rate**

- **What it is**: Percentage of merged PRs that used AI coding assistants (Claude, Cursor)
- **How it's calculated**: `(AI-Assisted PRs / Total PRs) × 100%`
- **Detection method**: Analyzes Git commit messages for "Assisted-by: Claude" or "Assisted-by: Cursor" trailers
- **Example**: 40% means 40% of PRs included AI-generated code
- **Why it matters**: Tracks AI tool adoption across the team

**AI-Assisted PRs / Non-AI PRs**

- **What it is**: Count breakdown of PRs with vs without AI assistance
- **Example**: 10 AI-assisted, 15 non-AI
- **Why it matters**: Shows absolute numbers behind adoption rate

**Claude PRs / Cursor PRs**

- **What it is**: Count of PRs using each specific AI tool
- **Note**: PRs can use multiple tools (some commits with Claude, others with Cursor)
- **Why it matters**: Tracks which AI tools are most popular

**Avg Time to Merge (days)**

- **What it is**: Average time from PR creation to merge
- **How it's calculated**: `Sum(Merged Date - Created Date) / Total PRs`, in days
- **Example**: 3.5d means PRs take 3.5 days on average from opening to merge
- **Why it matters**: Primary delivery speed indicator; lower values mean faster deployment

**Avg Time to First Review (hours)**

- **What it is**: Average time from PR creation until first human review is submitted
- **How it's calculated**: `Sum(First Review Time - Created Time) / PRs with Reviews`, in hours
- **Example**: 2.5h means PRs get initial review within 2.5 hours
- **Why it matters**: Indicates team responsiveness; faster reviews reduce PR cycle time

**Avg Changes Requested**

- **What it is**: Average number of times reviewers request changes per PR
- **How it's calculated**: Count of "CHANGES_REQUESTED" review states divided by total PRs
- **Example**: 0.8 means most PRs pass with minimal change requests
- **Why it matters**: Code quality indicator; lower values suggest better initial quality

**Avg Commits per PR**

- **What it is**: Average number of commits in each PR
- **How it's calculated**: `Sum(Commit Count) / Total PRs`
- **Example**: 2.3 commits per PR
- **Why it matters**: Can indicate PR size and complexity; very high values may suggest scope creep

**Avg Reviewers**

- **What it is**: Average number of unique reviewers per PR (includes all users, including bots)
- **How it's calculated**: `Sum(Unique Reviewer Count) / Total PRs`
- **Example**: 3.2 reviewers per PR
- **Why it matters**: Indicates code review coverage

**Avg Reviewers (excl. bots)**

- **What it is**: Average number of human reviewers per PR (excludes bots like CodeRabbit, Dependabot)
- **Bots excluded**: coderabbit, dependabot, renovate, github-actions, red-hat-konflux
- **Example**: 2.1 human reviewers per PR
- **Why it matters**: Shows actual human engagement in code review

**Avg Comments**

- **What it is**: Average total comments per PR (includes inline code comments, discussion comments, and review submission comments)
- **Includes**: All users (humans + bots), all comment types (including simple approvals)
- **Example**: 15.5 comments per PR
- **Why it matters**: Indicates overall review activity level

**Avg Comments (excl. bots & approvals)**

- **What it is**: Average substantive human discussion per PR
- **Excludes**:
  - Bot comments (from CodeRabbit, Dependabot, etc.)
  - Simple approval comments (empty or "LGTM", "approved", "👍")
  - Comments mentioning `@coderabbit` (human interactions with the bot)
- **Includes**: Only meaningful human-to-human review discussion
- **Example**: 5.2 substantive comments per PR
- **Why it matters**: Shows quality of human code review engagement; helps distinguish between bot activity and real human discussion

**Avg Lines Added / Deleted**

- **What it is**: Average code change size (additions and deletions)
- **How it's calculated**: Sum of additions/deletions across all PRs divided by PR count
- **Example**: 125 lines added, 45 lines deleted
- **Why it matters**: Indicates PR size and scope

**Avg Files Changed**

- **What it is**: Average number of files modified per PR
- **Example**: 8.5 files per PR
- **Why it matters**: Another PR size indicator; high values may indicate refactoring or cross-cutting changes

**Understanding the Metrics:**

_Bot vs Human Metrics:_

- Regular metrics include all activity (bots + humans)
- "(excl. bots)" metrics show only human engagement
- The difference reveals bot contribution (e.g., CodeRabbit's review impact)

_Comment Quality:_

- "Avg Comments" = All comments including bot reviews and simple "LGTM"
- "Avg Comments (excl. bots & approvals)" = Substantive human discussion only
- Large difference indicates heavy bot usage or many simple approvals

**Positive AI Impact Indicators:**

- ↓ Avg Time to Merge (faster delivery)
- ↓ Avg Time to First Review (quicker team response)
- ↓ Avg Changes Requested (better code quality on first attempt)
- ↑ AI Adoption Rate (increasing tool usage)
- Stable or ↑ Avg Reviewers (excl. bots) (maintained human oversight)

**Things to Watch:**

- If "Avg Comments" is much higher than "Avg Comments (excl. bots & approvals)" → heavy bot reliance
- If "Avg Reviewers (excl. bots)" decreases significantly → potential reduction in human oversight
- If Avg Time to Merge decreases but Avg Changes Requested increases → speed without quality improvement

### Jira Report Metrics

This section explains Jira issue metrics and how they're calculated.

#### Understanding N/A Values in Reports

**N/A (Not Applicable)** appears in reports when data is unavailable or not applicable for a specific metric:

**When N/A appears:**

1. **State Time Metrics** (e.g., "Waiting State Avg Time: N/A")

   - **Meaning**: No issues entered this workflow state during the period
   - **Example**: If "Waiting State Avg Time" shows N/A, it means zero issues were blocked/waiting
   - **Interpretation**: Could be positive (smooth workflow, no blockers) or simply mean that state isn't used in your workflow

2. **Re-entry Rate Metrics** (e.g., "Waiting Re-entry Rate: N/A")

   - **Meaning**: No issues re-entered this state (rate would be 0.00x)
   - **Example**: If "Review Re-entry Rate" shows N/A, all reviews passed on first attempt
   - **Interpretation**: Generally positive - indicates no rework in that state

3. **Period Information** (e.g., "Analysis Period: N/A")

   - **Meaning**: Date information is missing or couldn't be calculated
   - **Rare occurrence**: Usually indicates data quality issues in Jira

4. **Throughput Metrics** (e.g., "Daily Throughput: N/A")
   - **Meaning**: Period days couldn't be calculated, so throughput can't be computed
   - **Depends on**: Valid date range being available

**Comparing N/A across phases:**

| Metric           | Phase 1 | Phase 2 | Phase 3 | Interpretation                                         |
| ---------------- | ------- | ------- | ------- | ------------------------------------------------------ |
| Waiting State    | 30.77d  | N/A     | N/A     | Workflow improved - no blocking issues in later phases |
| Review Re-entry  | 1.13x   | N/A     | N/A     | Code quality improved - reviews pass first time        |
| Waiting Re-entry | 1.24x   | 1.33x   | N/A     | Further improvement in Phase 3 - no blocked issues     |

**Best practices:**

- **Don't ignore N/A** - it often indicates positive workflow improvements
- **Compare across phases** - N/A appearing in later phases may show AI tool benefits
- **Context matters** - N/A for "Waiting" is good; N/A for core states like "In Progress" would be concerning

#### Basic Metrics

**Analysis Period**

- **What it is**: The time range covered by the data, calculated from the earliest resolved issue to the latest resolved issue
- **How it's calculated**: `(Latest Resolved Date) - (Earliest Resolved Date)`
- **Example**: If issues were resolved between 2024-10-24 and 2025-05-30, the period is 218 days
- **Why it matters**: Provides context for comparing throughput across different phases

**Total Issues Completed**

- **What it is**: Count of all Jira issues that reached "Done" status during the analysis period
- **How it's calculated**: Direct count from Jira API query with `status = Done` and resolved date filters
- **Example**: 45 issues completed
- **Why it matters**: Indicates overall team productivity volume

**Average Closure Time**

- **What it is**: Average time from issue creation to resolution (moved to "Done" status)
- **How it's calculated**: `Sum(Resolution Date - Created Date) / Total Issues`
- **Example**: 12.5 days means on average issues take 12.5 days from creation to completion
- **Why it matters**: Primary indicator of development velocity; lower is generally better

**Longest Closure Time**

- **What it is**: Maximum time any single issue took from creation to resolution
- **How it's calculated**: `Max(Resolution Date - Created Date)` across all issues
- **Example**: 45.2 days
- **Why it matters**: Identifies outliers and potential bottlenecks; extremely long closure times may indicate blocked or complex issues

**Leave Days**

- **What it is**: Total leave days during the analysis period
- **Individual reports**: Member's leave days for this phase
- **Team reports**: Sum of all team members' leave days
- **Example**: 26 days (individual), 37.5 days (team total)
- **Why it matters**: Provides context for throughput calculations; helps explain productivity variations

**Capacity**

- **What it is**: Work capacity as percentage of full-time equivalent (FTE)
- **Individual reports**: Member's work capacity (0.0 to 1.0)
- **Team reports**: Sum of all members' capacity (total FTE)
- **Example**: 0.8 (80% time, individual), 4.5 (4.5 FTE total, team)
- **Why it matters**: Accounts for part-time work; capacity = 0.0 indicates member left team

**Daily Throughput (4 variants)**

The tool calculates four throughput metrics to provide comprehensive productivity analysis:

1. **Daily Throughput (skip leave days)**

   - **Formula**: `Total Issues / (Analysis Period - Leave Days)`
   - **Example**: 28 issues / (220 - 26) days = 0.14/d
   - **Use case**: Accounts for vacation time

2. **Daily Throughput (based on capacity)**

   - **Formula**: `Total Issues / (Analysis Period × Capacity)`
   - **Example**: 28 issues / (220 × 0.8) = 0.16/d
   - **Use case**: Accounts for part-time work

3. **Daily Throughput (considering leave days + capacity)**

   - **Formula**: `Total Issues / ((Analysis Period - Leave Days) × Capacity)`
   - **Example**: 28 issues / ((220 - 26) × 0.8) = 0.18/d
   - **Use case**: Most accurate - accounts for both vacation and capacity

4. **Daily Throughput**
   - **Formula**: `Total Issues / Analysis Period`
   - **Example**: 28 issues / 220 days = 0.13/d
   - **Use case**: Baseline metric for simple comparison

### State Time Metrics

These metrics track how long issues spend in each workflow state. The calculation uses Jira's changelog to track every status transition.

**How State Times are Calculated:**

1. For each issue, we extract its complete status transition history from Jira changelog
2. We calculate time spent in each state by measuring time between transitions:
   - `State Duration = (Transition Out Time) - (Transition In Time)`
3. If an issue enters the same state multiple times (re-entry), all durations are summed
4. Average is calculated across all issues: `Avg State Time = Sum(All State Durations) / Number of Issues`

**Common States:**

**New State Avg Time**

- **What it is**: Average time issues spend in "New" state (freshly created, not yet triaged)
- **Example**: 0.5d means issues typically wait half a day before being triaged
- **Why it matters**: High values suggest backlog grooming delays

**To Do State Avg Time**

- **What it is**: Average time issues spend in "To Do" state (triaged but not started)
- **Example**: 3.2d means issues wait 3.2 days after triage before work begins
- **Why it matters**: Indicates queue time; high values suggest resource constraints or prioritization issues

**In Progress State Avg Time**

- **What it is**: Average time issues spend actively being worked on
- **Example**: 5.5d means active development typically takes 5.5 days
- **Why it matters**: Core development efficiency metric; directly impacted by coding speed and tools

**Review State Avg Time**

- **What it is**: Average time issues spend in code review
- **Example**: 1.2d means code reviews take 1.2 days on average
- **Why it matters**: High values indicate review bottlenecks or insufficient reviewer capacity

**Release Pending State Avg Time**

- **What it is**: Average time issues wait for deployment/release
- **Example**: 2.0d means features wait 2 days to be deployed
- **Why it matters**: Indicates deployment frequency and release process efficiency

**Waiting State Avg Time**

- **What it is**: Average time issues spend blocked or waiting for external dependencies
- **Example**: 4.5d means blocked issues wait 4.5 days for resolution
- **Why it matters**: High values suggest dependency management issues

### Re-entry Rate Metrics

Re-entry rates measure workflow instability and rework.

**How Re-entry Rates are Calculated:**

1. For each issue, count how many times it entered each state
2. Calculate average: `Re-entry Rate = Total State Entries / Number of Issues`
3. A rate of 1.0 means each issue entered that state exactly once (ideal)
4. A rate > 1.0 means issues frequently return to that state (rework)

**Common Re-entry Metrics:**

**To Do Re-entry Rate**

- **What it is**: Average number of times issues return to "To Do" state
- **Example**: 1.5x means issues return to "To Do" an average of 1.5 times
- **Why it matters**: Values > 1.0 indicate scope changes or requirements clarification after work started

**In Progress Re-entry Rate**

- **What it is**: Average number of times issues return to "In Progress" state
- **Example**: 2.0x means issues are actively worked on in 2 separate periods on average
- **Why it matters**: High values suggest failed reviews, bugs found during testing, or work interruptions

**Review Re-entry Rate**

- **What it is**: Average number of times issues return to "Review" state
- **Example**: 1.8x means code typically goes through review 1.8 times
- **Why it matters**: Values > 1.0 indicate changes requested during review; very high values suggest code quality issues

**Waiting Re-entry Rate**

- **What it is**: Average number of times issues become blocked
- **Example**: 1.2x means issues get blocked 1.2 times on average
- **Why it matters**: Indicates dependency management and planning quality

### Issue Type Distribution

**Story Percentage**

- **What it is**: Percentage of completed issues that are "Story" type (user-facing features)
- **How it's calculated**: `(Story Count / Total Issues) × 100%`
- **Example**: 45.5% means nearly half of work is new features
- **Why it matters**: Shows balance between feature development vs other work

**Task Percentage**

- **What it is**: Percentage of completed issues that are "Task" type (technical work, non-user-facing)
- **Example**: 30.0% means 30% of work is technical tasks
- **Why it matters**: High task percentage may indicate technical debt work or infrastructure improvements

**Bug Percentage**

- **What it is**: Percentage of completed issues that are "Bug" type
- **Example**: 20.0% means one-fifth of effort goes to bug fixes
- **Why it matters**: High bug percentage may indicate code quality issues; lower values after AI adoption suggest better code quality

**Epic Percentage**

- **What it is**: Percentage of completed issues that are "Epic" type (large initiatives)
- **Example**: 4.5%
- **Why it matters**: Usually low percentage; tracks major project milestones

### Interpreting the Metrics

**Positive AI Impact Indicators:**

- ↓ Average Closure Time (faster completion)
- ↓ In Progress State Time (faster development)
- ↓ Review State Time (fewer review cycles or better code quality)
- ↑ Daily Throughput (all variants) (more work completed)
- ↓ Re-entry Rates (less rework, better quality on first attempt)
- ↓ Bug Percentage (better code quality)

**Comparing Daily Throughput Metrics:**

- **Baseline comparison**: Use "Daily Throughput" for simple period-to-period comparison
- **Accounting for vacation**: Use "Daily Throughput (skip leave days)" when leave varies significantly
- **Accounting for team changes**: Use "Daily Throughput (based on capacity)" when members join/leave
- **Most accurate**: Use "Daily Throughput (considering leave days + capacity)" for comprehensive analysis

**Things to Watch:**

- If Average Closure Time decreases but Bug Percentage increases → speed at cost of quality
- If In Progress time decreases significantly → direct AI coding assistance working
- If Review Re-entry Rate decreases → code quality improvements (fewer change requests)
- If Waiting State time increases → may indicate external dependencies, not tool-related
- **For team reports**: If capacity decreases (members leaving) but throughput stays constant → remaining team became more productive

## Developer

AI Impact Analysis is built with Python 3.11+. The project follows a modular structure with core functionality separated into reusable modules organized by layer (clients, core, models, scripts, utils).

### Contributing

To start contributing to AI Impact Analysis, clone the repository, create a new branch and start working on improvements. When ready commit and push the changes and open a merge request. In summary:

1. `git clone https://github.com/testcara/ai_impact_analysis.git`
2. `git switch -c <new_branch> master`
3. Create virtual environment with `python3 -m venv venv && source venv/bin/activate`
4. Install dependencies with `pip install -r requirements.txt`
5. Set PYTHONPATH with `export PYTHONPATH=.`
6. Development improvements
7. Commit and push changes
8. Submit a merge request

The `master` branch is protected to avoid any issues with production code.

### Project structure

```
ai-impact-analysis/
├── ai_impact_analysis/   # Core library
│   ├── __init__.py
│   ├── clients/         # API client implementations
│   │   ├── jira_client.py           # Jira API client with pagination
│   │   ├── github_client.py         # GitHub REST API client
│   │   ├── github_client_graphql.py # GitHub GraphQL API client (faster)
│   │   └── sheets_client.py         # Google Sheets API client
│   ├── core/            # Core business logic
│   │   ├── jira_metrics_calculator.py    # Jira metrics calculation
│   │   ├── jira_report_generator.py      # Jira report generation
│   │   ├── pr_metrics_calculator.py      # PR metrics calculation
│   │   ├── pr_report_generator.py        # PR report generation
│   │   └── report_orchestrator.py        # Report workflow orchestration
│   ├── models/          # Data models
│   │   └── config.py    # Configuration models
│   ├── scripts/         # Command-line scripts
│   │   ├── get_jira_metrics.py               # Fetch and analyze Jira issues
│   │   ├── generate_jira_report.py           # Generate Jira reports workflow
│   │   ├── generate_jira_comparison_report.py # Compare Jira reports
│   │   ├── get_pr_metrics.py                 # Fetch and analyze GitHub PRs
│   │   ├── generate_pr_report.py             # Generate PR reports workflow
│   │   ├── generate_pr_comparison_report.py  # Compare PR reports
│   │   ├── upload_to_sheets.py               # Upload reports to Google Sheets
│   │   └── verify_setup.py                   # Setup verification
│   └── utils/           # Utility functions
│       ├── core_utils.py      # Date conversion, JQL building
│       ├── logger.py          # Logging configuration
│       ├── report_utils.py    # Report formatting utilities
│       └── workflow_utils.py  # Workflow helper functions
├── config/               # Configuration files
│   ├── jira_report_config.yaml # Jira analysis configuration (phases, team members)
│   └── pr_report_config.yaml   # GitHub PR analysis configuration (phases, team members)
├── tests/                # Test suite
│   ├── test_utils.py
│   ├── test_jira_client.py
│   ├── test_github_client.py
│   ├── test_jira_integration.py   # Integration tests (optional)
│   └── test_github_integration.py # Integration tests (optional)
├── reports/              # Generated reports
│   ├── jira/            # Jira issue reports
│   └── github/          # GitHub PR reports
├── requirements.txt      # Dependencies
├── pyproject.toml        # Project configuration
└── tox.ini               # Test configuration
```

## Tests

The project includes comprehensive testing for both Jira and GitHub analysis functionality.

### Test Types

#### 1. Unit Tests

Unit tests verify individual components work correctly in isolation using mocks.

**Run all unit tests:**

```bash
# Using tox (recommended) - fast, ~0.1s
tox -e unittest --develop

# Or using tox with Python version
tox -e py311 --develop

# Or using pytest directly (requires pytest installation)
pytest tests/ --ignore=tests/test_jira_integration.py --ignore=tests/test_github_integration.py -v
```

**Test coverage:**

- `tests/test_utils.py` - Utility functions (date conversion, state calculations)
- `tests/test_jira_client.py` - Jira API client
- `tests/test_github_client.py` - GitHub API client

**Run with coverage report:**

```bash
tox -e coverage --develop
```

#### 2. Integration Tests

Integration tests make real API calls to verify end-to-end functionality. **Note:** These tests are SLOW due to real network calls and require valid API credentials.

**Jira Integration Tests:**

Requirements:

```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_API_TOKEN="your_token"
export JIRA_PROJECT_KEY="Konflux UI"
export JIRA_USER_EMAIL="your@email.com"  # optional
```

Run tests:

```bash
tox -e jira-integration
```

**GitHub Integration Tests:**

Requirements:

```bash
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO_OWNER="your-org"
export GITHUB_REPO_NAME="your-repo"
```

Run tests:

```bash
tox -e github-integration
```

What it tests:

- Connection to GitHub API
- Fetching merged PRs
- Getting PR detailed metrics (commits, reviews, comments)
- AI assistance detection in commit messages

#### 3. Code Quality Tests

**Linting (flake8 + black):**

```bash
tox -e lint
```

**Type checking (mypy):**

```bash
tox -e type
```

**Auto-format code:**

```bash
tox -e format
```

### Manual Testing

#### Test GitHub PR Analysis Workflow

**1. Set up environment:**

```bash
export GITHUB_TOKEN="your_token"
export GITHUB_REPO_OWNER="your-org"
export GITHUB_REPO_NAME="your-repo"
```

**2. Edit configuration:**

```bash
vim config/pr_report_config.yaml

# Set phases appropriate for your repo
phases:
  - name: "Phase 1"
    start: "2024-10-01"
    end: "2024-10-31"
  - name: "Phase 2"
    start: "2024-11-01"
    end: "2024-11-30"
```

**3. Test single phase collection:**

```bash
python3 -m ai_impact_analysis.scripts.get_pr_metrics --start 2024-10-01 --end 2024-10-31
```

**Expected output:**

- JSON file in `reports/github/pr_metrics_general_*.json`
- Text report in `reports/github/pr_report_general_*.txt`
- Summary showing AI vs non-AI PR metrics

**4. Test full workflow:**

```bash
python3 -m ai_impact_analysis.scripts.generate_pr_report
```

**Expected output:**

- Multiple phase reports in `reports/github/`
- Comparison report: `reports/github/pr_comparison_general_*.tsv`
- Preview of comparison data

**5. Verify AI detection:**

Check commit messages in your PRs contain:

```
Assisted-by: Claude
# or
Assisted-by: Cursor
```

Then verify the report correctly identifies AI-assisted PRs.

#### Test Jira Analysis Workflow

**1. Set up environment:**

```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_API_TOKEN="your_token"
export JIRA_PROJECT_KEY="Konflux UI"
```

**2. Edit configuration:**

```bash
vim config/jira_report_config.yaml

phases:
  - name: "No AI Period"
    start: "2024-10-24"
    end: "2025-05-30"
  - name: "Cursor Period"
    start: "2025-06-02"
    end: "2025-07-31"
  - name: "Full AI Period"
    start: "2025-08-01"
    end: "2025-10-20"
```

**3. Test full workflow:**

```bash
python3 -m ai_impact_analysis.scripts.generate_jira_report
```

**Expected output:**

- Phase reports in `reports/jira_report_general_*.txt`
- Comparison report: `reports/comparison_report_general_*.tsv`

### Continuous Integration

To run all tests before committing:

```bash
# Run unit tests (fast, recommended)
tox -e unittest --develop

# Run code quality checks
tox -e lint

# Run type checking
tox -e type

# Or run everything (slower, includes multi-version tests)
tox
```

### Troubleshooting

**pytest not found:**

Install test dependencies:

```bash
pip install pytest pytest-cov
```

Or use tox (which handles dependencies automatically):

```bash
pip install tox
tox -e unittest --develop
```

**GitHub API rate limiting:**

If you hit rate limits during integration tests:

- Use a GitHub token with higher rate limits
- Reduce the date range in tests
- Wait for rate limit reset (check headers in error message)

**Jira API errors:**

If Jira integration tests fail:

- Verify your API token is valid
- Check you have access to the specified project
- Ensure the project has closed issues in the test date range

### Test Maintenance

**Adding New Tests:**

Unit tests:

1. Add test file to `tests/` directory
2. Name file `test_*.py`
3. Use pytest conventions (class `Test*`, function `test_*`)
4. Mock external API calls

Integration tests:

1. Add to `tests/test_jira_integration.py` (Jira) or `tests/test_github_integration.py` (GitHub)
2. Use `pytest.mark.skipif` to skip when credentials not available
3. Use real API calls (minimal/recent date ranges)
4. Note: Integration tests are slow due to real network calls

**Updating Test Configuration:**

Edit `tox.ini` to:

- Add new test environments
- Modify test dependencies
- Adjust code quality rules

### Example Test Run

```bash
$ tox -e unittest --develop

unittest: commands[0] | pytest --ignore=tests/test_jira_integration.py --ignore=tests/test_github_integration.py -v
============================= test session starts ==============================
platform linux -- Python 3.11.14, pytest-8.4.2, pluggy-1.6.0
rootdir: /home/wlin/workspaces/ai-analysis
configfile: pyproject.toml
testpaths: tests
collected 35 items

tests/test_github_client.py .................                            [ 48%]
tests/test_jira_client.py .....                                          [ 62%]
tests/test_utils.py .............                                        [100%]

======================== 35 passed in 0.08s =========================
  unittest: OK (0.24 seconds)
  congratulations :) (0.30 seconds)
```
