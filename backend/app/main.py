from typing import Any

from fastapi import FastAPI

from app.api.routes.chat import router as chat_router

app = FastAPI(
    title="UniOps API",
    version="0.1.0",
    description=(
        "UniOps backend API for operations copiloting. "
        "This phase exposes baseline chat and stream stub endpoints with validation."
    ),
    openapi_tags=[
        {"name": "system", "description": "Service status and platform health endpoints."},
        {"name": "chat", "description": "Chat and reasoning trace endpoints."},
    ],
)
app.include_router(chat_router, prefix="/api")


@app.get("/health", tags=["system"], summary="Service health check")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "uniops-backend",
        "version": app.version,
        "services": {
            "api": "up",
            "milvus": "unknown",
        },
    }
