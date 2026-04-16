# UniOps - Small OS for Operations

Monorepo scaffold for a 24-hour hackathon build with 2 engineers working in parallel.

## Monorepo Structure

```text
.
├── frontend/                # Engineer A ownership
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── tests/
├── backend/                 # Engineer B ownership
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
├── data/
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

## Conflict Prevention Model (2 Engineers)

1. Strict ownership boundary:
   - Engineer A -> `frontend/**`
   - Engineer B -> `backend/**`
2. Shared zone (`shared/contracts/**`, `infra/**`, docs) uses short lock-based edits.
3. Contract-first integration: update shared contract before implementation changes.
4. Merge cadence: sync every 2 hours, small PRs, no direct commits to `main`.

See:
- `docs/ways-of-working/OWNERSHIP.md`
- `docs/ways-of-working/BRANCHING.md`
- `docs/ways-of-working/INTEGRATION_RULES.md`
- `docs/ways-of-working/TASK_SPLIT_24H.md`

## Quick Start

### Option A: Docker Compose

```bash
make up
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/health

### Option B: Run separately

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
- Next.js app shell page
- Shared chat contract at `shared/contracts/chat.contract.json`
- Sample data folders for Confluence, runbooks, incidents, GitHub, and Slack

## Next Build Targets

1. Add backend SSE endpoint for live reasoning trace.
2. Connect frontend chat + trace panel to API contract.
3. Implement native permission gate approval queue.
4. Add ingestion pipeline for markdown and simulated incident data.

## IRIS Data Parity Setup

Use repository source data to bootstrap the same incident-resolution context in IRIS:

```bash
python3 scripts/iris_setup_from_data.py --project-key SERVICE-X
```

Then follow:

- `docs/ways-of-working/IRIS_INCIDENT_SETUP.md`
