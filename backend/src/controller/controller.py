from __future__ import annotations

from typing import Any
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import uuid4

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


@dataclass
class ControllerResult:
    answer: str
    trace_id: str
    needs_approval: bool
    suggested_action: str
    trace: list[dict]
    dedup_summary: dict[str, Any]


class ControllerKernel:
    def __init__(self) -> None:
        self.memory = ThreeTierMemory()
        self.permission_gate = PermissionGate()
        self.retrieval_swarm = RetrievalSwarm(memory=self.memory)
        self.reasoning_swarm = ReasoningSwarm()
        self.execution_swarm = ExecutionSwarm(permission_gate=self.permission_gate)

    def _trace_step(self, step: str, agent: str, observation: str, sources: list[dict] | None = None) -> TraceStep:
        return TraceStep(
            step=step,
            agent=agent,
            observation=observation,
            sources=sources or [],
            timestamp=datetime.now(UTC).isoformat(),
        )

    def handle_query(self, query: str, session_id: str) -> ControllerResult:
        trace_id = f"trace-{uuid4().hex[:8]}"
        trace: list[TraceStep] = []
        self.memory.run_dedup_pass()
        dedup_summary = self.memory.summary()["dedup_summary"]

        retrieval = self.retrieval_swarm.run(query=query)
        trace.append(
            self._trace_step(
                step="retrieval",
                agent="retrieval_swarm",
                observation=f"Retrieved {retrieval['source_count']} sources for session {session_id}.",
                sources=[{"title": source["title"], "path": source["path"]} for source in retrieval["sources"]],
            )
        )

        reasoning = self.reasoning_swarm.run(
            {
                "query": query,
                "sources": retrieval["sources"],
                "dedup_summary": dedup_summary,
            }
        )
        trace.append(
            self._trace_step(
                step="reasoning",
                agent="reasoning_swarm",
                observation=reasoning["reasoning"],
                sources=[{"title": source["title"], "path": source["path"]} for source in reasoning["sources"]],
            )
        )

        execution = self.execution_swarm.run(trace_id=trace_id, action=reasoning["suggested_action"])
        trace.append(
            self._trace_step(
                step="execution",
                agent="execution_swarm",
                observation=f"{execution['status']}: {execution['reason']}",
                sources=[],
            )
        )

        trace_payload = [asdict(item) for item in trace]
        self.memory.persist_transcript(trace_id=trace_id, steps=trace_payload, dedup_summary=dedup_summary)

        return ControllerResult(
            answer=reasoning["answer"],
            trace_id=trace_id,
            needs_approval=execution["requires_human_approval"],
            suggested_action=reasoning["suggested_action"],
            trace=trace_payload,
            dedup_summary=dedup_summary,
        )
