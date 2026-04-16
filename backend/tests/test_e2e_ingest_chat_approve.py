import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes.chat import kernel
from app.main import app
from src.memory.three_tier_memory import ThreeTierMemory


class _FakeConfluenceClient:
    def fetch_page(self, page_id: str) -> dict[str, str]:
        return {
            "page_id": page_id,
            "title": f"Redis Latency Runbook {page_id}",
            "body": "Redis latency remediation steps include checking deploys and rollback readiness.",
            "source_url": f"https://confluence.example.internal/wiki/{page_id}",
        }


def _clear_runtime_documents() -> None:
    ThreeTierMemory._runtime_documents = []
    kernel.memory._documents_cache = None


def _read_stream_payloads(client: TestClient, trace_id: str) -> list[dict]:
    with client.stream("GET", f"/api/chat/stream?trace_id={trace_id}") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    data_lines = [line for line in lines if line.startswith("data:")]
    return [json.loads(line.split("data:", 1)[1].strip()) for line in data_lines]


def test_e2e_batch_ingest_chat_stream_approve_transcript() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.ConfluenceClient.from_env", return_value=_FakeConfluenceClient()):
        ingest_response = client.post(
            "/api/ingest/confluence",
            json={"page_ids": ["12345", "67890"]},
        )

    assert ingest_response.status_code == 200
    ingest_payload = ingest_response.json()
    assert ingest_payload["source"] == "confluence"
    assert ingest_payload["ingested_count"] == 2
    assert ingest_payload["failed_count"] == 0

    chat_response = client.post(
        "/api/chat",
        json={
            "message": "Create rollback PR and notify Slack and Jira for redis latency incident",
            "session_id": "sess-e2e-golden-flow",
        },
    )

    assert chat_response.status_code == 200
    chat_payload = chat_response.json()
    assert chat_payload["needs_approval"] is True
    trace_id = chat_payload["trace_id"]

    stream_payloads = _read_stream_payloads(client, trace_id)
    assert [item["step"] for item in stream_payloads] == ["retrieval", "reasoning", "execution"]

    approve_response = client.post(
        f"/api/approvals/{trace_id}",
        json={
            "decision": "approve",
            "approver_id": "sre-lead",
            "comment": "Approved in E2E test flow.",
        },
    )

    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["final_status"] == "executed"
    assert approve_payload["execution_result"]["status"] == "executed"

    transcript_response = client.get(f"/api/chat/transcript/{trace_id}")
    assert transcript_response.status_code == 200
    transcript_payload = transcript_response.json()

    assert transcript_payload["trace_id"] == trace_id
    assert transcript_payload["final_status"] == "executed"
    assert transcript_payload["approval"]["decision"] == "approve"
    assert transcript_payload["execution_result"]["status"] == "executed"
    assert [step["step"] for step in transcript_payload["steps"]] == [
        "retrieval",
        "reasoning",
        "execution",
        "approval",
    ]
    _clear_runtime_documents()
