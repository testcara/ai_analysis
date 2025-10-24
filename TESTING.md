# Testing Guide

This document describes how to test the AI Analysis tool.

## Test Types

### 1. Unit Tests

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
tox -e coverage
```

### 2. Integration Tests

Integration tests make real API calls to verify end-to-end functionality.

#### Jira Integration Tests

**Requirements:**
```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_API_TOKEN="your_token"
export JIRA_PROJECT_KEY="Konflux UI"
export JIRA_USER_EMAIL="your@email.com"  # optional
```

**Run tests:**
```bash
tox -e jira-integration
```

#### GitHub Integration Tests

**Requirements:**
```bash
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO_OWNER="your-org"
export GITHUB_REPO_NAME="your-repo"
```

**Run tests:**
```bash
tox -e github-integration
```

**What it tests:**
- Connection to GitHub API
- Fetching merged PRs
- Getting PR detailed metrics (commits, reviews, comments)
- AI assistance detection in commit messages

### 3. Code Quality Tests

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

## Manual Testing

### Test GitHub PR Analysis Workflow

**1. Set up environment:**
```bash
export GITHUB_TOKEN="your_token"
export GITHUB_REPO_OWNER="your-org"
export GITHUB_REPO_NAME="your-repo"
```

**2. Edit configuration:**
```bash
vim config/github_phases.conf

# Set phases appropriate for your repo
GITHUB_PHASES=(
    "Phase 1|2024-10-01|2024-10-31"
    "Phase 2|2024-11-01|2024-11-30"
)
```

**3. Test single phase collection:**
```bash
python3 -m ai_impact_analysis.cli.get_pr_metrics --start 2024-10-01 --end 2024-10-31
```

**Expected output:**
- JSON file in `reports/github/pr_metrics_general_*.json`
- Text report in `reports/github/pr_report_general_*.txt`
- Summary showing AI vs non-AI PR metrics

**4. Test full workflow:**
```bash
bash bin/generate_pr_report.sh
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

### Test Jira Analysis Workflow

**1. Set up environment:**
```bash
export JIRA_URL="https://issues.redhat.com"
export JIRA_API_TOKEN="your_token"
export JIRA_PROJECT_KEY="Konflux UI"
```

**2. Edit configuration:**
```bash
vim config/jira_phases.conf

PHASES=(
    "No AI Period|2024-10-24|2025-05-30"
    "Cursor Period|2025-06-02|2025-07-31"
    "Full AI Period|2025-08-01|2025-10-20"
)
```

**3. Test full workflow:**
```bash
bash bin/generate_jira_report.sh
```

**Expected output:**
- Phase reports in `reports/jira_report_general_*.txt`
- Comparison report: `reports/comparison_report_general_*.tsv`

## Continuous Integration

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

## Troubleshooting

### pytest not found

Install test dependencies:
```bash
pip install pytest pytest-cov
```

Or use tox (which handles dependencies automatically):
```bash
pip install tox
tox -e unittest --develop
```

### GitHub API rate limiting

If you hit rate limits during integration tests:
- Use a GitHub token with higher rate limits
- Reduce the date range in tests
- Wait for rate limit reset (check headers in error message)

### Jira API errors

If Jira integration tests fail:
- Verify your API token is valid
- Check you have access to the specified project
- Ensure the project has closed issues in the test date range

## Test Maintenance

### Adding New Tests

**Unit tests:**
1. Add test file to `tests/` directory
2. Name file `test_*.py`
3. Use pytest conventions (class `Test*`, function `test_*`)
4. Mock external API calls

**Integration tests:**
1. Add to `tests/test_jira_integration.py` (Jira) or `tests/test_github_integration.py` (GitHub)
2. Use `pytest.mark.skipif` to skip when credentials not available
3. Use real API calls (minimal/recent date ranges)
4. Note: Integration tests are slow due to real network calls

### Updating Test Configuration

Edit `tox.ini` to:
- Add new test environments
- Modify test dependencies
- Adjust code quality rules

## Example Test Run

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
