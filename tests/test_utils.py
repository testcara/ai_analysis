"""Tests for utility functions."""

from datetime import datetime
from ai_impact_analysis.utils import (
    convert_date_to_jql,
    parse_datetime,
    build_jql_query,
    calculate_state_durations,
)


class TestConvertDateToJQL:
    """Test date to JQL conversion."""

    def test_convert_date_today(self):
        """Test conversion of today's date."""
        today = datetime.now().strftime("%Y-%m-%d")
        result = convert_date_to_jql(today)
        assert result == "startOfDay()"

    def test_convert_date_past(self):
        """Test conversion of past date."""
        result = convert_date_to_jql("2024-01-01")
        assert result.startswith('"-')
        assert result.endswith('d"')

    def test_convert_date_none(self):
        """Test conversion of None."""
        result = convert_date_to_jql(None)
        assert result is None


class TestParseDatetime:
    """Test datetime parsing."""

    def test_parse_datetime_with_microseconds(self):
        """Test parsing datetime with microseconds."""
        dt_str = "2024-01-15T10:30:45.123000+0000"
        result = parse_datetime(dt_str)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_datetime_without_microseconds(self):
        """Test parsing datetime without microseconds."""
        dt_str = "2024-01-15T10:30:45+0000"
        result = parse_datetime(dt_str)
        assert result is not None
        assert result.year == 2024

    def test_parse_datetime_invalid(self):
        """Test parsing invalid datetime."""
        result = parse_datetime("invalid")
        assert result is None


class TestBuildJQLQuery:
    """Test JQL query building."""

    def test_build_jql_basic(self):
        """Test basic JQL query."""
        result = build_jql_query("TEST")
        assert result == 'project = "TEST"'

    def test_build_jql_with_assignee(self):
        """Test JQL query with assignee."""
        result = build_jql_query("TEST", assignee="user@example.com")
        assert 'project = "TEST"' in result
        assert 'assignee = "user@example.com"' in result

    def test_build_jql_with_dates(self):
        """Test JQL query with date range."""
        result = build_jql_query("TEST", start_date="2024-01-01", end_date="2024-12-31")
        assert 'project = "TEST"' in result
        assert "resolved >=" in result
        assert "resolved <=" in result

    def test_build_jql_with_status(self):
        """Test JQL query with status (no dates)."""
        result = build_jql_query("TEST", status="Done")
        assert 'project = "TEST"' in result
        assert 'status = "Done"' in result


class TestCalculateStateDurations:
    """Test state duration calculation."""

    def test_calculate_state_durations_no_changelog(self):
        """Test with issue that has no changelog."""
        issue = {
            "key": "TEST-123",
            "fields": {
                "created": "2024-01-01T10:00:00.000+0000",
                "status": {"name": "Done"},
                "resolutiondate": "2024-01-02T10:00:00.000+0000",
            },
        }
        result = calculate_state_durations(issue)
        assert "Done" in result
        assert result["Done"]["count"] == 1
        # Should be approximately 1 day = 86400 seconds
        assert 86300 < result["Done"]["total_seconds"] < 86500

    def test_calculate_state_durations_with_transitions(self):
        """Test with issue that has state transitions."""
        issue = {
            "key": "TEST-123",
            "fields": {
                "created": "2024-01-01T10:00:00.000+0000",
                "status": {"name": "Done"},
                "resolutiondate": "2024-01-03T10:00:00.000+0000",
            },
            "changelog": {
                "histories": [
                    {
                        "created": "2024-01-02T10:00:00.000+0000",
                        "items": [
                            {"field": "status", "fromString": "To Do", "toString": "In Progress"}
                        ],
                    }
                ]
            },
        }
        result = calculate_state_durations(issue)
        assert "To Do" in result
        assert "In Progress" in result
        # To Do should have ~1 day, In Progress should have ~1 day
        assert result["To Do"]["count"] == 1
        assert result["In Progress"]["count"] == 1

    def test_calculate_state_durations_no_created(self):
        """Test with issue missing created date."""
        issue = {"key": "TEST-123", "fields": {"status": {"name": "Done"}}}
        result = calculate_state_durations(issue)
        assert result == {}
