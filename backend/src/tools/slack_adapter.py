from __future__ import annotations

import os

import httpx

from src.tools.registry import ToolRegistryError


class SlackAdapter:
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
    def from_env(cls) -> "SlackAdapter":
        bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
        api_base_url = os.getenv("SLACK_API_BASE_URL", "https://slack.com/api").strip()

        if not bot_token:
            raise ToolRegistryError("SLACK_BOT_TOKEN is not configured")

        return cls(bot_token=bot_token, api_base_url=api_base_url or "https://slack.com/api")

    def fetch_channel_messages(self, *, channel: str, limit: int = 20) -> dict[str, object]:
        if not channel.strip():
            raise ToolRegistryError("channel is required for Slack message fetch")
        if limit <= 0:
            raise ToolRegistryError("limit must be a positive integer")

        url = f"{self.api_base_url}/conversations.history"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }
        params = {
            "channel": channel,
            "limit": limit,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise ToolRegistryError(f"Slack request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ToolRegistryError(f"Slack conversations.history failed with status {response.status_code}")

        body = response.json()
        if not bool(body.get("ok", False)):
            error_message = str(body.get("error", "unknown_error"))
            raise ToolRegistryError(f"Slack conversations.history failed: {error_message}")

        normalized_messages = self._normalize_messages(body.get("messages", []), limit)

        return {
            "status": "executed",
            "output": f"Fetched {len(normalized_messages)} Slack messages from channel {channel}.",
            "channel": channel,
            "message_count": len(normalized_messages),
            "has_more": bool(body.get("has_more", False)),
            "messages": normalized_messages,
        }

    def fetch_thread_messages(self, *, channel: str, thread_ts: str, limit: int = 20) -> dict[str, object]:
        if not channel.strip():
            raise ToolRegistryError("channel is required for Slack thread fetch")
        if not thread_ts.strip():
            raise ToolRegistryError("thread_ts is required for Slack thread fetch")
        if limit <= 0:
            raise ToolRegistryError("limit must be a positive integer")

        url = f"{self.api_base_url}/conversations.replies"
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }
        params = {
            "channel": channel,
            "ts": thread_ts,
            "limit": limit,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise ToolRegistryError(f"Slack request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ToolRegistryError(f"Slack conversations.replies failed with status {response.status_code}")

        body = response.json()
        if not bool(body.get("ok", False)):
            error_message = str(body.get("error", "unknown_error"))
            raise ToolRegistryError(f"Slack conversations.replies failed: {error_message}")

        normalized_messages = self._normalize_messages(body.get("messages", []), limit)

        return {
            "status": "executed",
            "output": f"Fetched {len(normalized_messages)} Slack thread messages from channel {channel}.",
            "channel": channel,
            "thread_ts": thread_ts,
            "message_count": len(normalized_messages),
            "has_more": bool(body.get("has_more", False)),
            "messages": normalized_messages,
        }

    def _normalize_messages(self, raw_messages: object, limit: int) -> list[dict[str, str]]:
        normalized_messages: list[dict[str, str]] = []
        if isinstance(raw_messages, list):
            for entry in raw_messages[:limit]:
                if not isinstance(entry, dict):
                    continue
                normalized_messages.append(
                    {
                        "ts": str(entry.get("ts", "")),
                        "user": str(entry.get("user", entry.get("username", ""))),
                        "text": str(entry.get("text", "")),
                    }
                )
        return normalized_messages
