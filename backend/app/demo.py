"""End-to-End Real Olist Investigation Demo for PicketIQ.

Demonstrates the complete PicketIQ intelligence pipeline on real e-commerce data:
Real Olist Data -> Daily KPI -> Anomaly -> Orchestrator -> Evidence -> LLM -> Validated Root Cause -> Recommendation

Principle: "When the numbers move, PicketIQ finds out why."
"""

import argparse
import json
import logging
import sys
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Anomaly, KPIDaily
from app.investigation import (
    investigate_anomaly,
    explain_investigation,
    InvestigationResult,
    InvestigationConclusionResult,
    get_llm_provider,
    BaseLLMProvider,
)

logger = logging.getLogger("picket_iq.demo")


def get_default_anomaly(session: Session, metric_name: Optional[str] = None) -> Anomaly:
    """Find the most significant real anomaly by absolute Z-score.

    Args:
        session: Active SQLAlchemy Session.
        metric_name: Optional KPI metric name filter.

    Returns:
        The strongest Anomaly entity in the database.
    """
    stmt = select(Anomaly)
    if metric_name:
        stmt = stmt.where(Anomaly.metric_name == metric_name)
    stmt = stmt.order_by(func.abs(Anomaly.z_score).desc()).limit(1)

    anomaly = session.execute(stmt).scalar_one_or_none()
    if anomaly is None:
        raise RuntimeError(
            "No anomalies found in database. Please run anomaly detection first:\n"
            "    python -m app.detection.zscore_detector"
        )
    return anomaly


def run_demo(
    anomaly_id: Optional[int] = None,
    metric_name: Optional[str] = None,
    provider_name: Optional[str] = None,
    as_json: bool = False,
    session: Optional[Session] = None,
) -> InvestigationConclusionResult:
    """Execute complete end-to-end investigation pipeline on real data.

    Args:
        anomaly_id: Optional anomaly ID. Defaults to strongest anomaly.
        metric_name: Optional metric filter when searching for strongest anomaly.
        provider_name: Optional LLM provider ('mock', 'openai', 'anthropic', 'gemini').
        as_json: If True, prints JSON output.
        session: Optional SQLAlchemy Session.

    Returns:
        Completed InvestigationConclusionResult.
    """
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        # 1. Resolve Target Anomaly
        if anomaly_id is not None:
            anomaly = session.execute(
                select(Anomaly).where(Anomaly.id == anomaly_id)
            ).scalar_one_or_none()
            if anomaly is None:
                raise ValueError(f"Anomaly with ID {anomaly_id} not found in database.")
        else:
            anomaly = get_default_anomaly(session, metric_name=metric_name)

        # 2. Run Deterministic Orchestrator (Phase 5C)
        inv_result: InvestigationResult = investigate_anomaly(
            anomaly_id=anomaly.id,
            session=session,
        )

        # 3. Run LLM Grounded Interpretation (Phase 5D)
        provider: BaseLLMProvider = get_llm_provider(provider_name)
        conclusion: InvestigationConclusionResult = explain_investigation(
            investigation_result=inv_result,
            provider=provider,
            session=session,
        )

        # 4. Present Formatted Output
        if as_json:
            full_payload = {
                "pipeline": "PicketIQ End-to-End Investigation Demo",
                "anomaly": inv_result.anomaly.to_dict(),
                "evidence_tools": {
                    "segment_breakdown": inv_result.breakdown.to_dict() if inv_result.breakdown else None,
                    "check_seasonality": inv_result.seasonality.to_dict() if inv_result.seasonality else None,
                    "get_recent_trend": inv_result.recent_trend.to_dict() if inv_result.recent_trend else None,
                },
                "conclusion": conclusion.to_dict(),
            }
            print(json.dumps(full_payload, indent=2))
        else:
            _print_demo_report(inv_result, conclusion)

        return conclusion

    finally:
        if close_session:
            session.close()


def _print_demo_report(
    inv: InvestigationResult,
    conclusion: InvestigationConclusionResult,
) -> None:
    """Render a clean, high-clarity terminal report of the investigation."""
    anom = inv.anomaly
    bd = inv.breakdown
    sn = inv.seasonality
    tr = inv.recent_trend

    # Metric label formatting
    metric_labels = {
        "order_count": "Order Count (Total Orders Created)",
        "daily_revenue": "Daily Revenue (Net Order Merchandise Value in R$)",
        "average_order_value": "Average Order Value (Revenue per Eligible Order)",
        "cancellation_rate": "Cancellation Rate (Ratio of Cancelled Orders)",
        "delivery_delay_rate": "Delivery Delay Rate (Orders Delivered After Estimated Date)",
    }
    metric_display = metric_labels.get(anom.metric_name, anom.metric_name)

    # Net delta percentage vs baseline
    delta_val = anom.actual_value - anom.expected_value
    if anom.expected_value != Decimal("0.0"):
        pct_vs_base = (delta_val / anom.expected_value) * Decimal("100.0")
        pct_vs_base_str = f" ({pct_vs_base:+.2f}% vs baseline)"
    else:
        pct_vs_base_str = ""

    print("\n" + "=" * 88)
    print("       PICKETIQ -- AUTONOMOUS BUSINESS SIGNAL INVESTIGATION PLATFORM")
    print("                    End-to-End Real Olist Investigation Demo")
    print("=" * 88)
    print("Product Principle: \"When the numbers move, PicketIQ finds out why.\"\n")

    print("[1] ANOMALY DETECTION SIGNAL")
    print("-" * 88)
    print(f"Anomaly Record ID  : #{anom.anomaly_id}")
    print(f"Business Metric    : {metric_display}")
    print(f"Incident Date      : {anom.date}")
    print(f"Actual Value       : {anom.actual_value}")
    print(f"Expected Baseline  : {anom.expected_value} (14-day rolling statistical baseline)")
    print(f"Observed Delta     : {delta_val:+}{pct_vs_base_str}")
    print(f"Statistical Signal : Z-Score = {anom.z_score:+} (Severity: {anom.severity.upper()})")
    print(f"Investigation Run  : #{inv.investigation_id} (Status: {inv.status.upper()})")
    print()

    print("[2] MULTI-DIMENSIONAL EVIDENCE COLLECTION (PHASE 5B)")
    print("-" * 88)

    # Step 1: Regional Breakdown
    print("Step 1: Regional Segment Breakdown (customer_state)")
    if bd and bd.status == "success":
        print(f"  - Status               : {bd.status.upper()}")
        print(f"  - Total Actual Volume  : {bd.total_actual}")
        print(f"  - Baseline Mean Volume : {bd.total_baseline}")
        print(f"  - Net Regional Delta   : {bd.total_delta:+}")
        if bd.top_contributor:
            top = bd.top_contributor
            c_pct = f"{top.percentage_contribution:+.2f}%" if top.percentage_contribution is not None else "N/A"
            s_pct = f"{top.share_of_total:.2f}%" if top.share_of_total is not None else "N/A"
            print(f"  - Primary Contributor  : '{top.segment}' (Actual: {top.actual_value} vs Baseline: {top.baseline_value}, Delta: {top.absolute_delta:+})")
            print(f"  - Contributor Impact   : {c_pct} of total net deviation (Volume share: {s_pct})")
        if bd.segments:
            print("  - Leading States Ranking:")
            for rank, seg in enumerate(bd.segments[:5], 1):
                p = f"{seg.percentage_contribution:+.1f}%" if seg.percentage_contribution is not None else "N/A"
                print(f"      {rank}. {seg.segment:2s} : Actual {seg.actual_value:8.2f} | Base {seg.baseline_value:8.2f} | Delta {seg.absolute_delta:+8.2f} | Share {p}")
        print(f"  - Tool Summary         : {bd.summary}")
    elif bd:
        print(f"  - Status               : {bd.status.upper()} ({bd.summary})")
    else:
        print("  - Status               : FAILED / SKIPPED")
    print()

    # Step 2: Seasonality Analysis
    print("Step 2: Day-of-Week Seasonality Analysis")
    if sn and sn.status == "success":
        seas_desc = "NORMAL (consistent with routine weekly patterns)" if sn.is_seasonal else "NON-SEASONAL (deviation exceeds routine weekday baseline)"
        print(f"  - Status               : {sn.status.upper()}")
        print(f"  - Day of Week          : {sn.day_of_week_name}")
        print(f"  - Target Value         : {sn.target_value}")
        print(f"  - Same-Weekday Mean    : {sn.same_dow_mean} (Sample StdDev: {sn.same_dow_std})")
        print(f"  - Same-Weekday Z-Score : {sn.same_dow_zscore:+}")
        print(f"  - Seasonality Verdict  : {seas_desc}")
        print(f"  - Sample Size          : {sn.sample_size} preceding {sn.day_of_week_name}s evaluated")
        print(f"  - Tool Summary         : {sn.summary}")
    elif sn:
        print(f"  - Status               : {sn.status.upper()} ({sn.summary})")
    else:
        print("  - Status               : FAILED / SKIPPED")
    print()

    # Step 3: Trajectory Trend
    print("Step 3: Trajectory & Recent Trend Analysis (14 Days)")
    if tr and tr.status == "success":
        pct_str = f" ({tr.single_day_pct_change:+}% change)" if tr.single_day_pct_change is not None else ""
        print(f"  - Status               : {tr.status.upper()}")
        print(f"  - Trajectory Class     : {tr.classification.upper()}")
        print(f"  - Preceding Mean       : {tr.preceding_mean} (StdDev: {tr.preceding_std})")
        print(f"  - Linear Daily Slope   : {tr.preceding_trend_slope:+}")
        print(f"  - Single-Day Jump      : {tr.single_day_delta:+}{pct_str}")
        print(f"  - Tool Summary         : {tr.summary}")
    elif tr:
        print(f"  - Status               : {tr.status.upper()} ({tr.summary})")
    else:
        print("  - Status               : FAILED / SKIPPED")
    print()

    print("[3] PROGRAMMATIC VALIDATION ENGINE (PHASE 5D)")
    print("-" * 88)
    print(f"Audit Status       : {'PASSED' if conclusion.validation_passed else 'FAILED'}")
    print(f"Step Citations     : {len(conclusion.evidence_references)} citations verified against database evidence logs")
    print(f"Segment Grounding  : '{conclusion.affected_segment or 'N/A'}' verified against customer geographic master")
    if conclusion.validation_errors:
        print(f"Audit Errors       : {'; '.join(conclusion.validation_errors)}")
    print()

    print("[4] EVIDENCE-GROUNDED ROOT CAUSE & RECOMMENDATION (LLM INTERPRETATION)")
    print("-" * 88)
    print(f"LLM Provider       : {conclusion.provider} (Model: {conclusion.model})")
    print(f"Confidence Level   : {conclusion.confidence.upper()}")
    print(f"Affected Segment   : {conclusion.affected_segment or 'None / Company-wide'}")
    print()
    print(f"IDENTIFIED ROOT CAUSE:\n  {conclusion.root_cause}")
    print()
    print(f"ANALYTICAL EXPLANATION:\n  {conclusion.explanation}")
    print()
    print("VERIFIED EVIDENCE CITATIONS:")
    for ref in conclusion.evidence_references:
        print(f"  - {ref}")
    print()
    print(f"RECOMMENDED OPERATIONAL ACTION:\n  {conclusion.recommended_action}")
    print()
    print("=" * 88)
    print(f"[PERSISTENCE AUDIT] Live Database Commit: Investigation #{inv.investigation_id} | Conclusion verified")
    print("=" * 88 + "\n")


def main() -> None:
    """CLI entrypoint for running the end-to-end investigation demo."""
    parser = argparse.ArgumentParser(
        description="PicketIQ End-to-End Real Olist Investigation Demo (Phase 5E)"
    )
    parser.add_argument(
        "--anomaly-id",
        type=int,
        default=None,
        help="Specific anomaly ID to investigate (default: selects strongest anomaly automatically)",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default=None,
        help="Filter candidate anomalies by metric (e.g., order_count, daily_revenue, cancellation_rate)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override LLM provider ('mock', 'openai', 'anthropic', 'gemini')",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output raw structured JSON for automated pipelines",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,  # Suppress debug logs during demo presentation
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        run_demo(
            anomaly_id=args.anomaly_id,
            metric_name=args.metric,
            provider_name=args.provider,
            as_json=args.as_json,
        )
    except Exception as exc:
        print(f"\nError running investigation demo: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
