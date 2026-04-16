#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
CONFLUENCE_PAGE_IDS="${CONFLUENCE_PAGE_IDS:-65868,65898}"
IRIS_CASE_ID="${IRIS_CASE_ID:-1}"
SESSION_ID="${SESSION_ID:-sess-$(date +%s)}"
CHAT_MESSAGE="${CHAT_MESSAGE:-Create rollback PR and notify Slack and Jira for redis latency incident}"
APPROVER_ID="${APPROVER_ID:-demo-approver}"
APPROVAL_DECISION="${APPROVAL_DECISION:-approve}"
APPROVAL_COMMENT="${APPROVAL_COMMENT:-Approved via scripted E2E flow.}"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

ingest_payload="$(python3 - "${CONFLUENCE_PAGE_IDS}" <<'PY'
import json
import sys

raw = sys.argv[1]
page_ids = [item.strip() for item in raw.split(',') if item.strip()]
print(json.dumps({"page_ids": page_ids}))
PY
)"

echo "[1/6] Ingesting Confluence runbooks: ${CONFLUENCE_PAGE_IDS}"
ingest_response="$(curl -sS -X POST "${BACKEND_URL}/api/ingest/confluence" -H "Content-Type: application/json" -d "${ingest_payload}")"
echo "${ingest_response}" | python3 -m json.tool

ingested_count="$(printf '%s' "${ingest_response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("ingested_count", 0))')"
failed_count="$(printf '%s' "${ingest_response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("failed_count", 0))')"

echo "Checkpoint: ingested_count=${ingested_count}, failed_count=${failed_count}"

echo "[2/6] Ingesting IRIS case: ${IRIS_CASE_ID}"
iris_response="$(curl -sS -X POST "${BACKEND_URL}/api/ingest/iris?case_id=${IRIS_CASE_ID}")"
echo "${iris_response}" | python3 -m json.tool

iris_ingested_case="$(printf '%s' "${iris_response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("case_id", ""))')"
echo "Checkpoint: iris_case_id=${iris_ingested_case}"

echo "[3/6] Creating chat trace"
chat_response="$(curl -sS -X POST "${BACKEND_URL}/api/chat" -H "Content-Type: application/json" -d "$(python3 - <<PY
import json
print(json.dumps({
  "message": "${CHAT_MESSAGE}",
  "session_id": "${SESSION_ID}"
}))
PY
)")"
echo "${chat_response}" | python3 -m json.tool

trace_id="$(printf '%s' "${chat_response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("trace_id", ""))')"
needs_approval="$(printf '%s' "${chat_response}" | python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("needs_approval", False)).lower())')"

if [[ -z "${trace_id}" ]]; then
  echo "Failed to parse trace_id from chat response"
  exit 1
fi

echo "Checkpoint: trace_id=${trace_id}, needs_approval=${needs_approval}"

echo "[4/6] Reading SSE trace events"
stream_response="$(curl -sS "${BACKEND_URL}/api/chat/stream?trace_id=${trace_id}" || true)"
printf '%s\n' "${stream_response}" | grep '^data:' || true
stream_event_count="$(printf '%s\n' "${stream_response}" | grep -c '^data:' || true)"
echo "Checkpoint: stream_events=${stream_event_count}"

if [[ "${needs_approval}" == "true" ]]; then
  echo "[5/6] Submitting approval decision: ${APPROVAL_DECISION}"
  approval_response="$(curl -sS -X POST "${BACKEND_URL}/api/approvals/${trace_id}" -H "Content-Type: application/json" -d "$(python3 - <<PY
import json
print(json.dumps({
  "decision": "${APPROVAL_DECISION}",
  "approver_id": "${APPROVER_ID}",
  "comment": "${APPROVAL_COMMENT}"
}))
PY
)")"
  echo "${approval_response}" | python3 -m json.tool
else
  echo "[5/6] Skipping approval because needs_approval=false"
fi

echo "[6/6] Fetching transcript final state"
transcript_response="$(curl -sS "${BACKEND_URL}/api/chat/transcript/${trace_id}")"
echo "${transcript_response}" | python3 -m json.tool

final_status="$(printf '%s' "${transcript_response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("final_status", "n/a"))')"
echo "Checkpoint: final_status=${final_status}"

echo "E2E flow complete for trace ${trace_id}."
