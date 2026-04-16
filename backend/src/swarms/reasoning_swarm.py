from __future__ import annotations

import os
from typing import Any

from src.adapters.llm_client import (
    LLMProviderError,
    LLMProviderRuntimeError,
    ReasoningLLMClient,
    create_reasoning_llm_client,
)


class ReasoningSwarm:
    SOURCE_TYPE_WEIGHT = {
        "runbooks": 0.25,
        "confluence": 0.2,
        "incidents": 0.15,
        "github": 0.1,
        "slack": 0.05,
    }

    def __init__(
        self,
        provider_name: str | None = None,
        llm_client: ReasoningLLMClient | None = None,
    ) -> None:
        self.provider_name = (provider_name if provider_name is not None else os.getenv("LLM_PROVIDER", "")).strip().lower()
        self._llm_client = llm_client

    def _get_llm_client(self) -> ReasoningLLMClient:
        if self._llm_client is None:
            self._llm_client = create_reasoning_llm_client(self.provider_name)
        if self._llm_client is None:
            raise LLMProviderRuntimeError("No reasoning provider is configured for this request.")
        return self._llm_client

    def _source_priority(self, source: dict[str, Any]) -> float:
        score = float(source.get("score", 0.0) or 0.0)
        source_type = str(source.get("source_type", "")).lower()
        weight = self.SOURCE_TYPE_WEIGHT.get(source_type, 0.0)
        return score + weight

    def _rank_sources(self, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            sources,
            key=lambda source: (self._source_priority(source), str(source.get("title", "")).lower()),
            reverse=True,
        )

    def _confidence(self, source_count: int, dedup_summary: dict[str, Any] | None) -> float:
        base_confidence = min(0.95, 0.45 + (0.1 * source_count))
        if dedup_summary is None:
            return round(base_confidence, 3)

        duplication_ratio = float(dedup_summary.get("duplication_ratio", 0.0) or 0.0)
        deduped_count = int(dedup_summary.get("deduped_count", 0) or 0)
        quality_bonus = max(0.0, 0.08 * (1.0 - duplication_ratio))
        duplicate_penalty = min(0.12, duplication_ratio * 0.25)
        clean_evidence_bonus = 0.02 if deduped_count == 0 else 0.0

        tuned_confidence = base_confidence + quality_bonus + clean_evidence_bonus - duplicate_penalty
        return round(max(0.2, min(0.97, tuned_confidence)), 3)

    def _confidence_breakdown(self, source_count: int, dedup_summary: dict[str, Any] | None) -> dict[str, Any]:
        base_confidence = min(0.95, 0.45 + (0.1 * source_count))
        if dedup_summary is None:
            return {
                "base_confidence": round(base_confidence, 3),
                "quality_bonus": 0.0,
                "duplicate_penalty": 0.0,
                "clean_evidence_bonus": 0.0,
                "final_confidence": round(base_confidence, 3),
            }

        duplication_ratio = float(dedup_summary.get("duplication_ratio", 0.0) or 0.0)
        deduped_count = int(dedup_summary.get("deduped_count", 0) or 0)
        quality_bonus = max(0.0, 0.08 * (1.0 - duplication_ratio))
        duplicate_penalty = min(0.12, duplication_ratio * 0.25)
        clean_evidence_bonus = 0.02 if deduped_count == 0 else 0.0
        final_confidence = round(max(0.2, min(0.97, base_confidence + quality_bonus + clean_evidence_bonus - duplicate_penalty)), 3)

        return {
            "base_confidence": round(base_confidence, 3),
            "quality_bonus": round(quality_bonus, 3),
            "duplicate_penalty": round(duplicate_penalty, 3),
            "clean_evidence_bonus": round(clean_evidence_bonus, 3),
            "duplication_ratio": round(duplication_ratio, 3),
            "final_confidence": final_confidence,
        }

    def _reasoning_steps(
        self,
        query: str,
        confidence: float,
        top_sources: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None,
    ) -> list[str]:
        source_types = sorted({str(source.get("source_type", "unknown")).lower() for source in top_sources})
        dedup_ratio = float((dedup_summary or {}).get("duplication_ratio", 0.0) or 0.0)
        steps = [
            f"Parsed incident intent from query with {len(query.split())} tokens.",
            f"Ranked top evidence sources by source-type weighting: {', '.join(source_types) or 'none' }.",
            f"Adjusted confidence using dedup signals (duplication_ratio={dedup_ratio:.3f}).",
            f"Selected action policy based on confidence={confidence:.3f} and operational intent.",
        ]
        return steps

    def _evidence_scores(self, top_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scores: list[dict[str, Any]] = []
        for source in top_sources:
            raw_score = float(source.get("score", 0.0) or 0.0)
            priority_score = round(self._source_priority(source), 3)
            scores.append(
                {
                    "title": source.get("title", ""),
                    "path": source.get("path", ""),
                    "source_type": source.get("source_type", "unknown"),
                    "raw_score": raw_score,
                    "priority_score": priority_score,
                }
            )
        return scores

    def _suggest_action(self, query: str, confidence: float, top_sources: list[dict[str, Any]]) -> str:
        normalized = query.lower()
        if any(word in normalized for word in ["rollback", "revert", "jira", "slack", "deploy", "pr"]):
            return "create rollback PR and notify Slack and Jira"

        operational_intent = any(word in normalized for word in ["cpu", "latency", "incident", "redis"])
        top_source_types = {str(source.get("source_type", "")).lower() for source in top_sources}
        has_runbook_evidence = any(source_type in {"runbooks", "confluence", "incidents"} for source_type in top_source_types)

        if operational_intent and confidence >= 0.55 and has_runbook_evidence:
            return "run high CPU diagnostic runbook in read-only mode"

        if confidence < 0.5:
            return "collect additional incident context and request approval before external actions"

        return "summarize findings and request approval for external actions"

    def _build_action_details(self, suggested_action: str) -> dict[str, Any]:
        normalized = suggested_action.lower()
        if "rollback" in normalized or "revert" in normalized or "pr" in normalized:
            return {
                "intent": "rollback_and_notify",
                "tool": "github.mock.rollback_pr",
                "parameters": {
                    "notify_channels": ["slack", "jira"],
                },
                "approval_required": True,
                "risk_hint": "high",
            }

        if "diagnostic" in normalized or "read-only" in normalized:
            return {
                "intent": "run_diagnostic",
                "tool": "generic.mock.noop",
                "parameters": {
                    "mode": "read-only",
                },
                "approval_required": False,
                "risk_hint": "low",
            }

        if "collect additional" in normalized:
            return {
                "intent": "collect_context",
                "tool": "generic.mock.noop",
                "parameters": {},
                "approval_required": True,
                "risk_hint": "medium",
            }

        return {
            "intent": "summarize_and_request_approval",
            "tool": "generic.mock.noop",
            "parameters": {},
            "approval_required": True,
            "risk_hint": "medium",
        }

    def _llm_reasoning(
        self,
        query: str,
        confidence: float,
        top_sources: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        client = self._get_llm_client()
        try:
            llm_result = client.reason(
                query=query,
                confidence=confidence,
                top_sources=top_sources,
                dedup_summary=dedup_summary,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderRuntimeError(f"{self.provider_name} provider request failed: {exc}") from exc

        return {
            "reasoning": llm_result["reasoning"],
            "answer": llm_result["answer"],
            "suggested_action": llm_result["suggested_action"],
            "action_details": llm_result.get("action_details")
            or self._build_action_details(llm_result["suggested_action"]),
            "confidence": confidence,
            "confidence_breakdown": llm_result.get("confidence_breakdown")
            or self._confidence_breakdown(source_count=len(top_sources), dedup_summary=dedup_summary),
            "reasoning_steps": llm_result.get("reasoning_steps")
            or self._reasoning_steps(
                query=query,
                confidence=confidence,
                top_sources=top_sources,
                dedup_summary=dedup_summary,
            ),
            "evidence_scores": llm_result.get("evidence_scores") or self._evidence_scores(top_sources),
            "sources": top_sources,
            "provider": getattr(client, "provider_name", self.provider_name),
            "model": getattr(client, "model_name", "unknown"),
        }

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        query = context.get("query", "")
        sources = context.get("sources", [])
        dedup_summary = context.get("dedup_summary")

        if not sources:
            raise LLMProviderRuntimeError(
                "No indexed evidence was found; ingest more operational context before reasoning."
            )

        ranked_sources = self._rank_sources(sources)
        top_sources = ranked_sources[:3]
        confidence = self._confidence(source_count=len(sources), dedup_summary=dedup_summary)
        return self._llm_reasoning(
            query=query,
            confidence=confidence,
            top_sources=top_sources,
            dedup_summary=dedup_summary,
        )
