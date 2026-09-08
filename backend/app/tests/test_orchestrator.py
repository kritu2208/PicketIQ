"""Deterministic unit tests for Phase 5C Investigation Orchestrator."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    Customer,
    Order,
    OrderItem,
    KPIDaily,
    Anomaly,
    Investigation,
    InvestigationEvidence,
)
from app.kpi.metadata import KPI_ORDER_COUNT
from app.investigation import (
    investigate_anomaly,
    InvestigationOrchestrator,
    AnomalyNotFoundError,
)


@pytest.fixture
def test_db_session():
    """Isolated in-memory SQLite database session for orchestrator tests."""
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
def populated_anomaly_data(test_db_session):
    """Sets up a complete realistic anomaly scenario with historical KPIs and operational orders."""
    session = test_db_session
    target_dt = date(2017, 11, 24)

    # 1. Customers
    c1 = Customer(
        customer_id="cust_sp_1",
        customer_unique_id="u1",
        customer_zip_code_prefix=1000,
        customer_city="Sao Paulo",
        customer_state="SP",
    )
    c2 = Customer(
        customer_id="cust_rj_1",
        customer_unique_id="u2",
        customer_zip_code_prefix=2000,
        customer_city="Rio de Janeiro",
        customer_state="RJ",
    )
    session.add_all([c1, c2])

    # 2. Historical baseline orders (preceding 14 days)
    for day_offset in range(14, 0, -1):
        hist_dt = target_dt - timedelta(days=day_offset)
        # SP order
        session.add(
            Order(
                order_id=f"ord_base_sp_{day_offset}",
                customer_id="cust_sp_1",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(hist_dt, datetime.min.time()),
            )
        )
        # Daily KPI record
        session.add(
            KPIDaily(
                metric_name=KPI_ORDER_COUNT,
                date=hist_dt,
                value=Decimal(str(100 + (day_offset % 5))),
                segment="all",
            )
        )

    # 3. Target date orders (SP: 8 orders, RJ: 2 orders -> total 10)
    for i in range(8):
        session.add(
            Order(
                order_id=f"ord_target_sp_{i}",
                customer_id="cust_sp_1",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(target_dt, datetime.min.time()),
            )
        )
    for i in range(2):
        session.add(
            Order(
                order_id=f"ord_target_rj_{i}",
                customer_id="cust_rj_1",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(target_dt, datetime.min.time()),
            )
        )

    # 4. Target date KPI observation
    session.add(
        KPIDaily(
            metric_name=KPI_ORDER_COUNT,
            date=target_dt,
            value=Decimal("850.0000"),
            segment="all",
        )
    )

    # 5. Detected Anomaly record
    anomaly = Anomaly(
        metric_name=KPI_ORDER_COUNT,
        date=target_dt,
        expected_value=Decimal("102.0000"),
        actual_value=Decimal("850.0000"),
        z_score=Decimal("25.5000"),
        severity="high",
        status="open",
        created_at=datetime.utcnow(),
    )
    session.add(anomaly)
    session.commit()

    return anomaly


# ==============================================================================
# 1. SUCCESSFUL ORCHESTRATION TESTS
# ==============================================================================

def test_investigate_anomaly_success(test_db_session, populated_anomaly_data):
    """Verify end-to-end deterministic coordination of all 3 evidence tools."""
    anomaly = populated_anomaly_data
    result = investigate_anomaly(anomaly.id, session=test_db_session)

    assert result.status == "completed"
    assert result.steps_executed == 3
    assert result.investigation_id > 0
    assert result.anomaly.anomaly_id == anomaly.id
    assert result.anomaly.metric_name == KPI_ORDER_COUNT
    assert result.anomaly.date == anomaly.date
    assert result.anomaly.actual_value == Decimal("850.0000")

    # Step sequence and tool verification
    assert len(result.evidence) == 3
    assert [e.step_number for e in result.evidence] == [1, 2, 3]
    assert [e.tool_name for e in result.evidence] == [
        "segment_breakdown",
        "check_seasonality",
        "get_recent_trend",
    ]
    for ev in result.evidence:
        assert ev.status in ("success", "insufficient_data")
        assert len(ev.summary) > 0
        assert isinstance(ev.input_parameters, dict)
        assert isinstance(ev.output_data, dict)

    # Typed tool result contracts
    assert result.breakdown is not None
    assert result.breakdown.tool_name == "segment_breakdown"
    assert result.breakdown.top_contributor.segment == "SP"

    assert result.seasonality is not None
    assert result.seasonality.tool_name == "check_seasonality"
    assert result.seasonality.day_of_week_name == "Friday"

    assert result.recent_trend is not None
    assert result.recent_trend.tool_name == "get_recent_trend"
    assert result.recent_trend.classification == "sudden"

    # Factual synthesis summary
    assert "Investigation for anomaly #" in result.summary
    assert "Step 1 (segment_breakdown)" in result.summary
    assert "Step 2 (check_seasonality)" in result.summary
    assert "Step 3 (get_recent_trend)" in result.summary


def test_orchestrator_class_wrapper(test_db_session, populated_anomaly_data):
    """Verify InvestigationOrchestrator class wrapper produces equivalent results."""
    anomaly = populated_anomaly_data
    orchestrator = InvestigationOrchestrator(session=test_db_session)
    result = orchestrator.investigate(anomaly.id)

    assert result.status == "completed"
    assert result.anomaly.anomaly_id == anomaly.id
    assert result.steps_executed == 3


# ==============================================================================
# 2. EVIDENCE PERSISTENCE TESTS
# ==============================================================================

def test_evidence_persistence_in_database(test_db_session, populated_anomaly_data):
    """Verify that Investigation and InvestigationEvidence records are cleanly persisted to DB."""
    anomaly = populated_anomaly_data
    result = investigate_anomaly(anomaly.id, session=test_db_session)

    # Query Investigation from DB
    inv = test_db_session.execute(
        select(Investigation).where(Investigation.id == result.investigation_id)
    ).scalar_one_or_none()
    assert inv is not None
    assert inv.anomaly_id == anomaly.id
    assert inv.status == "completed"
    assert inv.completed_at is not None
    assert len(inv.summary) > 0

    # Query InvestigationEvidence from DB
    evidence_rows = test_db_session.execute(
        select(InvestigationEvidence)
        .where(InvestigationEvidence.investigation_id == inv.id)
        .order_by(InvestigationEvidence.step_number)
    ).scalars().all()

    assert len(evidence_rows) == 3
    assert [r.step_number for r in evidence_rows] == [1, 2, 3]
    assert [r.tool_name for r in evidence_rows] == [
        "segment_breakdown",
        "check_seasonality",
        "get_recent_trend",
    ]
    for r in evidence_rows:
        assert r.anomaly_id == anomaly.id
        assert r.status == "success"
        assert isinstance(r.input_parameters, dict)
        assert isinstance(r.output_data, dict)

    # Verify Anomaly entity status updated
    updated_anomaly = test_db_session.execute(
        select(Anomaly).where(Anomaly.id == anomaly.id)
    ).scalar_one()
    assert updated_anomaly.status == "investigated"


# ==============================================================================
# 3. INVALID ANOMALY HANDLING TESTS
# ==============================================================================

def test_invalid_anomaly_id_not_found(test_db_session):
    """Verify AnomalyNotFoundError when given a non-existent anomaly ID."""
    with pytest.raises(AnomalyNotFoundError) as exc_info:
        investigate_anomaly(999999, session=test_db_session)
    assert "999999" in str(exc_info.value)


def test_invalid_anomaly_id_type_or_value(test_db_session):
    """Verify ValueError when given negative or non-integer anomaly IDs."""
    with pytest.raises(ValueError):
        investigate_anomaly(0, session=test_db_session)

    with pytest.raises(ValueError):
        investigate_anomaly(-5, session=test_db_session)

    with pytest.raises(ValueError):
        investigate_anomaly("invalid", session=test_db_session)  # type: ignore


# ==============================================================================
# 4. TOOL FAILURE RESILIENCE TESTS
# ==============================================================================

def test_tool_failure_resilience_partial_failure(test_db_session, populated_anomaly_data):
    """Verify that a tool exception does not crash the orchestrator and records an error step."""
    anomaly = populated_anomaly_data

    # Patch check_seasonality to simulate unexpected failure
    with patch(
        "app.investigation.orchestrator.check_seasonality",
        side_effect=RuntimeError("Simulated seasonality failure"),
    ):
        result = investigate_anomaly(anomaly.id, session=test_db_session)

    assert result.status == "partial_failure"
    assert result.steps_executed == 3

    # Step 1 succeeded
    assert result.evidence[0].step_number == 1
    assert result.evidence[0].status == "success"
    assert result.breakdown is not None

    # Step 2 failed gracefully
    assert result.evidence[1].step_number == 2
    assert result.evidence[1].status == "error"
    assert "Simulated seasonality failure" in result.evidence[1].output_data.get("error", "")
    assert result.seasonality is None

    # Step 3 still executed successfully
    assert result.evidence[2].step_number == 3
    assert result.evidence[2].status == "success"
    assert result.recent_trend is not None

    # Verify DB persistence of error step
    ev2 = test_db_session.execute(
        select(InvestigationEvidence).where(
            InvestigationEvidence.investigation_id == result.investigation_id,
            InvestigationEvidence.step_number == 2,
        )
    ).scalar_one()
    assert ev2.status == "error"


def test_all_tools_failure(test_db_session, populated_anomaly_data):
    """Verify handling when all tools fail."""
    anomaly = populated_anomaly_data

    with patch("app.investigation.orchestrator.segment_breakdown", side_effect=RuntimeError("Err 1")), \
         patch("app.investigation.orchestrator.check_seasonality", side_effect=RuntimeError("Err 2")), \
         patch("app.investigation.orchestrator.get_recent_trend", side_effect=RuntimeError("Err 3")):
        result = investigate_anomaly(anomaly.id, session=test_db_session)

    assert result.status == "failed"
    assert result.steps_executed == 3
    for ev in result.evidence:
        assert ev.status == "error"

    # Anomaly status reset to open
    updated_anomaly = test_db_session.execute(
        select(Anomaly).where(Anomaly.id == anomaly.id)
    ).scalar_one()
    assert updated_anomaly.status == "open"


# ==============================================================================
# 5. SERIALIZATION TESTS
# ==============================================================================

def test_investigation_result_json_serialization(test_db_session, populated_anomaly_data):
    """Verify that complete InvestigationResult serializes cleanly to JSON."""
    anomaly = populated_anomaly_data
    result = investigate_anomaly(anomaly.id, session=test_db_session)

    res_dict = result.to_dict()
    assert isinstance(res_dict, dict)
    assert res_dict["status"] == "completed"
    assert res_dict["steps_executed"] == 3
    assert len(res_dict["evidence"]) == 3
    assert res_dict["anomaly"]["metric_name"] == KPI_ORDER_COUNT

    # Validate that json.dumps serializes without Decimal or date errors
    json_str = json.dumps(res_dict)
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert parsed["investigation_id"] == result.investigation_id
