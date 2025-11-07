"""Configuration models for AI Impact Analysis."""

from dataclasses import dataclass
from typing import List, Tuple, Optional
from datetime import datetime


@dataclass
class Phase:
    """Represents an analysis phase."""

    name: str
    start_date: str  # YYYY-MM-DD format
    end_date: str    # YYYY-MM-DD format

    def __post_init__(self):
        """Validate dates."""
        # Basic validation that dates are in correct format
        try:
            datetime.strptime(self.start_date, "%Y-%m-%d")
            datetime.strptime(self.end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}")


@dataclass
class AnalysisConfig:
    """Configuration for report generation."""

    phases: List[Phase]
    default_assignee: Optional[str] = None
    project_key: Optional[str] = None
    report_type: str = "jira"  # "jira" or "github"

    @classmethod
    def from_tuples(
        cls,
        phases: List[Tuple[str, str, str]],
        default_assignee: Optional[str] = None,
        report_type: str = "jira"
    ) -> "AnalysisConfig":
        """Create config from list of phase tuples."""
        phase_objects = [Phase(name=p[0], start_date=p[1], end_date=p[2]) for p in phases]
        return cls(
            phases=phase_objects,
            default_assignee=default_assignee,
            report_type=report_type
        )


@dataclass
class ReportMetadata:
    """Metadata for a generated report."""

    identifier: str  # username or "general"
    report_type: str  # "jira" or "github"
    phase_name: str
    generated_at: datetime
    file_path: str
