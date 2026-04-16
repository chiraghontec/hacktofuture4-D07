from __future__ import annotations

import os

import httpx

from src.tools.registry import ToolRegistryError


class GitHubAdapter:
    def __init__(
        self,
        *,
        token: str,
        api_base_url: str = "https://api.github.com",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.token = token
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "GitHubAdapter":
        token = os.getenv("GITHUB_TOKEN", "").strip()
        api_base_url = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com").strip()

        if not token:
            raise ToolRegistryError("GITHUB_TOKEN is not configured")

        return cls(token=token, api_base_url=api_base_url or "https://api.github.com")

    def fetch_issue(self, *, repository: str, issue_number: int) -> dict[str, object]:
        if not repository.strip():
            raise ToolRegistryError("repository is required for GitHub issue fetch")
        if issue_number <= 0:
            raise ToolRegistryError("issue_number must be a positive integer")

        url = f"{self.api_base_url}/repos/{repository}/issues/{issue_number}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise ToolRegistryError(f"GitHub request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ToolRegistryError(f"GitHub issue fetch failed with status {response.status_code}")

        body = response.json()
        issue_url = str(body.get("html_url", "")).strip() or f"https://github.com/{repository}/issues/{issue_number}"
        title = str(body.get("title", "")).strip()
        state = str(body.get("state", "unknown")).strip() or "unknown"

        return {
            "status": "executed",
            "output": f"Fetched GitHub issue {repository}#{issue_number}.",
            "issue": {
                "repository": repository,
                "number": issue_number,
                "title": title,
                "state": state,
                "url": issue_url,
            },
        }
