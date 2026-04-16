from __future__ import annotations

import os
from typing import Any

import httpx


class GitHubClientError(RuntimeError):
    pass


class GitHubClient:
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
    def from_env(cls) -> "GitHubClient":
        token = os.getenv("GITHUB_TOKEN", "").strip()
        api_base_url = os.getenv("GITHUB_API_BASE_URL", "https://api.github.com").strip()

        if not token:
            raise GitHubClientError("GITHUB_TOKEN is not configured")

        return cls(token=token, api_base_url=api_base_url or "https://api.github.com")

    def fetch_issue(self, *, repository: str, issue_number: int) -> dict[str, Any]:
        normalized_repo = repository.strip()
        if not normalized_repo:
            raise GitHubClientError("repository is required")
        if issue_number <= 0:
            raise GitHubClientError("issue_number must be a positive integer")

        url = f"{self.api_base_url}/repos/{normalized_repo}/issues/{issue_number}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubClientError(f"GitHub request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise GitHubClientError("GitHub issue fetch failed: authentication or permission error")
        if response.status_code == 404:
            raise GitHubClientError(f"GitHub issue {normalized_repo}#{issue_number} was not found")
        if response.status_code >= 500:
            raise GitHubClientError(f"GitHub service error while fetching {normalized_repo}#{issue_number}")
        if response.status_code >= 400:
            raise GitHubClientError(f"GitHub issue fetch failed with status {response.status_code}")

        body = response.json()
        issue_url = str(body.get("html_url", "")).strip() or f"https://github.com/{normalized_repo}/issues/{issue_number}"
        title = str(body.get("title", "")).strip()
        state = str(body.get("state", "unknown")).strip() or "unknown"
        issue_body = str(body.get("body", "")).strip()

        return {
            "repository": normalized_repo,
            "number": issue_number,
            "title": title,
            "state": state,
            "url": issue_url,
            "body": issue_body,
        }
