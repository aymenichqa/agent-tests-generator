"""
KnowledgeAgent — preparation du contexte RAG.
==============================================

Recupere les specifications et suites de tests similaires a la spec
en cours d'analyse et les injecte dans le state sous forme de
KnowledgeContext.
"""

import logging

from src.agents.base import AgentBase
from src.memory.retrieval import MemoryRetriever
from src.models.graph_models import AgentState

logger = logging.getLogger("agents.knowledge")


class KnowledgeAgent(AgentBase):
    """Agent RAG : enrichit l'etat avec un contexte de connaissances."""

    @property
    def agent_name(self) -> str:
        return "knowledge"

    def __init__(self, dependencies=None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.knowledge")

    def execute(self, state: AgentState) -> dict:
        deps = self._dependencies
        if deps is None:
            return {"knowledge_context": None}

        rag_index = getattr(deps, "rag_index", None)
        llm_client = getattr(deps, "llm_client", None)

        if rag_index is None or llm_client is None:
            self._logger.debug("RAG non configure (rag_index ou llm_client absent)")
            return {"knowledge_context": None}

        if rag_index.count() == 0:
            self._logger.debug("Index RAG vide — pas de contexte similaire")
            return {"knowledge_context": None}

        parsed = state.parsed_spec
        query = parsed.title or ""
        if parsed.summary:
            query += " " + parsed.summary

        try:
            retriever = MemoryRetriever(rag_index)
            context = retriever.build_context(
                query_text=query,
                llm=llm_client,
                top_k=3,
                spec_kind="specification",
            )
            self._logger.info(
                "Contexte RAG construit | specs=%d | suites=%d",
                len(context.similar_specs),
                len(context.similar_test_suites),
            )
            return {"knowledge_context": context}
        except Exception as exc:  # noqa: BLE001 — fallback tolerant
            self._logger.warning("Echec de la recuperation RAG : %s", exc)
            return {"knowledge_context": None}
