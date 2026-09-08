"""Data schemas and evidence contracts for PicketIQ investigation tools.

Defines structured evidence representations returned by deterministic
investigation tools without premature causal speculation.
"""

from dataclasses import dataclass, asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any


def _serialize_value(val: Any) -> Any:
    """Helper to recursively serialize Decimal and date/datetime objects to JSON-friendly types."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, list):
        return [_serialize_value(item) for item in val]
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val


@dataclass
class SegmentContribution:
    """Individual segment's contribution to an anomalous metric movement."""

    segment: str
    actual_value: Decimal
    baseline_value: Decimal
    absolute_delta: Decimal
    percentage_contribution: Optional[Decimal] = None
    share_of_total: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class SegmentBreakdownResult:
    """Evidence result from segment_breakdown investigation tool."""

    tool_name: str
    metric_name: str
    date: date
    dimension: str
    total_actual: Decimal
    total_baseline: Decimal
    total_delta: Decimal
    top_contributor: Optional[SegmentContribution]
    segments: List[SegmentContribution]
    summary: str
    status: str  # "success", "insufficient_data", "error"

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class SeasonalityResult:
    """Evidence result from check_seasonality investigation tool."""

    tool_name: str
    metric_name: str
    date: date
    day_of_week: int
    day_of_week_name: str
    target_value: Decimal
    same_dow_mean: Decimal
    same_dow_std: Decimal
    same_dow_zscore: Decimal
    is_seasonal: bool
    dow_averages: Dict[str, Decimal]
    sample_size: int
    summary: str
    status: str  # "success", "insufficient_data", "error"

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class TrendPoint:
    """Single chronological time series observation."""

    date: date
    value: Decimal

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class RecentTrendResult:
    """Evidence result from get_recent_trend investigation tool."""

    tool_name: str
    metric_name: str
    date: date
    window_days: int
    observations_count: int
    classification: str  # "sudden", "gradual_deterioration", "gradual_improvement", "stable", "insufficient_data"
    target_value: Decimal
    preceding_mean: Decimal
    preceding_std: Decimal
    preceding_trend_slope: Decimal
    single_day_delta: Decimal
    single_day_pct_change: Optional[Decimal]
    history: List[TrendPoint]
    summary: str
    status: str  # "success", "insufficient_data", "error"

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class EvidenceItem:
    """Individual evidence step entry captured during investigation orchestration."""

    step_number: int
    tool_name: str
    status: str  # "success", "error"
    summary: str
    input_parameters: Dict[str, Any]
    output_data: Dict[str, Any]
    created_at: Optional[str] = None
    evidence_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class AnomalyDetails:
    """Snapshot of the anomaly being investigated."""

    anomaly_id: int
    metric_name: str
    date: date
    expected_value: Decimal
    actual_value: Decimal
    z_score: Decimal
    severity: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class InvestigationResult:
    """Structured, reproducible investigation result coordinating multi-tool evidence collection."""

    investigation_id: int
    anomaly: AnomalyDetails
    status: str  # "completed", "partial_failure", "failed"
    steps_executed: int
    evidence: List[EvidenceItem]
    breakdown: Optional[SegmentBreakdownResult] = None
    seasonality: Optional[SeasonalityResult] = None
    recent_trend: Optional[RecentTrendResult] = None
    summary: str = ""
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class InvestigationConclusionResult:
    """Structured, evidence-grounded root-cause investigation conclusion."""

    investigation_id: int
    anomaly_id: int
    root_cause: str
    explanation: str
    confidence: str  # "high", "medium", "low"
    affected_segment: Optional[str]
    evidence_references: List[str]
    recommended_action: str
    provider: str
    model: str
    validation_passed: bool
    validation_errors: List[str]
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


