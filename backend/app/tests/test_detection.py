"""Deterministic unit tests for rolling Z-score statistical anomaly detection."""

import math
from datetime import date, timedelta, datetime
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.session import Base
from app.db.models import KPIDaily, Anomaly
from app.detection.zscore_detector import (
    compute_baseline_stats,
    calculate_zscore,
    classify_severity,
    detect_anomalies_for_kpis,
    quantize_value,
    quantize_zscore,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
    DEFAULT_ZSCORE_THRESHOLD,
)


@pytest.fixture
def detection_db_session():
    """In-memory SQLite database session isolated per test."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def test_correct_rolling_mean():
    """Test compute_baseline_stats calculates the exact arithmetic mean."""
    values = [Decimal(str(x)) for x in [10, 20, 30, 40, 50, 60, 70]]
    mean, _ = compute_baseline_stats(values)
    assert mean == Decimal("40.0")


def test_correct_standard_deviation():
    """Test compute_baseline_stats calculates sample standard deviation (ddof=1)."""
    # Constant values -> standard deviation must be 0
    const_values = [Decimal("100.0")] * 7
    _, std_const = compute_baseline_stats(const_values)
    assert std_const == Decimal("0.0")

    # Sample variance with known manual calculation: [2, 4, 4, 4, 5, 5, 7, 9]
    # mean = 5.0, sum of sq diffs = (9+1+1+1+0+0+4+16) = 32. var = 32 / (8-1) = 32/7
    sample_values = [Decimal(str(x)) for x in [2, 4, 4, 4, 5, 5, 7, 9]]
    mean, std = compute_baseline_stats(sample_values)
    assert mean == Decimal("5.0")
    expected_var = Decimal("32") / Decimal("7")
    assert std == expected_var.sqrt()


def test_current_observation_excluded_from_baseline(detection_db_session):
    """Test that the current observation is strictly excluded when calculating its own baseline."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # 7 baseline days with value 100.0
    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("100.0000"),
                segment="all",
            )
        )

    # Day 8 with extreme spike of 1000.0
    day8_date = start_dt + timedelta(days=7)
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8_date,
            value=Decimal("1000.0000"),
            segment="all",
        )
    )
    session.commit()

    # Note: baseline values must have non-zero variance to compute z-score
    # Let's adjust day 1 to 99 and day 2 to 101 to give non-zero variance
    rec1 = session.execute(
        select(KPIDaily).where(KPIDaily.date == start_dt)
    ).scalar_one()
    rec1.value = Decimal("99.0000")
    rec2 = session.execute(
        select(KPIDaily).where(KPIDaily.date == start_dt + timedelta(days=1))
    ).scalar_one()
    rec2.value = Decimal("101.0000")
    session.commit()

    detect_anomalies_for_kpis(session)

    anomaly = session.execute(
        select(Anomaly).where(Anomaly.date == day8_date)
    ).scalar_one()

    # The expected value MUST be around 100.0 (baseline mean of previous 7 days)
    # If day 8 (1000.0) were included, mean would be > 200.0
    assert anomaly.expected_value == Decimal("100.0000")
    assert anomaly.actual_value == Decimal("1000.0000")


def test_fewer_than_7_historical_observations_skipped(detection_db_session):
    """Test that anomaly detection is skipped for observations with fewer than 7 historical days."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # Only 6 observations in total, ending with a huge spike on day 6
    for i in range(5):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("100.0000"),
                segment="all",
            )
        )
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=start_dt + timedelta(days=5),
            value=Decimal("9999.0000"),
            segment="all",
        )
    )
    session.commit()

    summary = detect_anomalies_for_kpis(session)
    assert summary["anomalies_detected"] == 0
    assert summary["observations_evaluated"] == 0

    anomalies = session.execute(select(Anomaly)).scalars().all()
    assert len(anomalies) == 0


def test_normal_observation_not_flagged(detection_db_session):
    """Test that standard fluctuations (|z| < 3.0) do not trigger anomalies."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # 10 days of values alternating between 10.0 and 12.0
    for i in range(10):
        val = Decimal("10.0000") if i % 2 == 0 else Decimal("12.0000")
        session.add(
            KPIDaily(
                metric_name="order_count",
                date=start_dt + timedelta(days=i),
                value=val,
                segment="all",
            )
        )
    session.commit()

    summary = detect_anomalies_for_kpis(session)
    assert summary["anomalies_detected"] == 0

    anomalies = session.execute(select(Anomaly)).scalars().all()
    assert len(anomalies) == 0


def test_zscore_ge_3_produces_anomaly(detection_db_session):
    """Test that a positive deviation producing |z| >= 3.0 creates an anomaly."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # 7 baseline days: [10, 12, 10, 12, 10, 12, 10] (mean ~ 10.8571, std ~ 1.0690)
    for i in range(7):
        val = Decimal("10.0000") if i % 2 == 0 else Decimal("12.0000")
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=val,
                segment="all",
            )
        )

    # Day 8: value = 15.0 -> z = (15 - 10.8571) / 1.0690 = 3.8753 >= 3.0
    day8 = start_dt + timedelta(days=7)
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8,
            value=Decimal("15.0000"),
            segment="all",
        )
    )
    session.commit()

    summary = detect_anomalies_for_kpis(session)
    assert summary["anomalies_detected"] == 1

    anomaly = session.execute(
        select(Anomaly).where(Anomaly.date == day8)
    ).scalar_one()
    assert anomaly.z_score >= Decimal("3.0")
    assert anomaly.status == "open"


def test_negative_zscore_anomaly(detection_db_session):
    """Test that a sharp downward drop creates an anomaly with negative z-score."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # 7 baseline days: [100, 102, 100, 102, 100, 102, 100] (mean ~ 100.8571, std ~ 1.0690)
    for i in range(7):
        val = Decimal("100.0000") if i % 2 == 0 else Decimal("102.0000")
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=val,
                segment="all",
            )
        )

    # Day 8: crash to 90.0 -> z = (90 - 100.8571) / 1.0690 = -10.156
    day8 = start_dt + timedelta(days=7)
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8,
            value=Decimal("90.0000"),
            segment="all",
        )
    )
    session.commit()

    detect_anomalies_for_kpis(session)

    anomaly = session.execute(
        select(Anomaly).where(Anomaly.date == day8)
    ).scalar_one()
    assert anomaly.z_score < Decimal("-3.0")
    assert anomaly.severity == SEVERITY_HIGH


def test_low_severity():
    """Test 3.0 <= |z| < 4.0 is classified as low severity."""
    assert classify_severity(Decimal("3.0")) == SEVERITY_LOW
    assert classify_severity(Decimal("3.5")) == SEVERITY_LOW
    assert classify_severity(Decimal("3.9999")) == SEVERITY_LOW


def test_medium_severity():
    """Test 4.0 <= |z| < 5.0 is classified as medium severity."""
    assert classify_severity(Decimal("4.0")) == SEVERITY_MEDIUM
    assert classify_severity(Decimal("4.5")) == SEVERITY_MEDIUM
    assert classify_severity(Decimal("4.9999")) == SEVERITY_MEDIUM


def test_high_severity():
    """Test |z| >= 5.0 is classified as high severity."""
    assert classify_severity(Decimal("5.0")) == SEVERITY_HIGH
    assert classify_severity(Decimal("5.5")) == SEVERITY_HIGH
    assert classify_severity(Decimal("10.0")) == SEVERITY_HIGH


def test_zero_variance_handling(detection_db_session):
    """Test that standard deviation of zero does not produce NaN, infinity, or unhandled errors."""
    # Direct calculate_zscore check
    z = calculate_zscore(Decimal("100"), Decimal("100"), Decimal("0"))
    assert z == Decimal("0.0")

    z_diff = calculate_zscore(Decimal("200"), Decimal("100"), Decimal("0"))
    assert z_diff == Decimal("0.0")

    # Time series check: constant series followed by a change
    session = detection_db_session
    start_dt = date(2017, 1, 1)
    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="cancellation_rate",
                date=start_dt + timedelta(days=i),
                value=Decimal("0.0000"),
                segment="all",
            )
        )
    session.add(
        KPIDaily(
            metric_name="cancellation_rate",
            date=start_dt + timedelta(days=7),
            value=Decimal("0.0500"),
            segment="all",
        )
    )
    session.commit()

    summary = detect_anomalies_for_kpis(session)
    # Zero variance must not produce NaN or infinity or crash
    assert summary["observations_evaluated"] == 1
    anomalies = session.execute(select(Anomaly)).scalars().all()
    for a in anomalies:
        assert not math.isnan(float(a.z_score))
        assert not math.isinf(float(a.z_score))


def test_expected_value_equals_baseline_mean(detection_db_session):
    """Test that expected_value matches the historical baseline mean."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # 7 days with values [10, 20, 10, 20, 10, 20, 10] -> sum = 100, mean = 100/7
    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("10.0000") if i % 2 == 0 else Decimal("20.0000"),
                segment="all",
            )
        )
    day8 = start_dt + timedelta(days=7)
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8,
            value=Decimal("100.0000"),
            segment="all",
        )
    )
    session.commit()

    detect_anomalies_for_kpis(session)

    anomaly = session.execute(select(Anomaly).where(Anomaly.date == day8)).scalar_one()
    expected_mean = quantize_value(Decimal("100") / Decimal("7"))
    assert anomaly.expected_value == expected_mean


def test_actual_value_equals_kpi_value(detection_db_session):
    """Test that actual_value matches the KPI observation value."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("10.0000") if i % 2 == 0 else Decimal("20.0000"),
                segment="all",
            )
        )
    day8 = start_dt + timedelta(days=7)
    kpi_val = Decimal("85.5000")
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8,
            value=kpi_val,
            segment="all",
        )
    )
    session.commit()

    detect_anomalies_for_kpis(session)

    anomaly = session.execute(select(Anomaly).where(Anomaly.date == day8)).scalar_one()
    assert anomaly.actual_value == kpi_val


def test_configurable_threshold(detection_db_session):
    """Test that detection threshold can be modified through the detector interface."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("10.0000") if i % 2 == 0 else Decimal("12.0000"),
                segment="all",
            )
        )
    # Day 8: z-score ~ 3.87
    day8 = start_dt + timedelta(days=7)
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8,
            value=Decimal("15.0000"),
            segment="all",
        )
    )
    session.commit()

    # With high threshold (5.0), |z| = 3.87 is NOT an anomaly
    sum_high = detect_anomalies_for_kpis(session, threshold=Decimal("5.0"))
    assert sum_high["anomalies_detected"] == 0

    # With standard threshold (3.0), it IS an anomaly
    sum_std = detect_anomalies_for_kpis(session, threshold=Decimal("3.0"))
    assert sum_std["anomalies_detected"] == 1


def test_date_filtering(detection_db_session):
    """Test evaluating a specific date range uses preceding history for baseline without re-evaluating preceding dates."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    # 10 days of observations: days 0-6 baseline, day 7 spike, day 8 normal, day 9 major spike
    for i in range(10):
        if i == 7:
            val = Decimal("100.0000")
        elif i == 9:
            val = Decimal("200.0000")
        else:
            val = Decimal("10.0000") if i % 2 == 0 else Decimal("12.0000")
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=val,
                segment="all",
            )
        )
    session.commit()

    # Filter only day 9
    day9 = start_dt + timedelta(days=9)
    summary = detect_anomalies_for_kpis(
        session,
        start_date=day9,
        end_date=day9,
    )
    assert summary["observations_evaluated"] == 1
    assert summary["anomalies_detected"] == 1

    anomalies = session.execute(select(Anomaly)).scalars().all()
    assert len(anomalies) == 1
    assert anomalies[0].date == day9


def test_anomaly_idempotency(detection_db_session):
    """Test that running anomaly detection multiple times produces identical results without duplicates."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("10.0000") if i % 2 == 0 else Decimal("12.0000"),
                segment="all",
            )
        )
    day8 = start_dt + timedelta(days=7)
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=day8,
            value=Decimal("30.0000"),
            segment="all",
        )
    )
    session.commit()

    sum1 = detect_anomalies_for_kpis(session)
    sum2 = detect_anomalies_for_kpis(session)

    assert sum1["anomalies_detected"] == sum2["anomalies_detected"]

    records = session.execute(select(Anomaly)).scalars().all()
    assert len(records) == 1


def test_unique_constraint(detection_db_session):
    """Test that database enforces uniqueness on (metric_name, date)."""
    session = detection_db_session
    a1 = Anomaly(
        metric_name="order_count",
        date=date(2017, 1, 10),
        expected_value=Decimal("50.0000"),
        actual_value=Decimal("150.0000"),
        z_score=Decimal("4.5000"),
        severity=SEVERITY_MEDIUM,
        status="open",
    )
    a2 = Anomaly(
        metric_name="order_count",
        date=date(2017, 1, 10),
        expected_value=Decimal("60.0000"),
        actual_value=Decimal("160.0000"),
        z_score=Decimal("4.8000"),
        severity=SEVERITY_MEDIUM,
        status="open",
    )
    session.add(a1)
    session.commit()

    session.add(a2)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_no_nan_or_infinite_values(detection_db_session):
    """Test that stored anomalies have valid, finite numerical values."""
    session = detection_db_session
    start_dt = date(2017, 1, 1)

    for i in range(7):
        session.add(
            KPIDaily(
                metric_name="daily_revenue",
                date=start_dt + timedelta(days=i),
                value=Decimal("100.0000") if i % 2 == 0 else Decimal("110.0000"),
                segment="all",
            )
        )
    session.add(
        KPIDaily(
            metric_name="daily_revenue",
            date=start_dt + timedelta(days=7),
            value=Decimal("500.0000"),
            segment="all",
        )
    )
    session.commit()

    detect_anomalies_for_kpis(session)

    anomalies = session.execute(select(Anomaly)).scalars().all()
    assert len(anomalies) > 0
    for a in anomalies:
        for val in (float(a.expected_value), float(a.actual_value), float(a.z_score)):
            assert not math.isnan(val)
            assert not math.isinf(val)
