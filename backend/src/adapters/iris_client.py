from __future__ import annotations

import os
from typing import Any

import httpx


class IrisClientError(RuntimeError):
    pass


class IrisClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        verify_ssl: bool = True,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_env(cls) -> "IrisClient":
        base_url = os.getenv("IRIS_BASE_URL", "").strip()
        api_key = os.getenv("IRIS_API_KEY", "").strip() or os.getenv("IRIS_API_TOKEN", "").strip()
        verify_ssl_env = os.getenv("IRIS_VERIFY_SSL", "true").strip().lower()
        verify_ssl = verify_ssl_env not in {"0", "false", "no"}

        if not base_url:
            raise IrisClientError("IRIS_BASE_URL is not configured")
        if not api_key:
            raise IrisClientError("IRIS_API_KEY is not configured")

        return cls(base_url=base_url, api_key=api_key, verify_ssl=verify_ssl)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_case_payload(self, payload: Any, case_id: str) -> dict[str, Any]:
        if isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                for item in data:
                    item_case_id = str(item.get("case_id", item.get("id", "")))
                    if item_case_id == case_id:
                        return item
                if data:
                    return data[0]

        raise IrisClientError("Unable to parse case payload from IRIS response")

    def fetch_case(self, case_id: str) -> dict[str, Any]:
        endpoints: list[tuple[str, str, dict[str, Any] | None]] = [
            ("POST", "/manage/cases/list?cid=1", {"case_id": case_id}),
            ("GET", f"/manage/cases/{case_id}?cid=1", None),
        ]

        last_error: str | None = None
        with httpx.Client(timeout=self.timeout_seconds, verify=self.verify_ssl) as client:
            for method, path, body in endpoints:
                url = f"{self.base_url}{path}"
                try:
                    response = client.request(method=method, url=url, json=body, headers=self._headers())
                    if response.status_code >= 400:
                        last_error = f"{method} {path} returned {response.status_code}"
                        continue

                    payload = response.json()
                    case_payload = self._extract_case_payload(payload, case_id)
                    return {
                        "source_system": "iris",
                        "case_id": str(case_payload.get("case_id", case_payload.get("id", case_id))),
                        "report_id": str(case_payload.get("report_id", case_payload.get("id", case_id))),
                        "report_url": case_payload.get("report_url") or f"{self.base_url}/case/{case_id}",
                        "ingested_at": case_payload.get("modification_date") or case_payload.get("created_at"),
                        "case_name": case_payload.get("case_name")
                        or case_payload.get("name")
                        or f"IRIS Case {case_id}",
                        "short_description": case_payload.get("case_description")
                        or case_payload.get("description")
                        or "No case description provided.",
                        "severity": str(case_payload.get("severity", "unknown")),
                        "tags": case_payload.get("tags", []),
                        "iocs": case_payload.get("iocs", []),
                        "timeline": case_payload.get("timeline", []),
                    }
                except (httpx.HTTPError, ValueError, IrisClientError) as exc:
                    last_error = str(exc)
                    continue

        raise IrisClientError(f"Failed to fetch case {case_id} from IRIS: {last_error or 'unknown error'}")
