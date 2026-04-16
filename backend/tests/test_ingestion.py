from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes.chat import kernel
from app.main import app
from src.memory.three_tier_memory import ThreeTierMemory


class _FakeIrisClient:
    def fetch_case(self, case_id: str) -> dict:
        return {
            "source_system": "iris",
            "case_id": case_id,
            "report_id": f"rep-{case_id}",
            "report_url": f"https://localhost/case/{case_id}",
            "ingested_at": "2026-04-16T00:00:00Z",
            "case_name": "Redis Latency Spike",
            "short_description": "Latency increased after deployment",
            "severity": "high",
            "tags": ["redis", "latency"],
            "iocs": [{"type": "host", "value": "cache-01"}],
            "timeline": [{"time": "10:10", "event": "Alert fired"}],
        }


class _FakeConfluenceClient:
    def fetch_page(self, page_id: str) -> dict[str, str]:
        return {
            "page_id": page_id,
            "title": "Redis Latency Runbook",
            "body": "Check recent deploys and cache hit ratio.",
            "source_url": f"https://confluence.example.internal/wiki/{page_id}",
        }


class _MixedConfluenceClient:
    def fetch_page(self, page_id: str) -> dict[str, str]:
        if page_id == "broken":
            raise RuntimeError("simulated confluence fetch failure")
        return {
            "page_id": page_id,
            "title": f"Runbook {page_id}",
            "body": "Check recent deploys and cache hit ratio.",
            "source_url": f"https://confluence.example.internal/wiki/{page_id}",
        }


def _clear_runtime_documents() -> None:
    ThreeTierMemory._runtime_documents = []
    kernel.memory._documents_cache = None


def test_ingest_iris_adds_runtime_incident_document() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.IrisClient.from_env", return_value=_FakeIrisClient()):
        response = client.post("/api/ingest/iris", params={"case_id": "2847"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "iris"
    assert payload["case_id"] == "2847"

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/iris/2847.json" for doc in docs)
    _clear_runtime_documents()


def test_ingest_confluence_batch_adds_runtime_documents() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.ConfluenceClient.from_env", return_value=_FakeConfluenceClient()):
        response = client.post(
            "/api/ingest/confluence",
            json={"page_ids": ["12345", "98765"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "confluence"
    assert payload["ingested_count"] == 2
    assert payload["failed_count"] == 0
    assert len(payload["results"]) == 2
    assert all(item["status"] == "ingested" for item in payload["results"])

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/confluence/12345.md" for doc in docs)
    assert any(doc.path == "runtime/confluence/98765.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_confluence_batch_reports_partial_failures() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.ConfluenceClient.from_env", return_value=_MixedConfluenceClient()):
        response = client.post(
            "/api/ingest/confluence",
            json={"page_ids": ["12345", "broken"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "confluence"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 1

    success = next(item for item in payload["results"] if item["page_id"] == "12345")
    failure = next(item for item in payload["results"] if item["page_id"] == "broken")
    assert success["status"] == "ingested"
    assert success["title"] == "Runbook 12345"
    assert failure["status"] == "failed"
    assert "simulated confluence fetch failure" in failure["error"]

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/confluence/12345.md" for doc in docs)
    assert not any(doc.path == "runtime/confluence/broken.md" for doc in docs)
    _clear_runtime_documents()
