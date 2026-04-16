from __future__ import annotations

from typing import Any, Generator
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4

from src.agents.orchestrator import LangChainOrchestrator
from src.adapters.llm_client import LLMProviderError, ReasoningLLMClient, create_shared_reasoning_llm_client
from src.gates.permission_gate import PermissionGate
from src.memory.three_tier_memory import ThreeTierMemory
from src.swarms.execution_swarm import ExecutionSwarm
from src.swarms.reasoning_swarm import ReasoningSwarm
from src.swarms.retrieval_swarm import RetrievalSwarm


@dataclass
class TraceStep:
    step: str
    agent: str
    observation: str
    sources: list[dict]
    timestamp: str
    metadata: dict[str, Any] | None = None


@dataclass
class ControllerResult:
    answer: str
    trace_id: str
    needs_approval: bool
    suggested_action: str
    trace: list[dict]
    dedup_summary: dict[str, Any]


class ControllerKernel:
    def __init__(
        self,
        provider_name: str | None = None,
        reasoning_llm_client: ReasoningLLMClient | None = None,
    ) -> None:
        selected_provider = (provider_name if provider_name is not None else os.getenv("LLM_PROVIDER", "")).strip().lower()
        shared_llm_client = reasoning_llm_client if reasoning_llm_client is not None else create_shared_reasoning_llm_client(
            selected_provider
        )

        self.memory = ThreeTierMemory()
        self.permission_gate = PermissionGate()
        self.retrieval_swarm = RetrievalSwarm(
            memory=self.memory,
            provider_name=selected_provider,
            llm_client=shared_llm_client,
        )
        self.reasoning_swarm = ReasoningSwarm(provider_name=selected_provider, llm_client=shared_llm_client)
        self.execution_swarm = ExecutionSwarm(
            permission_gate=self.permission_gate,
            provider_name=selected_provider,
            llm_client=shared_llm_client,
        )
        self.orchestrator = LangChainOrchestrator(
            retrieval_swarm=self.retrieval_swarm,
            reasoning_swarm=self.reasoning_swarm,
            execution_swarm=self.execution_swarm,
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _iso(ts: datetime) -> str:
        return ts.isoformat()

    @staticmethod
    def _duration_ms(started_at: datetime, finished_at: datetime) -> float:
        return round((finished_at - started_at).total_seconds() * 1000, 3)

    def _trace_step(
        self,
        step: str,
        agent: str,
        observation: str,
        sources: list[dict] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceStep:
        return TraceStep(
            step=step,
            agent=agent,
            observation=observation,
            sources=sources or [],
            timestamp=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )

    def _trace_step_with_timing(
        self,
        step: str,
        agent: str,
        observation: str,
        sources: list[dict] | None,
        metadata: dict[str, Any] | None,
        started_at: datetime,
        finished_at: datetime,
    ) -> TraceStep:
        merged_metadata = dict(metadata or {})
        merged_metadata.update(
            {
                "started_at": self._iso(started_at),
                "finished_at": self._iso(finished_at),
                "duration_ms": self._duration_ms(started_at, finished_at),
            }
        )
        return TraceStep(
            step=step,
            agent=agent,
            observation=observation,
            sources=sources or [],
            timestamp=self._iso(finished_at),
            metadata=merged_metadata,
        )

    def stream_query_events(self, query: str, session_id: str) -> Generator[dict[str, Any], None, None]:
        trace_id = f"trace-{uuid4().hex[:8]}"
        trace: list[TraceStep] = []

        self.memory.run_dedup_pass()
        dedup_summary = self.memory.summary()["dedup_summary"]

        yield {
            "event_type": "trace_started",
            "trace_id": trace_id,
            "status": "started",
            "metadata": {
                "session_id": session_id,
                "dedup_summary": dedup_summary,
            },
        }

        retrieval: dict[str, Any] | None = None
        reasoning: dict[str, Any] | None = None
        execution: dict[str, Any] | None = None

        try:
            retrieval_started = self._utc_now()
            retrieval = self.retrieval_swarm.run(query=query)
            retrieval_finished = self._utc_now()

            retrieval_step = self._trace_step_with_timing(
                step="retrieval",
                agent="retrieval_swarm",
                observation=(
                    f"Retrieved {retrieval['source_count']} sources for session {session_id} "
                    f"using {retrieval.get('retrieval_method', 'keyword')} retrieval."
                ),
                sources=[
                    {
                        "title": source["title"],
                        "path": source["path"],
                        "source_type": source.get("source_type"),
                        "score": source.get("score"),
                    }
                    for source in retrieval["sources"]
                ],
                metadata={
                    "retrieval_method": retrieval.get("retrieval_method", "keyword"),
                    "query_tokens": retrieval.get("query_tokens", []),
                    "llm_query_expansion": retrieval.get("llm_query_expansion"),
                },
                started_at=retrieval_started,
                finished_at=retrieval_finished,
            )
            trace.append(retrieval_step)
            yield {
                "event_type": "trace_step",
                "trace_id": trace_id,
                "status": "in_progress",
                "step": asdict(retrieval_step),
            }

            reasoning_started = self._utc_now()
            reasoning = self.reasoning_swarm.run(
                {
                    "query": query,
                    "sources": retrieval["sources"],
                    "dedup_summary": dedup_summary,
                }
            )
            reasoning_finished = self._utc_now()

            reasoning_step = self._trace_step_with_timing(
                step="reasoning",
                agent="reasoning_swarm",
                observation=reasoning["reasoning"],
                sources=[
                    {
                        "title": source["title"],
                        "path": source["path"],
                        "source_type": source.get("source_type"),
                        "score": source.get("score"),
                    }
                    for source in reasoning["sources"]
                ],
                metadata={
                    "confidence": reasoning.get("confidence"),
                    "confidence_breakdown": reasoning.get("confidence_breakdown"),
                    "reasoning_steps": reasoning.get("reasoning_steps", []),
                    "evidence_scores": reasoning.get("evidence_scores", []),
                    "provider": reasoning.get("provider"),
                    "model": reasoning.get("model"),
                    "action_details": reasoning.get("action_details"),
                    "answer": reasoning.get("answer"),
                    "suggested_action": reasoning.get("suggested_action"),
                },
                started_at=reasoning_started,
                finished_at=reasoning_finished,
            )
            trace.append(reasoning_step)
            yield {
                "event_type": "trace_step",
                "trace_id": trace_id,
                "status": "in_progress",
                "step": asdict(reasoning_step),
            }

            execution_started = self._utc_now()
            execution = self.execution_swarm.run(
                trace_id=trace_id,
                action=reasoning["suggested_action"],
                action_details=reasoning.get("action_details"),
            )
            execution_finished = self._utc_now()

            execution_step = self._trace_step_with_timing(
                step="execution",
                agent="execution_swarm",
                observation=f"{execution['status']}: {execution['reason']}",
                sources=[],
                metadata={
                    "risk_level": execution.get("risk_level"),
                    "requires_human_approval": execution.get("requires_human_approval"),
                    "execution_reasoning": execution.get("execution_reasoning"),
                    "provider": execution.get("provider"),
                    "model": execution.get("model"),
                    "risk_hint": execution.get("risk_hint"),
                    "action": execution.get("action"),
                    "original_action": execution.get("original_action"),
                },
                started_at=execution_started,
                finished_at=execution_finished,
            )
            trace.append(execution_step)
            yield {
                "event_type": "trace_step",
                "trace_id": trace_id,
                "status": "in_progress",
                "step": asdict(execution_step),
            }

            trace_payload = [asdict(item) for item in trace]
            self.memory.persist_transcript(
                trace_id=trace_id,
                steps=trace_payload,
                dedup_summary=dedup_summary,
                suggested_action=reasoning["suggested_action"],
                action_details=reasoning.get("action_details"),
                needs_approval=execution["requires_human_approval"],
                execution_status=execution["status"],
            )

            yield {
                "event_type": "trace_complete",
                "trace_id": trace_id,
                "status": "completed",
                "answer": reasoning["answer"],
                "needs_approval": execution["requires_human_approval"],
                "suggested_action": reasoning["suggested_action"],
                "metadata": {
                    "dedup_summary": dedup_summary,
                    "action_details": reasoning.get("action_details"),
                    "execution_status": execution.get("status"),
                    "step_count": len(trace_payload),
                },
            }
        except LLMProviderError as exc:
            trace_payload = [asdict(item) for item in trace]
            self.memory.persist_transcript(
                trace_id=trace_id,
                steps=trace_payload,
                dedup_summary=dedup_summary,
                suggested_action=(reasoning or {}).get("suggested_action"),
                action_details=(reasoning or {}).get("action_details"),
                needs_approval=(execution or {}).get("requires_human_approval"),
                execution_status="failed",
            )
            yield {
                "event_type": "trace_error",
                "trace_id": trace_id,
                "status": "failed",
                "error_code": "provider_error",
                "error": str(exc),
                "metadata": {
                    "dedup_summary": dedup_summary,
                    "step_count": len(trace_payload),
                },
            }
        except Exception as exc:
            trace_payload = [asdict(item) for item in trace]
            self.memory.persist_transcript(
                trace_id=trace_id,
                steps=trace_payload,
                dedup_summary=dedup_summary,
                suggested_action=(reasoning or {}).get("suggested_action"),
                action_details=(reasoning or {}).get("action_details"),
                needs_approval=(execution or {}).get("requires_human_approval"),
                execution_status="failed",
            )
            yield {
                "event_type": "trace_error",
                "trace_id": trace_id,
                "status": "failed",
                "error_code": "controller_runtime_error",
                "error": f"Unhandled controller error: {exc}",
                "metadata": {
                    "dedup_summary": dedup_summary,
                    "step_count": len(trace_payload),
                },
            }

    def handle_query(self, query: str, session_id: str) -> ControllerResult:
        trace_id = f"trace-{uuid4().hex[:8]}"
        trace: list[TraceStep] = []
        self.memory.run_dedup_pass()
        dedup_summary = self.memory.summary()["dedup_summary"]

        orchestration = self.orchestrator.run(query=query, trace_id=trace_id, dedup_summary=dedup_summary)
        retrieval = orchestration.retrieval
        trace.append(
            self._trace_step(
                step="retrieval",
                agent="retrieval_swarm",
                observation=(
                    f"Retrieved {retrieval['source_count']} sources for session {session_id} "
                    f"using {retrieval.get('retrieval_method', 'keyword')} retrieval."
                ),
                sources=[
                    {
                        "title": source["title"],
                        "path": source["path"],
                        "source_type": source.get("source_type"),
                        "score": source.get("score"),
                    }
                    for source in retrieval["sources"]
                ],
                metadata={
                    "retrieval_method": retrieval.get("retrieval_method", "keyword"),
                    "query_tokens": retrieval.get("query_tokens", []),
                    "llm_query_expansion": retrieval.get("llm_query_expansion"),
                },
            )
        )

        reasoning = orchestration.reasoning
        trace.append(
            self._trace_step(
                step="reasoning",
                agent="reasoning_swarm",
                observation=reasoning["reasoning"],
                sources=[
                    {
                        "title": source["title"],
                        "path": source["path"],
                        "source_type": source.get("source_type"),
                        "score": source.get("score"),
                    }
                    for source in reasoning["sources"]
                ],
                metadata={
                    "confidence": reasoning.get("confidence"),
                    "confidence_breakdown": reasoning.get("confidence_breakdown"),
                    "reasoning_steps": reasoning.get("reasoning_steps", []),
                    "evidence_scores": reasoning.get("evidence_scores", []),
                    "provider": reasoning.get("provider"),
                    "model": reasoning.get("model"),
                    "action_details": reasoning.get("action_details"),
                },
            )
        )

        execution = orchestration.execution
        trace.append(
            self._trace_step(
                step="execution",
                agent="execution_swarm",
                observation=f"{execution['status']}: {execution['reason']}",
                sources=[],
                metadata={
                    "risk_level": execution.get("risk_level"),
                    "requires_human_approval": execution.get("requires_human_approval"),
                    "execution_reasoning": execution.get("execution_reasoning"),
                    "provider": execution.get("provider"),
                    "model": execution.get("model"),
                    "risk_hint": execution.get("risk_hint"),
                },
            )
        )

        trace_payload = [asdict(item) for item in trace]
        self.memory.persist_transcript(
            trace_id=trace_id,
            steps=trace_payload,
            dedup_summary=dedup_summary,
            suggested_action=reasoning["suggested_action"],
            action_details=reasoning.get("action_details"),
            needs_approval=execution["requires_human_approval"],
            execution_status=execution["status"],
        )

        return ControllerResult(
            answer=reasoning["answer"],
            trace_id=trace_id,
            needs_approval=execution["requires_human_approval"],
            suggested_action=reasoning["suggested_action"],
            trace=trace_payload,
            dedup_summary=dedup_summary,
        )
