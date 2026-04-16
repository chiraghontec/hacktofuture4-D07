from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.routes.chat import memory
from src.tools.executor import MockToolExecutor

router = APIRouter()
executor = MockToolExecutor()


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    approver_id: str
    comment: str | None = None


class ApprovalDecisionResponse(BaseModel):
    trace_id: str
    final_status: str
    approval: dict
    execution_result: dict


@router.post("/approvals/{trace_id}", response_model=ApprovalDecisionResponse)
def submit_approval(trace_id: str, payload: ApprovalDecisionRequest) -> ApprovalDecisionResponse:
    transcript = memory.get_transcript(trace_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail=f"trace {trace_id} not found")

    suggested_action = str(transcript.get("suggested_action", "")).strip()
    action_details = transcript.get("action_details") if isinstance(transcript.get("action_details"), dict) else None
    if not suggested_action and not action_details:
        raise HTTPException(status_code=409, detail="trace does not contain a suggested action")

    if not suggested_action and action_details is not None:
        suggested_action = str(action_details.get("intent") or "execute approved action")

    approval = {
        "decision": payload.decision,
        "approver_id": payload.approver_id,
        "comment": payload.comment or "",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if payload.decision == "reject":
        execution_result = {
            "tool": "none",
            "status": "rejected",
            "output": "Action was rejected by approver. No execution performed.",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        final_status = "rejected"
    else:
        execution_result = executor.execute(suggested_action, action_details=action_details)
        final_status = "executed"

    memory.persist_approval_decision(
        trace_id=trace_id,
        approval=approval,
        execution_result=execution_result,
        final_status=final_status,
    )

    return ApprovalDecisionResponse(
        trace_id=trace_id,
        final_status=final_status,
        approval=approval,
        execution_result=execution_result,
    )
