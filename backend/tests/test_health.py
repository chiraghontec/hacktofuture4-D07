from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "uniops-backend"
    assert payload["version"] == "0.1.0"
    assert payload["services"]["api"] == "up"
    assert payload["services"]["milvus"] == "unknown"
