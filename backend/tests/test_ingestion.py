from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes.chat import kernel
from app.main import app
from src.adapters.iris_client import IrisClientError
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

    def create_incident(
        self,
        *,
        case_name: str,
        case_description: str,
        severity: str,
        tags: list[str],
        case_customer: int,
        case_soc_id: str,
        classification_id: int | None,
        case_template_id: str | None,
        custom_attributes: dict[str, object] | None,
    ) -> dict:
        return {
            "source_system": "iris",
            "case_id": "9001",
            "report_id": "rep-9001",
            "report_url": "https://localhost/case/9001",
            "ingested_at": "2026-04-16T00:00:00Z",
            "case_name": case_name,
            "short_description": case_description,
            "severity": severity,
            "tags": tags,
            "iocs": [],
            "timeline": [],
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


class _FakeGitHubClient:
    def fetch_issue(self, *, repository: str, issue_number: int) -> dict:
        return {
            "repository": repository,
            "number": issue_number,
            "title": f"Issue {issue_number}",
            "state": "open",
            "url": f"https://github.com/{repository}/issues/{issue_number}",
            "body": "Sample GitHub issue body",
        }


class _MixedGitHubClient:
    def fetch_issue(self, *, repository: str, issue_number: int) -> dict:
        if issue_number == 404:
            raise RuntimeError("simulated github fetch failure")
        return {
            "repository": repository,
            "number": issue_number,
            "title": f"Issue {issue_number}",
            "state": "open",
            "url": f"https://github.com/{repository}/issues/{issue_number}",
            "body": "Sample GitHub issue body",
        }


class _FakeJiraClient:
    def fetch_issue(self, *, issue_key: str) -> dict:
        return {
            "key": issue_key,
            "summary": f"Summary for {issue_key}",
            "status": "To Do",
            "priority": "High",
            "assignee": "Demo User",
            "description": "Sample Jira issue description",
            "url": f"https://example.atlassian.net/browse/{issue_key}",
        }


class _MixedJiraClient:
    def fetch_issue(self, *, issue_key: str) -> dict:
        if issue_key == "OPS-404":
            raise RuntimeError("simulated jira fetch failure")
        return {
            "key": issue_key,
            "summary": f"Summary for {issue_key}",
            "status": "To Do",
            "priority": "High",
            "assignee": "Demo User",
            "description": "Sample Jira issue description",
            "url": f"https://example.atlassian.net/browse/{issue_key}",
        }


class _FakeSlackClient:
    def fetch_channel_messages(self, *, channel_id: str, limit: int = 20) -> dict:
        messages = [
            {"ts": "1712345678.100001", "thread_ts": "1712345678.100001", "user": "U123", "text": "Investigating"},
            {"ts": "1712345679.100002", "thread_ts": "1712345678.100001", "user": "U124", "text": "Rollback started"},
        ]
        return {
            "channel_id": channel_id,
            "message_count": min(len(messages), limit),
            "has_more": False,
            "messages": messages[:limit],
        }

    def fetch_thread_messages(self, *, channel_id: str, thread_ts: str, limit: int = 20) -> dict:
        messages = [
            {"ts": thread_ts, "thread_ts": thread_ts, "user": "U123", "text": "Primary alert thread"},
            {"ts": "1712345680.100003", "thread_ts": thread_ts, "user": "U124", "text": "Mitigation confirmed"},
        ]
        return {
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "message_count": min(len(messages), limit),
            "has_more": False,
            "messages": messages[:limit],
        }


class _MixedSlackClient:
    def fetch_channel_messages(self, *, channel_id: str, limit: int = 20) -> dict:
        if channel_id == "C-BROKEN":
            raise RuntimeError("simulated slack channel fetch failure")
        return {
            "channel_id": channel_id,
            "message_count": 1,
            "has_more": False,
            "messages": [{"ts": "1712345678.100001", "thread_ts": "1712345678.100001", "user": "U123", "text": "Investigating"}],
        }

    def fetch_thread_messages(self, *, channel_id: str, thread_ts: str, limit: int = 20) -> dict:
        if thread_ts == "1712345999.999999":
            raise RuntimeError("simulated slack thread fetch failure")
        return {
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "message_count": 1,
            "has_more": False,
            "messages": [{"ts": thread_ts, "thread_ts": thread_ts, "user": "U123", "text": "Thread message"}],
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


def test_create_iris_incident_adds_runtime_document() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.IrisClient.from_env", return_value=_FakeIrisClient()):
        response = client.post(
            "/api/incidents/create",
            json={
                "case_name": "Redis latency in production",
                "case_description": "P95 latency increased after deploy",
                "severity": "high",
                "tags": ["redis", "latency", "redis"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "iris"
    assert payload["case_id"] == "9001"
    assert payload["incident_report"]["case_name"] == "Redis latency in production"
    assert payload["incident_report"]["tags"] == ["redis", "latency"]

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/iris/9001.json" for doc in docs)
    _clear_runtime_documents()


def test_create_iris_incident_returns_502_on_upstream_failure() -> None:
    client = TestClient(app)

    with patch(
        "app.api.routes.ingestion.IrisClient.from_env",
        side_effect=IrisClientError("IRIS API unavailable"),
    ):
        response = client.post(
            "/api/incidents/create",
            json={
                "case_name": "Redis latency in production",
                "case_description": "P95 latency increased after deploy",
            },
        )

    assert response.status_code == 502
    assert "IRIS API unavailable" in response.json()["detail"]


def test_ingest_github_batch_adds_runtime_documents() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.GitHubClient.from_env", return_value=_FakeGitHubClient()):
        response = client.post(
            "/api/ingest/github",
            json={
                "issue_refs": [
                    {"repository": "org/repo", "issue_number": 101},
                    {"repository": "org/repo", "issue_number": 202},
                ]
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "github"
    assert payload["ingested_count"] == 2
    assert payload["failed_count"] == 0

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/github/org__repo-101.md" for doc in docs)
    assert any(doc.path == "runtime/github/org__repo-202.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_github_batch_reports_partial_failures() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.GitHubClient.from_env", return_value=_MixedGitHubClient()):
        response = client.post(
            "/api/ingest/github",
            json={
                "issue_refs": [
                    {"repository": "org/repo", "issue_number": 101},
                    {"repository": "org/repo", "issue_number": 404},
                ]
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "github"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 1

    success = next(item for item in payload["results"] if item["issue_number"] == 101)
    failure = next(item for item in payload["results"] if item["issue_number"] == 404)
    assert success["status"] == "ingested"
    assert failure["status"] == "failed"
    assert "simulated github fetch failure" in failure["error"]

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/github/org__repo-101.md" for doc in docs)
    assert not any(doc.path == "runtime/github/org__repo-404.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_jira_batch_adds_runtime_documents() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.JiraClient.from_env", return_value=_FakeJiraClient()):
        response = client.post(
            "/api/ingest/jira",
            json={"issue_keys": ["OPS-101", "OPS-202"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "jira"
    assert payload["ingested_count"] == 2
    assert payload["failed_count"] == 0

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/jira/OPS-101.md" for doc in docs)
    assert any(doc.path == "runtime/jira/OPS-202.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_jira_batch_reports_partial_failures() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.JiraClient.from_env", return_value=_MixedJiraClient()):
        response = client.post(
            "/api/ingest/jira",
            json={"issue_keys": ["OPS-101", "OPS-404"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "jira"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 1

    success = next(item for item in payload["results"] if item["issue_key"] == "OPS-101")
    failure = next(item for item in payload["results"] if item["issue_key"] == "OPS-404")
    assert success["status"] == "ingested"
    assert failure["status"] == "failed"
    assert "simulated jira fetch failure" in failure["error"]

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/jira/OPS-101.md" for doc in docs)
    assert not any(doc.path == "runtime/jira/OPS-404.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_slack_channels_adds_runtime_documents() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.SlackClient.from_env", return_value=_FakeSlackClient()):
        response = client.post(
            "/api/ingest/slack/channels",
            json={"channels": [{"channel_id": "C12345", "limit": 10}]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "slack"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 0

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/slack/channel-C12345.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_slack_channels_reports_partial_failures() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.SlackClient.from_env", return_value=_MixedSlackClient()):
        response = client.post(
            "/api/ingest/slack/channels",
            json={
                "channels": [
                    {"channel_id": "C12345", "limit": 10},
                    {"channel_id": "C-BROKEN", "limit": 10},
                ]
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "slack"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 1

    success = next(item for item in payload["results"] if item["channel_id"] == "C12345")
    failure = next(item for item in payload["results"] if item["channel_id"] == "C-BROKEN")
    assert success["status"] == "ingested"
    assert failure["status"] == "failed"
    assert "simulated slack channel fetch failure" in failure["error"]

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/slack/channel-C12345.md" for doc in docs)
    assert not any(doc.path == "runtime/slack/channel-C-BROKEN.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_slack_threads_adds_runtime_documents() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.SlackClient.from_env", return_value=_FakeSlackClient()):
        response = client.post(
            "/api/ingest/slack/threads",
            json={"threads": [{"channel_id": "C12345", "thread_ts": "1712345678.123456", "limit": 10}]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "slack"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 0

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/slack/thread-C12345-1712345678_123456.md" for doc in docs)
    _clear_runtime_documents()


def test_ingest_slack_threads_reports_partial_failures() -> None:
    _clear_runtime_documents()
    client = TestClient(app)

    with patch("app.api.routes.ingestion.SlackClient.from_env", return_value=_MixedSlackClient()):
        response = client.post(
            "/api/ingest/slack/threads",
            json={
                "threads": [
                    {"channel_id": "C12345", "thread_ts": "1712345678.123456", "limit": 10},
                    {"channel_id": "C12345", "thread_ts": "1712345999.999999", "limit": 10},
                ]
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "slack"
    assert payload["ingested_count"] == 1
    assert payload["failed_count"] == 1

    success = next(item for item in payload["results"] if item["thread_ts"] == "1712345678.123456")
    failure = next(item for item in payload["results"] if item["thread_ts"] == "1712345999.999999")
    assert success["status"] == "ingested"
    assert failure["status"] == "failed"
    assert "simulated slack thread fetch failure" in failure["error"]

    docs = kernel.memory.load_documents(force_reload=True)
    assert any(doc.path == "runtime/slack/thread-C12345-1712345678_123456.md" for doc in docs)
    assert not any(doc.path == "runtime/slack/thread-C12345-1712345999_999999.md" for doc in docs)
    _clear_runtime_documents()
