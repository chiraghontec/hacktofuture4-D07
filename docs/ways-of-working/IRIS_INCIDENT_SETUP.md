# IRIS Incident Resolution Setup (Service-X)

This guide sets up DFIR-IRIS incident resolution using the same source data already present in this repository.

Before continuing, complete local DFIR-IRIS setup:

- `docs/ways-of-working/LOCAL_DFIR_IRIS_SETUP_MACOS.md`

## Source Data (Authoritative Inputs)

- `data/confluence/redis-latency-runbook.md`
- `data/runbooks/high-cpu-service-x.md`
- `data/incidents/incident-2026-04-08.json`
- `data/github/pr-rollback-example.md`
- `data/slack/customer-xyz-thread.md`

## Step 0: Restore Data Folder from `origin/main`

Run this before setup to ensure data parity:

```bash
cd /Volumes/LocalDrive/hacktofuture4-D07
git fetch origin
git restore --source origin/main -- data
git status --short -- data
```

Expected: no unexpected local drift in `data/`.

## Step 1: Generate IRIS Import Bundle from Repository Data

```bash
cd /Volumes/LocalDrive/hacktofuture4-D07
python3 scripts/iris_setup_from_data.py --project-key SERVICE-X
```

Generated files:

- `data/iris/import_bundle/iris-incident-seed.json`
- `data/iris/import_bundle/iris-resolution-plan.json`
- `data/iris/import_bundle/iris-runbook-mapping.json`
- `data/iris/import_bundle/iris-import-manifest.json`

## Step 2: Configure DFIR-IRIS Project and Taxonomy

1. Create or select project `SERVICE-X` in DFIR-IRIS.
2. Create service `service-x`.
3. Create incident type `redis_latency_spike_after_deployment`.
4. Configure severity map:
   - `SEV-1 -> critical`
   - `SEV-2 -> high`
   - `SEV-3 -> medium`
   - `SEV-4 -> low`
5. Add tags: `redis`, `latency`, `production`, `feature-flag`.

## Step 3: Import Incident Seed and Runbook Mapping

1. Import `iris-incident-seed.json` into DFIR-IRIS incident templates/seeds.
2. Import `iris-runbook-mapping.json` into DFIR-IRIS runbook linkage configuration.
3. Validate the incident type links to both runbooks:
   - Redis Latency Runbook
   - High CPU Runbook for Service X

## Step 4: Create Incident Resolution Workflow in DFIR-IRIS

Create workflow stages:

1. Detect
2. Triage
3. Diagnose
4. Propose Action
5. Approval
6. Execute
7. Resolve
8. Postmortem

Set policy: actions containing rollback/deploy/update/scale/create require explicit SRE approval.

## Step 5: Add Operational Evidence Context in DFIR-IRIS

1. Add GitHub rollback note using `data/github/pr-rollback-example.md`.
2. Add Slack context using `data/slack/customer-xyz-thread.md`.
3. Ensure these records are linked to the incident type and appear during triage/diagnosis.

## Step 6: Validate Against UniOps Contract Expectations

Use `incident_report` payload shape expected by:

- `backend/app/api/routes/chat.py`
- `shared/contracts/chat.contract.json`

Required behavior:

1. `message` only request works.
2. `incident_report` only request works.
3. If both are present, `incident_report` takes precedence for canonical query context.

## Step 7: Execute End-to-End Resolution Verification

1. Trigger test incident in DFIR-IRIS with the generated seed attributes.
2. Confirm runbook recommendation includes approval-gated rollback guidance.
3. Confirm incident transitions through `Approval` stage for high-risk actions.
4. Confirm final resolution + postmortem includes linked source evidence.

## Optional API Environment Settings

Add these to `.env` when integrating live DFIR-IRIS and Confluence APIs:

```env
IRIS_BASE_URL=https://localhost
IRIS_PROJECT_KEY=SERVICE-X
IRIS_API_KEY=replace_me
IRIS_VERIFY_SSL=false
CONFLUENCE_BASE_URL=https://confluence.example.internal
CONFLUENCE_SPACE_KEY=OPS
CONFLUENCE_API_TOKEN=replace_me
CONFLUENCE_EMAIL=replace_me@example.com
```
