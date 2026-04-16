from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional fallback if dependency is unavailable
    load_dotenv = None

if load_dotenv is not None:
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env")

# Import routes only after environment variables are loaded.
# The chat router initializes a shared ControllerKernel at import time,
# so LLM_PROVIDER/GROQ_* must be available first.
from app.api.routes.approvals import router as approvals_router
from app.api.routes.chat import router as chat_router
from app.api.routes.ingestion import router as ingestion_router

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
