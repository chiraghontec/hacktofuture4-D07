import json

from fastapi.testclient import TestClient

from app.main import app


def _create_high_risk_trace(client: TestClient) -> str:
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "message": "Create rollback PR and notify Slack and Jira",
            "session_id": "sess-approval",
        },
    ) as response:
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

    completion = next(item["payload"] for item in events if item["event"] == "trace_complete")
    assert completion["needs_approval"] is True
    return completion["trace_id"]


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
