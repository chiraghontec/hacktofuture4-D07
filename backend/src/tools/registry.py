class ToolRegistry:
    def list_tools(self) -> list[str]:
        return [
            "github.mock.rollback_pr",
            "slack.mock.post_message",
            "jira.mock.update_issue",
        ]
