from __future__ import annotations

from src.tools.registry import ToolRegistry


class ActionExecutor:
    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()

    def _pick_tool(self, action: str) -> str:
        normalized = action.lower()
        if "rollback" in normalized or "revert" in normalized:
            return "github.mock.rollback_pr"
        if "slack" in normalized or "notify" in normalized:
            return "slack.mock.post_message"
        if "jira" in normalized or "issue" in normalized:
            return "jira.mock.update_issue"
        return self.registry.list_tools()[0]

    def execute(self, action_id: str, trace_id: str, action: str) -> dict:
        tool_name = self._pick_tool(action)
        available = self.registry.list_tools()
        if tool_name not in available:
            return {
                "action_id": action_id,
                "trace_id": trace_id,
                "action": action,
                "status": "failed",
                "tool": tool_name,
                "message": "Requested tool is not registered.",
            }

        return {
            "action_id": action_id,
            "trace_id": trace_id,
            "action": action,
            "status": "mock_executed",
            "tool": tool_name,
            "message": f"Executed using {tool_name} in mock mode.",
        }
