from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError


class LLMProviderError(RuntimeError):
    """Base exception for provider selection and runtime failures."""


class LLMProviderConfigurationError(LLMProviderError):
    """Raised when provider configuration is invalid or incomplete."""


class LLMProviderRuntimeError(LLMProviderError):
    """Raised when a selected provider fails while serving a request."""


class _ReasoningResponse(BaseModel):
    reasoning: str
    answer: str
    suggested_action: str
    action_details: dict[str, Any] | None = None
    reasoning_steps: list[str] | None = None
    confidence_breakdown: dict[str, Any] | None = None
    evidence_scores: list[dict[str, Any]] | None = None


class _QueryExpansionResponse(BaseModel):
    expanded_terms: list[str] = Field(default_factory=list)


class _ExecutionAssessmentResponse(BaseModel):
    normalized_action: str
    reasoning: str
    risk_hint: str | None = None


class ReasoningLLMClient(Protocol):
    provider_name: str
    model_name: str

    def reason(
        self,
        query: str,
        confidence: float,
        top_sources: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        ...

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        ...

    def assess_execution_action(self, action: str, action_details: dict[str, Any] | None) -> dict[str, Any]:
        ...


@dataclass
class LangChainReasoningLLMClient:
    provider_name: str
    model_name: str
    chat_model: Any

    def _extract_json_payload(self, content: str) -> dict[str, Any]:
        normalized = content.strip()

        if normalized.startswith("```"):
            lines = normalized.splitlines()
            if len(lines) >= 3:
                normalized = "\n".join(lines[1:-1]).strip()

        start = normalized.find("{")
        end = normalized.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise LLMProviderRuntimeError("Provider did not return valid JSON output.")

        try:
            return json.loads(normalized[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMProviderRuntimeError("Provider returned malformed JSON output.") from exc

    def reason(
        self,
        query: str,
        confidence: float,
        top_sources: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        prompt = (
            "You are a reliability copilot. Return ONLY JSON with this schema: "
            '{"reasoning": string, "answer": string, "suggested_action": string, '
            '"action_details": {"intent": string, "tool": string|null, "parameters": object, '
            '"approval_required": boolean, "risk_hint": string|null}, '
            '"reasoning_steps": [string, ...], '
            '"confidence_breakdown": object, '
            '"evidence_scores": [{"title": string, "path": string, "source_type": string, '
            '"raw_score": number, "priority_score": number}, ...]}. '
            "Do not include markdown fences or extra keys. "
            f"Query: {query}\n"
            f"Confidence (0-1): {confidence}\n"
            f"Top sources: {json.dumps(top_sources, ensure_ascii=True)}\n"
            f"Dedup summary: {json.dumps(dedup_summary or {}, ensure_ascii=True)}"
        )

        try:
            response = self.chat_model.invoke(prompt)
            content = str(getattr(response, "content", "") or "")
            parsed = self._extract_json_payload(content)
            validated = _ReasoningResponse.model_validate(parsed)
        except LLMProviderRuntimeError:
            raise
        except ValidationError as exc:
            raise LLMProviderRuntimeError("Provider response schema validation failed.") from exc
        except Exception as exc:  # pragma: no cover - network/provider dependent
            raise LLMProviderRuntimeError(f"{self.provider_name} provider request failed: {exc}") from exc

        return {
            "reasoning": validated.reasoning,
            "answer": validated.answer,
            "suggested_action": validated.suggested_action,
            "action_details": validated.action_details,
            "reasoning_steps": validated.reasoning_steps,
            "confidence_breakdown": validated.confidence_breakdown,
            "evidence_scores": validated.evidence_scores,
        }

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        prompt = (
            "You are helping retrieval quality for reliability incidents. Return ONLY JSON with this schema: "
            '{"expanded_terms": [string, ...]}. '
            "Expand query tokens with incident/systems synonyms. Keep it concise (max 8 terms). "
            "Do not include markdown fences or extra keys. "
            f"Query: {query}\n"
            f"Existing query tokens: {json.dumps(query_tokens, ensure_ascii=True)}"
        )

        try:
            response = self.chat_model.invoke(prompt)
            content = str(getattr(response, "content", "") or "")
            parsed = self._extract_json_payload(content)
            validated = _QueryExpansionResponse.model_validate(parsed)
        except LLMProviderRuntimeError:
            raise
        except ValidationError as exc:
            raise LLMProviderRuntimeError("Provider query-expansion schema validation failed.") from exc
        except Exception as exc:  # pragma: no cover - network/provider dependent
            raise LLMProviderRuntimeError(f"{self.provider_name} provider request failed: {exc}") from exc

        deduped_terms: list[str] = []
        seen: set[str] = set()
        for term in validated.expanded_terms:
            normalized = str(term).strip().lower()
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped_terms.append(normalized)
            if len(deduped_terms) >= 8:
                break
        return deduped_terms

    def assess_execution_action(self, action: str, action_details: dict[str, Any] | None) -> dict[str, Any]:
        prompt = (
            "You are evaluating a proposed reliability action before HITL approval. Return ONLY JSON with this schema: "
            '{"normalized_action": string, "reasoning": string, "risk_hint": string|null}. '
            "Do not include markdown fences or extra keys. "
            f"Suggested action: {action}\n"
            f"Action details: {json.dumps(action_details or {}, ensure_ascii=True)}"
        )

        try:
            response = self.chat_model.invoke(prompt)
            content = str(getattr(response, "content", "") or "")
            parsed = self._extract_json_payload(content)
            validated = _ExecutionAssessmentResponse.model_validate(parsed)
        except LLMProviderRuntimeError:
            raise
        except ValidationError as exc:
            raise LLMProviderRuntimeError("Provider execution-assessment schema validation failed.") from exc
        except Exception as exc:  # pragma: no cover - network/provider dependent
            raise LLMProviderRuntimeError(f"{self.provider_name} provider request failed: {exc}") from exc

        return {
            "normalized_action": validated.normalized_action,
            "reasoning": validated.reasoning,
            "risk_hint": validated.risk_hint,
        }


@dataclass
class LazyReasoningLLMClient:
    provider_name: str
    model_name: str = "pending"
    _resolved_client: ReasoningLLMClient | None = None

    def _resolve_client(self) -> ReasoningLLMClient:
        if self._resolved_client is None:
            client = create_reasoning_llm_client(self.provider_name)
            if client is None:
                raise LLMProviderRuntimeError("No reasoning provider is configured for this request.")
            self._resolved_client = client
            self.model_name = getattr(client, "model_name", self.model_name)
        return self._resolved_client

    def reason(
        self,
        query: str,
        confidence: float,
        top_sources: list[dict[str, Any]],
        dedup_summary: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return self._resolve_client().reason(
            query=query,
            confidence=confidence,
            top_sources=top_sources,
            dedup_summary=dedup_summary,
        )

    def expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        return self._resolve_client().expand_query_terms(query=query, query_tokens=query_tokens)

    def assess_execution_action(self, action: str, action_details: dict[str, Any] | None) -> dict[str, Any]:
        return self._resolve_client().assess_execution_action(action=action, action_details=action_details)


def create_reasoning_llm_client(provider_name: str | None) -> ReasoningLLMClient | None:
    normalized = (provider_name or "").strip().lower()
    if not normalized:
        return None

    if normalized not in {"groq", "apfel"}:
        raise LLMProviderConfigurationError("LLM_PROVIDER must be either 'groq' or 'apfel'.")

    if normalized == "groq":
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
        if not api_key:
            raise LLMProviderConfigurationError("GROQ_API_KEY is required when LLM_PROVIDER=groq.")

        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise LLMProviderConfigurationError(
                "langchain-groq is required for LLM_PROVIDER=groq. Install backend requirements."
            ) from exc

        chat_model = ChatGroq(api_key=api_key, model=model_name, temperature=0)
        return LangChainReasoningLLMClient(provider_name="groq", model_name=model_name, chat_model=chat_model)

    base_url = os.getenv("APFEL_BASE_URL", "").strip()
    api_key = os.getenv("APFEL_API_KEY", "").strip()
    model_name = os.getenv("APFEL_MODEL", "apfel-chat").strip()
    if not base_url:
        raise LLMProviderConfigurationError("APFEL_BASE_URL is required when LLM_PROVIDER=apfel.")
    if not api_key:
        raise LLMProviderConfigurationError("APFEL_API_KEY is required when LLM_PROVIDER=apfel.")

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise LLMProviderConfigurationError(
            "langchain-openai is required for LLM_PROVIDER=apfel. Install backend requirements."
        ) from exc

    chat_model = ChatOpenAI(api_key=api_key, model=model_name, base_url=base_url, temperature=0)
    return LangChainReasoningLLMClient(provider_name="apfel", model_name=model_name, chat_model=chat_model)


def create_shared_reasoning_llm_client(provider_name: str | None) -> ReasoningLLMClient | None:
    normalized = (provider_name or "").strip().lower()
    if not normalized:
        return None
    return LazyReasoningLLMClient(provider_name=normalized)