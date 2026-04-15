import json
from pathlib import Path

from src.memory.three_tier_memory import ThreeTierMemory


def _build_memory(tmp_path: Path) -> ThreeTierMemory:
    memory = ThreeTierMemory()
    memory.repo_root = tmp_path
    memory.data_root = tmp_path / "data"
    memory.transcript_root = tmp_path / "backend" / ".uniops" / "transcripts"
    memory.transcript_root.mkdir(parents=True, exist_ok=True)
    return memory


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_transcript(transcript_root: Path, trace_id: str, steps: list[dict]) -> None:
    payload = {"trace_id": trace_id, "steps": steps}
    (transcript_root / f"{trace_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _strip_timestamp(report: dict) -> dict:
    clone = json.loads(json.dumps(report))
    clone["last_run_at"] = "<ts>"
    return clone


def test_run_dedup_pass_identifies_document_and_transcript_duplicates(tmp_path: Path) -> None:
    memory = _build_memory(tmp_path)

    _write_file(tmp_path / "data" / "confluence" / "redis-a.md", "Redis latency runbook")
    _write_file(tmp_path / "data" / "runbooks" / "redis-b.md", "  redis   latency   RUNBOOK  ")
    _write_file(tmp_path / "data" / "incidents" / "inc-1.json", '{"kind":"incident"}')

    _write_transcript(memory.transcript_root, "trace-01", [{"step": "retrieval", "observation": "same"}])
    _write_transcript(memory.transcript_root, "trace-02", [{"step": "retrieval", "observation": "same"}])
    _write_transcript(memory.transcript_root, "trace-03", [{"step": "execution", "observation": "different"}])

    report = memory.run_dedup_pass()

    assert report["documents"]["scanned"] == 3
    assert report["documents"]["duplicates"] == 1
    assert report["documents"]["duplicate_map"] == [
        {"duplicate": "data/runbooks/redis-b.md", "retained": "data/confluence/redis-a.md"}
    ]

    assert report["transcripts"]["scanned"] == 3
    assert report["transcripts"]["duplicates"] == 1
    assert report["transcripts"]["duplicate_map"] == [{"duplicate": "trace-02", "retained": "trace-01"}]

    assert report["deduped_count"] == 2

    summary = memory.summary()["dedup_summary"]
    assert summary["documents"]["duplicates"] == 1
    assert summary["transcripts"]["duplicates"] == 1
    assert summary["duplication_ratio"] == 0.3333


def test_run_dedup_pass_is_idempotent_and_deterministic(tmp_path: Path) -> None:
    memory = _build_memory(tmp_path)

    _write_file(tmp_path / "data" / "confluence" / "same.md", "CPU runbook")
    _write_file(tmp_path / "data" / "github" / "same-copy.md", "cpu   RUNBOOK")

    _write_transcript(memory.transcript_root, "trace-10", [{"step": "a", "sources": [{"p": "x"}]}])
    _write_transcript(memory.transcript_root, "trace-11", [{"step": "a", "sources": [{"p": "x"}]}])

    first = memory.run_dedup_pass()
    second = memory.run_dedup_pass()

    assert _strip_timestamp(first) == _strip_timestamp(second)

    assert first["documents"]["retained"] == ["data/confluence/same.md"]
    assert first["transcripts"]["retained"] == ["trace-10"]

    summary = memory.summary()["dedup_summary"]
    assert summary["deduped_count"] == 2
    assert summary["documents"]["scanned"] == 2
    assert summary["transcripts"]["scanned"] == 2
    assert summary["duplication_ratio"] == 0.5
