"""API routes package."""

from app.api.health import router as health_router
from app.api.anomalies import router as anomalies_router

__all__ = ["health_router", "anomalies_router"]
