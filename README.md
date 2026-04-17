# hacktofuture4 — D07

Monorepo scaffold for the HackToFuture 4 (D07) build, designed for fast parallel development across frontend and backend.

## Repository Structure

```text
.
├── frontend/                # Next.js app
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── tests/
├── backend/                 # FastAPI API + orchestration
│   ├── app/
│   │   └── api/routes/
│   ├── src/
│   │   ├── controller/
│   │   ├── swarms/
│   │   ├── gates/
│   │   ├── memory/
│   │   └── tools/
│   └── tests/
├── shared/
│   └── contracts/           # Shared integration boundary
├── data/                    # Sample/source data
│   ├── confluence/
│   ├── runbooks/
│   ├── incidents/
│   ├── github/
│   └── slack/
├── infra/
│   └── docker-compose.yml
├── scripts/
└── docs/
    ├── UniOps PRD.md
    └── ways-of-working/
```

## Quick Start

### Option A: Docker Compose (recommended)

From the repository root:

```bash
make up
```

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- Milvus: localhost:19530

### Option B: Run services separately

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Current MVP Scaffold

- FastAPI app with `/health` and `POST /api/chat`
- Next.js app shell
- Shared chat contract: `shared/contracts/chat.contract.json`
- Sample data folders for Confluence, runbooks, incidents, GitHub, and Slack

## Vector DB (Milvus)

Retrieval behavior is controlled by `RETRIEVAL_MODE`:

- `keyword`: keyword-only retrieval (no vector indexing)
- `semantic`: Milvus semantic retrieval (falls back to keyword when unavailable)
- `hybrid`: semantic-first with keyword backfill

Example `.env` values:

```bash
RETRIEVAL_MODE=hybrid
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION_NAME=uniops_documents
EMBEDDING_PROVIDER=deterministic
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

Vector endpoints:

- `GET /api/vector/status`
- `POST /api/vector/rebuild`

## Working Agreements (parallel build)

- Frontend work stays in `frontend/**`
- Backend work stays in `backend/**`
- Shared areas (`shared/**`, `infra/**`, docs) should be changed with extra care to avoid conflicts

See:
- `docs/ways-of-working/OWNERSHIP.md`
- `docs/ways-of-working/BRANCHING.md`
- `docs/ways-of-working/INTEGRATION_RULES.md`
- `docs/ways-of-working/TASK_SPLIT_24H.md`
