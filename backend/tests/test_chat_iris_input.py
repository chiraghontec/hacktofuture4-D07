from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.main import app
from src.controller.controller import ControllerResult


def _incident_report_payload() -> dict:
    return {
        "source_system": "iris",
        "case_id": "2847",
        "report_id": "rep-42",
        "report_url": "https://iris.local/cases/2847",
        "ingested_at": "2026-04-16T10:00:00Z",
        "case_name": "Redis Latency Spike",
        "short_description": "P95 latency increased sharply after deployment.",
        "severity": "high",
        "tags": ["redis", "latency", "production"],
        "iocs": [
            "redis://cache-prod",
            {"type": "ip", "value": "10.2.3.44"},
        ],
        "timeline": [
            {"time": "09:35", "event": "alert triggered"},
            {"time": "09:41", "event": "case escalated"},
        ],
    }


def test_chat_accepts_incident_report_only() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "session_id": "sess-iris-only",
            "incident_report": _incident_report_payload(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"].startswith("trace-")
    assert isinstance(payload["answer"], str)
    assert isinstance(payload["needs_approval"], bool)


def test_chat_requires_message_or_incident_report() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "session_id": "sess-iris-invalid",
        },
    )

    assert response.status_code == 422


def test_chat_prefers_incident_report_over_message() -> None:
    client = TestClient(app)
    captured: dict[str, str] = {}

    def fake_handle_query(query: str, session_id: str) -> ControllerResult:
        captured["query"] = query
        captured["session_id"] = session_id
        return ControllerResult(
            answer="ok",
            trace_id="trace-iris-precedence",
            needs_approval=False,
            suggested_action="summarize findings",
            trace=[],
        )

    with patch.object(chat_route.kernel, "handle_query", side_effect=fake_handle_query):
        response = client.post(
            "/api/chat",
            json={
                "message": "ignore this free-text query",
                "session_id": "sess-iris-both",
                "incident_report": _incident_report_payload(),
            },
        )

    assert response.status_code == 200
    assert "Case Name: Redis Latency Spike" in captured["query"]
    assert "ignore this free-text query" not in captured["query"]
    assert captured["session_id"] == "sess-iris-both"


def test_chat_message_mode_still_supported() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={
            "message": "Explain Redis latency from last week",
            "session_id": "sess-message-mode",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"].startswith("trace-")
