from __future__ import annotations

import os
from typing import Any

from src.adapters.llm_client import LLMProviderError, LLMProviderRuntimeError, ReasoningLLMClient
from src.gates.permission_gate import PermissionGate, PermissionRequest


class ExecutionSwarm:
    def __init__(
        self,
        permission_gate: PermissionGate,
        provider_name: str | None = None,
        llm_client: ReasoningLLMClient | None = None,
    ) -> None:
        self.permission_gate = permission_gate
        self.provider_name = (provider_name if provider_name is not None else os.getenv("LLM_PROVIDER", "")).strip().lower()
        self._llm_client = llm_client

    def _get_llm_client(self) -> ReasoningLLMClient:
        if self._llm_client is None:
            raise LLMProviderRuntimeError("No execution provider client is configured for this request.")
        return self._llm_client

    def _llm_assess_action(self, action: str, action_details: dict[str, Any] | None) -> dict[str, Any]:
        client = self._get_llm_client()
        try:
            return client.assess_execution_action(action=action, action_details=action_details)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderRuntimeError(f"{self.provider_name} execution assessment failed: {exc}") from exc

    def run(self, trace_id: str, action: str, action_details: dict[str, Any] | None = None) -> dict:
        if not self.provider_name:
            raise LLMProviderRuntimeError("Execution requires a configured LLM provider.")

        assessment = self._llm_assess_action(action=action, action_details=action_details)
        normalized_action = str(assessment.get("normalized_action") or action)
        execution_reasoning = str(assessment.get("reasoning") or "Execution assessment completed via provider.")
        risk_hint = assessment.get("risk_hint")
        model_name = getattr(self._llm_client, "model_name", "unknown") if self._llm_client else "unknown"

        decision = self.permission_gate.evaluate(PermissionRequest(trace_id=trace_id, action=normalized_action))
        if decision["requires_human_approval"]:
            return {
                "action": normalized_action,
                "original_action": action,
                "action_details": action_details or {},
                "status": "pending_approval",
                "requires_human_approval": True,
                "risk_level": decision["risk_level"],
                "reason": decision["reason"],
                "execution_reasoning": execution_reasoning,
                "provider": self.provider_name,
                "model": model_name,
                "risk_hint": risk_hint,
            }

        return {
            "action": normalized_action,
            "original_action": action,
            "action_details": action_details or {},
            "status": "mock_executed",
            "requires_human_approval": False,
            "risk_level": decision["risk_level"],
            "reason": decision["reason"],
            "execution_reasoning": execution_reasoning,
            "provider": self.provider_name,
            "model": model_name,
            "risk_hint": risk_hint,
        }
