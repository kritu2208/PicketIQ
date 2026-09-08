"""Anomaly detection module for detecting unusual metric movements."""

from typing import Any

__all__ = [
    "DEFAULT_BASELINE_WINDOW",
    "DEFAULT_MIN_HISTORY",
    "DEFAULT_ZSCORE_THRESHOLD",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "SEVERITY_HIGH",
    "compute_baseline_stats",
    "calculate_zscore",
    "classify_severity",
    "detect_anomalies_for_kpis",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        import app.detection.zscore_detector as detector
        return getattr(detector, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
