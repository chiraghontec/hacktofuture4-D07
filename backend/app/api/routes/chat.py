from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, model_validator
from sse_starlette.sse import EventSourceResponse

from src.controller.controller import ControllerKernel
from src.memory.three_tier_memory import ThreeTierMemory

router = APIRouter()
kernel = ControllerKernel()
memory = ThreeTierMemory()


class IncidentReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_system: str = "iris"
    case_id: str | None = None
    report_id: str | None = None
    report_url: str | None = None
    ingested_at: str | None = None
    case_name: str
    short_description: str
    severity: str
    tags: list[str]
    iocs: list[Any]
    timeline: list[Any]


class ChatRequest(BaseModel):
    message: str | None = None
    session_id: str
    incident_report: IncidentReport | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "ChatRequest":
        has_message = bool(self.message and self.message.strip())
        has_incident_report = self.incident_report is not None
        if not has_message and not has_incident_report:
            raise ValueError("Either message or incident_report must be provided.")
        return self


class ChatResponse(BaseModel):
    answer: str
    trace_id: str
    needs_approval: bool
    dedup_summary: dict[str, Any]


def _stable_json(items: list[Any]) -> str:
    return json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def incident_report_to_query(report: IncidentReport) -> str:
    lines = [
        "IRIS Incident Report",
        f"Source System: {report.source_system}",
        f"Case Name: {report.case_name}",
        f"Short Description: {report.short_description}",
        f"Severity: {report.severity}",
        f"Tags: {', '.join(report.tags) if report.tags else 'none'}",
        f"IOCs: {_stable_json(report.iocs)}",
        f"Timeline: {_stable_json(report.timeline)}",
    ]

    if report.case_id:
        lines.append(f"Case ID: {report.case_id}")
    if report.report_id:
        lines.append(f"Report ID: {report.report_id}")
    if report.report_url:
        lines.append(f"Report URL: {report.report_url}")
    if report.ingested_at:
        lines.append(f"Ingested At: {report.ingested_at}")

    return "\n".join(lines)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    query = payload.message.strip() if payload.message else ""
    if payload.incident_report is not None:
        query = incident_report_to_query(payload.incident_report)

    result = kernel.handle_query(query=query, session_id=payload.session_id)
    return ChatResponse(
        answer=result.answer,
        trace_id=result.trace_id,
        needs_approval=result.needs_approval,
        dedup_summary=result.dedup_summary,
    )


def _to_stream_payload(step: dict) -> dict[str, object]:
    return {
        "step": step.get("step", ""),
        "agent": step.get("agent", ""),
        "observation": step.get("observation", ""),
        "sources": step.get("sources", []),
    }


@router.get("/chat/transcript/{trace_id}")
def get_transcript(trace_id: str) -> dict:
    transcript = memory.get_transcript(trace_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail=f"trace {trace_id} not found")
    return transcript


@router.get("/chat/stream")
async def stream_chat_trace(trace_id: str) -> EventSourceResponse:
    transcript = memory.get_transcript(trace_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail=f"trace {trace_id} not found")

    async def event_generator():
        for step in transcript.get("steps", []):
            yield {
                "event": "trace_step",
                "data": json.dumps(_to_stream_payload(step)),
            }

    return EventSourceResponse(event_generator())
