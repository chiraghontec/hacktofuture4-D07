from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.approvals import router as approvals_router
from app.api.routes.chat import router as chat_router
from app.api.routes.ingestion import router as ingestion_router

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional fallback if dependency is unavailable
    load_dotenv = None

if load_dotenv is not None:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")

app = FastAPI(title="UniOps API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router, prefix="/api")
app.include_router(ingestion_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
