"""StoreMemoryAgent — assemblage, persistance et indexation RAG de la suite finale.

Termine le workflow : a partir de l'etat du graphe, il construit une
TestSuiteModel finale (cas finalises VALIDATED/REJECTED/DRAFT selon la
review, + couverture, + metriques).

Il persiste ensuite :
    - la suite dans la base de donnees (TestSuiteRecord)
    - un resume dans l'index RAG (MemoryEntry) pour enrichir les futurs runs.
"""

import logging
import uuid
from dataclasses import replace

from src.agents.base import AgentBase
from src.models.agent_models import TestCaseModel, TestCaseStatus, TestSuiteModel
from src.models.graph_models import AgentState

logger = logging.getLogger("agents.store_memory")


class StoreMemoryAgent(AgentBase):
    @property
    def agent_name(self) -> str:
        return "store_memory"

    def __init__(self, dependencies=None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.store_memory")

    def execute(self, state: AgentState) -> dict:
        parsed = state.parsed_spec
        if parsed is None:
            return {"test_suite": None, "current_node": "store_memory"}

        cases = self._finalize_cases(state)
        suite = TestSuiteModel(
            specification_title=parsed.title,
            specification_id=str(getattr(parsed, "title", "")),
            test_cases=cases,
            coverage_report=state.coverage_report,
            review_report=state.review_report,
            metrics=self._collect_metrics(state, parsed),
            metadata={"source_spec": parsed.title},
        )
        self._logger.info("TestSuite assemblee | cas=%d", len(cases))
        self._persist(suite, state)
        return {"test_suite": suite, "current_node": "store_memory"}

    def _finalize_cases(self, state: AgentState) -> list[TestCaseModel]:
        review = state.review_report
        validated: set[str] = set()
        rejected: set[str] = set()
        if review is not None:
            validated = set(review.validated or [])
            rejected = {getattr(r, "title", "") for r in (review.rejected or [])}

        def _matched(title: str, labels: set[str]) -> bool:
            return any(
                label == title or label.startswith(title + " (") for label in labels
            )

        out = []
        for tc in (state.draft_test_cases or []) + (state.edge_cases or []):
            if _matched(tc.title, validated):
                status = TestCaseStatus.VALIDATED
            elif _matched(tc.title, rejected):
                status = TestCaseStatus.REJECTED
            else:
                status = TestCaseStatus.DRAFT
            out.append(replace(tc, status=status))
        return out

    def _collect_metrics(self, state: AgentState, parsed) -> dict:
        return {
            "coverage_score": getattr(state.coverage_report, "score", 0.0)
            if state.coverage_report
            else 0.0,
            "review_score": getattr(state.review_report, "quality_score", 0.0)
            if state.review_report
            else 0.0,
            "requirements_count": len(parsed.requirements or []),
            "business_rules_count": len(parsed.business_rules or []),
            "exceptions_count": len(parsed.exceptions or []),
            "draft_cases": len(state.draft_test_cases or []),
            "edge_cases": len(state.edge_cases or []),
        }

    def _persist(self, suite: TestSuiteModel, state: AgentState) -> None:
        deps = self._dependencies
        if deps is None:
            return
        rag_index = getattr(deps, "rag_index", None)
        llm_client = getattr(deps, "llm_client", None)
        db_session = getattr(deps, "db_session", None)

        if db_session is not None:
            try:
                from src.db import crud

                status = (
                    "validated"
                    if any(
                        tc.status == TestCaseStatus.VALIDATED for tc in suite.test_cases
                    )
                    else "draft"
                )
                crud.create_suite_record(
                    db_session,
                    suite_id=str(uuid.uuid4()),
                    run_id=getattr(state, "run_id", ""),
                    spec_title=suite.specification_title,
                    status=status,
                    cases_count=len(suite.test_cases),
                    metrics=suite.metrics,
                )
                self._logger.info("Suite de tests persistee en DB")
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("Echec persistance DB de la suite : %s", exc)

        if rag_index is not None and llm_client is not None:
            # --- Import des utilitaires dédiés (un seul point source) ---
            # Réutilise exactement _case_to_text / _case_metadata du script
            # debug/index_existing_cases.py — même format, cohérence garantie.
            from debug.index_existing_cases import _case_to_text, _case_metadata

            try:
                summary = self._build_summary(suite)
                vectors = llm_client.embed([summary])
                if vectors:
                    rag_index.add(
                        entry_id=str(uuid.uuid4()),
                        text=summary,
                        embedding=vectors[0],
                        metadata={
                            "kind": "test_suite",
                            "spec_title": suite.specification_title,
                            "cases_count": len(suite.test_cases),
                            "coverage_score": suite.metrics.get("coverage_score", 0.0),
                            "review_score": suite.metrics.get("review_score", 0.0),
                        },
                    )
                    self._logger.info("Suite de tests indexee dans le RAG")
            except Exception as exc:  # noqa: BLE001
                self._logger.warning("Echec indexation RAG de la suite : %s", exc)

            # --- Indexation individuelle de chaque cas (A2) ---
            for case in suite.test_cases:
                try:
                    case_text = _case_to_text(case)
                    embeddings = llm_client.embed([case_text])
                    if embeddings:
                        rag_index.add(
                            entry_id=str(uuid.uuid4()),
                            text=case_text,
                            embedding=embeddings[0],
                            metadata=_case_metadata(case),
                        )
                        self._logger.info("Cas indexe individuellement: %s", case.title)
                except Exception as exc:  # noqa: BLE001
                    self._logger.warning(
                        "Echec indexation cas '%s' : %s — passage au cas suivant",
                        getattr(case, "title", "<unknown>"),
                        exc,
                    )

    def _build_summary(self, suite: TestSuiteModel) -> str:
        lines = [
            f"Suite de tests pour : {suite.specification_title}",
            f"Nombre de cas : {len(suite.test_cases)}",
            f"Couverture : {suite.metrics.get('coverage_score', 0.0):.2f}",
            f"Review : {suite.metrics.get('review_score', 0.0):.2f}",
        ]
        for tc in suite.test_cases[:10]:
            lines.append(f"- {tc.title} ({tc.type.value}) : {tc.description}")
        return "\n".join(lines)
