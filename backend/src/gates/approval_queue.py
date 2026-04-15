from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass
class ApprovalItem:
    id: str
    trace_id: str
    action: str
    risk_level: str
    reason: str
    status: str
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    rejection_reason: str | None = None


class ApprovalQueue:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.queue_root = self.repo_root / "backend" / ".uniops" / "approvals"
        self.queue_root.mkdir(parents=True, exist_ok=True)

        self.pending_file = self.queue_root / "pending.json"
        self.history_file = self.queue_root / "history.json"

    def _read_items(self, file_path: Path) -> list[dict]:
        if not file_path.exists():
            return []
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def _write_items(self, file_path: Path, items: list[dict]) -> None:
        file_path.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def clear_all(self) -> None:
        self._write_items(self.pending_file, [])
        self._write_items(self.history_file, [])

    def list_pending(self) -> list[dict]:
        return self._read_items(self.pending_file)

    def enqueue(self, trace_id: str, action: str, risk_level: str, reason: str) -> dict:
        pending = self._read_items(self.pending_file)
        for item in pending:
            if item.get("trace_id") == trace_id and item.get("action") == action and item.get("status") == "pending":
                return item

        queued = ApprovalItem(
            id=f"act-{uuid4().hex[:10]}",
            trace_id=trace_id,
            action=action,
            risk_level=risk_level,
            reason=reason,
            status="pending",
            created_at=datetime.now(UTC).isoformat(),
        )

        payload = asdict(queued)
        pending.append(payload)
        self._write_items(self.pending_file, pending)
        return payload

    def approve(self, action_id: str, decided_by: str) -> dict | None:
        pending = self._read_items(self.pending_file)
        history = self._read_items(self.history_file)

        for index, item in enumerate(pending):
            if item.get("id") != action_id:
                continue

            item["status"] = "approved"
            item["decided_by"] = decided_by
            item["decided_at"] = datetime.now(UTC).isoformat()

            approved = item
            pending.pop(index)
            history.append(approved)
            self._write_items(self.pending_file, pending)
            self._write_items(self.history_file, history)
            return approved

        return None

    def reject(self, action_id: str, decided_by: str, reason: str | None = None) -> dict | None:
        pending = self._read_items(self.pending_file)
        history = self._read_items(self.history_file)

        for index, item in enumerate(pending):
            if item.get("id") != action_id:
                continue

            item["status"] = "rejected"
            item["decided_by"] = decided_by
            item["decided_at"] = datetime.now(UTC).isoformat()
            item["rejection_reason"] = reason

            rejected = item
            pending.pop(index)
            history.append(rejected)
            self._write_items(self.pending_file, pending)
            self._write_items(self.history_file, history)
            return rejected

        return None
