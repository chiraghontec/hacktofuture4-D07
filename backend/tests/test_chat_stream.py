import json

from fastapi.testclient import TestClient

from app.main import app


def _create_trace(client: TestClient, session_id: str) -> str:
    response = client.post(
        "/api/chat",
        json={"message": "Explain Redis latency from last week", "session_id": session_id},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload["trace_id"]


def _read_stream_payloads(client: TestClient, trace_id: str) -> list[dict]:
    with client.stream("GET", f"/api/chat/stream?trace_id={trace_id}") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    data_lines = [line for line in lines if line.startswith("data:")]
    return [json.loads(line.split("data:", 1)[1].strip()) for line in data_lines]


def test_transcript_endpoint_returns_persisted_trace() -> None:
    client = TestClient(app)
    trace_id = _create_trace(client, "sess-stream-1")

    response = client.get(f"/api/chat/transcript/{trace_id}")
    assert response.status_code == 200

    payload = response.json()
    assert payload["trace_id"] == trace_id
    assert isinstance(payload["steps"], list)
    assert len(payload["steps"]) == 3
    assert isinstance(payload["dedup_summary"], dict)
    assert "deduped_count" in payload["dedup_summary"]


def test_stream_endpoint_emits_contract_payload_shape() -> None:
    client = TestClient(app)
    trace_id = _create_trace(client, "sess-stream-2")

    payloads = _read_stream_payloads(client, trace_id)
    assert len(payloads) == 3

    expected_steps = ["retrieval", "reasoning", "execution"]
    assert [item["step"] for item in payloads] == expected_steps

    for item in payloads:
        assert set(item.keys()) == {"step", "agent", "observation", "sources"}
        assert isinstance(item["step"], str)
        assert isinstance(item["agent"], str)
        assert isinstance(item["observation"], str)
        assert isinstance(item["sources"], list)


def test_stream_endpoint_returns_404_for_unknown_trace() -> None:
    client = TestClient(app)
    response = client.get("/api/chat/stream?trace_id=trace-not-found")
    assert response.status_code == 404


def test_transcript_endpoint_returns_404_for_unknown_trace() -> None:
    client = TestClient(app)
    response = client.get("/api/chat/transcript/trace-not-found")
    assert response.status_code == 404
