"""Deterministic unit tests for anomaly API endpoints using FastAPI TestClient and SQLite test session."""

from datetime import date, datetime
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import get_db
from app.db.models import (
    Base,
    Anomaly,
    Investigation,
    InvestigationEvidence,
    InvestigationConclusion,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session for deterministic API testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_list_metrics(client):
    """Test /api/metrics returns the 5 core business KPIs."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert len(metrics) == 5
    metric_names = [m["name"] for m in metrics]
    assert "order_count" in metric_names
    assert "daily_revenue" in metric_names
    assert "cancellation_rate" in metric_names


def test_list_anomalies_empty(client):
    """Test /api/anomalies returns empty list when no anomalies exist."""
    response = client.get("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_anomalies_populated_and_sorted(client, db_session):
    """Test /api/anomalies returns populated list with proper sorting and formatting."""
    a1 = Anomaly(
        metric_name="order_count",
        date=date(2017, 11, 24),
        expected_value=Decimal("200.0000"),
        actual_value=Decimal("1000.0000"),
        z_score=Decimal("25.0000"),
        severity="high",
        status="open",
    )
    a2 = Anomaly(
        metric_name="daily_revenue",
        date=date(2017, 11, 24),
        expected_value=Decimal("20000.0000"),
        actual_value=Decimal("100000.0000"),
        z_score=Decimal("12.0000"),
        severity="high",
        status="open",
    )
    a3 = Anomaly(
        metric_name="cancellation_rate",
        date=date(2018, 5, 1),
        expected_value=Decimal("0.0100"),
        actual_value=Decimal("0.0500"),
        z_score=Decimal("3.5000"),
        severity="low",
        status="open",
    )
    db_session.add_all([a1, a2, a3])
    db_session.commit()

    # Default sort by z_score_desc
    resp = client.get("/api/anomalies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    items = data["items"]
    assert items[0]["metric_name"] == "order_count"
    assert items[0]["z_score"] == 25.0
    assert items[0]["actual_value"] == 1000.0
    assert items[0]["expected_value"] == 200.0
    assert items[0]["delta"] == 800.0
    assert items[0]["delta_pct"] == 400.0
    assert items[0]["severity"] == "high"
    assert items[0]["has_investigation"] is False

    # Filter by metric
    resp_filtered = client.get("/api/anomalies?metric=cancellation_rate")
    assert resp_filtered.status_code == 200
    data_filtered = resp_filtered.json()
    assert data_filtered["total"] == 1
    assert data_filtered["items"][0]["metric_name"] == "cancellation_rate"

    # Filter by severity
    resp_sev = client.get("/api/anomalies?severity=low")
    assert resp_sev.status_code == 200
    assert resp_sev.json()["total"] == 1


def test_get_anomaly_detail(client, db_session):
    """Test /api/anomalies/{id} returns details for single anomaly or 404."""
    a = Anomaly(
        metric_name="order_count",
        date=date(2017, 11, 24),
        expected_value=Decimal("196.6429"),
        actual_value=Decimal("1176.0000"),
        z_score=Decimal("26.8209"),
        severity="high",
        status="open",
    )
    db_session.add(a)
    db_session.commit()

    resp = client.get(f"/api/anomalies/{a.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == a.id
    assert data["metric_name"] == "order_count"
    assert data["actual_value"] == 1176.0

    # Non-existent
    resp_404 = client.get("/api/anomalies/999999")
    assert resp_404.status_code == 404


def test_get_investigation_not_found(client, db_session):
    """Test /api/anomalies/{id}/investigation returns 404 when no investigation exists."""
    a = Anomaly(
        metric_name="order_count",
        date=date(2017, 11, 24),
        expected_value=Decimal("196.6429"),
        actual_value=Decimal("1176.0000"),
        z_score=Decimal("26.8209"),
        severity="high",
        status="open",
    )
    db_session.add(a)
    db_session.commit()

    resp = client.get(f"/api/anomalies/{a.id}/investigation")
    assert resp.status_code == 404
    assert "No investigation found" in resp.json()["detail"]


def test_get_investigation_success(client, db_session):
    """Test /api/anomalies/{id}/investigation returns evidence steps and conclusion."""
    a = Anomaly(
        metric_name="order_count",
        date=date(2017, 11, 24),
        expected_value=Decimal("196.6429"),
        actual_value=Decimal("1176.0000"),
        z_score=Decimal("26.8209"),
        severity="high",
        status="open",
    )
    db_session.add(a)
    db_session.commit()

    inv = Investigation(
        anomaly_id=a.id,
        status="completed",
        summary="Investigation completed",
    )
    db_session.add(inv)
    db_session.commit()

    ev1 = InvestigationEvidence(
        investigation_id=inv.id,
        anomaly_id=a.id,
        step_number=1,
        tool_name="segment_breakdown",
        input_parameters={"metric_name": "order_count", "date": "2017-11-24"},
        output_data={"primary_contributor": "SP", "contribution_share": 38.39},
        status="success",
        summary="Top contributor was SP",
    )
    db_session.add(ev1)

    conc = InvestigationConclusion(
        investigation_id=inv.id,
        anomaly_id=a.id,
        root_cause="Sudden surge in order_count driven by region SP",
        explanation="Orders spiked sharply in region SP.",
        confidence="high",
        affected_segment="SP",
        evidence_references=["Step 1 (segment_breakdown): Top contributor was SP"],
        recommended_action="Review marketing campaigns in region SP",
        provider="mock",
        model_name="mock-grounded-analyst",
        validation_passed=True,
    )
    db_session.add(conc)
    db_session.commit()

    resp = client.get(f"/api/anomalies/{a.id}/investigation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["anomaly"]["id"] == a.id
    assert data["investigation"]["status"] == "completed"
    assert len(data["evidence_steps"]) == 1
    assert data["evidence_steps"][0]["tool_name"] == "segment_breakdown"
    assert data["conclusion"]["root_cause"] == "Sudden surge in order_count driven by region SP"
    assert data["conclusion"]["confidence"] == "high"
    assert data["conclusion"]["validation_passed"] is True
