from __future__ import annotations

import os
from typing import Any


class LlamaIndexHybridService:
    """Provides semantic retrieval through LlamaIndex + Milvus with keyword fallback."""

    def __init__(self, mode: str | None = None) -> None:
        self.mode = (mode or os.getenv("RETRIEVAL_MODE", "keyword")).strip().lower()
        self.collection_name = os.getenv("MILVUS_COLLECTION_NAME", "uniops_documents")
        self.milvus_host = os.getenv("MILVUS_HOST", "127.0.0.1")
        self.milvus_port = int(os.getenv("MILVUS_PORT", "19530"))

    def _semantic_retrieve(self, query: str, max_sources: int) -> list[dict[str, Any]]:
        try:
            from llama_index.core import VectorStoreIndex 
            from llama_index.vector_stores.milvus import MilvusVectorStore  
        except Exception:
            return []

        try:
            vector_store = MilvusVectorStore(
                collection_name=self.collection_name,
                host=self.milvus_host,
                port=self.milvus_port,
                overwrite=False,
            )
            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            retriever = index.as_retriever(similarity_top_k=max_sources)
            nodes = retriever.retrieve(query)
        except Exception:
            return []

        sources: list[dict[str, Any]] = []
        for node in nodes:
            metadata = dict(getattr(node, "metadata", {}) or {})
            content = ""
            if hasattr(node, "get_content"):
                content = str(node.get_content() or "")
            elif hasattr(node, "node") and hasattr(node.node, "get_content"):
                content = str(node.node.get_content() or "")

            sources.append(
                {
                    "title": str(metadata.get("title") or metadata.get("doc_title") or "Vector Source"),
                    "path": str(metadata.get("path") or metadata.get("source_path") or "vector://milvus"),
                    "source_type": str(metadata.get("source_type") or "vector"),
                    "snippet": " ".join(content.split())[:220],
                    "score": float(getattr(node, "score", 0.0) or 0.0),
                }
            )

        return sources

    def _merge_sources(
        self,
        semantic_sources: list[dict[str, Any]],
        keyword_sources: list[dict[str, Any]],
        max_sources: int,
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()

        for source in semantic_sources + keyword_sources:
            key = (str(source.get("path", "")), str(source.get("title", "")))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            merged.append(source)
            if len(merged) >= max_sources:
                break

        return merged

    def run(
        self,
        query: str,
        max_sources: int,
        keyword_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.mode == "keyword":
            return {"sources": keyword_sources[:max_sources], "retrieval_method": "keyword"}

        semantic_sources = self._semantic_retrieve(query=query, max_sources=max_sources)

        if self.mode == "semantic":
            if semantic_sources:
                return {"sources": semantic_sources[:max_sources], "retrieval_method": "semantic"}
            return {
                "sources": keyword_sources[:max_sources],
                "retrieval_method": "keyword_fallback",
            }

        # Hybrid mode: semantic first, then keyword fill.
        if semantic_sources:
            merged = self._merge_sources(semantic_sources, keyword_sources, max_sources=max_sources)
            return {"sources": merged, "retrieval_method": "hybrid"}

        return {
            "sources": keyword_sources[:max_sources],
            "retrieval_method": "keyword_fallback",
        }
