import pytest

from src.adapters.llm_client import LLMProviderRuntimeError
from src.gates.permission_gate import PermissionGate
from src.memory.three_tier_memory import MemoryDocument
from src.swarms.execution_swarm import ExecutionSwarm
from src.swarms.retrieval_swarm import RetrievalSwarm


class _StubMemory:
    def __init__(self) -> None:
        self._documents = [
            MemoryDocument(
                title="Redis Latency Runbook",
                path="data/runbooks/high-cpu-service-x.md",
                source_type="runbooks",
                content="Redis latency runbook covers diagnostic and rollback readiness.",
            ),
            MemoryDocument(
                title="Incident Timeline",
                path="data/incidents/incident-2026-04-08.json",
                source_type="incidents",
                content="Incident notes mention cache saturation and redis latency.",
            ),
        ]

    def load_documents(self) -> list[MemoryDocument]:
        return self._documents


class _FakeRetrievalLLMClient:
    provider_name = "groq"
    model_name = "groq-retrieval-test"

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        return [*query_tokens, "cache", "throughput"]

    def reason(self, query, confidence, top_sources, dedup_summary):  # pragma: no cover - not used in this test
        raise NotImplementedError

    def assess_execution_action(self, action, action_details):  # pragma: no cover - not used in this test
        raise NotImplementedError


class _FakeFailingRetrievalLLMClient(_FakeRetrievalLLMClient):
    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        raise RuntimeError("provider unavailable")


class _FakeExecutionLLMClient:
    provider_name = "groq"
    model_name = "groq-execution-test"

    def reason(self, query, confidence, top_sources, dedup_summary):  # pragma: no cover - not used in this test
        raise NotImplementedError

    def expand_query_terms(self, query, query_tokens):  # pragma: no cover - not used in this test
        raise NotImplementedError

    def assess_execution_action(self, action: str, action_details: dict | None) -> dict:
        return {
            "normalized_action": "create rollback PR and notify Slack and Jira",
            "reasoning": "Action modifies external systems; keep approval required.",
            "risk_hint": "high",
        }


class _FakeFailingExecutionLLMClient(_FakeExecutionLLMClient):
    def assess_execution_action(self, action: str, action_details: dict | None) -> dict:
        raise RuntimeError("provider unavailable")


def test_retrieval_uses_llm_query_expansion_when_provider_selected() -> None:
    swarm = RetrievalSwarm(
        memory=_StubMemory(),
        provider_name="groq",
        llm_client=_FakeRetrievalLLMClient(),
    )

    result = swarm.run("redis latency")

    assert result["llm_query_expansion"]["used"] is True
    assert "cache" in result["query_tokens"]
    assert result["llm_query_expansion"]["provider"] == "groq"


def test_retrieval_strict_mode_raises_on_provider_failure() -> None:
    swarm = RetrievalSwarm(
        memory=_StubMemory(),
        provider_name="groq",
        llm_client=_FakeFailingRetrievalLLMClient(),
    )

    with pytest.raises(LLMProviderRuntimeError):
        swarm.run("redis latency")


def test_retrieval_strict_mode_raises_when_provider_is_missing() -> None:
    swarm = RetrievalSwarm(
        memory=_StubMemory(),
        provider_name="",
        llm_client=_FakeRetrievalLLMClient(),
    )

    with pytest.raises(LLMProviderRuntimeError):
        swarm.run("redis latency")


def test_execution_uses_llm_assessment_when_provider_selected() -> None:
    swarm = ExecutionSwarm(
        permission_gate=PermissionGate(),
        provider_name="groq",
        llm_client=_FakeExecutionLLMClient(),
    )

    result = swarm.run(
        trace_id="trace-groq-execution",
        action="rollback maybe",
        action_details={"intent": "rollback_and_notify"},
    )

    assert result["provider"] == "groq"
    assert result["model"] == "groq-execution-test"
    assert result["action"] == "create rollback PR and notify Slack and Jira"
    assert result["execution_reasoning"]


def test_execution_strict_mode_raises_on_provider_failure() -> None:
    swarm = ExecutionSwarm(
        permission_gate=PermissionGate(),
        provider_name="groq",
        llm_client=_FakeFailingExecutionLLMClient(),
    )

    with pytest.raises(LLMProviderRuntimeError):
        swarm.run(
            trace_id="trace-groq-execution-fail",
            action="rollback maybe",
            action_details={"intent": "rollback_and_notify"},
        )


def test_execution_strict_mode_raises_when_provider_is_missing() -> None:
    swarm = ExecutionSwarm(
        permission_gate=PermissionGate(),
        provider_name="",
        llm_client=_FakeExecutionLLMClient(),
    )

    with pytest.raises(LLMProviderRuntimeError):
        swarm.run(
            trace_id="trace-groq-execution-missing-provider",
            action="rollback maybe",
            action_details={"intent": "rollback_and_notify"},
        )
