from __future__ import annotations

from src.tools.executor import ToolExecutor
from src.tools.registry import ToolRegistry, ToolRegistryError


def test_tool_registry_register_and_execute() -> None:
    registry = ToolRegistry()
    registry.register_tool(
        name="example.tool",
        description="Example tool for registry tests.",
        read_only=True,
        handler=lambda params: {"status": "executed", "output": f"processed:{params['value']}"},
    )

    assert registry.list_tools() == ["example.tool"]
    result = registry.execute_tool("example.tool", {"value": "ok"})

    assert result["tool"] == "example.tool"
    assert result["status"] == "executed"
    assert result["output"] == "processed:ok"


def test_tool_registry_rejects_unknown_tool() -> None:
    registry = ToolRegistry()

    try:
        registry.execute_tool("unknown.tool", {})
        assert False, "Expected ToolRegistryError for unknown tool"
    except ToolRegistryError as exc:
        assert "not registered" in str(exc)


def test_executor_maps_multi_tool_action_and_executes_in_order(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("GITHUB_ISSUE_NUMBER", "123")
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C001")
    monkeypatch.setenv("SLACK_THREAD_TS", "1712345678.123456")
    monkeypatch.setenv("SLACK_CONTEXT_LIMIT", "5")

    call_order: list[str] = []
    registry = ToolRegistry()

    def _github_handler(params: dict[str, object]) -> dict[str, object]:
        call_order.append("github.fetch_issue")
        assert params["repository"] == "org/repo"
        assert params["issue_number"] == 123
        return {"status": "executed", "output": "github ok"}

    def _slack_handler(params: dict[str, object]) -> dict[str, object]:
        call_order.append("slack.fetch_thread_messages")
        assert params["channel"] == "C001"
        assert params["thread_ts"] == "1712345678.123456"
        assert params["limit"] == 5
        return {"status": "executed", "output": "slack ok"}

    def _jira_handler(params: dict[str, object]) -> dict[str, object]:
        call_order.append("jira.fetch_issue")
        assert params["issue_key"] == "OPS-101"
        return {"status": "executed", "output": "jira ok"}

    registry.register_tool(
        name="github.fetch_issue",
        description="GitHub issue fetch",
        read_only=True,
        handler=_github_handler,
    )
    registry.register_tool(
        name="slack.fetch_thread_messages",
        description="Slack thread fetch",
        read_only=True,
        handler=_slack_handler,
    )
    registry.register_tool(
        name="jira.fetch_issue",
        description="Jira issue fetch",
        read_only=True,
        handler=_jira_handler,
    )

    executor = ToolExecutor(registry=registry)
    result = executor.execute("Create rollback PR, fetch Slack thread, and update Jira OPS-101")

    assert result["status"] == "executed"
    assert len(result["details"]) == 3
    assert [item["tool"] for item in result["details"]] == [
        "github.fetch_issue",
        "slack.fetch_thread_messages",
        "jira.fetch_issue",
    ]
    assert call_order == [
        "github.fetch_issue",
        "slack.fetch_thread_messages",
        "jira.fetch_issue",
    ]


def test_executor_fails_when_jira_keyword_has_no_issue_key(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C001")

    registry = ToolRegistry()
    registry.register_tool(
        name="jira.fetch_issue",
        description="Jira issue fetch",
        read_only=True,
        handler=lambda params: {"status": "executed", "output": "ok"},
    )

    executor = ToolExecutor(registry=registry)
    result = executor.execute("Notify Jira about incident update")

    assert result["status"] == "failed"
    assert "No Jira issue key found" in result["output"]


def test_executor_fails_when_slack_thread_target_missing(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C001")
    monkeypatch.delenv("SLACK_THREAD_TS", raising=False)

    registry = ToolRegistry()
    registry.register_tool(
        name="slack.fetch_thread_messages",
        description="Slack thread fetch",
        read_only=True,
        handler=lambda params: {"status": "executed", "output": "ok"},
    )

    executor = ToolExecutor(registry=registry)
    result = executor.execute("Fetch Slack thread for incident response")

    assert result["status"] == "failed"
    assert "SLACK_THREAD_TS" in result["output"]


def test_executor_fails_fast_when_required_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_ISSUE_NUMBER", raising=False)

    registry = ToolRegistry()
    registry.register_tool(
        name="github.fetch_issue",
        description="GitHub issue fetch",
        read_only=True,
        handler=lambda params: {"status": "executed", "output": "ok"},
    )

    executor = ToolExecutor(registry=registry)
    result = executor.execute("Create rollback PR")

    assert result["status"] == "failed"
    assert "GITHUB_REPOSITORY" in result["output"]


def test_executor_supports_confluence_read_only_dispatch(monkeypatch) -> None:
    monkeypatch.setenv("CONFLUENCE_PAGE_ID", "65868")

    registry = ToolRegistry()
    registry.register_tool(
        name="confluence.fetch_page",
        description="Confluence read-only page fetch",
        read_only=True,
        handler=lambda params: {
            "status": "executed",
            "output": f"Fetched {params['page_id']}",
        },
    )

    executor = ToolExecutor(registry=registry)
    result = executor.execute("Fetch confluence runbook page")

    assert result["status"] == "executed"
    assert len(result["details"]) == 1
    assert result["details"][0]["tool"] == "confluence.fetch_page"


def test_executor_maps_iris_create_incident(monkeypatch) -> None:
    monkeypatch.setenv("IRIS_CASE_CUSTOMER_ID", "1")
    monkeypatch.setenv("IRIS_CASE_SOC_ID", "")

    registry = ToolRegistry()
    captured: dict[str, object] = {}

    def _iris_handler(params: dict[str, object]) -> dict[str, object]:
        captured.update(params)
        return {
            "status": "executed",
            "output": "Created IRIS incident 9001",
            "incident": {"case_id": "9001"},
        }

    registry.register_tool(
        name="iris.create_incident",
        description="IRIS mutation",
        read_only=False,
        handler=_iris_handler,
    )

    executor = ToolExecutor(registry=registry)
    result = executor.execute('Create incident for redis latency in prod "Redis Latency Spike"')

    assert result["status"] == "executed"
    assert len(result["details"]) == 1
    assert result["details"][0]["tool"] == "iris.create_incident"
    assert captured["case_name"] == "Redis Latency Spike"
    assert captured["severity"] == "medium"
