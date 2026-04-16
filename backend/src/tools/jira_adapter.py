from __future__ import annotations

import os
import re

import httpx

from src.tools.registry import ToolRegistryError


JIRA_ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")


class JiraAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        api_token: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "JiraAdapter":
        base_url = os.getenv("JIRA_BASE_URL", "").strip()
        email = os.getenv("JIRA_EMAIL", "").strip()
        api_token = os.getenv("JIRA_API_TOKEN", "").strip()

        if not base_url:
            raise ToolRegistryError("JIRA_BASE_URL is not configured")
        if not email:
            raise ToolRegistryError("JIRA_EMAIL is not configured")
        if not api_token:
            raise ToolRegistryError("JIRA_API_TOKEN is not configured")

        return cls(base_url=base_url, email=email, api_token=api_token)

    def fetch_issue(self, *, issue_key: str) -> dict[str, object]:
        normalized_issue_key = issue_key.strip().upper()
        if not normalized_issue_key:
            raise ToolRegistryError("issue_key is required for Jira issue fetch")
        if not JIRA_ISSUE_KEY_PATTERN.match(normalized_issue_key):
            raise ToolRegistryError(
                f"issue_key '{issue_key}' does not match expected format PROJECT-123"
            )

        url = f"{self.base_url}/rest/api/3/issue/{normalized_issue_key}"
        auth = httpx.BasicAuth(username=self.email, password=self.api_token)
        params = {
            "fields": "summary,status,priority,assignee",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=params, auth=auth)
        except httpx.HTTPError as exc:
            raise ToolRegistryError(f"Jira request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise ToolRegistryError("Jira issue fetch failed: authentication or permission error")
        if response.status_code == 404:
            raise ToolRegistryError(f"Jira issue {normalized_issue_key} was not found")
        if response.status_code >= 500:
            raise ToolRegistryError(f"Jira service error while fetching {normalized_issue_key}")
        if response.status_code >= 400:
            raise ToolRegistryError(f"Jira issue fetch failed with status {response.status_code}")

        body = response.json()
        fields = body.get("fields", {})
        if not isinstance(fields, dict):
            fields = {}

        status_block = fields.get("status", {})
        priority_block = fields.get("priority", {})
        assignee_block = fields.get("assignee", {})

        status_name = str(status_block.get("name", "")) if isinstance(status_block, dict) else ""
        priority_name = str(priority_block.get("name", "")) if isinstance(priority_block, dict) else ""
        assignee_name = str(assignee_block.get("displayName", "")) if isinstance(assignee_block, dict) else ""

        return {
            "status": "executed",
            "output": f"Fetched Jira issue {normalized_issue_key}.",
            "issue": {
                "key": normalized_issue_key,
                "summary": str(fields.get("summary", "")),
                "status": status_name,
                "priority": priority_name,
                "assignee": assignee_name,
            },
        }
