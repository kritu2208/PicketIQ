"""Deterministic unit tests for KPI computation and daily analytical data layer."""

from datetime import datetime, date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.session import Base
from app.db.models import Customer, Seller, Product, Order, OrderItem, KPIDaily
from app.kpi.compute_kpis import (
    compute_kpis_for_range,
    KPI_DAILY_REVENUE,
    KPI_ORDER_COUNT,
    KPI_AVERAGE_ORDER_VALUE,
    KPI_CANCELLATION_RATE,
    KPI_DELIVERY_DELAY_RATE,
)
from app.kpi.metadata import KPI_REGISTRY, get_kpi_metadata


@pytest.fixture
def kpi_db_session():
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


@pytest.fixture
def populated_kpi_session(kpi_db_session):
    """Populates deterministic test orders and items with realistic edge cases across multiple dates."""
    session = kpi_db_session

    # Base dimensional entities
    customer = Customer(
        customer_id="cust_1",
        customer_unique_id="uniq_1",
        customer_zip_code_prefix=10000,
        customer_city="Sao Paulo",
        customer_state="SP",
    )
    seller = Seller(
        seller_id="seller_1",
        seller_zip_code_prefix=20000,
        seller_city="Rio de Janeiro",
        seller_state="RJ",
    )
    product_a = Product(product_id="prod_a", product_category_name="electronics")
    product_b = Product(product_id="prod_b", product_category_name="home")
    session.add_all([customer, seller, product_a, product_b])
    session.flush()

    # --- Day 1: 2017-10-01 ---
    # o1: delivered on time (2017-10-08 <= 2017-10-10). Two items (50.00 each)
    o1 = Order(
        order_id="o1",
        customer_id="cust_1",
        order_status="delivered",
        order_purchase_timestamp=datetime(2017, 10, 1, 10, 0, 0),
        order_delivered_customer_date=datetime(2017, 10, 8, 12, 0, 0),
        order_estimated_delivery_date=datetime(2017, 10, 10, 0, 0, 0),
    )
    o1_i1 = OrderItem(
        order_id="o1",
        order_item_id=1,
        product_id="prod_a",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 5, 0, 0, 0),
        price=Decimal("50.00"),
        freight_value=Decimal("10.00"),
    )
    o1_i2 = OrderItem(
        order_id="o1",
        order_item_id=2,
        product_id="prod_b",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 5, 0, 0, 0),
        price=Decimal("50.00"),
        freight_value=Decimal("10.00"),
    )

    # o2: delivered delayed (2017-10-15 > 2017-10-12). One item (150.00)
    o2 = Order(
        order_id="o2",
        customer_id="cust_1",
        order_status="delivered",
        order_purchase_timestamp=datetime(2017, 10, 1, 14, 0, 0),
        order_delivered_customer_date=datetime(2017, 10, 15, 12, 0, 0),
        order_estimated_delivery_date=datetime(2017, 10, 12, 0, 0, 0),
    )
    o2_i1 = OrderItem(
        order_id="o2",
        order_item_id=1,
        product_id="prod_a",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 5, 0, 0, 0),
        price=Decimal("150.00"),
        freight_value=Decimal("15.00"),
    )

    # o3: canceled order. One item (200.00) - MUST be excluded from revenue
    o3 = Order(
        order_id="o3",
        customer_id="cust_1",
        order_status="canceled",
        order_purchase_timestamp=datetime(2017, 10, 1, 18, 0, 0),
        order_delivered_customer_date=None,
        order_estimated_delivery_date=datetime(2017, 10, 10, 0, 0, 0),
    )
    o3_i1 = OrderItem(
        order_id="o3",
        order_item_id=1,
        product_id="prod_a",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 5, 0, 0, 0),
        price=Decimal("200.00"),
        freight_value=Decimal("20.00"),
    )

    # o4: unavailable order. One item (300.00) - MUST be excluded from revenue
    o4 = Order(
        order_id="o4",
        customer_id="cust_1",
        order_status="unavailable",
        order_purchase_timestamp=datetime(2017, 10, 1, 20, 0, 0),
        order_delivered_customer_date=None,
        order_estimated_delivery_date=datetime(2017, 10, 10, 0, 0, 0),
    )
    o4_i1 = OrderItem(
        order_id="o4",
        order_item_id=1,
        product_id="prod_b",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 5, 0, 0, 0),
        price=Decimal("300.00"),
        freight_value=Decimal("30.00"),
    )

    # --- Day 2: 2017-10-02 ---
    # o5: delivered on time (2017-10-06 <= 2017-10-08). Price 80.00
    o5 = Order(
        order_id="o5",
        customer_id="cust_1",
        order_status="delivered",
        order_purchase_timestamp=datetime(2017, 10, 2, 9, 0, 0),
        order_delivered_customer_date=datetime(2017, 10, 6, 12, 0, 0),
        order_estimated_delivery_date=datetime(2017, 10, 8, 0, 0, 0),
    )
    o5_i1 = OrderItem(
        order_id="o5",
        order_item_id=1,
        product_id="prod_a",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 6, 0, 0, 0),
        price=Decimal("80.00"),
        freight_value=Decimal("12.00"),
    )

    # o6: delivered but MISSING customer delivery date. Price 120.00
    o6 = Order(
        order_id="o6",
        customer_id="cust_1",
        order_status="delivered",
        order_purchase_timestamp=datetime(2017, 10, 2, 11, 0, 0),
        order_delivered_customer_date=None,
        order_estimated_delivery_date=datetime(2017, 10, 9, 0, 0, 0),
    )
    o6_i1 = OrderItem(
        order_id="o6",
        order_item_id=1,
        product_id="prod_b",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 6, 0, 0, 0),
        price=Decimal("120.00"),
        freight_value=Decimal("15.00"),
    )

    # --- Day 3: 2017-10-03 (Edge Case: Only canceled order) ---
    o7 = Order(
        order_id="o7",
        customer_id="cust_1",
        order_status="canceled",
        order_purchase_timestamp=datetime(2017, 10, 3, 15, 0, 0),
        order_delivered_customer_date=None,
        order_estimated_delivery_date=datetime(2017, 10, 10, 0, 0, 0),
    )
    o7_i1 = OrderItem(
        order_id="o7",
        order_item_id=1,
        product_id="prod_a",
        seller_id="seller_1",
        shipping_limit_date=datetime(2017, 10, 7, 0, 0, 0),
        price=Decimal("500.00"),
        freight_value=Decimal("50.00"),
    )

    session.add_all([
        o1, o1_i1, o1_i2,
        o2, o2_i1,
        o3, o3_i1,
        o4, o4_i1,
        o5, o5_i1,
        o6, o6_i1,
        o7, o7_i1,
    ])
    session.commit()
    return session


def get_kpi_value(session, metric_name: str, kpi_date: date) -> Decimal:
    """Helper to fetch a specific KPI metric value on a given date."""
    return session.execute(
        select(KPIDaily.value).where(
            KPIDaily.metric_name == metric_name,
            KPIDaily.date == kpi_date,
            KPIDaily.segment == "all",
        )
    ).scalar_one()


def test_daily_revenue_calculation(populated_kpi_session):
    """Test daily_revenue correctly sums items price and excludes freight."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 1: o1 (50 + 50) + o2 (150) = 250.0000 (freight ignored, o3 & o4 excluded)
    day1_rev = get_kpi_value(populated_kpi_session, KPI_DAILY_REVENUE, date(2017, 10, 1))
    assert day1_rev == Decimal("250.0000")

    # Day 2: o5 (80) + o6 (120) = 200.0000
    day2_rev = get_kpi_value(populated_kpi_session, KPI_DAILY_REVENUE, date(2017, 10, 2))
    assert day2_rev == Decimal("200.0000")


def test_order_count(populated_kpi_session):
    """Test order_count includes all orders placed on the purchase date regardless of status."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 1: o1, o2, o3, o4 = 4 total
    day1_count = get_kpi_value(populated_kpi_session, KPI_ORDER_COUNT, date(2017, 10, 1))
    assert day1_count == Decimal("4.0000")

    # Day 2: o5, o6 = 2 total
    day2_count = get_kpi_value(populated_kpi_session, KPI_ORDER_COUNT, date(2017, 10, 2))
    assert day2_count == Decimal("2.0000")

    # Day 3: o7 = 1 total
    day3_count = get_kpi_value(populated_kpi_session, KPI_ORDER_COUNT, date(2017, 10, 3))
    assert day3_count == Decimal("1.0000")


def test_average_order_value(populated_kpi_session):
    """Test average_order_value = daily_revenue / revenue_eligible_orders."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 1: 250.00 / 2 eligible orders (o1, o2) = 125.0000
    day1_aov = get_kpi_value(populated_kpi_session, KPI_AVERAGE_ORDER_VALUE, date(2017, 10, 1))
    assert day1_aov == Decimal("125.0000")

    # Day 2: 200.00 / 2 eligible orders (o5, o6) = 100.0000
    day2_aov = get_kpi_value(populated_kpi_session, KPI_AVERAGE_ORDER_VALUE, date(2017, 10, 2))
    assert day2_aov == Decimal("100.0000")


def test_cancellation_rate(populated_kpi_session):
    """Test cancellation_rate = canceled_orders / total_orders as a ratio between 0 and 1."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 1: 1 canceled (o3) / 4 total = 0.2500
    day1_cancel = get_kpi_value(populated_kpi_session, KPI_CANCELLATION_RATE, date(2017, 10, 1))
    assert day1_cancel == Decimal("0.2500")

    # Day 2: 0 canceled / 2 total = 0.0000
    day2_cancel = get_kpi_value(populated_kpi_session, KPI_CANCELLATION_RATE, date(2017, 10, 2))
    assert day2_cancel == Decimal("0.0000")

    # Day 3: 1 canceled (o7) / 1 total = 1.0000
    day3_cancel = get_kpi_value(populated_kpi_session, KPI_CANCELLATION_RATE, date(2017, 10, 3))
    assert day3_cancel == Decimal("1.0000")


def test_delivery_delay_rate(populated_kpi_session):
    """Test delivery_delay_rate = delayed_orders / delivered_orders_with_valid_dates."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 1: o1 on-time, o2 delayed (15 > 12). 1 delayed / 2 delivered with dates = 0.5000
    day1_delay = get_kpi_value(populated_kpi_session, KPI_DELIVERY_DELAY_RATE, date(2017, 10, 1))
    assert day1_delay == Decimal("0.5000")


def test_cancelled_and_unavailable_revenue_exclusion(populated_kpi_session):
    """Test specifically that cancelled and unavailable orders do not add to daily_revenue."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 3 has only a canceled order with price 500.00. Revenue must be 0.0000.
    day3_rev = get_kpi_value(populated_kpi_session, KPI_DAILY_REVENUE, date(2017, 10, 3))
    assert day3_rev == Decimal("0.0000")


def test_missing_delivery_dates_handling(populated_kpi_session):
    """Test that orders with null delivery timestamps are excluded from the delivery delay rate denominator."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 2: o5 has valid dates (on time), o6 is missing actual delivery date.
    # Denominator must be 1 (only o5), delayed is 0. Result: 0 / 1 = 0.0000.
    day2_delay = get_kpi_value(populated_kpi_session, KPI_DELIVERY_DELAY_RATE, date(2017, 10, 2))
    assert day2_delay == Decimal("0.0000")


def test_zero_denominator_handling(populated_kpi_session):
    """Test that dates with 0 eligible or delivered orders produce 0.0000 without division by zero."""
    compute_kpis_for_range(populated_kpi_session)

    # Day 3 has 0 revenue-eligible orders and 0 delivered orders
    day3_aov = get_kpi_value(populated_kpi_session, KPI_AVERAGE_ORDER_VALUE, date(2017, 10, 3))
    assert day3_aov == Decimal("0.0000")

    day3_delay = get_kpi_value(populated_kpi_session, KPI_DELIVERY_DELAY_RATE, date(2017, 10, 3))
    assert day3_delay == Decimal("0.0000")


def test_date_filtering(populated_kpi_session):
    """Test that specifying start_date and end_date restricts computation to the specified window."""
    # Compute ONLY for Day 2 (2017-10-02)
    summary = compute_kpis_for_range(
        populated_kpi_session,
        start_date=date(2017, 10, 2),
        end_date=date(2017, 10, 2),
    )
    assert summary["dates_processed"] == 1
    assert summary["records_written"] == 5

    records = populated_kpi_session.execute(select(KPIDaily)).scalars().all()
    assert len(records) == 5
    for rec in records:
        assert rec.date == date(2017, 10, 2)


def test_kpi_idempotency(populated_kpi_session):
    """Test that running KPI computation multiple times does not duplicate records or fail."""
    summary1 = compute_kpis_for_range(populated_kpi_session)
    summary2 = compute_kpis_for_range(populated_kpi_session)

    assert summary1["records_written"] == summary2["records_written"]

    total_records = len(populated_kpi_session.execute(select(KPIDaily)).scalars().all())
    # 3 dates * 5 KPIs = 15 records exactly
    assert total_records == 15


def test_unique_constraint_enforcement(kpi_db_session):
    """Test that database enforces uniqueness on (metric_name, date, segment)."""
    rec1 = KPIDaily(
        metric_name=KPI_DAILY_REVENUE,
        date=date(2017, 10, 1),
        value=Decimal("100.0000"),
        segment="all",
    )
    rec2 = KPIDaily(
        metric_name=KPI_DAILY_REVENUE,
        date=date(2017, 10, 1),
        value=Decimal("200.0000"),
        segment="all",
    )
    kpi_db_session.add(rec1)
    kpi_db_session.commit()

    kpi_db_session.add(rec2)
    with pytest.raises(IntegrityError):
        kpi_db_session.commit()
    kpi_db_session.rollback()


def test_invalid_date_range_validation(populated_kpi_session):
    """Test that start_date > end_date raises ValueError."""
    with pytest.raises(ValueError) as exc:
        compute_kpis_for_range(
            populated_kpi_session,
            start_date=date(2017, 10, 10),
            end_date=date(2017, 10, 5),
        )
    assert "start_date" in str(exc.value)
    assert "cannot be after end_date" in str(exc.value)


def test_empty_database_handling(kpi_db_session):
    """Test that computing KPIs on an empty database does not invent dates or crash."""
    summary = compute_kpis_for_range(kpi_db_session)
    assert summary["dates_processed"] == 0
    assert summary["records_written"] == 0


def test_metadata_registry():
    """Test that KPI metadata registry contains all core metrics with complete documentation."""
    for metric_name in [
        KPI_DAILY_REVENUE,
        KPI_ORDER_COUNT,
        KPI_AVERAGE_ORDER_VALUE,
        KPI_CANCELLATION_RATE,
        KPI_DELIVERY_DELAY_RATE,
    ]:
        meta = get_kpi_metadata(metric_name)
        assert meta is not None
        assert meta.name == metric_name
        assert meta.description != ""
        assert len(meta.source_tables) > 0
        assert meta.date_attribution_rule != ""
        assert meta.unit in ("currency_brl", "count", "ratio")
