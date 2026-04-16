from fastapi.testclient import TestClient

from app.main import app
from src.controller.controller import ControllerKernel


def test_chat_endpoint_uses_controller_kernel() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"message": "Explain Redis latency from last week", "session_id": "sess-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"].startswith("trace-")
    assert isinstance(payload["answer"], str)
    assert isinstance(payload["needs_approval"], bool)
    assert isinstance(payload["dedup_summary"], dict)
    assert "deduped_count" in payload["dedup_summary"]


def test_controller_marks_high_risk_actions_for_approval() -> None:
    kernel = ControllerKernel()
    result = kernel.handle_query("Create rollback PR and update Jira", session_id="sess-2")

    assert result.needs_approval is True
    assert result.suggested_action
    assert len(result.trace) == 3
    assert isinstance(result.dedup_summary, dict)
