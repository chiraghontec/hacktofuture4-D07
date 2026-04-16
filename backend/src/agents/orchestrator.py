from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AgentOrchestrationResult:
    retrieval: dict[str, Any]
    reasoning: dict[str, Any]
    execution: dict[str, Any]
    mode: str


class LangChainOrchestrator:
    """Runs retrieval, reasoning, and execution through a LangChain runnable pipeline.

    Falls back to sequential local orchestration when LangChain is not installed.
    """

    def __init__(self, retrieval_swarm: Any, reasoning_swarm: Any, execution_swarm: Any) -> None:
        self.retrieval_swarm = retrieval_swarm
        self.reasoning_swarm = reasoning_swarm
        self.execution_swarm = execution_swarm
        self._pipeline: Any = None
        self._initialize_pipeline()

    def _initialize_pipeline(self) -> None:
        try:
            from langchain_core.runnables import RunnableLambda 
        except Exception:
            self._pipeline = None
            return

        self._pipeline = (
            RunnableLambda(self._run_retrieval_step)
            | RunnableLambda(self._run_reasoning_step)
            | RunnableLambda(self._run_execution_step)
        )

    def _run_retrieval_step(self, state: dict[str, Any]) -> dict[str, Any]:
        retrieval = self.retrieval_swarm.run(query=state["query"])
        state["retrieval"] = retrieval
        return state

    def _run_reasoning_step(self, state: dict[str, Any]) -> dict[str, Any]:
        retrieval = state["retrieval"]
        reasoning = self.reasoning_swarm.run(
            {
                "query": state["query"],
                "sources": retrieval["sources"],
                "dedup_summary": state["dedup_summary"],
            }
        )
        state["reasoning"] = reasoning
        return state

    def _run_execution_step(self, state: dict[str, Any]) -> dict[str, Any]:
        reasoning = state["reasoning"]
        execution = self.execution_swarm.run(
            trace_id=state["trace_id"],
            action=reasoning["suggested_action"],
            action_details=reasoning.get("action_details"),
        )
        state["execution"] = execution
        return state

    def run(self, query: str, trace_id: str, dedup_summary: dict[str, Any]) -> AgentOrchestrationResult:
        initial_state = {
            "query": query,
            "trace_id": trace_id,
            "dedup_summary": dedup_summary,
        }

        if self._pipeline is None:
            state = self._run_execution_step(self._run_reasoning_step(self._run_retrieval_step(initial_state)))
            return AgentOrchestrationResult(
                retrieval=state["retrieval"],
                reasoning=state["reasoning"],
                execution=state["execution"],
                mode="sequential_fallback",
            )

        state = self._pipeline.invoke(initial_state)
        return AgentOrchestrationResult(
            retrieval=state["retrieval"],
            reasoning=state["reasoning"],
            execution=state["execution"],
            mode="langchain",
        )
