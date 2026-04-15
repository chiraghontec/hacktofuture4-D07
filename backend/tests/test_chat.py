from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_chat_success() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "message": "Run the high CPU runbook",
            "session_id": str(uuid4()),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Received: Run the high CPU runbook"
    assert payload["trace_id"].startswith("trace-")
    assert payload["needs_approval"] is False


def test_chat_rejects_empty_message() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "message": "   ",
            "session_id": str(uuid4()),
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "message must not be empty"
    assert payload["trace_id"] is None
    assert payload["status_code"] == 400


def test_chat_rejects_invalid_session_id() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "message": "hello",
            "session_id": "invalid-session",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"] == "session_id must be a valid UUID string"
    assert payload["trace_id"] is None
    assert payload["status_code"] == 400


def test_chat_stream_stub() -> None:
    client = TestClient(app)
    response = client.get("/api/chat/stream", params={"trace_id": "trace-test-001"})

    assert response.status_code == 501
    payload = response.json()
    assert payload["error"] == "stream_not_implemented"
    assert payload["trace_id"] == "trace-test-001"
    assert payload["status_code"] == 501
