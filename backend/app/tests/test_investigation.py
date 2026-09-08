"""Deterministic unit tests for Phase 5B investigation evidence tools."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Customer, Order, OrderItem, KPIDaily
from app.kpi.metadata import (
    KPI_DAILY_REVENUE,
    KPI_ORDER_COUNT,
    KPI_AVERAGE_ORDER_VALUE,
    KPI_CANCELLATION_RATE,
    KPI_DELIVERY_DELAY_RATE,
)
from app.investigation import (
    segment_breakdown,
    check_seasonality,
    get_recent_trend,
)


@pytest.fixture
def test_db_session():
    """In-memory SQLite database session isolated per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ==============================================================================
# 1. SEGMENT BREAKDOWN TESTS
# ==============================================================================

def test_segment_breakdown_order_count(test_db_session):
    """Test regional order count breakdown identifies top contributing state."""
    # Setup customers
    c1 = Customer(customer_id="c_sp1", customer_unique_id="u1", customer_zip_code_prefix=1000, customer_city="Sao Paulo", customer_state="SP")
    c2 = Customer(customer_id="c_sp2", customer_unique_id="u2", customer_zip_code_prefix=1000, customer_city="Sao Paulo", customer_state="SP")
    c3 = Customer(customer_id="c_rj1", customer_unique_id="u3", customer_zip_code_prefix=2000, customer_city="Rio", customer_state="RJ")
    test_db_session.add_all([c1, c2, c3])

    # Target date: 2017-11-24 (SP: 2 orders, RJ: 1 order)
    o1 = Order(order_id="o_t1", customer_id="c_sp1", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 24, 10, 0, 0))
    o2 = Order(order_id="o_t2", customer_id="c_sp2", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 24, 11, 0, 0))
    o3 = Order(order_id="o_t3", customer_id="c_rj1", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 24, 12, 0, 0))

    # Baseline date: 2017-11-20 (SP: 1 order, RJ: 1 order)
    o_b1 = Order(order_id="o_b1", customer_id="c_sp1", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 20, 10, 0, 0))
    o_b2 = Order(order_id="o_b2", customer_id="c_rj1", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 20, 12, 0, 0))
    test_db_session.add_all([o1, o2, o3, o_b1, o_b2])
    test_db_session.commit()

    res = segment_breakdown(KPI_ORDER_COUNT, "2017-11-24", session=test_db_session, baseline_days=7)

    assert res.status == "success"
    assert res.metric_name == KPI_ORDER_COUNT
    assert res.total_actual == Decimal("3.0000")
    # 2 baseline orders over 1 active baseline day = 2.0 total baseline
    assert res.total_baseline == Decimal("2.0000")
    assert res.total_delta == Decimal("1.0000")

    assert res.top_contributor is not None
    assert res.top_contributor.segment == "SP"
    # SP actual 2, base 1 -> delta +1.0
    assert res.top_contributor.absolute_delta == Decimal("1.0000")
    assert res.top_contributor.percentage_contribution == Decimal("100.00")
    assert res.top_contributor.share_of_total == Decimal("66.67")


def test_segment_breakdown_daily_revenue(test_db_session):
    """Test revenue breakdown correctly filters out canceled and unavailable orders."""
    c_sp = Customer(customer_id="c_sp", customer_unique_id="u1", customer_zip_code_prefix=1000, customer_city="SP", customer_state="SP")
    c_rj = Customer(customer_id="c_rj", customer_unique_id="u2", customer_zip_code_prefix=2000, customer_city="RJ", customer_state="RJ")
    test_db_session.add_all([c_sp, c_rj])

    # Target date orders: SP delivered R$ 100, SP canceled R$ 500 (excluded), RJ delivered R$ 50
    o_sp_del = Order(order_id="o_sp_del", customer_id="c_sp", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 24, 10, 0, 0))
    o_sp_canc = Order(order_id="o_sp_canc", customer_id="c_sp", order_status="canceled", order_purchase_timestamp=datetime(2017, 11, 24, 10, 0, 0))
    o_rj_del = Order(order_id="o_rj_del", customer_id="c_rj", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 24, 10, 0, 0))

    item1 = OrderItem(order_id="o_sp_del", order_item_id=1, product_id="p1", seller_id="s1", shipping_limit_date=datetime(2017, 11, 28), price=Decimal("100.00"), freight_value=Decimal("10.00"))
    item2 = OrderItem(order_id="o_sp_canc", order_item_id=1, product_id="p1", seller_id="s1", shipping_limit_date=datetime(2017, 11, 28), price=Decimal("500.00"), freight_value=Decimal("10.00"))
    item3 = OrderItem(order_id="o_rj_del", order_item_id=1, product_id="p1", seller_id="s1", shipping_limit_date=datetime(2017, 11, 28), price=Decimal("50.00"), freight_value=Decimal("10.00"))
    test_db_session.add_all([o_sp_del, o_sp_canc, o_rj_del, item1, item2, item3])
    test_db_session.commit()

    res = segment_breakdown(KPI_DAILY_REVENUE, "2017-11-24", session=test_db_session)
    assert res.status == "success"
    # Total revenue should be 150.00 (canceled 500 excluded)
    assert res.total_actual == Decimal("150.0000")
    assert res.top_contributor.segment == "SP"
    assert res.top_contributor.actual_value == Decimal("100.0000")


def test_segment_breakdown_cancellation_rate(test_db_session):
    """Test cancellation rate breakdown across regions."""
    c_sp = Customer(customer_id="c_sp", customer_unique_id="u1", customer_zip_code_prefix=1000, customer_city="SP", customer_state="SP")
    c_rj = Customer(customer_id="c_rj", customer_unique_id="u2", customer_zip_code_prefix=2000, customer_city="RJ", customer_state="RJ")
    test_db_session.add_all([c_sp, c_rj])

    # SP: 1 delivered, 1 canceled (cancel rate = 0.50)
    # RJ: 2 delivered, 0 canceled (cancel rate = 0.00)
    o1 = Order(order_id="o1", customer_id="c_sp", order_status="delivered", order_purchase_timestamp=datetime(2018, 8, 30, 10, 0, 0))
    o2 = Order(order_id="o2", customer_id="c_sp", order_status="canceled", order_purchase_timestamp=datetime(2018, 8, 30, 11, 0, 0))
    o3 = Order(order_id="o3", customer_id="c_rj", order_status="delivered", order_purchase_timestamp=datetime(2018, 8, 30, 10, 0, 0))
    o4 = Order(order_id="o4", customer_id="c_rj", order_status="delivered", order_purchase_timestamp=datetime(2018, 8, 30, 11, 0, 0))
    test_db_session.add_all([o1, o2, o3, o4])
    test_db_session.commit()

    res = segment_breakdown(KPI_CANCELLATION_RATE, "2018-08-30", session=test_db_session)
    assert res.status == "success"
    sp_seg = next(s for s in res.segments if s.segment == "SP")
    rj_seg = next(s for s in res.segments if s.segment == "RJ")
    assert sp_seg.actual_value == Decimal("0.5000")
    assert rj_seg.actual_value == Decimal("0.0000")
    assert res.top_contributor.segment == "SP"


def test_segment_breakdown_invalid_inputs(test_db_session):
    """Test validation errors for invalid metric or date string."""
    with pytest.raises(ValueError, match="Unsupported metric"):
        segment_breakdown("non_existent_kpi", "2017-11-24", session=test_db_session)

    with pytest.raises(ValueError, match="Invalid date format"):
        segment_breakdown(KPI_ORDER_COUNT, "24-11-2017", session=test_db_session)


def test_segment_breakdown_empty_date(test_db_session):
    """Test safe handling when no observations exist on target date."""
    res = segment_breakdown(KPI_ORDER_COUNT, "2020-01-01", session=test_db_session)
    assert res.status == "insufficient_data"
    assert res.total_actual == Decimal("0.0")
    assert len(res.segments) == 0
    assert res.top_contributor is None


# ==============================================================================
# 2. CHECK SEASONALITY TESTS
# ==============================================================================

def test_check_seasonality_expected_pattern(test_db_session):
    """Test that regular day-of-week fluctuations are classified as seasonal."""
    target_dt = date(2017, 11, 17)  # Friday

    # Populate preceding Fridays with values ~100 (std: ~5)
    for w in range(1, 6):
        past_friday = target_dt - timedelta(weeks=w)
        test_db_session.add(
            KPIDaily(metric_name=KPI_ORDER_COUNT, date=past_friday, value=Decimal(str(100 + (w % 3))), segment="all")
        )
    # Target Friday has normal value: 102
    test_db_session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("102.0000"), segment="all")
    )
    test_db_session.commit()

    res = check_seasonality(KPI_ORDER_COUNT, target_dt, session=test_db_session)
    assert res.status == "success"
    assert res.day_of_week_name == "Friday"
    assert res.target_value == Decimal("102.0000")
    assert res.is_seasonal is True  # Low z-score relative to Friday baseline
    assert abs(res.same_dow_zscore) < Decimal("2.0")


def test_check_seasonality_anomalous_day(test_db_session):
    """Test that a true anomaly produces is_seasonal = False and high z-score."""
    target_dt = date(2017, 11, 24)  # Black Friday

    # Preceding Fridays average ~100
    for w in range(1, 6):
        past_friday = target_dt - timedelta(weeks=w)
        test_db_session.add(
            KPIDaily(metric_name=KPI_ORDER_COUNT, date=past_friday, value=Decimal("100.0000"), segment="all")
        )
    # Target Friday spikes to 800
    test_db_session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("800.0000"), segment="all")
    )
    test_db_session.commit()

    res = check_seasonality(KPI_ORDER_COUNT, target_dt, session=test_db_session)
    assert res.status == "success"
    assert res.day_of_week_name == "Friday"
    assert res.target_value == Decimal("800.0000")
    assert res.is_seasonal is False  # Extremely anomalous for a Friday
    assert "not explained by typical weekly seasonality" in res.summary


def test_check_seasonality_insufficient_history(test_db_session):
    """Test safe handling when no prior same-DOW history exists."""
    target_dt = date(2017, 1, 6)
    test_db_session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("50.0000"), segment="all")
    )
    test_db_session.commit()

    res = check_seasonality(KPI_ORDER_COUNT, target_dt, session=test_db_session)
    assert res.status == "insufficient_data"
    assert res.is_seasonal is False
    assert res.sample_size == 0


def test_check_seasonality_zero_variance_protection(test_db_session):
    """Test that zero variance across historical observations does not crash with division by zero."""
    target_dt = date(2017, 11, 17)
    for w in range(1, 4):
        past_friday = target_dt - timedelta(weeks=w)
        test_db_session.add(
            KPIDaily(metric_name=KPI_ORDER_COUNT, date=past_friday, value=Decimal("100.0000"), segment="all")
        )
    test_db_session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("100.0000"), segment="all")
    )
    test_db_session.commit()

    res = check_seasonality(KPI_ORDER_COUNT, target_dt, session=test_db_session)
    assert res.status == "success"
    assert res.same_dow_std == Decimal("0.0000")
    assert res.same_dow_zscore == Decimal("0.0000")
    assert res.is_seasonal is True


# ==============================================================================
# 3. GET RECENT TREND TESTS
# ==============================================================================

def test_get_recent_trend_sudden_jump(test_db_session):
    """Test that a sharp single-day spike following a stable baseline is classified as 'sudden'."""
    target_dt = date(2017, 11, 24)

    # 13 stable baseline days around 100
    for d in range(13, 0, -1):
        test_db_session.add(
            KPIDaily(
                metric_name=KPI_ORDER_COUNT,
                date=target_dt - timedelta(days=d),
                value=Decimal(str(100 + (d % 3))),
                segment="all",
            )
        )
    # Day 14: Sudden spike to 500
    test_db_session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("500.0000"), segment="all")
    )
    test_db_session.commit()

    res = get_recent_trend(KPI_ORDER_COUNT, target_dt, window_days=14, session=test_db_session)
    assert res.status == "success"
    assert res.classification == "sudden"
    assert res.observations_count == 14
    assert res.target_value == Decimal("500.0000")
    assert res.single_day_delta > Decimal("300.0")


def test_get_recent_trend_gradual_deterioration(test_db_session):
    """Test that a steady multi-day worsening is classified as 'gradual_deterioration'."""
    target_dt = date(2018, 8, 30)

    # Cancellation rate steadily deteriorating over 7 days: 0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10
    rates = [Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.04"), Decimal("0.06"), Decimal("0.08"), Decimal("0.10")]
    for idx, r in enumerate(rates):
        d_offset = len(rates) - 1 - idx
        test_db_session.add(
            KPIDaily(
                metric_name=KPI_CANCELLATION_RATE,
                date=target_dt - timedelta(days=d_offset),
                value=r,
                segment="all",
            )
        )
    test_db_session.commit()

    res = get_recent_trend(KPI_CANCELLATION_RATE, target_dt, window_days=7, session=test_db_session)
    assert res.status == "success"
    assert res.classification == "gradual_deterioration"
    assert res.preceding_trend_slope > Decimal("0.0")


def test_get_recent_trend_gradual_improvement(test_db_session):
    """Test that a steady multi-day positive climb is classified as 'gradual_improvement'."""
    target_dt = date(2017, 10, 10)

    # Revenue steadily climbing over 6 days: 100, 110, 120, 130, 140, 150
    revs = [Decimal("100"), Decimal("110"), Decimal("120"), Decimal("130"), Decimal("140"), Decimal("150")]
    for idx, r in enumerate(revs):
        d_offset = len(revs) - 1 - idx
        test_db_session.add(
            KPIDaily(
                metric_name=KPI_DAILY_REVENUE,
                date=target_dt - timedelta(days=d_offset),
                value=r,
                segment="all",
            )
        )
    test_db_session.commit()

    res = get_recent_trend(KPI_DAILY_REVENUE, target_dt, window_days=6, session=test_db_session)
    assert res.status == "success"
    assert res.classification == "gradual_improvement"
    assert res.preceding_trend_slope > Decimal("0.0")


def test_get_recent_trend_insufficient_data(test_db_session):
    """Test safe handling when fewer than 3 observations exist in window."""
    target_dt = date(2017, 1, 2)
    test_db_session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("10.0000"), segment="all")
    )
    test_db_session.commit()

    res = get_recent_trend(KPI_ORDER_COUNT, target_dt, window_days=14, session=test_db_session)
    assert res.status == "insufficient_data"
    assert res.classification == "insufficient_data"
    assert res.observations_count == 1


def test_get_recent_trend_invalid_inputs(test_db_session):
    """Test validation errors for invalid window_days or metric."""
    with pytest.raises(ValueError, match="window_days must be at least 3"):
        get_recent_trend(KPI_ORDER_COUNT, "2017-11-24", window_days=2, session=test_db_session)

    with pytest.raises(ValueError, match="Unsupported metric"):
        get_recent_trend("unknown_metric", "2017-11-24", session=test_db_session)


# ==============================================================================
# 4. SERIALIZATION AND EVIDENCE CONTRACT TESTS
# ==============================================================================

def test_evidence_contract_serialization(test_db_session):
    """Verify that all evidence results serialize cleanly to JSON-compatible dictionaries."""
    target_dt = date(2017, 11, 24)

    # Setup simple data
    c = Customer(customer_id="c1", customer_unique_id="u1", customer_zip_code_prefix=1000, customer_city="SP", customer_state="SP")
    o = Order(order_id="o1", customer_id="c1", order_status="delivered", order_purchase_timestamp=datetime(2017, 11, 24, 10, 0, 0))
    test_db_session.add_all([c, o])

    for i in range(5):
        test_db_session.add(
            KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt - timedelta(days=i), value=Decimal("10.0"), segment="all")
        )
    test_db_session.commit()

    # 1. Segment breakdown serialization
    res_seg = segment_breakdown(KPI_ORDER_COUNT, target_dt, session=test_db_session)
    d_seg = res_seg.to_dict()
    assert isinstance(d_seg, dict)
    assert d_seg["tool_name"] == "segment_breakdown"
    assert isinstance(d_seg["total_actual"], float)
    assert isinstance(d_seg["date"], str)
    assert isinstance(d_seg["segments"], list)

    # 2. Seasonality serialization
    res_sea = check_seasonality(KPI_ORDER_COUNT, target_dt, session=test_db_session)
    d_sea = res_sea.to_dict()
    assert isinstance(d_sea, dict)
    assert d_sea["tool_name"] == "check_seasonality"
    assert isinstance(d_sea["target_value"], float)

    # 3. Recent trend serialization
    res_tr = get_recent_trend(KPI_ORDER_COUNT, target_dt, window_days=5, session=test_db_session)
    d_tr = res_tr.to_dict()
    assert isinstance(d_tr, dict)
    assert d_tr["tool_name"] == "get_recent_trend"
    assert isinstance(d_tr["history"], list)
    assert len(d_tr["history"]) == 5
