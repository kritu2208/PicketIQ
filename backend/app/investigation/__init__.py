"""Investigation module for multi-dimensional root cause intelligence.

Exports deterministic evidence-gathering tools and orchestrator:
- segment_breakdown
- check_seasonality
- get_recent_trend
- investigate_anomaly
- InvestigationOrchestrator
"""

from app.investigation.schema import (
    SegmentContribution,
    SegmentBreakdownResult,
    SeasonalityResult,
    TrendPoint,
    RecentTrendResult,
    EvidenceItem,
    AnomalyDetails,
    InvestigationResult,
    InvestigationConclusionResult,
)
from app.investigation.tools import (
    segment_breakdown,
    check_seasonality,
    get_recent_trend,
)
__all__ = [
    "SegmentContribution",
    "SegmentBreakdownResult",
    "SeasonalityResult",
    "TrendPoint",
    "RecentTrendResult",
    "EvidenceItem",
    "AnomalyDetails",
    "InvestigationResult",
    "InvestigationConclusionResult",
    "segment_breakdown",
    "check_seasonality",
    "get_recent_trend",
    "investigate_anomaly",
    "InvestigationOrchestrator",
    "AnomalyNotFoundError",
    "explain_investigation",
    "investigate_and_explain",
    "BaseLLMProvider",
    "MockLLMProvider",
    "get_llm_provider",
]


def __getattr__(name: str):
    if name in ("investigate_anomaly", "InvestigationOrchestrator", "AnomalyNotFoundError"):
        import app.investigation.orchestrator as orch
        return getattr(orch, name)
    if name in ("explain_investigation", "investigate_and_explain"):
        import app.investigation.llm as llm_mod
        return getattr(llm_mod, name)
    if name in ("BaseLLMProvider", "MockLLMProvider", "get_llm_provider"):
        import app.investigation.llm as llm_mod
        return getattr(llm_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")



