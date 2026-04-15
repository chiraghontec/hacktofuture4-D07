from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    answer: str
    trace_id: str
    needs_approval: bool


class ErrorResponse(BaseModel):
    error: str
    trace_id: str | None
    status_code: int


def _error_response(message: str, trace_id: str | None, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=message,
            trace_id=trace_id,
            status_code=status_code,
        ).model_dump(),
    )


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["chat"],
    summary="Submit chat query",
    description=(
        "Validates the user query and session id, then returns a baseline response "
        "with a generated trace id."
    ),
)
def chat(
    payload: ChatRequest = Body(
        ...,
        examples={
            "valid": {
                "summary": "Valid request",
                "value": {
                    "message": "Run the standard high-CPU runbook for service X",
                    "session_id": "550e8400-e29b-41d4-a716-446655440000",
                },
            },
            "invalid_session": {
                "summary": "Invalid session id",
                "value": {
                    "message": "Investigate Redis latency spike",
                    "session_id": "invalid-session",
                },
            },
        },
    )
) -> ChatResponse | JSONResponse:
    message = payload.message.strip()
    if not message:
        return _error_response(
            message="message must not be empty",
            trace_id=None,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not _is_uuid(payload.session_id):
        return _error_response(
            message="session_id must be a valid UUID string",
            trace_id=None,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return ChatResponse(
        answer=f"Received: {message}",
        trace_id=f"trace-{uuid4().hex[:12]}",
        needs_approval=False,
    )


@router.get(
    "/chat/stream",
    responses={501: {"model": ErrorResponse}},
    tags=["chat"],
    summary="Stream reasoning trace (stub)",
    description=(
        "Hour 0-2 stub endpoint for trace streaming. "
        "Returns not-implemented until SSE pipeline is wired in later phases."
    ),
)
def chat_stream(
    trace_id: str = Query(
        ...,
        min_length=1,
        description="Trace identifier returned from POST /api/chat",
        examples=["trace-2f9c8d20e5a1"],
    )
) -> JSONResponse:
    return _error_response(
        message="stream_not_implemented",
        trace_id=trace_id,
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
    )
