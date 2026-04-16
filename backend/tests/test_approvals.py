from fastapi.testclient import TestClient

from app.main import app


def _create_high_risk_trace(client: TestClient) -> str:
    response = client.post(
        "/api/chat",
        json={
            "message": "Create rollback PR and notify Slack and Jira",
            "session_id": "sess-approval",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["needs_approval"] is True
    return payload["trace_id"]


def test_approve_trace_executes_mock_tool_and_persists_audit() -> None:
    client = TestClient(app)
    trace_id = _create_high_risk_trace(client)

    response = client.post(
        f"/api/approvals/{trace_id}",
        json={
            "decision": "approve",
            "approver_id": "sre-lead",
            "comment": "Approved for execution.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == trace_id
    assert payload["final_status"] == "executed"
    assert payload["approval"]["decision"] == "approve"
    assert payload["execution_result"]["status"] == "executed"

    transcript = client.get(f"/api/chat/transcript/{trace_id}")
    assert transcript.status_code == 200
    transcript_payload = transcript.json()
    assert transcript_payload["final_status"] == "executed"
    assert transcript_payload["approval"]["approver_id"] == "sre-lead"


def test_reject_trace_does_not_execute_tool_and_marks_rejected() -> None:
    client = TestClient(app)
    trace_id = _create_high_risk_trace(client)

    response = client.post(
        f"/api/approvals/{trace_id}",
        json={
            "decision": "reject",
            "approver_id": "incident-commander",
            "comment": "Rejecting until more evidence.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_status"] == "rejected"
    assert payload["execution_result"]["status"] == "rejected"

    transcript = client.get(f"/api/chat/transcript/{trace_id}")
    assert transcript.status_code == 200
    transcript_payload = transcript.json()
    assert transcript_payload["final_status"] == "rejected"
    assert transcript_payload["approval"]["decision"] == "reject"
