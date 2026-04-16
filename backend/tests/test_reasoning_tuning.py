from src.controller.controller import ControllerKernel
from src.swarms.reasoning_swarm import ReasoningSwarm


def test_reasoning_reranks_sources_by_quality_weight() -> None:
    swarm = ReasoningSwarm()
    result = swarm.run(
        {
            "query": "redis latency incident",
            "sources": [
                {
                    "title": "Slack Thread",
                    "path": "data/slack/customer-xyz-thread.md",
                    "source_type": "slack",
                    "score": 2,
                },
                {
                    "title": "Runbook",
                    "path": "data/runbooks/high-cpu-service-x.md",
                    "source_type": "runbooks",
                    "score": 2,
                },
            ],
            "dedup_summary": {
                "documents": {"scanned": 5, "duplicates": 0},
                "transcripts": {"scanned": 10, "duplicates": 0},
                "deduped_count": 0,
                "duplication_ratio": 0.0,
                "last_run_at": "2026-04-16T00:00:00Z",
            },
        }
    )

    assert result["sources"][0]["source_type"] == "runbooks"
    assert result["confidence"] >= 0.65


def test_reasoning_confidence_drops_with_high_duplication_ratio() -> None:
    swarm = ReasoningSwarm()
    base_context = {
        "query": "investigate incident",
        "sources": [
            {"title": "Incident", "path": "data/incidents/x.json", "source_type": "incidents", "score": 3},
            {"title": "Runbook", "path": "data/runbooks/x.md", "source_type": "runbooks", "score": 2},
        ],
    }

    high_quality = swarm.run(
        {
            **base_context,
            "dedup_summary": {
                "documents": {"scanned": 5, "duplicates": 0},
                "transcripts": {"scanned": 10, "duplicates": 0},
                "deduped_count": 0,
                "duplication_ratio": 0.0,
                "last_run_at": "2026-04-16T00:00:00Z",
            },
        }
    )
    low_quality = swarm.run(
        {
            **base_context,
            "dedup_summary": {
                "documents": {"scanned": 5, "duplicates": 4},
                "transcripts": {"scanned": 10, "duplicates": 8},
                "deduped_count": 12,
                "duplication_ratio": 0.8,
                "last_run_at": "2026-04-16T00:00:00Z",
            },
        }
    )

    assert high_quality["confidence"] > low_quality["confidence"]


def test_controller_passes_dedup_summary_to_reasoning_swarm() -> None:
    kernel = ControllerKernel()
    captured_context: dict = {}

    def fake_reasoning_run(context: dict) -> dict:
        captured_context.update(context)
        return {
            "reasoning": "ok",
            "answer": "ok",
            "suggested_action": "summarize findings and request approval for external actions",
            "confidence": 0.7,
            "sources": context["sources"][:3],
        }

    kernel.reasoning_swarm.run = fake_reasoning_run  # type: ignore[assignment]
    result = kernel.handle_query("redis incident", session_id="sess-reasoning-dedup")

    assert "dedup_summary" in captured_context
    assert "deduped_count" in captured_context["dedup_summary"]
    assert isinstance(result.trace, list)
    assert len(result.trace) == 3
