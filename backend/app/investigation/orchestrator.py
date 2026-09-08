"""Deterministic Investigation Orchestrator for PicketIQ.

Coordinates multi-tool evidence collection across detected anomalies:
1. segment_breakdown (Step 1)
2. check_seasonality (Step 2)
3. get_recent_trend (Step 3)

Maintains sequential step logs, handles tool errors gracefully without corrupting
the investigation or transaction, persists evidence to PostgreSQL, and produces
structured, reproducible investigation results without premature causal speculation.
"""

import argparse
import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Anomaly, Investigation, InvestigationEvidence
from app.investigation.schema import (
    EvidenceItem,
    AnomalyDetails,
    InvestigationResult,
    SegmentBreakdownResult,
    SeasonalityResult,
    RecentTrendResult,
)
from app.investigation.tools import (
    segment_breakdown,
    check_seasonality,
    get_recent_trend,
)

logger = logging.getLogger("picket_iq.investigation.orchestrator")


class AnomalyNotFoundError(ValueError):
    """Raised when an anomaly ID does not exist in the database."""
    pass


def _extract_anomaly_details(anomaly: Anomaly) -> AnomalyDetails:
    """Extract strongly-typed snapshot from Anomaly ORM entity."""
    return AnomalyDetails(
        anomaly_id=anomaly.id,
        metric_name=anomaly.metric_name,
        date=anomaly.date,
        expected_value=Decimal(str(anomaly.expected_value)),
        actual_value=Decimal(str(anomaly.actual_value)),
        z_score=Decimal(str(anomaly.z_score)),
        severity=anomaly.severity,
        status=anomaly.status,
    )


def _build_synthesis_summary(
    anomaly: Anomaly,
    breakdown_res: Optional[SegmentBreakdownResult],
    seasonality_res: Optional[SeasonalityResult],
    trend_res: Optional[RecentTrendResult],
) -> str:
    """Synthesize an objective, multi-tool factual summary without causal speculation."""
    summary_parts = [
        f"Investigation for anomaly #{anomaly.id} ('{anomaly.metric_name}' on {anomaly.date}): "
        f"Observed value was {Decimal(str(anomaly.actual_value)):.4f} vs expected "
        f"{Decimal(str(anomaly.expected_value)):.4f} (z: {Decimal(str(anomaly.z_score)):+.4f}, "
        f"severity: {anomaly.severity})."
    ]

    # Step 1 synthesis
    if breakdown_res and breakdown_res.status == "success":
        if breakdown_res.top_contributor:
            top = breakdown_res.top_contributor
            pct_str = (
                f" ({top.percentage_contribution:+.2f}% of total deviation)"
                if top.percentage_contribution is not None
                else ""
            )
            summary_parts.append(
                f"Step 1 (segment_breakdown): Top contributing region was '{top.segment}' with "
                f"actual {top.actual_value} vs baseline {top.baseline_value} "
                f"(delta: {top.absolute_delta:+}{pct_str})."
            )
        else:
            summary_parts.append(f"Step 1 (segment_breakdown): {breakdown_res.summary}")
    elif breakdown_res:
        summary_parts.append(f"Step 1 (segment_breakdown): {breakdown_res.summary}")

    # Step 2 synthesis
    if seasonality_res and seasonality_res.status == "success":
        seas_str = (
            "consistent with typical weekly seasonality"
            if seasonality_res.is_seasonal
            else "not explained by typical weekly seasonality"
        )
        summary_parts.append(
            f"Step 2 (check_seasonality): {seasonality_res.day_of_week_name} baseline mean was "
            f"{seasonality_res.same_dow_mean} (std: {seasonality_res.same_dow_std}, "
            f"same-DOW z: {seasonality_res.same_dow_zscore:+}; {seas_str})."
        )
    elif seasonality_res:
        summary_parts.append(f"Step 2 (check_seasonality): {seasonality_res.summary}")

    # Step 3 synthesis
    if trend_res and trend_res.status == "success":
        summary_parts.append(
            f"Step 3 (get_recent_trend): Trajectory classified as '{trend_res.classification}' "
            f"over {trend_res.observations_count} evaluated days (single-day shift: "
            f"{trend_res.single_day_delta:+})."
        )
    elif trend_res:
        summary_parts.append(f"Step 3 (get_recent_trend): {trend_res.summary}")

    return " ".join(summary_parts)


def investigate_anomaly(
    anomaly_id: int,
    session: Optional[Session] = None,
) -> InvestigationResult:
    """Coordinate deterministic investigation tools on an existing anomaly.

    Execution Flow:
        1. Load anomaly from database by ID.
        2. Create Investigation database tracking record.
        3. Step 1: Execute segment_breakdown (by customer_state).
        4. Step 2: Execute check_seasonality (day-of-week).
        5. Step 3: Execute get_recent_trend (14-day trajectory).
        6. Capture inputs, outputs, and status for each step into InvestigationEvidence.
        7. Synthesize an auditable factual summary without causal claims.
        8. Return structured InvestigationResult.

    Args:
        anomaly_id: Database ID of the anomaly to investigate.
        session: Optional SQLAlchemy Session. If None, manages a local session.

    Returns:
        InvestigationResult containing anomaly snapshot and sequential evidence.

    Raises:
        AnomalyNotFoundError: If anomaly_id does not exist in the database.
    """
    if not isinstance(anomaly_id, int) or anomaly_id <= 0:
        raise ValueError(f"Invalid anomaly_id '{anomaly_id}'. Must be a positive integer.")

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        # 1. Fetch anomaly
        anomaly = session.execute(
            select(Anomaly).where(Anomaly.id == anomaly_id)
        ).scalar_one_or_none()

        if anomaly is None:
            raise AnomalyNotFoundError(f"Anomaly with ID {anomaly_id} not found in database.")

        logger.info(
            "Starting investigation for anomaly #%d: metric='%s', date=%s, severity='%s'",
            anomaly.id,
            anomaly.metric_name,
            anomaly.date,
            anomaly.severity,
        )

        # 2. Create Investigation record
        investigation = Investigation(
            anomaly_id=anomaly.id,
            status="in_progress",
            created_at=datetime.utcnow(),
        )
        session.add(investigation)
        session.flush()

        anomaly.status = "investigating"

        # Evidence tracking containers
        evidence_items: List[EvidenceItem] = []
        breakdown_res: Optional[SegmentBreakdownResult] = None
        seasonality_res: Optional[SeasonalityResult] = None
        trend_res: Optional[RecentTrendResult] = None

        # ----------------------------------------------------------------------
        # STEP 1: Regional Segment Breakdown
        # ----------------------------------------------------------------------
        step1_num = 1
        step1_tool = "segment_breakdown"
        step1_inputs = {
            "metric_name": anomaly.metric_name,
            "target_date": anomaly.date.isoformat(),
        }
        try:
            breakdown_res = segment_breakdown(
                metric_name=anomaly.metric_name,
                target_date=anomaly.date,
                session=session,
            )
            step1_status = breakdown_res.status
            step1_summary = breakdown_res.summary
            step1_outputs = breakdown_res.to_dict()
        except Exception as exc:
            logger.warning("Step 1 ('%s') failed for anomaly #%d: %s", step1_tool, anomaly.id, exc)
            step1_status = "error"
            step1_summary = f"Tool '{step1_tool}' execution failed: {exc}"
            step1_outputs = {"error": str(exc), "error_type": exc.__class__.__name__}

        ev1 = InvestigationEvidence(
            investigation_id=investigation.id,
            anomaly_id=anomaly.id,
            step_number=step1_num,
            tool_name=step1_tool,
            input_parameters=step1_inputs,
            output_data=step1_outputs,
            status=step1_status,
            summary=step1_summary,
            created_at=datetime.utcnow(),
        )
        session.add(ev1)
        session.flush()

        evidence_items.append(
            EvidenceItem(
                step_number=step1_num,
                tool_name=step1_tool,
                status=step1_status,
                summary=step1_summary,
                input_parameters=step1_inputs,
                output_data=step1_outputs,
                created_at=ev1.created_at.isoformat(),
                evidence_id=ev1.id,
            )
        )

        # ----------------------------------------------------------------------
        # STEP 2: Weekly Seasonality Analysis
        # ----------------------------------------------------------------------
        step2_num = 2
        step2_tool = "check_seasonality"
        step2_inputs = {
            "metric_name": anomaly.metric_name,
            "target_date": anomaly.date.isoformat(),
            "lookback_weeks": 8,
        }
        try:
            seasonality_res = check_seasonality(
                metric_name=anomaly.metric_name,
                target_date=anomaly.date,
                session=session,
                lookback_weeks=8,
            )
            step2_status = seasonality_res.status
            step2_summary = seasonality_res.summary
            step2_outputs = seasonality_res.to_dict()
        except Exception as exc:
            logger.warning("Step 2 ('%s') failed for anomaly #%d: %s", step2_tool, anomaly.id, exc)
            step2_status = "error"
            step2_summary = f"Tool '{step2_tool}' execution failed: {exc}"
            step2_outputs = {"error": str(exc), "error_type": exc.__class__.__name__}

        ev2 = InvestigationEvidence(
            investigation_id=investigation.id,
            anomaly_id=anomaly.id,
            step_number=step2_num,
            tool_name=step2_tool,
            input_parameters=step2_inputs,
            output_data=step2_outputs,
            status=step2_status,
            summary=step2_summary,
            created_at=datetime.utcnow(),
        )
        session.add(ev2)
        session.flush()

        evidence_items.append(
            EvidenceItem(
                step_number=step2_num,
                tool_name=step2_tool,
                status=step2_status,
                summary=step2_summary,
                input_parameters=step2_inputs,
                output_data=step2_outputs,
                created_at=ev2.created_at.isoformat(),
                evidence_id=ev2.id,
            )
        )

        # ----------------------------------------------------------------------
        # STEP 3: Recent Trajectory Trend
        # ----------------------------------------------------------------------
        step3_num = 3
        step3_tool = "get_recent_trend"
        step3_inputs = {
            "metric_name": anomaly.metric_name,
            "target_date": anomaly.date.isoformat(),
            "window_days": 14,
        }
        try:
            trend_res = get_recent_trend(
                metric_name=anomaly.metric_name,
                target_date=anomaly.date,
                session=session,
                window_days=14,
            )
            step3_status = trend_res.status
            step3_summary = trend_res.summary
            step3_outputs = trend_res.to_dict()
        except Exception as exc:
            logger.warning("Step 3 ('%s') failed for anomaly #%d: %s", step3_tool, anomaly.id, exc)
            step3_status = "error"
            step3_summary = f"Tool '{step3_tool}' execution failed: {exc}"
            step3_outputs = {"error": str(exc), "error_type": exc.__class__.__name__}

        ev3 = InvestigationEvidence(
            investigation_id=investigation.id,
            anomaly_id=anomaly.id,
            step_number=step3_num,
            tool_name=step3_tool,
            input_parameters=step3_inputs,
            output_data=step3_outputs,
            status=step3_status,
            summary=step3_summary,
            created_at=datetime.utcnow(),
        )
        session.add(ev3)
        session.flush()

        evidence_items.append(
            EvidenceItem(
                step_number=step3_num,
                tool_name=step3_tool,
                status=step3_status,
                summary=step3_summary,
                input_parameters=step3_inputs,
                output_data=step3_outputs,
                created_at=ev3.created_at.isoformat(),
                evidence_id=ev3.id,
            )
        )

        # ----------------------------------------------------------------------
        # Overall Status & Synthesis
        # ----------------------------------------------------------------------
        success_count = sum(1 for e in evidence_items if e.status in ("success", "insufficient_data"))
        error_count = sum(1 for e in evidence_items if e.status == "error")

        if error_count == 0:
            overall_status = "completed"
            anomaly.status = "investigated"
        elif success_count > 0:
            overall_status = "partial_failure"
            anomaly.status = "investigated"
        else:
            overall_status = "failed"
            anomaly.status = "open"

        completed_at = datetime.utcnow()
        investigation.status = overall_status
        investigation.completed_at = completed_at
        overall_summary = _build_synthesis_summary(anomaly, breakdown_res, seasonality_res, trend_res)
        investigation.summary = overall_summary

        session.commit()

        anomaly_details = _extract_anomaly_details(anomaly)

        return InvestigationResult(
            investigation_id=investigation.id,
            anomaly=anomaly_details,
            status=overall_status,
            steps_executed=len(evidence_items),
            evidence=evidence_items,
            breakdown=breakdown_res,
            seasonality=seasonality_res,
            recent_trend=trend_res,
            summary=overall_summary,
            created_at=investigation.created_at.isoformat(),
            completed_at=completed_at.isoformat(),
        )

    except Exception:
        session.rollback()
        raise
    finally:
        if close_session:
            session.close()


class InvestigationOrchestrator:
    """Class wrapper providing object-oriented interface for investigation orchestration."""

    def __init__(self, session: Optional[Session] = None):
        self._session = session

    def investigate(self, anomaly_id: int) -> InvestigationResult:
        """Run complete deterministic investigation on an anomaly."""
        return investigate_anomaly(anomaly_id=anomaly_id, session=self._session)


def main() -> None:
    """CLI entrypoint for running an investigation on an existing anomaly."""
    parser = argparse.ArgumentParser(description="PicketIQ Investigation Orchestrator CLI")
    parser.add_argument(
        "--anomaly-id",
        type=int,
        required=True,
        help="ID of the anomaly to investigate",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured investigation result as JSON",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        result = investigate_anomaly(anomaly_id=args.anomaly_id)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print("\n" + "=" * 70)
            print(f"  INVESTIGATION RESULT FOR ANOMALY #{result.anomaly.anomaly_id}")
            print("=" * 70)
            print(f"Status        : {result.status}")
            print(f"Metric        : {result.anomaly.metric_name}")
            print(f"Date          : {result.anomaly.date}")
            print(f"Actual Value  : {result.anomaly.actual_value}")
            print(f"Expected Value: {result.anomaly.expected_value}")
            print(f"Z-Score       : {result.anomaly.z_score:+}")
            print(f"Severity      : {result.anomaly.severity}")
            print(f"Steps Run     : {result.steps_executed}")
            print("\nEVIDENCE CHAIN:")
            for ev in result.evidence:
                print(f"  Step {ev.step_number} [{ev.tool_name}] -> {ev.status}")
                print(f"    Summary: {ev.summary}")
            print(f"\nSYNTHESIS SUMMARY:\n  {result.summary}\n")
    except AnomalyNotFoundError as exc:
        print(f"Error: {exc}")
    except Exception as exc:
        logger.error("Investigation failed: %s", exc, exc_info=True)


if __name__ == "__main__":
    main()
