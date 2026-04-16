from __future__ import annotations

import json
from datetime import UTC, datetime
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any


@dataclass
class MemoryDocument:
    title: str
    path: str
    source_type: str
    content: str


class ThreeTierMemory:
    def __init__(self) -> None:
        self.index_layer = "MEMORY.MD"
        self.docs_layer = "markdown"
        self.transcript_layer = "json"
        self.repo_root = Path(__file__).resolve().parents[3]
        self.data_root = self.repo_root / "data"
        self.transcript_root = self.repo_root / "backend" / ".uniops" / "transcripts"
        self.transcript_root.mkdir(parents=True, exist_ok=True)
        self._documents_cache: list[MemoryDocument] | None = None
        self._last_dedup_report: dict[str, Any] = {
            "documents": {"scanned": 0, "duplicates": 0, "retained": [], "duplicate_map": []},
            "transcripts": {"scanned": 0, "duplicates": 0, "retained": [], "duplicate_map": []},
            "deduped_count": 0,
            "last_run_at": None,
        }

    def summary(self) -> dict[str, Any]:
        documents = self.load_documents()
        dedup_total_scanned = self._last_dedup_report["documents"]["scanned"] + self._last_dedup_report["transcripts"]["scanned"]
        dedup_ratio = 0.0
        if dedup_total_scanned > 0:
            dedup_ratio = round(self._last_dedup_report["deduped_count"] / dedup_total_scanned, 4)

        return {
            "index": self.index_layer,
            "documents": self.docs_layer,
            "transcripts": self.transcript_layer,
            "document_count": len(documents),
            "dedup_summary": {
                "documents": {
                    "scanned": self._last_dedup_report["documents"]["scanned"],
                    "duplicates": self._last_dedup_report["documents"]["duplicates"],
                },
                "transcripts": {
                    "scanned": self._last_dedup_report["transcripts"]["scanned"],
                    "duplicates": self._last_dedup_report["transcripts"]["duplicates"],
                },
                "deduped_count": self._last_dedup_report["deduped_count"],
                "duplication_ratio": dedup_ratio,
                "last_run_at": self._last_dedup_report["last_run_at"],
            },
        }

    def load_documents(self, force_reload: bool = False) -> list[MemoryDocument]:
        if self._documents_cache is not None and not force_reload:
            return self._documents_cache

        collected: list[MemoryDocument] = []
        source_dirs = ["confluence", "runbooks", "incidents", "github", "slack"]
        for source_dir in source_dirs:
            folder = self.data_root / source_dir
            if not folder.exists():
                continue

            for file_path in folder.glob("**/*"):
                if file_path.is_dir() or file_path.suffix.lower() not in {".md", ".json"}:
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8")
                except OSError:
                    continue

                rel_path = file_path.relative_to(self.repo_root).as_posix()
                collected.append(
                    MemoryDocument(
                        title=file_path.stem.replace("-", " ").title(),
                        path=rel_path,
                        source_type=source_dir,
                        content=content,
                    )
                )

        self._documents_cache = collected
        return collected

    def persist_transcript(
        self,
        trace_id: str,
        steps: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None = None,
    ) -> None:
        target = self.transcript_root / f"{trace_id}.json"
        payload = {
            "trace_id": trace_id,
            "steps": steps,
        }
        if dedup_summary is not None:
            payload["dedup_summary"] = dedup_summary
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_transcript(self, trace_id: str) -> dict[str, Any] | None:
        target = self.transcript_root / f"{trace_id}.json"
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def run_dedup_pass(self) -> dict[str, Any]:
        def normalize_text(text: str) -> str:
            return " ".join(text.split()).lower()

        document_signature_to_retained: dict[str, str] = {}
        document_duplicates: list[dict[str, str]] = []
        retained_documents: list[str] = []

        documents = sorted(self.load_documents(force_reload=True), key=lambda item: item.path)
        for document in documents:
            signature = hashlib.sha256(normalize_text(document.content).encode("utf-8")).hexdigest()
            retained_path = document_signature_to_retained.get(signature)
            if retained_path is None:
                document_signature_to_retained[signature] = document.path
                retained_documents.append(document.path)
                continue

            document_duplicates.append({"duplicate": document.path, "retained": retained_path})

        transcript_signature_to_retained: dict[str, str] = {}
        transcript_duplicates: list[dict[str, str]] = []
        retained_transcripts: list[str] = []
        transcript_paths = sorted(self.transcript_root.glob("*.json"), key=lambda item: item.name)

        for transcript_path in transcript_paths:
            try:
                payload = json.loads(transcript_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            trace_id = str(payload.get("trace_id", transcript_path.stem))
            steps_payload = payload.get("steps", [])
            canonical_steps = json.dumps(steps_payload, sort_keys=True, separators=(",", ":"))
            signature = hashlib.sha256(canonical_steps.encode("utf-8")).hexdigest()

            retained_trace_id = transcript_signature_to_retained.get(signature)
            if retained_trace_id is None:
                transcript_signature_to_retained[signature] = trace_id
                retained_transcripts.append(trace_id)
                continue

            transcript_duplicates.append({"duplicate": trace_id, "retained": retained_trace_id})

        dedup_report = {
            "documents": {
                "scanned": len(documents),
                "duplicates": len(document_duplicates),
                "retained": retained_documents,
                "duplicate_map": document_duplicates,
            },
            "transcripts": {
                "scanned": len(transcript_paths),
                "duplicates": len(transcript_duplicates),
                "retained": retained_transcripts,
                "duplicate_map": transcript_duplicates,
            },
            "deduped_count": len(document_duplicates) + len(transcript_duplicates),
            "last_run_at": datetime.now(UTC).isoformat(),
        }
        self._last_dedup_report = dedup_report
        return dedup_report

    def get_last_dedup_report(self) -> dict[str, Any]:
        return self._last_dedup_report
