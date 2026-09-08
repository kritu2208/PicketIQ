"""Rolling Z-Score Statistical Anomaly Detection Engine.

Analyzes daily KPI time series using a rolling historical baseline window
to detect and classify significant business signal deviations.
"""

import argparse
import logging
import sys
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.db.models import KPIDaily, Anomaly
from app.kpi.metadata import CORE_KPIS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("picket_iq.detection.zscore")

# Precision constants
VALUE_PLACES = Decimal("0.0001")
ZSCORE_PLACES = Decimal("0.0001")

# Default detection parameters
DEFAULT_BASELINE_WINDOW = 14
DEFAULT_MIN_HISTORY = 7
DEFAULT_ZSCORE_THRESHOLD = Decimal("3.0")

SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"


def quantize_value(val: Decimal) -> Decimal:
    """Format decimal value to 4 decimal places with standard half-up rounding."""
    return val.quantize(VALUE_PLACES, rounding=ROUND_HALF_UP)


def quantize_zscore(val: Decimal) -> Decimal:
    """Format z-score to 4 decimal places with standard half-up rounding."""
    return val.quantize(ZSCORE_PLACES, rounding=ROUND_HALF_UP)


def parse_cli_date(date_str: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD string into a date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.")


def compute_baseline_stats(values: List[Decimal]) -> Tuple[Decimal, Decimal]:
    """Calculate sample mean and sample standard deviation (ddof=1) from historical baseline.

    Args:
        values: List of preceding historical Decimal observations.

    Returns:
        Tuple of (mean, sample_standard_deviation).
    """
    n = len(values)
    if n == 0:
        return Decimal("0.0"), Decimal("0.0")

    mean = sum(values) / Decimal(n)
    if n < 2:
        return mean, Decimal("0.0")

    # Sample variance with Bessel's correction (N - 1 degrees of freedom)
    variance = sum((x - mean) ** 2 for x in values) / Decimal(n - 1)
    std_dev = variance.sqrt()
    return mean, std_dev


def calculate_zscore(actual: Decimal, mean: Decimal, std_dev: Decimal) -> Decimal:
    """Calculate standard Z-score with zero-variance protection.

    If historical standard deviation is zero:
    Returns Decimal("0.0") to avoid division by zero or infinite/undefined values.
    """
    if std_dev == Decimal("0"):
        return Decimal("0.0")
    return (actual - mean) / std_dev


def classify_severity(abs_z: Decimal) -> str:
    """Classify anomaly severity based on absolute Z-score deviation tiers:

    - HIGH:   |z| >= 5.0
    - MEDIUM: 4.0 <= |z| < 5.0
    - LOW:    3.0 <= |z| < 4.0 (or below 4.0 for custom thresholds)
    """
    if abs_z >= Decimal("5.0"):
        return SEVERITY_HIGH
    elif abs_z >= Decimal("4.0"):
        return SEVERITY_MEDIUM
    else:
        return SEVERITY_LOW


def detect_anomalies_for_kpis(
    session: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    threshold: Decimal = DEFAULT_ZSCORE_THRESHOLD,
    window_size: int = DEFAULT_BASELINE_WINDOW,
    min_history: int = DEFAULT_MIN_HISTORY,
    metrics: Optional[List[str]] = None,
    segment: str = "all",
) -> Dict[str, Any]:
    """Execute rolling Z-score anomaly detection across daily KPI series.

    Args:
        session: Active SQLAlchemy Session instance.
        start_date: Start date of the evaluation window (inclusive).
        end_date: End date of the evaluation window (inclusive).
        threshold: Absolute Z-score anomaly threshold (default: 3.0).
        window_size: Maximum historical observations in baseline window (default: 14).
        min_history: Minimum historical observations required to evaluate (default: 7).
        metrics: List of metric names to evaluate (default: all core KPIs).
        segment: KPI segment dimension to evaluate (default: 'all').

    Returns:
        Summary dict containing execution metrics and anomaly counts.
    """
    if start_date and end_date and start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) cannot be after end_date ({end_date})."
        )

    target_metrics = metrics or CORE_KPIS
    logger.info(
        "Starting rolling Z-score anomaly detection (threshold=%s, window=%d, min_history=%d)...",
        threshold,
        window_size,
        min_history,
    )

    total_evaluated = 0
    anomalies_to_insert: List[Anomaly] = []
    severity_counts = {SEVERITY_LOW: 0, SEVERITY_MEDIUM: 0, SEVERITY_HIGH: 0}

    eval_min_date: Optional[date] = None
    eval_max_date: Optional[date] = None

    for metric_name in target_metrics:
        # Query all observations up to end_date (including prior history for baseline)
        query = (
            select(KPIDaily.date, KPIDaily.value)
            .where(
                and_(
                    KPIDaily.metric_name == metric_name,
                    KPIDaily.segment == segment,
                )
            )
            .order_by(KPIDaily.date.asc())
        )
        if end_date:
            query = query.where(KPIDaily.date <= end_date)

        rows = session.execute(query).all()
        if not rows:
            continue

        # Chronological history buffer of (date, value)
        history: List[Tuple[date, Decimal]] = []

        for obs_date, obs_value in rows:
            # Check if this observation falls within the target evaluation window
            is_in_eval_window = True
            if start_date and obs_date < start_date:
                is_in_eval_window = False
            if end_date and obs_date > end_date:
                is_in_eval_window = False

            if is_in_eval_window:
                if eval_min_date is None or obs_date < eval_min_date:
                    eval_min_date = obs_date
                if eval_max_date is None or obs_date > eval_max_date:
                    eval_max_date = obs_date

                # Evaluate using baseline window of strictly preceding observations
                if len(history) >= min_history:
                    total_evaluated += 1
                    baseline_values = [val for _, val in history[-window_size:]]
                    mean, std_dev = compute_baseline_stats(baseline_values)
                    z_score = calculate_zscore(obs_value, mean, std_dev)
                    abs_z = abs(z_score)

                    if abs_z >= threshold:
                        severity = classify_severity(abs_z)
                        severity_counts[severity] += 1
                        anomaly = Anomaly(
                            metric_name=metric_name,
                            date=obs_date,
                            expected_value=quantize_value(mean),
                            actual_value=quantize_value(obs_value),
                            z_score=quantize_zscore(z_score),
                            severity=severity,
                            status="open",
                        )
                        anomalies_to_insert.append(anomaly)

            # Append current observation to history for subsequent dates
            history.append((obs_date, obs_value))

    # Idempotent persistence: delete existing anomalies in evaluated range, then insert
    if eval_min_date and eval_max_date:
        effective_start = start_date or eval_min_date
        effective_end = end_date or eval_max_date
        with session.begin_nested():
            session.execute(
                delete(Anomaly).where(
                    and_(
                        Anomaly.metric_name.in_(target_metrics),
                        Anomaly.date >= effective_start,
                        Anomaly.date <= effective_end,
                    )
                )
            )
            session.add_all(anomalies_to_insert)
        session.commit()
    elif anomalies_to_insert:
        with session.begin_nested():
            session.add_all(anomalies_to_insert)
        session.commit()

    logger.info(
        "Detection complete: %d observations evaluated, %d anomalies detected (%s).",
        total_evaluated,
        len(anomalies_to_insert),
        severity_counts,
    )

    return {
        "start_date": start_date or eval_min_date,
        "end_date": end_date or eval_max_date,
        "metrics_processed": target_metrics,
        "observations_evaluated": total_evaluated,
        "anomalies_detected": len(anomalies_to_insert),
        "low_count": severity_counts[SEVERITY_LOW],
        "medium_count": severity_counts[SEVERITY_MEDIUM],
        "high_count": severity_counts[SEVERITY_HIGH],
    }


def main() -> None:
    """CLI entrypoint for Z-score anomaly detector."""
    parser = argparse.ArgumentParser(
        description="PicketIQ Rolling Z-Score Anomaly Detector."
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=None,
        help="Evaluation start date in YYYY-MM-DD format (default: all available dates)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="Evaluation end date in YYYY-MM-DD format (default: all available dates)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=3.0,
        help="Z-score absolute anomaly threshold (default: 3.0)",
    )
    args = parser.parse_args()

    try:
        start_dt = parse_cli_date(args.start_date)
        end_dt = parse_cli_date(args.end_date)
        threshold_dec = Decimal(str(args.threshold))
    except ValueError as err:
        logger.error(str(err))
        sys.exit(1)

    session = SessionLocal()
    try:
        summary = detect_anomalies_for_kpis(
            session=session,
            start_date=start_dt,
            end_date=end_dt,
            threshold=threshold_dec,
        )

        print("\n========================================")
        print("   PicketIQ Anomaly Detection Summary   ")
        print("========================================")
        print(f"Date Range:              {summary['start_date']} to {summary['end_date']}")
        print(f"Metrics Processed:       {len(summary['metrics_processed'])}")
        print(f"Observations Evaluated:  {summary['observations_evaluated']}")
        print(f"Anomalies Detected:      {summary['anomalies_detected']}")
        print(f"  - Low Severity:        {summary['low_count']}")
        print(f"  - Medium Severity:     {summary['medium_count']}")
        print(f"  - High Severity:       {summary['high_count']}")
        print("========================================\n")
    except Exception as exc:
        session.rollback()
        logger.error("Anomaly detection failed: %s", exc)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
