# AI Analysis

- [Overview](#overview)
- [Usage](#usage)
    - [Quick start](#quick-start)
    - [Generate reports](#generate-reports)
    - [Manual usage](#manual-usage)
- [Developer](#developer)
    - [Contributing](#contributing)
    - [Project structure](#project-structure)
- [Tests](#tests)
    - [Lint tests](#lint-tests)
    - [Unit tests](#unit-tests)

## Overview

AI Analysis is a Python tool to analyze the impact of AI tools on development efficiency by comparing Jira issue data across different time periods. The tool fetches issues from Jira, analyzes closure times, state durations, and generates comparison reports to measure productivity improvements.

## Usage

### Quick start

To start using the tool follow the procedure below:

1. Clone the repo
2. Create a virtual environment with `python3 -m venv venv && source venv/bin/activate`
3. Install dependencies with `pip install -r requirements.txt`
4. Set the python app path to the repo root directory with `export PYTHONPATH=.`
5. Set environment variables:
```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_API_TOKEN="your_api_token_here"
export JIRA_PROJECT_KEY="Konflux UI"
```

### Generate reports

**For team overall analysis:**
```bash
bash bin/generate_report.sh
```

**For individual team member:**
```bash
bash bin/generate_report.sh user@redhat.com
```

The script will:
1. Clean up old reports
2. Generate 3 phase reports comparing different time periods
3. Create a comparison TSV file in `reports/` directory
4. Output results that can be copied directly into Google Sheets

**Customize time periods:**

Edit `bin/generate_report.sh` to change the analysis periods:
```bash
# Phase 1: No AI Tools
PHASE1_START="2024-10-24"
PHASE1_END="2025-05-30"

# Phase 2: Using Cursor
PHASE2_START="2025-06-02"
PHASE2_END="2025-07-31"

# Phase 3: Comprehensive AI
PHASE3_START="2025-08-01"
PHASE3_END="2025-10-20"
```

### Manual usage

**Generate individual phase report:**
```bash
python3 bin/get_issues.py --start 2024-10-24 --end 2025-05-30
python3 bin/get_issues.py --start 2024-10-24 --end 2025-05-30 --assignee "user@redhat.com"
```

**Available parameters:**
- `--start` - Start date (YYYY-MM-DD)
- `--end` - End date (YYYY-MM-DD)
- `--status` - Issue status (default: Done)
- `--project` - Project key (overrides JIRA_PROJECT_KEY)
- `--assignee` - Assignee username or email

**Generate comparison report:**
```bash
# Team comparison (uses last 3 reports in reports/ directory)
python3 bin/generate_comparison_report.py

# Individual comparison
python3 bin/generate_comparison_report.py --assignee user@redhat.com
```

**Output files:**

Reports are saved in `reports/` directory:
- `jira_report_YYYYMMDD_HHMMSS.txt` - Team phase reports
- `jira_report_{assignee}_YYYYMMDD_HHMMSS.txt` - Individual phase reports
- `comparison_report_YYYYMMDD_HHMMSS.tsv` - Team comparison (TSV format)
- `comparison_report_{assignee}_YYYYMMDD_HHMMSS.tsv` - Individual comparison

**Report metrics:**
- Average closure time
- Daily throughput
- Time in each state (New, To Do, In Progress, Review, etc.)
- State re-entry rates (indication of rework)
- Issue type distribution (Story, Task, Bug, Epic)

## Developer

AI Analysis is built with Python 3.11. The project follows a modular structure with core functionality separated into reusable modules and CLI scripts in the `bin/` directory.

### Contributing

To start contributing on AI Analysis clone the repository, create a new branch and start working on improvements. When ready commit and push the changes and open a merge request. In summary:

1. `git clone <repository_url>`
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
ai-analysis/
├── ai_analysis/          # Core modules
│   ├── __init__.py
│   ├── jira_client.py   # Jira API client with pagination
│   ├── utils.py         # Date conversion, state analysis, JQL building
│   └── logger.py        # Logging configuration
├── bin/                  # CLI scripts
│   ├── get_issues.py    # Fetch and analyze Jira issues
│   ├── generate_comparison_report.py  # Compare reports
│   └── generate_report.sh  # Automated workflow
├── tests/                # Test suite
│   ├── test_utils.py
│   └── test_jira_client.py
├── reports/              # Generated reports
├── requirements.txt      # Dependencies
├── pyproject.toml        # Project configuration
└── tox.ini               # Test configuration
```

## Tests

The tests are designed to run with [tox](https://tox.wiki/). Make sure you have tox installed in your environment. There are three types of tests: lint tests, unit tests, and type checking.

To run all tests execute on a terminal `tox`

### Lint tests

Lint tests are responsible for code style and ensure files are readable. The lint is applied to all Python code inside `bin/`, `ai_analysis/` and `tests/` directories.

To run only the lint test execute on a terminal `tox -e lint`

### Unit tests

The unit tests ensure the functions work properly according to a set of inputs. The tests check each function individually through mocks.

To run the unit tests execute on a terminal `tox -e py311`

Or use pytest directly: `pytest`

**Auto-format code:**
```bash
tox -e format
```

**Type checking:**
```bash
tox -e type
```

**Coverage report:**
```bash
tox -e coverage
```
