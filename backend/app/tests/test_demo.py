"""Deterministic unit tests for Phase 5E end-to-end investigation demo."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    Customer,
    Order,
    KPIDaily,
    Anomaly,
)
from app.kpi.metadata import KPI_ORDER_COUNT
from app.demo import run_demo, get_default_anomaly


@pytest.fixture
def test_db_session():
    """Isolated in-memory SQLite database session for demo tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def populated_demo_scenario(test_db_session):
    """Sets up a complete realistic anomaly scenario with historical KPIs and orders."""
    session = test_db_session
    target_dt = date(2017, 11, 24)

    # Customers
    c1 = Customer(
        customer_id="cust_demo_sp",
        customer_unique_id="u1",
        customer_zip_code_prefix=1000,
        customer_city="Sao Paulo",
        customer_state="SP",
    )
    session.add(c1)

    # 14 historical baseline days
    for day_offset in range(14, 0, -1):
        hist_dt = target_dt - timedelta(days=day_offset)
        session.add(
            Order(
                order_id=f"ord_demo_base_{day_offset}",
                customer_id="cust_demo_sp",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(hist_dt, datetime.min.time()),
            )
        )
        session.add(
            KPIDaily(
                metric_name=KPI_ORDER_COUNT,
                date=hist_dt,
                value=Decimal(str(100 + (day_offset % 3))),
                segment="all",
            )
        )

    # Target date orders (10 orders in SP)
    for i in range(10):
        session.add(
            Order(
                order_id=f"ord_demo_target_{i}",
                customer_id="cust_demo_sp",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(target_dt, datetime.min.time()),
            )
        )

    # Target KPI and Anomaly
    session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("1100.0000"), segment="all")
    )
    anomaly = Anomaly(
        metric_name=KPI_ORDER_COUNT,
        date=target_dt,
        expected_value=Decimal("101.0000"),
        actual_value=Decimal("1100.0000"),
        z_score=Decimal("30.2000"),
        severity="high",
        status="open",
        created_at=datetime.utcnow(),
    )
    session.add(anomaly)
    session.commit()

    return anomaly


def test_demo_run_default_anomaly(test_db_session, populated_demo_scenario):
    """Verify demo automatically resolves strongest anomaly and runs pipeline."""
    anomaly = populated_demo_scenario
    conclusion = run_demo(session=test_db_session)

    assert conclusion is not None
    assert conclusion.anomaly_id == anomaly.id
    assert conclusion.validation_passed is True
    assert conclusion.confidence in ("high", "medium")
    assert len(conclusion.evidence_references) == 3


def test_demo_run_specific_anomaly_id(test_db_session, populated_demo_scenario):
    """Verify demo executes properly for explicit anomaly ID."""
    anomaly = populated_demo_scenario
    conclusion = run_demo(anomaly_id=anomaly.id, session=test_db_session)

    assert conclusion.anomaly_id == anomaly.id
    assert conclusion.validation_passed is True


def test_demo_run_with_metric_filter(test_db_session, populated_demo_scenario):
    """Verify demo resolves strongest anomaly filtered by metric name."""
    anomaly = populated_demo_scenario
    conclusion = run_demo(metric_name=KPI_ORDER_COUNT, session=test_db_session)

    assert conclusion.anomaly_id == anomaly.id


def test_demo_run_as_json(test_db_session, populated_demo_scenario, capsys):
    """Verify demo JSON mode outputs parseable structured JSON to stdout."""
    anomaly = populated_demo_scenario
    conclusion = run_demo(anomaly_id=anomaly.id, as_json=True, session=test_db_session)

    captured = capsys.readouterr()
    assert len(captured.out) > 0
    parsed = json.loads(captured.out)
    assert parsed["pipeline"] == "PicketIQ End-to-End Investigation Demo"
    assert parsed["anomaly"]["anomaly_id"] == anomaly.id
    assert parsed["conclusion"]["validation_passed"] is True


def test_demo_empty_database_error(test_db_session):
    """Verify RuntimeError when running demo on database with no anomalies."""
    with pytest.raises(RuntimeError) as exc_info:
        run_demo(session=test_db_session)
    assert "No anomalies found" in str(exc_info.value)


def test_demo_invalid_anomaly_id_error(test_db_session, populated_demo_scenario):
    """Verify ValueError when given non-existent anomaly ID."""
    with pytest.raises(ValueError) as exc_info:
        run_demo(anomaly_id=999999, session=test_db_session)
    assert "999999" in str(exc_info.value)
