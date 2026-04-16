import pytest

from src.adapters.llm_client import LLMProviderConfigurationError, LLMProviderRuntimeError
from src.controller.controller import ControllerKernel
from src.swarms.reasoning_swarm import ReasoningSwarm


class _FakeSuccessLLMClient:
    provider_name = "apfel"
    model_name = "apfel-test"

    def reason(self, query: str, confidence: float, top_sources: list[dict], dedup_summary: dict | None) -> dict[str, str]:
        return {
            "reasoning": f"LLM reasoning for query: {query}",
            "answer": "Use runbook first and request approval for external updates.",
            "suggested_action": "summarize findings and request approval for external actions",
            "reasoning_steps": ["Ranked evidence", "Prepared safe action"],
            "confidence_breakdown": {"base_confidence": 0.65, "final_confidence": 0.72},
            "evidence_scores": [
                {
                    "title": "Runbook",
                    "path": "data/runbooks/high-cpu-service-x.md",
                    "source_type": "runbooks",
                    "raw_score": 2,
                    "priority_score": 2.25,
                }
            ],
        }

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        return query_tokens

    def assess_execution_action(self, action: str, action_details: dict | None) -> dict[str, str | None]:
        return {
            "normalized_action": action,
            "reasoning": "Execution assessment completed.",
            "risk_hint": "medium",
        }


class _FakeFailingLLMClient:
    provider_name = "groq"
    model_name = "groq-test"

    def reason(self, query: str, confidence: float, top_sources: list[dict], dedup_summary: dict | None) -> dict[str, str]:
        raise RuntimeError("provider unavailable")


def _sample_context() -> dict:
    return {
        "query": "redis latency incident",
        "sources": [
            {
                "title": "Runbook",
                "path": "data/runbooks/high-cpu-service-x.md",
                "source_type": "runbooks",
                "score": 2,
            },
            {
                "title": "Incident",
                "path": "data/incidents/incident-2026-04-08.json",
                "source_type": "incidents",
                "score": 1,
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


def test_reasoning_reranks_sources_by_quality_weight() -> None:
    swarm = ReasoningSwarm(provider_name="apfel", llm_client=_FakeSuccessLLMClient())
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
    assert isinstance(result["reasoning_steps"], list)
    assert isinstance(result["confidence_breakdown"], dict)
    assert isinstance(result["evidence_scores"], list)


def test_reasoning_confidence_drops_with_high_duplication_ratio() -> None:
    swarm = ReasoningSwarm(provider_name="apfel", llm_client=_FakeSuccessLLMClient())
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
    kernel = ControllerKernel(provider_name="groq", reasoning_llm_client=_FakeSuccessLLMClient())
    captured_context: dict = {}

    def fake_reasoning_run(context: dict) -> dict:
        captured_context.update(context)
        return {
            "reasoning": "ok",
            "answer": "ok",
            "suggested_action": "summarize findings and request approval for external actions",
            "action_details": {
                "intent": "summarize_and_request_approval",
                "tool": "generic.mock.noop",
                "parameters": {},
                "approval_required": True,
                "risk_hint": "medium",
            },
            "confidence": 0.7,
            "sources": context["sources"][:3],
        }

    kernel.reasoning_swarm.run = fake_reasoning_run  # type: ignore[assignment]
    result = kernel.handle_query("redis incident", session_id="sess-reasoning-dedup")

    assert "dedup_summary" in captured_context
    assert "deduped_count" in captured_context["dedup_summary"]
    assert isinstance(result.trace, list)
    assert len(result.trace) == 3


def test_reasoning_uses_provider_client_when_selected() -> None:
    swarm = ReasoningSwarm(provider_name="apfel", llm_client=_FakeSuccessLLMClient())
    result = swarm.run(_sample_context())

    assert result["provider"] == "apfel"
    assert result["model"] == "apfel-test"
    assert result["suggested_action"] == "summarize findings and request approval for external actions"
    assert isinstance(result["action_details"], dict)
    assert result["action_details"]["intent"]
    assert isinstance(result["reasoning_steps"], list)
    assert isinstance(result["confidence_breakdown"], dict)
    assert isinstance(result["evidence_scores"], list)


def test_reasoning_strict_mode_has_no_deterministic_fallback_on_provider_failure() -> None:
    swarm = ReasoningSwarm(provider_name="groq", llm_client=_FakeFailingLLMClient())

    with pytest.raises(LLMProviderRuntimeError):
        swarm.run(_sample_context())


def test_reasoning_invalid_provider_raises_configuration_error() -> None:
    swarm = ReasoningSwarm(provider_name="invalid-provider")

    with pytest.raises(LLMProviderConfigurationError):
        swarm.run(_sample_context())


def test_reasoning_no_sources_fails_in_strict_mode() -> None:
    swarm = ReasoningSwarm(provider_name="groq", llm_client=_FakeSuccessLLMClient())

    with pytest.raises(LLMProviderRuntimeError):
        swarm.run({"query": "redis incident", "sources": [], "dedup_summary": {}})
