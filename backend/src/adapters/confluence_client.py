from __future__ import annotations

import os
from typing import Any

import httpx


class ConfluenceClientError(RuntimeError):
    pass


class ConfluenceClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        email: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.email = email
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "ConfluenceClient":
        base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip() or os.getenv("CLOUDFLUENCE_BASE_URL", "").strip()
        api_token = os.getenv("CONFLUENCE_API_TOKEN", "").strip() or os.getenv("CLOUDFLUENCE_API_TOKEN", "").strip()
        email = os.getenv("CONFLUENCE_EMAIL", "").strip()

        if not base_url:
            raise ConfluenceClientError("CONFLUENCE_BASE_URL is not configured")
        if not api_token:
            raise ConfluenceClientError("CONFLUENCE_API_TOKEN is not configured")
        if not email:
            raise ConfluenceClientError("CONFLUENCE_EMAIL is not configured")

        return cls(base_url=base_url, api_token=api_token, email=email)

    def fetch_page(self, page_id: str) -> dict[str, str]:
        auth = httpx.BasicAuth(username=self.email, password=self.api_token)
        candidates = [
            f"/wiki/api/v2/pages/{page_id}?body-format=storage",
            f"/rest/api/content/{page_id}?expand=body.storage",
        ]

        last_error: str | None = None
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for path in candidates:
                url = f"{self.base_url}{path}"
                try:
                    response = client.get(url, auth=auth)
                    if response.status_code >= 400:
                        last_error = f"GET {path} returned {response.status_code}"
                        continue

                    payload = response.json()
                    title = payload.get("title", f"Confluence Page {page_id}")

                    body = ""
                    body_obj: Any = payload.get("body", {})
                    if isinstance(body_obj, dict):
                        if "storage" in body_obj and isinstance(body_obj["storage"], dict):
                            body = str(body_obj["storage"].get("value", ""))
                        elif "value" in body_obj:
                            body = str(body_obj.get("value", ""))

                    webui = payload.get("_links", {}).get("webui") if isinstance(payload.get("_links"), dict) else None
                    source_url = f"{self.base_url}{webui}" if isinstance(webui, str) else f"{self.base_url}/wiki/spaces/{page_id}"

                    return {
                        "page_id": page_id,
                        "title": title,
                        "body": body,
                        "source_url": source_url,
                    }
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = str(exc)
                    continue

        raise ConfluenceClientError(
            f"Failed to fetch Confluence page {page_id}: {last_error or 'unknown error'}"
        )
