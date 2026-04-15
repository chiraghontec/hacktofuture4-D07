from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.controller.controller import ControllerKernel
from src.gates.approval_queue import ApprovalQueue
from src.gates.executor import ActionExecutor
from src.gates.permission_gate import PermissionGate, PermissionRequest
from src.memory.three_tier_memory import ThreeTierMemory

router = APIRouter()
kernel = ControllerKernel()
memory = ThreeTierMemory()
queue_manager = ApprovalQueue()
action_executor = ActionExecutor()
permission_gate = PermissionGate()


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    answer: str
    trace_id: str
    needs_approval: bool


class ApproveActionRequest(BaseModel):
    decided_by: str = "human"


class RejectActionRequest(BaseModel):
    decided_by: str = "human"
    reason: str | None = None


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    result = kernel.handle_query(query=payload.message, session_id=payload.session_id)

    if result.needs_approval:
        decision = permission_gate.evaluate(
            PermissionRequest(trace_id=result.trace_id, action=result.suggested_action)
        )
        queue_manager.enqueue(
            trace_id=result.trace_id,
            action=result.suggested_action,
            risk_level=decision["risk_level"],
            reason=decision["reason"],
        )

    return ChatResponse(
        answer=result.answer,
        trace_id=result.trace_id,
        needs_approval=result.needs_approval,
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


@router.get("/actions/pending")
def list_pending_actions() -> dict:
    return {"actions": queue_manager.list_pending()}


@router.post("/actions/{action_id}/approve")
def approve_action(action_id: str, payload: ApproveActionRequest) -> dict:
    approved = queue_manager.approve(action_id=action_id, decided_by=payload.decided_by)
    if approved is None:
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")

    execution = action_executor.execute(
        action_id=approved["id"],
        trace_id=approved["trace_id"],
        action=approved["action"],
    )
    return {
        "action_id": action_id,
        "status": "executed",
        "execution": execution,
    }


@router.post("/actions/{action_id}/reject")
def reject_action(action_id: str, payload: RejectActionRequest) -> dict:
    rejected = queue_manager.reject(
        action_id=action_id,
        decided_by=payload.decided_by,
        reason=payload.reason,
    )
    if rejected is None:
        raise HTTPException(status_code=404, detail=f"action {action_id} not found")

    return {
        "action_id": action_id,
        "status": "rejected",
        "rejection_reason": rejected.get("rejection_reason"),
    }
