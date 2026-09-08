"""Deterministic Investigation Evidence Tools for PicketIQ.

Implements three core evidence-gathering tools:
1. `segment_breakdown`: Identifies regional/state-level contributions to anomalous movements.
2. `check_seasonality`: Compares anomalous movements to historical day-of-week seasonality baselines.
3. `get_recent_trend`: Evaluates preceding time-series trajectory (sudden, gradual, or stable).

All tools produce reproducible, deterministic database evidence without causal speculation.
"""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Union
from sqlalchemy import select, func, and_, case
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models import Customer, Order, OrderItem, KPIDaily
from app.kpi.metadata import (
    CORE_KPIS,
    KPI_DAILY_REVENUE,
    KPI_ORDER_COUNT,
    KPI_AVERAGE_ORDER_VALUE,
    KPI_CANCELLATION_RATE,
    KPI_DELIVERY_DELAY_RATE,
)
from app.investigation.schema import (
    SegmentContribution,
    SegmentBreakdownResult,
    SeasonalityResult,
    TrendPoint,
    RecentTrendResult,
)

logger = logging.getLogger("picket_iq.investigation.tools")

DECIMAL_PLACES = Decimal("0.0001")
PERCENT_PLACES = Decimal("0.01")


def _quantize(val: Union[Decimal, float], places: Decimal = DECIMAL_PLACES) -> Decimal:
    """Format decimal value with standard half-up rounding."""
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(places, rounding=ROUND_HALF_UP)


def _parse_date(target_date: Union[date, str]) -> date:
    """Parse string or date into a standard datetime.date instance."""
    if isinstance(target_date, date):
        return target_date
    if isinstance(target_date, str):
        try:
            return datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Invalid date format '{target_date}'. Expected 'YYYY-MM-DD'.")
    raise TypeError(f"Expected date or str, got {type(target_date).__name__}")


def _validate_metric(metric_name: str) -> None:
    """Verify that metric_name is registered in CORE_KPIS."""
    if metric_name not in CORE_KPIS:
        raise ValueError(
            f"Unsupported metric '{metric_name}'. Must be one of: {', '.join(CORE_KPIS)}"
        )


def _compute_sample_stats(values: List[Decimal]) -> Tuple[Decimal, Decimal]:
    """Calculate sample mean and sample standard deviation with Bessel's correction."""
    n = len(values)
    if n == 0:
        return Decimal("0.0"), Decimal("0.0")
    mean = sum(values) / Decimal(n)
    if n < 2:
        return mean, Decimal("0.0")
    variance = sum((x - mean) ** 2 for x in values) / Decimal(n - 1)
    std_dev = variance.sqrt()
    return mean, std_dev


# ==============================================================================
# TOOL 1: segment_breakdown
# ==============================================================================

def segment_breakdown(
    metric_name: str,
    target_date: Union[date, str],
    session: Optional[Session] = None,
    baseline_days: int = 14,
) -> SegmentBreakdownResult:
    """Break down anomalous KPI movement by customer geographic state vs historical baseline.

    Args:
        metric_name: Registered core KPI name.
        target_date: Date of the anomalous observation (YYYY-MM-DD or date object).
        session: Optional SQLAlchemy Session. If None, creates a managed session.
        baseline_days: Number of preceding calendar days to evaluate for baseline (default: 14).

    Returns:
        SegmentBreakdownResult containing state-level actuals, baselines, deltas, and top contributor.
    """
    dt = _parse_date(target_date)
    _validate_metric(metric_name)

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        dt_str = dt.isoformat()
        start_baseline_dt = dt - timedelta(days=baseline_days)
        start_baseline_str = start_baseline_dt.isoformat()

        date_expr = func.date(Order.order_purchase_timestamp)

        # 1. State-level actuals on the anomalous target date
        if metric_name == KPI_DAILY_REVENUE:
            # Revenue by state (excludes canceled/unavailable)
            actual_stmt = (
                select(Customer.customer_state, func.sum(OrderItem.price))
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .where(
                    date_expr == dt_str,
                    ~Order.order_status.in_(["canceled", "unavailable"]),
                )
                .group_by(Customer.customer_state)
            )
            # Baseline revenue by state over preceding window
            baseline_stmt = (
                select(Customer.customer_state, func.sum(OrderItem.price))
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .where(
                    date_expr >= start_baseline_str,
                    date_expr < dt_str,
                    ~Order.order_status.in_(["canceled", "unavailable"]),
                )
                .group_by(Customer.customer_state)
            )

        elif metric_name == KPI_ORDER_COUNT:
            # Order count by state
            actual_stmt = (
                select(Customer.customer_state, func.count(Order.order_id))
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .where(date_expr == dt_str)
                .group_by(Customer.customer_state)
            )
            baseline_stmt = (
                select(Customer.customer_state, func.count(Order.order_id))
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .where(
                    date_expr >= start_baseline_str,
                    date_expr < dt_str,
                )
                .group_by(Customer.customer_state)
            )

        elif metric_name == KPI_AVERAGE_ORDER_VALUE:
            # Revenue and eligible orders by state for AOV
            actual_stmt = (
                select(
                    Customer.customer_state,
                    func.sum(OrderItem.price),
                    func.count(func.distinct(Order.order_id)),
                )
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .where(
                    date_expr == dt_str,
                    ~Order.order_status.in_(["canceled", "unavailable"]),
                )
                .group_by(Customer.customer_state)
            )
            baseline_stmt = (
                select(
                    Customer.customer_state,
                    func.sum(OrderItem.price),
                    func.count(func.distinct(Order.order_id)),
                )
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .join(OrderItem, Order.order_id == OrderItem.order_id)
                .where(
                    date_expr >= start_baseline_str,
                    date_expr < dt_str,
                    ~Order.order_status.in_(["canceled", "unavailable"]),
                )
                .group_by(Customer.customer_state)
            )

        elif metric_name == KPI_CANCELLATION_RATE:
            # Total orders and canceled orders by state
            actual_stmt = (
                select(
                    Customer.customer_state,
                    func.count(Order.order_id),
                    func.count(case((Order.order_status == "canceled", 1))),
                )
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .where(date_expr == dt_str)
                .group_by(Customer.customer_state)
            )
            baseline_stmt = (
                select(
                    Customer.customer_state,
                    func.count(Order.order_id),
                    func.count(case((Order.order_status == "canceled", 1))),
                )
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .where(
                    date_expr >= start_baseline_str,
                    date_expr < dt_str,
                )
                .group_by(Customer.customer_state)
            )

        elif metric_name == KPI_DELIVERY_DELAY_RATE:
            # Delivered orders with dates and delayed orders by state
            actual_stmt = (
                select(
                    Customer.customer_state,
                    func.count(
                        case(
                            (
                                and_(
                                    Order.order_delivered_customer_date.isnot(None),
                                    Order.order_estimated_delivery_date.isnot(None),
                                ),
                                1,
                            )
                        )
                    ),
                    func.count(
                        case(
                            (
                                and_(
                                    Order.order_delivered_customer_date.isnot(None),
                                    Order.order_estimated_delivery_date.isnot(None),
                                    Order.order_delivered_customer_date > Order.order_estimated_delivery_date,
                                ),
                                1,
                            )
                        )
                    ),
                )
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .where(date_expr == dt_str)
                .group_by(Customer.customer_state)
            )
            baseline_stmt = (
                select(
                    Customer.customer_state,
                    func.count(
                        case(
                            (
                                and_(
                                    Order.order_delivered_customer_date.isnot(None),
                                    Order.order_estimated_delivery_date.isnot(None),
                                ),
                                1,
                            )
                        )
                    ),
                    func.count(
                        case(
                            (
                                and_(
                                    Order.order_delivered_customer_date.isnot(None),
                                    Order.order_estimated_delivery_date.isnot(None),
                                    Order.order_delivered_customer_date > Order.order_estimated_delivery_date,
                                ),
                                1,
                            )
                        )
                    ),
                )
                .select_from(Order)
                .join(Customer, Order.customer_id == Customer.customer_id)
                .where(
                    date_expr >= start_baseline_str,
                    date_expr < dt_str,
                )
                .group_by(Customer.customer_state)
            )

        actual_rows = session.execute(actual_stmt).all()
        baseline_rows = session.execute(baseline_stmt).all()

        # Count active days in baseline window to compute proper daily averages
        active_days_cnt = session.execute(
            select(func.count(func.distinct(date_expr))).where(
                date_expr >= start_baseline_str,
                date_expr < dt_str,
            )
        ).scalar() or 1
        num_baseline_days = max(1, active_days_cnt)

        # 2. Map actual and baseline per state
        actual_by_state: Dict[str, Decimal] = {}
        baseline_by_state: Dict[str, Decimal] = {}

        if metric_name in (KPI_DAILY_REVENUE, KPI_ORDER_COUNT):
            for state, val in actual_rows:
                actual_by_state[state] = Decimal(str(val)) if val is not None else Decimal("0.0")
            for state, val in baseline_rows:
                tot = Decimal(str(val)) if val is not None else Decimal("0.0")
                baseline_by_state[state] = tot / Decimal(num_baseline_days)

        elif metric_name == KPI_AVERAGE_ORDER_VALUE:
            for state, rev, ords in actual_rows:
                r = Decimal(str(rev)) if rev is not None else Decimal("0.0")
                o = int(ords or 0)
                actual_by_state[state] = (r / Decimal(o)) if o > 0 else Decimal("0.0")
            for state, rev, ords in baseline_rows:
                r = Decimal(str(rev)) if rev is not None else Decimal("0.0")
                o = int(ords or 0)
                baseline_by_state[state] = (r / Decimal(o)) if o > 0 else Decimal("0.0")

        elif metric_name == KPI_CANCELLATION_RATE:
            for state, tot, canc in actual_rows:
                t = int(tot or 0)
                c = int(canc or 0)
                actual_by_state[state] = (Decimal(c) / Decimal(t)) if t > 0 else Decimal("0.0")
            for state, tot, canc in baseline_rows:
                t = int(tot or 0)
                c = int(canc or 0)
                baseline_by_state[state] = (Decimal(c) / Decimal(t)) if t > 0 else Decimal("0.0")

        elif metric_name == KPI_DELIVERY_DELAY_RATE:
            for state, delivered, delayed in actual_rows:
                d = int(delivered or 0)
                l = int(delayed or 0)
                actual_by_state[state] = (Decimal(l) / Decimal(d)) if d > 0 else Decimal("0.0")
            for state, delivered, delayed in baseline_rows:
                d = int(delivered or 0)
                l = int(delayed or 0)
                baseline_by_state[state] = (Decimal(l) / Decimal(d)) if d > 0 else Decimal("0.0")

        all_states = sorted(set(actual_by_state.keys()) | set(baseline_by_state.keys()))

        if not all_states:
            return SegmentBreakdownResult(
                tool_name="segment_breakdown",
                metric_name=metric_name,
                date=dt,
                dimension="customer_state",
                total_actual=Decimal("0.0"),
                total_baseline=Decimal("0.0"),
                total_delta=Decimal("0.0"),
                top_contributor=None,
                segments=[],
                summary=f"No operational observations found for {metric_name} on {dt_str}.",
                status="insufficient_data",
            )

        # 3. Overall Totals
        # For additive metrics, sum across states. For rates, compute overall rate.
        if metric_name in (KPI_DAILY_REVENUE, KPI_ORDER_COUNT):
            tot_actual = sum(actual_by_state.values())
            tot_baseline = sum(baseline_by_state.values())
        else:
            # Query overall KPI from kpi_daily if available
            kpi_val = session.execute(
                select(KPIDaily.value).where(
                    KPIDaily.metric_name == metric_name,
                    KPIDaily.date == dt,
                    KPIDaily.segment == "all",
                )
            ).scalar()
            tot_actual = Decimal(str(kpi_val)) if kpi_val is not None else (
                sum(actual_by_state.values()) / Decimal(len(actual_by_state)) if actual_by_state else Decimal("0.0")
            )
            # Baseline mean from kpi_daily
            base_kpis = session.execute(
                select(KPIDaily.value).where(
                    KPIDaily.metric_name == metric_name,
                    KPIDaily.date >= start_baseline_dt,
                    KPIDaily.date < dt,
                    KPIDaily.segment == "all",
                )
            ).scalars().all()
            tot_baseline = (sum(base_kpis) / Decimal(len(base_kpis))) if base_kpis else Decimal("0.0")

        tot_delta = tot_actual - tot_baseline

        # 4. Construct segment contributions
        segments: List[SegmentContribution] = []
        for state in all_states:
            act = actual_by_state.get(state, Decimal("0.0"))
            base = baseline_by_state.get(state, Decimal("0.0"))
            d = act - base

            # Contribution share of total delta
            pct_contrib: Optional[Decimal] = None
            if tot_delta != Decimal("0.0"):
                pct_contrib = _quantize((d / tot_delta) * Decimal("100.0"), PERCENT_PLACES)

            # Share of actual volume on target date
            share_of_tot: Optional[Decimal] = None
            if tot_actual > Decimal("0.0") and metric_name in (KPI_DAILY_REVENUE, KPI_ORDER_COUNT):
                share_of_tot = _quantize((act / tot_actual) * Decimal("100.0"), PERCENT_PLACES)

            segments.append(
                SegmentContribution(
                    segment=state,
                    actual_value=_quantize(act),
                    baseline_value=_quantize(base),
                    absolute_delta=_quantize(d),
                    percentage_contribution=pct_contrib,
                    share_of_total=share_of_tot,
                )
            )

        # Sort segments by absolute delta descending
        segments.sort(key=lambda s: abs(s.absolute_delta), reverse=True)
        top = segments[0] if segments else None

        # 5. Build factual summary
        if top and top.percentage_contribution is not None:
            summary = (
                f"Customer state breakdown for '{metric_name}' on {dt_str}: Total was "
                f"{_quantize(tot_actual)} (baseline: {_quantize(tot_baseline)}, delta: {_quantize(tot_delta):+}). "
                f"Top contributing region was '{top.segment}' with actual {_quantize(top.actual_value)} "
                f"vs baseline {_quantize(top.baseline_value)} ({_quantize(top.absolute_delta):+}, "
                f"{top.percentage_contribution}% of total deviation)."
            )
        elif top:
            summary = (
                f"Customer state breakdown for '{metric_name}' on {dt_str}: Total was "
                f"{_quantize(tot_actual)} (baseline: {_quantize(tot_baseline)}). "
                f"Top region by delta was '{top.segment}' with delta {_quantize(top.absolute_delta):+}."
            )
        else:
            summary = f"No segments found for '{metric_name}' on {dt_str}."

        return SegmentBreakdownResult(
            tool_name="segment_breakdown",
            metric_name=metric_name,
            date=dt,
            dimension="customer_state",
            total_actual=_quantize(tot_actual),
            total_baseline=_quantize(tot_baseline),
            total_delta=_quantize(tot_delta),
            top_contributor=top,
            segments=segments,
            summary=summary,
            status="success",
        )

    finally:
        if close_session:
            session.close()


# ==============================================================================
# TOOL 2: check_seasonality
# ==============================================================================

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def check_seasonality(
    metric_name: str,
    target_date: Union[date, str],
    session: Optional[Session] = None,
    lookback_weeks: int = 8,
) -> SeasonalityResult:
    """Evaluate whether an anomalous observation aligns with historical day-of-week seasonality.

    Args:
        metric_name: Registered core KPI name.
        target_date: Date of the observation (YYYY-MM-DD or date object).
        session: Optional SQLAlchemy Session. If None, creates a managed session.
        lookback_weeks: Maximum preceding weeks of same-weekday observations to compare (default: 8).

    Returns:
        SeasonalityResult containing same-DOW mean, std dev, same-DOW z-score, and seasonality flag.
    """
    dt = _parse_date(target_date)
    _validate_metric(metric_name)

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        dt_str = dt.isoformat()
        dow_idx = dt.weekday()
        dow_name = DAY_NAMES[dow_idx]

        # 1. Target observation value from kpi_daily
        target_kpi = session.execute(
            select(KPIDaily.value).where(
                KPIDaily.metric_name == metric_name,
                KPIDaily.date == dt,
                KPIDaily.segment == "all",
            )
        ).scalar()

        if target_kpi is None:
            return SeasonalityResult(
                tool_name="check_seasonality",
                metric_name=metric_name,
                date=dt,
                day_of_week=dow_idx,
                day_of_week_name=dow_name,
                target_value=Decimal("0.0"),
                same_dow_mean=Decimal("0.0"),
                same_dow_std=Decimal("0.0"),
                same_dow_zscore=Decimal("0.0"),
                is_seasonal=False,
                dow_averages={},
                sample_size=0,
                summary=f"No KPI observation found for '{metric_name}' on {dt_str}.",
                status="insufficient_data",
            )

        target_val = Decimal(str(target_kpi))

        # 2. Query historical observations for this metric strictly prior to target date
        hist_rows = session.execute(
            select(KPIDaily.date, KPIDaily.value)
            .where(
                KPIDaily.metric_name == metric_name,
                KPIDaily.date < dt,
                KPIDaily.segment == "all",
            )
            .order_by(KPIDaily.date.desc())
        ).all()

        if not hist_rows:
            return SeasonalityResult(
                tool_name="check_seasonality",
                metric_name=metric_name,
                date=dt,
                day_of_week=dow_idx,
                day_of_week_name=dow_name,
                target_value=_quantize(target_val),
                same_dow_mean=Decimal("0.0"),
                same_dow_std=Decimal("0.0"),
                same_dow_zscore=Decimal("0.0"),
                is_seasonal=False,
                dow_averages={},
                sample_size=0,
                summary=f"No prior historical observations available before {dt_str}.",
                status="insufficient_data",
            )

        # 3. Extract same day-of-week observations (up to lookback_weeks)
        same_dow_values: List[Decimal] = []
        dow_buckets: Dict[int, List[Decimal]] = {i: [] for i in range(7)}

        for obs_date, obs_val in hist_rows:
            obs_dt = obs_date if isinstance(obs_date, date) else date.fromisoformat(str(obs_date))
            val_dec = Decimal(str(obs_val))
            obs_dow = obs_dt.weekday()

            dow_buckets[obs_dow].append(val_dec)
            if obs_dow == dow_idx and len(same_dow_values) < lookback_weeks:
                same_dow_values.append(val_dec)

        # Compute full weekly DOW historical averages
        dow_averages: Dict[str, Decimal] = {}
        for i in range(7):
            b_vals = dow_buckets[i]
            if b_vals:
                dow_averages[DAY_NAMES[i]] = _quantize(sum(b_vals) / Decimal(len(b_vals)))
            else:
                dow_averages[DAY_NAMES[i]] = Decimal("0.0000")

        sample_size = len(same_dow_values)
        if sample_size == 0:
            return SeasonalityResult(
                tool_name="check_seasonality",
                metric_name=metric_name,
                date=dt,
                day_of_week=dow_idx,
                day_of_week_name=dow_name,
                target_value=_quantize(target_val),
                same_dow_mean=Decimal("0.0"),
                same_dow_std=Decimal("0.0"),
                same_dow_zscore=Decimal("0.0"),
                is_seasonal=False,
                dow_averages=dow_averages,
                sample_size=0,
                summary=f"Insufficient same-weekday historical observations for {dow_name} prior to {dt_str}.",
                status="insufficient_data",
            )

        # Baseline statistics for this weekday
        mean_dow, std_dow = _compute_sample_stats(same_dow_values)

        # Same-DOW Z-score with zero-variance protection
        if std_dow > Decimal("0.0"):
            z_dow = (target_val - mean_dow) / std_dow
            is_seasonal = abs(z_dow) < Decimal("2.0")
        else:
            if target_val == mean_dow:
                z_dow = Decimal("0.0")
                is_seasonal = True
            else:
                z_dow = Decimal("99.9999") if target_val > mean_dow else Decimal("-99.9999")
                is_seasonal = False

        if is_seasonal:
            summary = (
                f"Seasonality check for '{metric_name}' on {dt_str} ({dow_name}): Observed value was "
                f"{_quantize(target_val)} vs {dow_name} baseline mean of {_quantize(mean_dow)} "
                f"(std: {_quantize(std_dow)}, same-DOW z: {_quantize(z_dow):+}). "
                f"The observation is consistent with expected weekly seasonality (same-DOW |z| < 2.0)."
            )
        else:
            summary = (
                f"Seasonality check for '{metric_name}' on {dt_str} ({dow_name}): Observed value was "
                f"{_quantize(target_val)} vs {dow_name} baseline mean of {_quantize(mean_dow)} "
                f"(std: {_quantize(std_dow)}, same-DOW z: {_quantize(z_dow):+}). "
                f"The observation is not explained by typical weekly seasonality (same-DOW |z| >= 2.0)."
            )

        return SeasonalityResult(
            tool_name="check_seasonality",
            metric_name=metric_name,
            date=dt,
            day_of_week=dow_idx,
            day_of_week_name=dow_name,
            target_value=_quantize(target_val),
            same_dow_mean=_quantize(mean_dow),
            same_dow_std=_quantize(std_dow),
            same_dow_zscore=_quantize(z_dow),
            is_seasonal=is_seasonal,
            dow_averages=dow_averages,
            sample_size=sample_size,
            summary=summary,
            status="success",
        )

    finally:
        if close_session:
            session.close()


# ==============================================================================
# TOOL 3: get_recent_trend
# ==============================================================================

def get_recent_trend(
    metric_name: str,
    target_date: Union[date, str],
    window_days: int = 14,
    session: Optional[Session] = None,
) -> RecentTrendResult:
    """Evaluate recent trajectory leading up to anomalous date (sudden vs gradual vs stable).

    Args:
        metric_name: Registered core KPI name.
        target_date: Date of the observation (YYYY-MM-DD or date object).
        window_days: Number of days in evaluation window including target date (default: 14, min: 3).
        session: Optional SQLAlchemy Session. If None, creates a managed session.

    Returns:
        RecentTrendResult containing trend classification, slope, single-day jump, and history points.
    """
    dt = _parse_date(target_date)
    _validate_metric(metric_name)

    if window_days < 3:
        raise ValueError(f"window_days must be at least 3, received {window_days}.")

    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        dt_str = dt.isoformat()
        start_window_dt = dt - timedelta(days=window_days - 1)

        # Query daily KPI values in [start_window_dt, dt]
        rows = session.execute(
            select(KPIDaily.date, KPIDaily.value)
            .where(
                KPIDaily.metric_name == metric_name,
                KPIDaily.date >= start_window_dt,
                KPIDaily.date <= dt,
                KPIDaily.segment == "all",
            )
            .order_by(KPIDaily.date.asc())
        ).all()

        history_points: List[TrendPoint] = []
        for r_dt, r_val in rows:
            obs_dt = r_dt if isinstance(r_dt, date) else date.fromisoformat(str(r_dt))
            history_points.append(TrendPoint(date=obs_dt, value=_quantize(Decimal(str(r_val)))))

        n = len(history_points)
        if n < 3:
            return RecentTrendResult(
                tool_name="get_recent_trend",
                metric_name=metric_name,
                date=dt,
                window_days=window_days,
                observations_count=n,
                classification="insufficient_data",
                target_value=history_points[-1].value if n > 0 else Decimal("0.0"),
                preceding_mean=Decimal("0.0"),
                preceding_std=Decimal("0.0"),
                preceding_trend_slope=Decimal("0.0"),
                single_day_delta=Decimal("0.0"),
                single_day_pct_change=None,
                history=history_points,
                summary=f"Insufficient observations in window ({n} found, minimum 3 required).",
                status="insufficient_data",
            )

        target_point = history_points[-1]
        target_val = target_point.value
        preceding_points = history_points[:-1]
        preceding_vals = [p.value for p in preceding_points]
        k = len(preceding_vals)

        # Baseline statistics of preceding observations
        mean_p, std_p = _compute_sample_stats(preceding_vals)

        # Single-day step from day before target to target
        prev_val = preceding_vals[-1]
        single_day_delta = target_val - prev_val
        single_day_pct: Optional[Decimal] = None
        if prev_val != Decimal("0.0"):
            single_day_pct = _quantize((single_day_delta / prev_val) * Decimal("100.0"), PERCENT_PLACES)

        # Linear regression slope over preceding points: y = a + beta * x
        # x_i = 0, 1, ..., k-1
        x_mean = Decimal(k - 1) / Decimal("2.0")
        ss_xx = sum((Decimal(i) - x_mean) ** 2 for i in range(k))
        if ss_xx > Decimal("0.0"):
            ss_xy = sum((Decimal(i) - x_mean) * (preceding_vals[i] - mean_p) for i in range(k))
            slope = ss_xy / ss_xx
        else:
            slope = Decimal("0.0")

        # Pearson correlation coefficient r
        ss_yy = sum((y - mean_p) ** 2 for y in preceding_vals)
        if ss_xx > Decimal("0.0") and ss_yy > Decimal("0.0"):
            corr_r = ss_xy / (ss_xx.sqrt() * ss_yy.sqrt())
        else:
            corr_r = Decimal("0.0")

        # Total deviation from preceding mean
        total_deviation = target_val - mean_p

        # Classification logic:
        # 1. Check for sudden jump:
        #    - Single day step change is >= 2.5 * std_p
        #    - Or step change accounts for majority (> 65%) of the total deviation from baseline
        is_sudden = False
        if std_p > Decimal("0.0"):
            z_step = abs(single_day_delta) / std_p
            if z_step >= Decimal("2.5"):
                is_sudden = True
            elif abs(total_deviation) >= Decimal("2.5") * std_p and total_deviation != Decimal("0.0"):
                if (abs(single_day_delta) / abs(total_deviation)) >= Decimal("0.65"):
                    is_sudden = True
        elif single_day_delta != Decimal("0.0"):
            is_sudden = True

        if is_sudden:
            classification = "sudden"
        else:
            # Check for gradual trends in the preceding period
            # Metrics where increase is deteriorating: cancellation_rate, delivery_delay_rate
            negative_metrics = (KPI_CANCELLATION_RATE, KPI_DELIVERY_DELAY_RATE)

            if metric_name in negative_metrics:
                # Worsening = slope > 0 (cancellations or delays increasing)
                if slope > Decimal("0.0") and corr_r >= Decimal("0.40"):
                    classification = "gradual_deterioration"
                elif slope < Decimal("0.0") and corr_r <= Decimal("-0.40"):
                    classification = "gradual_improvement"
                else:
                    classification = "stable"
            else:
                # For revenue, order_count, AOV: worsening = slope < 0
                if slope < Decimal("0.0") and corr_r <= Decimal("-0.40"):
                    classification = "gradual_deterioration"
                elif slope > Decimal("0.0") and corr_r >= Decimal("0.40"):
                    classification = "gradual_improvement"
                else:
                    classification = "stable"

        # Construct factual summary
        pct_str = f" ({single_day_pct:+}% change)" if single_day_pct is not None else ""
        summary = (
            f"Recent trend analysis for '{metric_name}' on {dt_str} ({n} days evaluated): "
            f"Classified as '{classification}'. Preceding baseline mean was {_quantize(mean_p)} "
            f"(std: {_quantize(std_p)}, daily slope: {_quantize(slope):+}). "
            f"Single-day shift on {dt_str} was {_quantize(single_day_delta):+}{pct_str}."
        )

        return RecentTrendResult(
            tool_name="get_recent_trend",
            metric_name=metric_name,
            date=dt,
            window_days=window_days,
            observations_count=n,
            classification=classification,
            target_value=_quantize(target_val),
            preceding_mean=_quantize(mean_p),
            preceding_std=_quantize(std_p),
            preceding_trend_slope=_quantize(slope),
            single_day_delta=_quantize(single_day_delta),
            single_day_pct_change=single_day_pct,
            history=history_points,
            summary=summary,
            status="success",
        )

    finally:
        if close_session:
            session.close()
