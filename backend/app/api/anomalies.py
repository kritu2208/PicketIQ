"""API endpoints for anomaly browsing and automated investigation execution."""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func

from app.db.session import get_db
from app.db.models import Anomaly, Investigation, InvestigationEvidence, InvestigationConclusion
from app.kpi.metadata import KPI_REGISTRY, CORE_KPIS
from app.investigation.orchestrator import AnomalyNotFoundError
from app.investigation.llm.investigator import investigate_and_explain

logger = logging.getLogger("picket_iq.api.anomalies")

router = APIRouter(tags=["anomalies"])


def _format_anomaly(a: Anomaly, has_investigation: bool = False, latest_inv_id: Optional[int] = None) -> Dict[str, Any]:
    meta = KPI_REGISTRY.get(a.metric_name)
    actual = float(a.actual_value)
    expected = float(a.expected_value)
    delta = actual - expected
    delta_pct = (delta / expected * 100.0) if expected != 0 else 0.0

    return {
        "id": a.id,
        "metric_name": a.metric_name,
        "metric_display_name": meta.display_name if meta else a.metric_name.replace("_", " ").title(),
        "unit": meta.unit if meta else "number",
        "date": a.date.isoformat(),
        "actual_value": actual,
        "expected_value": expected,
        "delta": round(delta, 4),
        "delta_pct": round(delta_pct, 2),
        "z_score": float(a.z_score),
        "severity": a.severity,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "has_investigation": has_investigation,
        "latest_investigation_id": latest_inv_id,
    }


@router.get("/metrics")
def list_metrics() -> List[Dict[str, Any]]:
    """List available business KPI metrics with descriptions and units."""
    metrics = []
    for kpi_key in CORE_KPIS:
        meta = KPI_REGISTRY.get(kpi_key)
        if meta:
            metrics.append({
                "name": meta.name,
                "display_name": meta.display_name,
                "description": meta.description,
                "unit": meta.unit,
                "date_attribution_rule": meta.date_attribution_rule,
            })
    return metrics


@router.get("/anomalies")
def list_anomalies(
    metric: Optional[str] = Query(None, description="Filter by KPI metric name"),
    severity: Optional[str] = Query(None, description="Filter by severity (high, medium, low)"),
    status: Optional[str] = Query(None, description="Filter by status (open, investigating, resolved)"),
    sort_by: str = Query("z_score_desc", description="Sort order: z_score_desc, date_desc, date_asc, severity_desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List detected business metric anomalies with filtering, sorting, and pagination."""
    query = db.query(Anomaly)

    if metric:
        query = query.filter(Anomaly.metric_name == metric)
    if severity:
        query = query.filter(Anomaly.severity == severity.lower())
    if status:
        query = query.filter(Anomaly.status == status.lower())

    total = query.count()

    # Apply sorting
    if sort_by == "z_score_desc":
        query = query.order_by(desc(func.abs(Anomaly.z_score)), desc(Anomaly.date))
    elif sort_by == "date_desc":
        query = query.order_by(desc(Anomaly.date), desc(func.abs(Anomaly.z_score)))
    elif sort_by == "date_asc":
        query = query.order_by(asc(Anomaly.date), desc(func.abs(Anomaly.z_score)))
    elif sort_by == "severity_desc":
        query = query.order_by(desc(Anomaly.severity), desc(func.abs(Anomaly.z_score)))
    else:
        query = query.order_by(desc(func.abs(Anomaly.z_score)))

    anomalies = query.offset(offset).limit(limit).all()

    # Query investigations count/ids for these anomalies to populate has_investigation flag
    anomaly_ids = [a.id for a in anomalies]
    inv_map: Dict[int, int] = {}
    if anomaly_ids:
        # Get latest investigation ID per anomaly
        latest_invs = (
            db.query(
                Investigation.anomaly_id,
                func.max(Investigation.id).label("max_id")
            )
            .filter(Investigation.anomaly_id.in_(anomaly_ids))
            .group_by(Investigation.anomaly_id)
            .all()
        )
        for anomaly_id, max_id in latest_invs:
            inv_map[anomaly_id] = max_id

    items = [
        _format_anomaly(
            a,
            has_investigation=a.id in inv_map,
            latest_inv_id=inv_map.get(a.id)
        )
        for a in anomalies
    ]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@router.get("/anomalies/{anomaly_id}")
def get_anomaly_detail(anomaly_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve complete details for a single anomaly."""
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly with ID {anomaly_id} not found",
        )

    latest_inv = (
        db.query(Investigation)
        .filter(Investigation.anomaly_id == anomaly_id)
        .order_by(desc(Investigation.id))
        .first()
    )

    return _format_anomaly(
        anomaly,
        has_investigation=latest_inv is not None,
        latest_inv_id=latest_inv.id if latest_inv else None,
    )


@router.get("/anomalies/{anomaly_id}/investigation")
def get_anomaly_investigation(anomaly_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Retrieve the latest completed investigation and conclusion for an anomaly."""
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anomaly with ID {anomaly_id} not found",
        )

    investigation = (
        db.query(Investigation)
        .filter(Investigation.anomaly_id == anomaly_id)
        .order_by(desc(Investigation.id))
        .first()
    )
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation found for anomaly ID {anomaly_id}",
        )

    # Load evidence steps
    evidence_records = (
        db.query(InvestigationEvidence)
        .filter(InvestigationEvidence.investigation_id == investigation.id)
        .order_by(InvestigationEvidence.step_number.asc())
        .all()
    )

    evidence_steps = [
        {
            "id": ev.id,
            "step_number": ev.step_number,
            "tool_name": ev.tool_name,
            "status": ev.status,
            "summary": ev.summary,
            "input_parameters": ev.input_parameters,
            "output_data": ev.output_data,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in evidence_records
    ]

    # Load conclusion if exists
    conclusion = (
        db.query(InvestigationConclusion)
        .filter(InvestigationConclusion.investigation_id == investigation.id)
        .first()
    )

    conclusion_data = None
    if conclusion:
        conclusion_data = {
            "id": conclusion.id,
            "root_cause": conclusion.root_cause,
            "explanation": conclusion.explanation,
            "confidence": conclusion.confidence,
            "affected_segment": conclusion.affected_segment,
            "evidence_references": conclusion.evidence_references,
            "recommended_action": conclusion.recommended_action,
            "provider": conclusion.provider,
            "model_name": conclusion.model_name,
            "validation_passed": conclusion.validation_passed,
            "created_at": conclusion.created_at.isoformat() if conclusion.created_at else None,
        }

    return {
        "anomaly": _format_anomaly(anomaly, has_investigation=True, latest_inv_id=investigation.id),
        "investigation": {
            "id": investigation.id,
            "anomaly_id": investigation.anomaly_id,
            "status": investigation.status,
            "summary": investigation.summary,
            "created_at": investigation.created_at.isoformat() if investigation.created_at else None,
            "completed_at": investigation.completed_at.isoformat() if investigation.completed_at else None,
        },
        "evidence_steps": evidence_steps,
        "conclusion": conclusion_data,
    }


@router.post("/anomalies/{anomaly_id}/investigate")
def trigger_investigation(
    anomaly_id: int,
    provider: Optional[str] = Query(None, description="Optional LLM provider override (mock, openai, anthropic, gemini)"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Execute the full end-to-end investigation pipeline on an anomaly and return results."""
    logger.info("API trigger: Investigating anomaly #%d (provider: %s)", anomaly_id, provider)

    try:
        investigate_and_explain(
            anomaly_id=anomaly_id,
            session=db,
        )
    except AnomalyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Investigation failed unexpectedly for anomaly #%d", anomaly_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation execution failed: {str(exc)}",
        )

    # Return the full investigation representation
    return get_anomaly_investigation(anomaly_id=anomaly_id, db=db)
