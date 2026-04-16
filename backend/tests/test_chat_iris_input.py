import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.main import app


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


def _collect_sse_events(client: TestClient, payload: dict) -> list[dict]:
    with client.stream("POST", "/api/chat", json=payload) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    events: list[dict] = []
    pending_event = "message"
    pending_data: list[str] = []
    for raw_line in lines:
        line = str(raw_line).strip()
        if line == "":
            if pending_data:
                events.append({"event": pending_event, "payload": json.loads("\n".join(pending_data))})
            pending_event = "message"
            pending_data = []
            continue
        if line.startswith("event:"):
            pending_event = line.split("event:", 1)[1].strip()
            continue
        if line.startswith("data:"):
            pending_data.append(line.split("data:", 1)[1].strip())

    return events


def test_chat_accepts_incident_report_only() -> None:
    client = TestClient(app)
    events = _collect_sse_events(
        client,
        {
            "session_id": "sess-iris-only",
            "incident_report": _incident_report_payload(),
        },
    )

    completion = next(item["payload"] for item in events if item["event"] == "trace_complete")
    assert completion["trace_id"].startswith("trace-")
    assert isinstance(completion["answer"], str)
    assert isinstance(completion["needs_approval"], bool)
    assert isinstance(completion.get("metadata", {}).get("dedup_summary", {}), dict)


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

    def fake_stream_query_events(query: str, session_id: str):
        captured["query"] = query
        captured["session_id"] = session_id
        yield {
            "event_type": "trace_started",
            "trace_id": "trace-iris-precedence",
            "status": "started",
            "metadata": {
                "session_id": session_id,
                "dedup_summary": {"deduped_count": 0},
            },
        }
        yield {
            "event_type": "trace_complete",
            "trace_id": "trace-iris-precedence",
            "status": "completed",
            "answer": "ok",
            "needs_approval": False,
            "suggested_action": "summarize findings",
            "metadata": {
                "dedup_summary": {"deduped_count": 0},
                "step_count": 0,
            },
        }

    with patch.object(chat_route.kernel, "stream_query_events", side_effect=fake_stream_query_events):
        events = _collect_sse_events(
            client,
            {
                "message": "ignore this free-text query",
                "session_id": "sess-iris-both",
                "incident_report": _incident_report_payload(),
            },
        )

    assert any(item["event"] == "trace_complete" for item in events)
    assert "Case Name: Redis Latency Spike" in captured["query"]
    assert "ignore this free-text query" not in captured["query"]
    assert captured["session_id"] == "sess-iris-both"


def test_chat_message_mode_still_supported() -> None:
    client = TestClient(app)
    events = _collect_sse_events(
        client,
        {
            "message": "Explain Redis latency from last week",
            "session_id": "sess-message-mode",
        },
    )

    completion = next(item["payload"] for item in events if item["event"] == "trace_complete")
    assert completion["trace_id"].startswith("trace-")
    assert isinstance(completion.get("metadata", {}).get("dedup_summary", {}), dict)
