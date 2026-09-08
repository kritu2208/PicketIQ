"""Deterministic unit tests for Phase 5D LLM Investigation layer."""

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.models import (
    Base,
    Customer,
    Order,
    KPIDaily,
    Anomaly,
    InvestigationConclusion,
)
from app.kpi.metadata import KPI_ORDER_COUNT
from app.investigation import (
    investigate_anomaly,
    investigate_and_explain,
    explain_investigation,
    MockLLMProvider,
)
from app.investigation.llm.validator import validate_investigation_conclusion


@pytest.fixture
def test_db_session():
    """Isolated in-memory SQLite database session for LLM investigation tests."""
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
def populated_anomaly(test_db_session):
    """Sets up a complete realistic anomaly scenario with historical KPIs and orders."""
    session = test_db_session
    target_dt = date(2017, 11, 24)

    # Customers
    c1 = Customer(customer_id="cust_sp_1", customer_unique_id="u1", customer_zip_code_prefix=1000, customer_city="Sao Paulo", customer_state="SP")
    c2 = Customer(customer_id="cust_rj_1", customer_unique_id="u2", customer_zip_code_prefix=2000, customer_city="Rio", customer_state="RJ")
    session.add_all([c1, c2])

    # 14 historical baseline days
    for day_offset in range(14, 0, -1):
        hist_dt = target_dt - timedelta(days=day_offset)
        session.add(
            Order(
                order_id=f"ord_base_sp_{day_offset}",
                customer_id="cust_sp_1",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(hist_dt, datetime.min.time()),
            )
        )
        session.add(
            KPIDaily(
                metric_name=KPI_ORDER_COUNT,
                date=hist_dt,
                value=Decimal(str(100 + (day_offset % 4))),
                segment="all",
            )
        )

    # Target date orders (SP: 9 orders, RJ: 1 order)
    for i in range(9):
        session.add(
            Order(
                order_id=f"ord_tgt_sp_{i}",
                customer_id="cust_sp_1",
                order_status="delivered",
                order_purchase_timestamp=datetime.combine(target_dt, datetime.min.time()),
            )
        )
    session.add(
        Order(
            order_id="ord_tgt_rj_0",
            customer_id="cust_rj_1",
            order_status="delivered",
            order_purchase_timestamp=datetime.combine(target_dt, datetime.min.time()),
        )
    )

    # Target KPI and Anomaly
    session.add(
        KPIDaily(metric_name=KPI_ORDER_COUNT, date=target_dt, value=Decimal("900.0000"), segment="all")
    )
    anomaly = Anomaly(
        metric_name=KPI_ORDER_COUNT,
        date=target_dt,
        expected_value=Decimal("101.5000"),
        actual_value=Decimal("900.0000"),
        z_score=Decimal("28.4000"),
        severity="high",
        status="open",
        created_at=datetime.utcnow(),
    )
    session.add(anomaly)
    session.commit()

    return anomaly


# ==============================================================================
# 1. END-TO-END LLM INVESTIGATION TESTS
# ==============================================================================

def test_end_to_end_investigate_and_explain_mock(test_db_session, populated_anomaly):
    """Verify complete pipeline: Anomaly -> Orchestrator -> Evidence -> LLM -> Validated Conclusion."""
    anomaly = populated_anomaly
    provider = MockLLMProvider()

    conclusion = investigate_and_explain(
        anomaly_id=anomaly.id,
        provider=provider,
        session=test_db_session,
    )

    assert conclusion.anomaly_id == anomaly.id
    assert conclusion.investigation_id > 0
    assert conclusion.validation_passed is True
    assert conclusion.validation_errors == []
    assert conclusion.confidence in ("high", "medium")
    assert conclusion.affected_segment == "SP"
    assert len(conclusion.evidence_references) == 3
    assert len(conclusion.root_cause) > 0
    assert len(conclusion.explanation) > 0
    assert len(conclusion.recommended_action) > 0
    assert conclusion.provider == "mock"


def test_conclusion_db_persistence(test_db_session, populated_anomaly):
    """Verify that InvestigationConclusion record is cleanly committed to PostgreSQL / SQLite."""
    anomaly = populated_anomaly
    provider = MockLLMProvider()

    conclusion = investigate_and_explain(
        anomaly_id=anomaly.id,
        provider=provider,
        session=test_db_session,
    )

    # Query DB
    rec = test_db_session.execute(
        select(InvestigationConclusion).where(
            InvestigationConclusion.investigation_id == conclusion.investigation_id
        )
    ).scalar_one_or_none()

    assert rec is not None
    assert rec.anomaly_id == anomaly.id
    assert rec.root_cause == conclusion.root_cause
    assert rec.confidence == conclusion.confidence
    assert rec.affected_segment == "SP"
    assert rec.validation_passed is True
    assert isinstance(rec.evidence_references, list)
    assert len(rec.evidence_references) == 3


# ==============================================================================
# 2. EVIDENCE REFERENCE AND CITATION VALIDATION TESTS
# ==============================================================================

def test_evidence_reference_validation_success(test_db_session, populated_anomaly):
    """Verify that correctly cited evidence passes validation."""
    anomaly = populated_anomaly
    inv_res = investigate_anomaly(anomaly.id, session=test_db_session)

    valid_payload = {
        "root_cause": "Black Friday demand spike in SP",
        "explanation": "Verified regional spike concentrated in SP (+376 delta).",
        "confidence": "high",
        "affected_segment": "SP",
        "evidence_references": [
            "Step 1 (segment_breakdown): SP contributed 90% of delta",
            "Step 2 (check_seasonality): is_seasonal=False",
            "Step 3 (get_recent_trend): sudden shift",
        ],
        "recommended_action": "Audit logistics capacity in SP.",
    }

    is_valid, errors = validate_investigation_conclusion(valid_payload, inv_res)
    assert is_valid is True
    assert errors == []


def test_evidence_reference_validation_rejects_hallucinated_step(test_db_session, populated_anomaly):
    """Verify that referencing non-existent step numbers fails validation."""
    anomaly = populated_anomaly
    inv_res = investigate_anomaly(anomaly.id, session=test_db_session)

    invalid_payload = {
        "root_cause": "Spike driven by promotions",
        "explanation": "Promotions caused this.",
        "confidence": "high",
        "affected_segment": "SP",
        "evidence_references": [
            "Step 1 (segment_breakdown): SP contributed 90%",
            "Step 4 (marketing_engine): Ad spend doubled",  # Hallucinated step
        ],
        "recommended_action": "Check ads.",
    }

    is_valid, errors = validate_investigation_conclusion(invalid_payload, inv_res)
    assert is_valid is False
    assert any("Hallucinated reference" in e and "Step 4" in e for e in errors)


def test_evidence_reference_validation_rejects_hallucinated_segment(test_db_session, populated_anomaly):
    """Verify that claiming an affected segment not in regional breakdown fails validation."""
    anomaly = populated_anomaly
    inv_res = investigate_anomaly(anomaly.id, session=test_db_session)

    invalid_payload = {
        "root_cause": "Spike in non-existent territory",
        "explanation": "California drove the orders.",
        "confidence": "high",
        "affected_segment": "CA",  # Not in Brazilian states dataset
        "evidence_references": [
            "Step 1 (segment_breakdown): Breakdown analyzed",
            "Step 2 (check_seasonality): Seasonality checked",
            "Step 3 (get_recent_trend): Trend sudden",
        ],
        "recommended_action": "Check CA orders.",
    }

    is_valid, errors = validate_investigation_conclusion(invalid_payload, inv_res)
    assert is_valid is False
    assert any("Hallucinated segment" in e and "CA" in e for e in errors)


def test_confidence_mismatch_validation(test_db_session):
    """Verify that declaring high confidence when evidence is insufficient fails validation."""
    target_dt = date(2017, 1, 5)
    # Anomaly with no history
    anomaly = Anomaly(
        metric_name=KPI_ORDER_COUNT,
        date=target_dt,
        expected_value=Decimal("0.0"),
        actual_value=Decimal("10.0"),
        z_score=Decimal("0.0"),
        severity="low",
        status="open",
    )
    test_db_session.add(anomaly)
    test_db_session.commit()

    inv_res = investigate_anomaly(anomaly.id, session=test_db_session)

    # Premature high confidence payload
    unsubstantiated_payload = {
        "root_cause": "Systemic demand surge",
        "explanation": "Definitive surge.",
        "confidence": "high",  # Mismatch: evidence had insufficient_data
        "affected_segment": None,
        "evidence_references": [
            "Step 1 (segment_breakdown): analyzed",
            "Step 2 (check_seasonality): checked",
            "Step 3 (get_recent_trend): checked",
        ],
        "recommended_action": "Prepare for growth.",
    }

    is_valid, errors = validate_investigation_conclusion(unsubstantiated_payload, inv_res)
    assert is_valid is False
    assert any("Confidence mismatch" in e for e in errors)


# ==============================================================================
# 3. INSUFFICIENT EVIDENCE & UNCERTAINTY HANDLING
# ==============================================================================

def test_insufficient_evidence_inconclusive_handling(test_db_session):
    """Verify that MockLLMProvider produces honest Inconclusive conclusion on sparse data."""
    target_dt = date(2017, 1, 5)
    anomaly = Anomaly(
        metric_name=KPI_ORDER_COUNT,
        date=target_dt,
        expected_value=Decimal("0.0"),
        actual_value=Decimal("5.0"),
        z_score=Decimal("0.0"),
        severity="low",
        status="open",
    )
    test_db_session.add(anomaly)
    test_db_session.commit()

    provider = MockLLMProvider()
    conclusion = investigate_and_explain(
        anomaly_id=anomaly.id,
        provider=provider,
        session=test_db_session,
    )

    assert conclusion.confidence == "low"
    assert "Inconclusive" in conclusion.root_cause
    assert "insufficient" in conclusion.explanation.lower()
    assert conclusion.validation_passed is True


# ==============================================================================
# 4. CUSTOM MOCK AND SERIALIZATION TESTS
# ==============================================================================

def test_custom_mock_provider_response(test_db_session, populated_anomaly):
    """Verify that custom mock LLM responses are processed and validated."""
    anomaly = populated_anomaly
    custom_dict = {
        "root_cause": "Black Friday localized order surge in SP",
        "explanation": "Orders surged sharply in SP without weekly precedent.",
        "confidence": "high",
        "affected_segment": "SP",
        "evidence_references": [
            "Step 1 (segment_breakdown): SP generated +376 net orders",
            "Step 2 (check_seasonality): non-seasonal deviation",
            "Step 3 (get_recent_trend): sudden single-day spike",
        ],
        "recommended_action": "Prepare regional inventory fulfillment in SP.",
    }
    provider = MockLLMProvider(custom_response=custom_dict)
    conclusion = investigate_and_explain(
        anomaly_id=anomaly.id,
        provider=provider,
        session=test_db_session,
    )

    assert conclusion.root_cause == custom_dict["root_cause"]
    assert conclusion.validation_passed is True


def test_conclusion_json_serialization(test_db_session, populated_anomaly):
    """Verify that InvestigationConclusionResult cleanly serializes to JSON via to_dict()."""
    anomaly = populated_anomaly
    conclusion = investigate_and_explain(
        anomaly_id=anomaly.id,
        provider=MockLLMProvider(),
        session=test_db_session,
    )

    data = conclusion.to_dict()
    assert isinstance(data, dict)
    assert data["anomaly_id"] == anomaly.id
    assert data["validation_passed"] is True

    # Validate json.dumps succeeds
    json_str = json.dumps(data)
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert parsed["confidence"] == conclusion.confidence
