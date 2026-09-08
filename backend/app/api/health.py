"""System health and database connectivity check endpoint."""

import logging
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Service Health Check",
    description="Validates API responsiveness and active database connectivity.",
)
def health_check(db: Session = Depends(get_db)):
    """Check service and database operational status.
    
    Executes a lightweight ping query (`SELECT 1`) against the configured
    database to confirm connectivity.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "db": "connected",
        }
    except Exception as exc:
        logger.error("Database health check failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "db": "disconnected",
                "detail": "Database is currently unreachable",
            },
        )
