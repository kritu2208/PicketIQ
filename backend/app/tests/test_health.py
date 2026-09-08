"""Deterministic unit tests for /health endpoint using FastAPI TestClient and mock DB sessions."""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.db.session import get_db


@pytest.fixture
def client():
    """Provides a TestClient with dependency overrides cleaned up after each test."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_success(client):
    """Test /health returns HTTP 200 and connected status when database is reachable."""
    mock_session = MagicMock()
    mock_session.execute.return_value = None

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "connected",
    }
    mock_session.execute.assert_called_once()


def test_health_db_failure(client):
    """Test /health returns HTTP 503 and disconnected status when database query fails."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = OperationalError(
        statement="SELECT 1",
        params={},
        orig=Exception("Connection refused to database host"),
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "db": "disconnected",
        "detail": "Database is currently unreachable",
    }


def test_health_failure_does_not_leak_details(client):
    """Test /health failure response does not expose internal exception details, credentials, or stack traces."""
    sensitive_db_error = "FATAL: password authentication failed for user 'secret_user' at /var/lib/postgresql"
    mock_session = MagicMock()
    mock_session.execute.side_effect = OperationalError(
        statement="SELECT 1",
        params={},
        orig=Exception(sensitive_db_error),
    )

    def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    response = client.get("/health")

    assert response.status_code == 503
    response_body = response.text

    # Ensure no internal error strings, credentials, or traceback traces leak to the client
    assert "secret_user" not in response_body
    assert "authentication failed" not in response_body
    assert "Traceback" not in response_body
    assert "SELECT 1" not in response_body
    assert response.json() == {
        "status": "error",
        "db": "disconnected",
        "detail": "Database is currently unreachable",
    }
