from __future__ import annotations

from datetime import UTC, datetime


class MockToolExecutor:
    def execute(self, action: str, action_details: dict | None = None) -> dict[str, str]:
        normalized = action.lower()
        timestamp = datetime.now(UTC).isoformat()
        tool_hint = str((action_details or {}).get("tool", "")).strip().lower()

        if tool_hint == "github.mock.rollback_pr":
            return {
                "tool": "github.mock.rollback_pr",
                "status": "executed",
                "output": "Mock rollback PR created successfully.",
                "timestamp": timestamp,
            }

        if tool_hint == "slack.mock.post_message":
            return {
                "tool": "slack.mock.post_message",
                "status": "executed",
                "output": "Mock Slack incident update posted.",
                "timestamp": timestamp,
            }

        if tool_hint == "jira.mock.update_issue":
            return {
                "tool": "jira.mock.update_issue",
                "status": "executed",
                "output": "Mock Jira issue updated.",
                "timestamp": timestamp,
            }

        if "rollback" in normalized or "pr" in normalized:
            return {
                "tool": "github.mock.rollback_pr",
                "status": "executed",
                "output": "Mock rollback PR created successfully.",
                "timestamp": timestamp,
            }

        if "slack" in normalized or "post" in normalized:
            return {
                "tool": "slack.mock.post_message",
                "status": "executed",
                "output": "Mock Slack incident update posted.",
                "timestamp": timestamp,
            }

        if "jira" in normalized or "ticket" in normalized or "issue" in normalized or "update" in normalized:
            return {
                "tool": "jira.mock.update_issue",
                "status": "executed",
                "output": "Mock Jira issue updated.",
                "timestamp": timestamp,
            }

        return {
            "tool": "generic.mock.noop",
            "status": "executed",
            "output": "Mock action executed with no external side effects.",
            "timestamp": timestamp,
        }
