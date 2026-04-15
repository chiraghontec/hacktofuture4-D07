from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ChatResponse(BaseModel):
    answer: str
    trace_id: str
    needs_approval: bool


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer=f"Received: {payload.message}",
        trace_id="trace-dev-0001",
        needs_approval=False,
    )
