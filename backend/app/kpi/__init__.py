"""KPI intelligence module for computing daily analytical business metrics."""

from typing import Any
from app.kpi.metadata import (
    KPIMetadata,
    KPI_REGISTRY,
    CORE_KPIS,
    KPI_DAILY_REVENUE,
    KPI_ORDER_COUNT,
    KPI_AVERAGE_ORDER_VALUE,
    KPI_CANCELLATION_RATE,
    KPI_DELIVERY_DELAY_RATE,
    get_kpi_metadata,
)


def __getattr__(name: str) -> Any:
    if name == "compute_kpis_for_range":
        from app.kpi.compute_kpis import compute_kpis_for_range
        return compute_kpis_for_range
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "KPIMetadata",
    "KPI_REGISTRY",
    "CORE_KPIS",
    "KPI_DAILY_REVENUE",
    "KPI_ORDER_COUNT",
    "KPI_AVERAGE_ORDER_VALUE",
    "KPI_CANCELLATION_RATE",
    "KPI_DELIVERY_DELAY_RATE",
    "get_kpi_metadata",
    "compute_kpis_for_range",
]
