from __future__ import annotations

import os
import re
from typing import Any

from src.adapters.llm_client import LLMProviderError, LLMProviderRuntimeError, ReasoningLLMClient
from src.memory.three_tier_memory import MemoryDocument, ThreeTierMemory
from src.vector_store.llamaindex_hybrid import LlamaIndexHybridService


class RetrievalSwarm:
    def __init__(
        self,
        memory: ThreeTierMemory,
        max_sources: int = 4,
        provider_name: str | None = None,
        llm_client: ReasoningLLMClient | None = None,
    ) -> None:
        self.memory = memory
        self.max_sources = max_sources
        self.semantic_service = LlamaIndexHybridService()
        self.provider_name = (provider_name if provider_name is not None else os.getenv("LLM_PROVIDER", "")).strip().lower()
        self._llm_client = llm_client

    def _get_llm_client(self) -> ReasoningLLMClient:
        if self._llm_client is None:
            raise LLMProviderRuntimeError("No retrieval provider client is configured for this request.")
        return self._llm_client

    def _tokenize(self, query: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 2]

    def _score(self, doc: MemoryDocument, query_tokens: list[str]) -> int:
        haystack = f"{doc.title} {doc.content}".lower()
        return sum(haystack.count(token) for token in query_tokens)

    def _keyword_retrieve(self, query: str, query_tokens: list[str] | None = None) -> dict:
        active_query_tokens = query_tokens if query_tokens is not None else self._tokenize(query)
        docs = self.memory.load_documents()
        ranked: list[tuple[int, MemoryDocument]] = []
        for doc in docs:
            ranked.append((self._score(doc, active_query_tokens), doc))

        ranked.sort(key=lambda item: item[0], reverse=True)
        top_ranked = ranked[: self.max_sources]
        if top_ranked and top_ranked[0][0] == 0:
            top_ranked = ranked[: min(len(ranked), 2)]

        sources: list[dict] = []
        for score, doc in top_ranked:
            snippet = " ".join(doc.content.strip().split())[:220]
            sources.append(
                {
                    "title": doc.title,
                    "path": doc.path,
                    "source_type": doc.source_type,
                    "snippet": snippet,
                    "score": score,
                }
            )

        return {
            "query": query,
            "sources": sources,
            "source_count": len(sources),
            "retrieval_method": "keyword",
            "query_tokens": active_query_tokens,
        }

    def _merge_sources(self, primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        for source in primary + secondary:
            key = (str(source.get("path", "")), str(source.get("title", "")))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(source)
            if len(merged) >= self.max_sources:
                break

        return merged

    def _llm_expand_query_terms(self, query: str, query_tokens: list[str]) -> list[str]:
        client = self._get_llm_client()
        try:
            expanded_terms = client.expand_query_terms(query=query, query_tokens=query_tokens)
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderRuntimeError(f"{self.provider_name} retrieval expansion failed: {exc}") from exc

        combined_terms: list[str] = []
        seen_terms: set[str] = set()
        for token in [*query_tokens, *expanded_terms]:
            normalized = str(token).strip().lower()
            if len(normalized) < 3:
                continue
            if normalized in seen_terms:
                continue
            seen_terms.add(normalized)
            combined_terms.append(normalized)

        return combined_terms

    def run(self, query: str) -> dict:
        if not self.provider_name:
            raise LLMProviderRuntimeError("Retrieval requires a configured LLM provider.")

        keyword_result = self._keyword_retrieve(query=query)
        keyword_sources = keyword_result["sources"]
        query_tokens = keyword_result.get("query_tokens", [])
        expanded_query_tokens = self._llm_expand_query_terms(query=query, query_tokens=query_tokens)
        llm_query_expansion = {
            "used": expanded_query_tokens != query_tokens,
            "provider": self.provider_name,
            "model": getattr(self._llm_client, "model_name", "unknown") if self._llm_client else "unknown",
            "expanded_query_tokens": expanded_query_tokens,
        }

        if expanded_query_tokens != query_tokens:
            expanded_keyword_result = self._keyword_retrieve(query=query, query_tokens=expanded_query_tokens)
            keyword_sources = self._merge_sources(keyword_sources, expanded_keyword_result["sources"])

        semantic_result = self.semantic_service.run(
            query=query,
            max_sources=self.max_sources,
            keyword_sources=keyword_sources,
        )

        sources = semantic_result["sources"]
        return {
            "query": query,
            "sources": sources,
            "source_count": len(sources),
            "retrieval_method": semantic_result["retrieval_method"],
            "query_tokens": llm_query_expansion["expanded_query_tokens"],
            "llm_query_expansion": llm_query_expansion,
        }
