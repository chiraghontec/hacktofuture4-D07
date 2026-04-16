from __future__ import annotations

from typing import Any

import pytest

from app.api.routes import chat as chat_route
from src.controller.controller import ControllerKernel


class _FakeGroqLLMClient:
    provider_name = "groq"
    model_name = "groq-test"

    def reason(
        self,
        query: str,
        confidence: float,
        top_sources: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized_query = query.lower()
        high_risk = any(keyword in normalized_query for keyword in ["rollback", "revert", "pr", "slack", "jira", "deploy"])
        suggested_action = (
            "create rollback PR and notify Slack and Jira"
            if high_risk
            else "summarize findings and request approval for external actions"
        )
        evidence_scores = [
            {
                "title": source.get("title", ""),
                "path": source.get("path", ""),
                "source_type": source.get("source_type", "unknown"),
                "raw_score": float(source.get("score", 0.0) or 0.0),
                "priority_score": float(source.get("score", 0.0) or 0.0),
            }
            for source in top_sources
        ]
        return {
            "reasoning": "Provider-generated reasoning based on indexed operational evidence.",
            "answer": "Use runbook-guided mitigation and require approval for external coordination.",
            "suggested_action": suggested_action,
            "action_details": {
                "intent": "rollback_and_notify" if high_risk else "summarize_and_request_approval",
                "tool": "github.mock.rollback_pr" if high_risk else "generic.mock.noop",
                "parameters": {},
                "approval_required": True,
                "risk_hint": "high" if high_risk else "medium",
            },
            "reasoning_steps": [
                "Parsed operational context.",
                "Ranked evidence sources.",
                "Selected policy-compliant action.",
            ],
            "confidence_breakdown": {
                "base_confidence": round(confidence, 3),
                "quality_bonus": 0.0,
                "duplicate_penalty": 0.0,
                "clean_evidence_bonus": 0.0,
                "final_confidence": round(confidence, 3),
            },
            "evidence_scores": evidence_scores,
        }

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        expanded = [*query_tokens]
        for token in ["incident", "runbook"]:
            if token not in expanded:
                expanded.append(token)
        return expanded

    def assess_execution_action(self, action: str, action_details: dict[str, Any] | None) -> dict[str, Any]:
        normalized = action.lower()
        high_risk = "rollback" in normalized or "pr" in normalized or "rollback" in str((action_details or {}).get("intent", ""))
        return {
            "normalized_action": action,
            "reasoning": "Provider execution assessment completed before permission-gate evaluation.",
            "risk_hint": "high" if high_risk else "low",
        }


@pytest.fixture(autouse=True)
def _inject_test_groq_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ControllerKernel(provider_name="groq", reasoning_llm_client=_FakeGroqLLMClient())
    monkeypatch.setattr(chat_route, "kernel", kernel)
