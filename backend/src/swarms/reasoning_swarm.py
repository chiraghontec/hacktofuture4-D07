from __future__ import annotations

from typing import Any


class ReasoningSwarm:
    SOURCE_TYPE_WEIGHT = {
        "runbooks": 0.25,
        "confluence": 0.2,
        "incidents": 0.15,
        "github": 0.1,
        "slack": 0.05,
    }

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

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        query = context.get("query", "")
        sources = context.get("sources", [])
        dedup_summary = context.get("dedup_summary")

        if not sources:
            return {
                "reasoning": "No indexed evidence was found; provide more context or ingest more runbooks.",
                "answer": "I could not find enough evidence in the current knowledge base.",
                "suggested_action": "collect additional context before taking action",
                "confidence": 0.25,
                "sources": [],
            }

        ranked_sources = self._rank_sources(sources)
        top_sources = ranked_sources[:3]
        confidence = self._confidence(source_count=len(sources), dedup_summary=dedup_summary)
        source_titles = ", ".join(source["title"] for source in top_sources)
        answer = (
            f"Based on {len(sources)} relevant sources ({source_titles}), the issue appears linked "
            "to recent operational context. Start with the documented runbook path and only execute "
            "external actions after explicit approval."
        )

        return {
            "reasoning": "Correlated query intent with indexed runbooks/incidents, prioritized high-quality evidence, and tuned confidence with dedup signals.",
            "answer": answer,
            "suggested_action": self._suggest_action(query=query, confidence=confidence, top_sources=top_sources),
            "confidence": confidence,
            "sources": top_sources,
        }
