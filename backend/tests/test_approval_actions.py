from fastapi.testclient import TestClient

from app.api.routes.chat import queue_manager
from app.main import app


def _high_risk_chat(client: TestClient, session_id: str) -> dict:
    response = client.post(
        "/api/chat",
        json={"message": "Create rollback PR and update Jira", "session_id": session_id},
    )
    assert response.status_code == 200
    return response.json()


def test_high_risk_chat_creates_pending_action() -> None:
    queue_manager.clear_all()
    client = TestClient(app)

    payload = _high_risk_chat(client, "sess-queue-1")
    assert payload["needs_approval"] is True

    pending = client.get("/api/actions/pending")
    assert pending.status_code == 200
    actions = pending.json()["actions"]
    assert len(actions) == 1
    assert actions[0]["trace_id"] == payload["trace_id"]
    assert actions[0]["status"] == "pending"


def test_approve_action_executes_and_removes_pending() -> None:
    queue_manager.clear_all()
    client = TestClient(app)

    _high_risk_chat(client, "sess-queue-2")
    actions = client.get("/api/actions/pending").json()["actions"]
    action_id = actions[0]["id"]

    approve = client.post(f"/api/actions/{action_id}/approve", json={"decided_by": "tester"})
    assert approve.status_code == 200
    approved_payload = approve.json()
    assert approved_payload["status"] == "executed"
    assert approved_payload["execution"]["status"] == "mock_executed"

    remaining = client.get("/api/actions/pending").json()["actions"]
    assert remaining == []


def test_reject_action_removes_pending() -> None:
    queue_manager.clear_all()
    client = TestClient(app)

    _high_risk_chat(client, "sess-queue-3")
    actions = client.get("/api/actions/pending").json()["actions"]
    action_id = actions[0]["id"]

    reject = client.post(
        f"/api/actions/{action_id}/reject",
        json={"decided_by": "tester", "reason": "not now"},
    )
    assert reject.status_code == 200
    rejected_payload = reject.json()
    assert rejected_payload["status"] == "rejected"

    remaining = client.get("/api/actions/pending").json()["actions"]
    assert remaining == []


def test_safe_chat_does_not_enqueue_actions() -> None:
    queue_manager.clear_all()
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        json={"message": "Explain Redis latency from last week", "session_id": "sess-queue-safe"},
    )
    assert response.status_code == 200
    assert response.json()["needs_approval"] is False

    pending = client.get("/api/actions/pending")
    assert pending.status_code == 200
    assert pending.json()["actions"] == []
