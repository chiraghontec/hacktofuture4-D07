import json

from fastapi.testclient import TestClient

from app.api.routes import chat as chat_route
from app.main import app
from src.controller.controller import ControllerKernel


class _FakeGroqLLMClient:
    provider_name = "groq"
    model_name = "groq-test"

    def reason(self, query: str, confidence: float, top_sources: list[dict], dedup_summary: dict | None) -> dict[str, object]:
        return {
            "reasoning": "Provider-generated reasoning.",
            "answer": "Provider-generated answer.",
            "suggested_action": "create rollback PR and notify Slack and Jira",
            "action_details": {
                "intent": "rollback_and_notify",
                "tool": "github.mock.rollback_pr",
                "parameters": {},
                "approval_required": True,
                "risk_hint": "high",
            },
            "reasoning_steps": ["Analyze evidence", "Select action"],
            "confidence_breakdown": {"base_confidence": confidence, "final_confidence": confidence},
            "evidence_scores": [],
        }

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        return query_tokens

    def assess_execution_action(self, action: str, action_details: dict | None) -> dict[str, str]:
        return {
            "normalized_action": action,
            "reasoning": "Provider execution assessment completed.",
            "risk_hint": "high",
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


def test_chat_endpoint_uses_controller_kernel() -> None:
    client = TestClient(app)
    events = _collect_sse_events(
        client,
        {"message": "Explain Redis latency from last week", "session_id": "sess-1"},
    )

    event_names = [item["event"] for item in events]
    assert "trace_started" in event_names
    assert "trace_complete" in event_names

    complete_payload = next(item["payload"] for item in events if item["event"] == "trace_complete")
    assert complete_payload["trace_id"].startswith("trace-")
    assert isinstance(complete_payload["answer"], str)
    assert isinstance(complete_payload["needs_approval"], bool)
    dedup_summary = complete_payload.get("metadata", {}).get("dedup_summary", {})
    assert isinstance(dedup_summary, dict)
    assert "deduped_count" in dedup_summary

    transcript = client.get(f"/api/chat/transcript/{complete_payload['trace_id']}")
    assert transcript.status_code == 200
    transcript_payload = transcript.json()
    assert isinstance(transcript_payload.get("action_details"), dict)
    assert transcript_payload["action_details"].get("intent")


def test_controller_marks_high_risk_actions_for_approval() -> None:
    kernel = ControllerKernel(provider_name="groq", reasoning_llm_client=_FakeGroqLLMClient())
    result = kernel.handle_query("Create rollback PR and update Jira", session_id="sess-2")

    assert result.needs_approval is True
    assert result.suggested_action
    assert len(result.trace) == 3
    assert isinstance(result.dedup_summary, dict)


def test_chat_endpoint_emits_trace_error_for_invalid_provider(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.setattr(chat_route, "kernel", ControllerKernel(provider_name="invalid-provider"))

    events = _collect_sse_events(
        client,
        {"message": "Explain Redis latency from last week", "session_id": "sess-invalid-provider"},
    )

    error_payload = next(item["payload"] for item in events if item["event"] == "trace_error")
    assert error_payload.get("error_code") == "provider_error"
    assert "LLM_PROVIDER" in str(error_payload.get("error", ""))


def test_chat_endpoint_emits_trace_error_when_selected_provider_is_misconfigured(monkeypatch) -> None:
    client = TestClient(app)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(chat_route, "kernel", ControllerKernel(provider_name="groq"))

    events = _collect_sse_events(
        client,
        {"message": "Explain Redis latency from last week", "session_id": "sess-missing-groq-key"},
    )

    error_payload = next(item["payload"] for item in events if item["event"] == "trace_error")
    assert error_payload.get("error_code") == "provider_error"
    assert "GROQ_API_KEY" in str(error_payload.get("error", ""))
