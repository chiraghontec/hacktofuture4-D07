from __future__ import annotations

import os
from typing import Any

import httpx


class SlackClientError(RuntimeError):
    pass


class SlackClient:
    def __init__(
        self,
        *,
        bot_token: str,
        api_base_url: str = "https://slack.com/api",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.bot_token = bot_token
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "SlackClient":
        bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
        api_base_url = os.getenv("SLACK_API_BASE_URL", "https://slack.com/api").strip()

        if not bot_token:
            raise SlackClientError("SLACK_BOT_TOKEN is not configured")

        return cls(bot_token=bot_token, api_base_url=api_base_url or "https://slack.com/api")

    def fetch_channel_messages(self, *, channel_id: str, limit: int = 20) -> dict[str, Any]:
        normalized_channel = channel_id.strip()
        if not normalized_channel:
            raise SlackClientError("channel_id is required")
        if limit <= 0:
            raise SlackClientError("limit must be a positive integer")

        body = self._request(
            endpoint="/conversations.history",
            params={"channel": normalized_channel, "limit": limit},
        )

        messages = self._normalize_messages(body.get("messages", []), limit)
        return {
            "channel_id": normalized_channel,
            "message_count": len(messages),
            "has_more": bool(body.get("has_more", False)),
            "messages": messages,
        }

    def fetch_thread_messages(self, *, channel_id: str, thread_ts: str, limit: int = 20) -> dict[str, Any]:
        normalized_channel = channel_id.strip()
        normalized_thread_ts = thread_ts.strip()
        if not normalized_channel:
            raise SlackClientError("channel_id is required")
        if not normalized_thread_ts:
            raise SlackClientError("thread_ts is required")
        if limit <= 0:
            raise SlackClientError("limit must be a positive integer")

        body = self._request(
            endpoint="/conversations.replies",
            params={"channel": normalized_channel, "ts": normalized_thread_ts, "limit": limit},
        )

        messages = self._normalize_messages(body.get("messages", []), limit)
        return {
            "channel_id": normalized_channel,
            "thread_ts": normalized_thread_ts,
            "message_count": len(messages),
            "has_more": bool(body.get("has_more", False)),
            "messages": messages,
        }

    def _request(self, *, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise SlackClientError(f"Slack request failed: {exc}") from exc

        if response.status_code >= 400:
            raise SlackClientError(f"Slack API call failed with status {response.status_code}")

        body = response.json()
        if not bool(body.get("ok", False)):
            error_message = str(body.get("error", "unknown_error"))
            raise SlackClientError(f"Slack API call failed: {error_message}")

        return body

    def _normalize_messages(self, raw_messages: object, limit: int) -> list[dict[str, str]]:
        normalized_messages: list[dict[str, str]] = []
        if isinstance(raw_messages, list):
            for entry in raw_messages[:limit]:
                if not isinstance(entry, dict):
                    continue
                normalized_messages.append(
                    {
                        "ts": str(entry.get("ts", "")),
                        "thread_ts": str(entry.get("thread_ts", entry.get("ts", ""))),
                        "user": str(entry.get("user", entry.get("username", ""))),
                        "text": str(entry.get("text", "")),
                    }
                )

        return normalized_messages