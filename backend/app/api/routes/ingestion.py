from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.routes.chat import IncidentReport, kernel
from src.adapters.confluence_client import ConfluenceClient, ConfluenceClientError
from src.adapters.iris_client import IrisClient, IrisClientError
from src.memory.three_tier_memory import MemoryDocument

router = APIRouter()


class IngestIrisResponse(BaseModel):
    ingested_count: int
    source: str
    case_id: str
    incident_report: IncidentReport


class IngestConfluenceRequest(BaseModel):
    page_ids: list[str] = Field(min_length=1)

    @field_validator("page_ids")
    @classmethod
    def validate_page_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for page_id in value:
            normalized = page_id.strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)

        if not cleaned:
            raise ValueError("page_ids must contain at least one non-empty page id")
        return cleaned


class IngestConfluenceResult(BaseModel):
    page_id: str
    status: Literal["ingested", "failed"]
    title: str | None = None
    error: str | None = None


class IngestConfluenceResponse(BaseModel):
    ingested_count: int
    failed_count: int
    source: str
    results: list[IngestConfluenceResult]


@router.post("/ingest/iris", response_model=IngestIrisResponse)
def ingest_iris(case_id: str) -> IngestIrisResponse:
    try:
        client = IrisClient.from_env()
        case_payload = client.fetch_case(case_id=case_id)
        incident_report = IncidentReport(**case_payload)
    except (IrisClientError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    doc = MemoryDocument(
        title=f"IRIS Case {incident_report.case_id or case_id}",
        path=f"runtime/iris/{incident_report.case_id or case_id}.json",
        source_type="incidents",
        content=json.dumps(incident_report.model_dump(mode="json"), indent=2, ensure_ascii=False),
    )
    kernel.memory.ingest_runtime_document(doc)

    return IngestIrisResponse(
        ingested_count=1,
        source="iris",
        case_id=incident_report.case_id or case_id,
        incident_report=incident_report,
    )


@router.post("/ingest/confluence", response_model=IngestConfluenceResponse)
def ingest_confluence(payload: IngestConfluenceRequest) -> IngestConfluenceResponse:
    try:
        client = ConfluenceClient.from_env()
    except ConfluenceClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: list[IngestConfluenceResult] = []
    for page_id in payload.page_ids:
        try:
            page_payload = client.fetch_page(page_id=page_id)
            content = f"# {page_payload['title']}\n\n{page_payload['body']}\n\nSource: {page_payload['source_url']}\n"
            doc = MemoryDocument(
                title=page_payload["title"],
                path=f"runtime/confluence/{page_id}.md",
                source_type="confluence",
                content=content,
            )
            kernel.memory.ingest_runtime_document(doc)
            results.append(
                IngestConfluenceResult(
                    page_id=page_id,
                    status="ingested",
                    title=page_payload["title"],
                )
            )
        except Exception as exc:  # Keep batch ingestion resilient to per-page failures.
            results.append(
                IngestConfluenceResult(
                    page_id=page_id,
                    status="failed",
                    error=str(exc),
                )
            )

    ingested_count = len([item for item in results if item.status == "ingested"])
    failed_count = len(results) - ingested_count

    return IngestConfluenceResponse(
        ingested_count=ingested_count,
        failed_count=failed_count,
        source="confluence",
        results=results,
    )
