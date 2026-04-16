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

    _SEVERITY_TO_ID = {
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 4,
    }

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

    def _normalize_case_payload(
        self,
        *,
        case_payload: dict[str, Any],
        fallback_case_id: str,
        fallback_case_name: str,
        fallback_description: str,
        fallback_severity: str,
        fallback_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        case_id = str(case_payload.get("case_id", case_payload.get("id", fallback_case_id)))
        return {
            "source_system": "iris",
            "case_id": case_id,
            "report_id": str(case_payload.get("report_id", case_payload.get("id", case_id))),
            "report_url": case_payload.get("report_url") or f"{self.base_url}/case/{case_id}",
            "ingested_at": case_payload.get("modification_date") or case_payload.get("created_at"),
            "case_name": case_payload.get("case_name") or case_payload.get("name") or fallback_case_name,
            "short_description": case_payload.get("case_description")
            or case_payload.get("description")
            or fallback_description,
            "severity": str(case_payload.get("severity", fallback_severity)),
            "tags": case_payload.get("tags") or fallback_tags or [],
            "iocs": case_payload.get("iocs", []),
            "timeline": case_payload.get("timeline", []),
        }

    def _severity_id_from_label(self, severity: str) -> int:
        normalized = severity.strip().lower()
        if normalized in self._SEVERITY_TO_ID:
            return self._SEVERITY_TO_ID[normalized]

        if normalized.isdigit() and int(normalized) > 0:
            return int(normalized)

        return self._SEVERITY_TO_ID["medium"]

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
                    return self._normalize_case_payload(
                        case_payload=case_payload,
                        fallback_case_id=case_id,
                        fallback_case_name=f"IRIS Case {case_id}",
                        fallback_description="No case description provided.",
                        fallback_severity="unknown",
                    )
                except (httpx.HTTPError, ValueError, IrisClientError) as exc:
                    last_error = str(exc)
                    continue

        raise IrisClientError(f"Failed to fetch case {case_id} from IRIS: {last_error or 'unknown error'}")

    def create_incident(
        self,
        *,
        case_name: str,
        case_description: str,
        severity: str = "medium",
        tags: list[str] | None = None,
        case_customer: int = 1,
        case_soc_id: str = "",
        classification_id: int | None = None,
        case_template_id: str | None = None,
        custom_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized_name = case_name.strip()
        normalized_description = case_description.strip()
        if not normalized_name:
            raise IrisClientError("case_name must be provided")
        if not normalized_description:
            raise IrisClientError("case_description must be provided")

        payload: dict[str, Any] = {
            "case_name": normalized_name,
            "case_description": normalized_description,
            "case_customer": case_customer,
            "case_soc_id": case_soc_id,
            "severity_id": self._severity_id_from_label(severity),
        }

        if tags:
            payload["case_tags"] = ",".join(item.strip() for item in tags if item.strip())
        if classification_id is not None:
            payload["classification_id"] = classification_id
        if case_template_id:
            payload["case_template_id"] = str(case_template_id)
        if custom_attributes is not None:
            payload["custom_attributes"] = custom_attributes

        endpoints: list[tuple[str, str]] = [
            ("POST", "/manage/cases/add"),
        ]

        last_error: str | None = None
        with httpx.Client(timeout=self.timeout_seconds, verify=self.verify_ssl) as client:
            for method, path in endpoints:
                url = f"{self.base_url}{path}"
                try:
                    response = client.request(method=method, url=url, json=payload, headers=self._headers())
                    if response.status_code >= 400:
                        last_error = f"{method} {path} returned {response.status_code}"
                        continue

                    body = response.json()
                    case_payload = self._extract_case_payload(body, case_id="new")
                    created_case_id = str(case_payload.get("case_id", case_payload.get("id", "new")))
                    return self._normalize_case_payload(
                        case_payload=case_payload,
                        fallback_case_id=created_case_id,
                        fallback_case_name=normalized_name,
                        fallback_description=normalized_description,
                        fallback_severity=severity,
                        fallback_tags=tags,
                    )
                except (httpx.HTTPError, ValueError, IrisClientError) as exc:
                    last_error = str(exc)
                    continue

        raise IrisClientError(f"Failed to create IRIS incident: {last_error or 'unknown error'}")
