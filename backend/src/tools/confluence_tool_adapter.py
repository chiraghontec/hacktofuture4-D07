from __future__ import annotations

from src.adapters.confluence_client import ConfluenceClient
from src.tools.registry import ToolRegistryError


class ConfluenceToolAdapter:
    def __init__(self, *, client: ConfluenceClient | None = None) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "ConfluenceToolAdapter":
        return cls(client=ConfluenceClient.from_env())

    def fetch_page(self, *, page_id: str) -> dict[str, str]:
        if not page_id.strip():
            raise ToolRegistryError("page_id is required for Confluence page fetch")

        client = self._client or ConfluenceClient.from_env()

        try:
            payload = client.fetch_page(page_id=page_id)
        except Exception as exc:
            raise ToolRegistryError(f"Confluence page fetch failed: {exc}") from exc

        title = str(payload.get("title", f"Confluence Page {page_id}"))
        source_url = str(payload.get("source_url", ""))
        return {
            "status": "executed",
            "output": f"Fetched Confluence page {page_id}: {title}.",
            "page_id": page_id,
            "title": title,
            "source_url": source_url,
        }
