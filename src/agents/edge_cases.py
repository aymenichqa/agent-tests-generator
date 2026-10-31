"""
EdgeCasesAgent — Génération des cas limites et d'erreur.
==========================================================

Produit des TestCaseModel de type boundary / error à partir
des règles métier, exceptions et scénarios de la spécification.

Alimente l'état du graphe :
    - `edge_cases`          : liste des cas limites (TestCaseModel).
    - `edge_cases_summary`  : synthèse texte de l'analyse.
"""

import logging

from src.agents.base import AgentBase
from src.models.node_types import TaskType
from src.agents.router import ModelRouter
from src.models.graph_models import AgentState
from src.models.node_types import AgentDependencies
from src.models.agent_models import TestCaseModel, TestStepModel, TestType
from src.prompts.manager import PromptManager
from src.utils.json_parser import extract_json, JSONParseError

logger = logging.getLogger("agents.edge_cases")


class EdgeCasesAgent(AgentBase):

    @property
    def agent_name(self) -> str:
        return "edge_cases"

    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.edge_cases")

    def execute(self, state: AgentState) -> dict:
        if not state.parsed_spec:
            self._logger.warning("Aucune spécification à analyser.")
            return {"edge_cases": []}

        deps = self._dependencies
        if deps is None:
            return self._execute_fallback(state, "Aucune dépendance injectée")

        prompt_manager: PromptManager = deps.prompt_manager
        executor = deps.executor
        router: ModelRouter = deps.router

        if prompt_manager is None or executor is None or router is None:
            return self._execute_fallback(state, "Dépendances insuffisantes")

        try:
            system_prompt = prompt_manager.get("edge_cases")
        except FileNotFoundError:
            return self._execute_fallback(
                state, "Prompt introuvable : prompts/v1/edge_cases.md"
            )

        user_prompt = self._build_user_prompt(state.parsed_spec)
        model = router.select(TaskType.EDGE_CASES)

        result = executor.execute(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            task_type=TaskType.EDGE_CASES,
        )

        if result.error:
            return self._execute_fallback(
                state, f"Erreur LLM : {result.error}", result.token_usage
            )

        try:
            data = extract_json(result.content)
            cases = self._parse_cases(data)
            self._logger.info("EdgeCases générés | nb=%d", len(cases))
            return {
                "edge_cases": cases,
                "edge_cases_summary": data.get("summary", ""),
                "token_usage": result.token_usage,
            }

        except JSONParseError as exc:
            return self._execute_fallback(
                state, f"Erreur de parsing JSON : {exc}", result.token_usage
            )

    def _build_user_prompt(self, spec) -> str:
        from src.agents.spec_formatting import format_spec_items

        lines = [f"# {spec.title}"]
        if spec.summary:
            lines.append(f"\nRésumé : {spec.summary}")

        items = format_spec_items(spec)

        # Grouper par catégorie pour l'affichage
        current_kind = None
        for kind, code, text in items:
            if kind != current_kind:
                if kind == "REQ":
                    lines.append("\nExigences fonctionnelles :")
                elif kind == "RG":
                    lines.append("\nRègles métier :")
                elif kind == "EX":
                    lines.append("\nExceptions et erreurs :")
                current_kind = kind
            lines.append(f"- {code}: {text}")

        if spec.main_flow:
            lines.append("\nScénario principal :")
            for s in spec.main_flow:
                lines.append(f"  - {s}")
        if spec.alternative_flows:
            lines.append("\nScénarios alternatifs :")
            for alt in spec.alternative_flows:
                lines.append(f"  - {alt.title if hasattr(alt, 'title') else alt}")
        if spec.constraints:
            lines.append("\nContraintes :")
            for c in spec.constraints:
                lines.append(f"  - {c}")

        return "\n".join(lines)

    def _parse_cases(self, data: dict) -> list[TestCaseModel]:
        """Parse les cas limites depuis le dictionnaire JSON."""
        raw_cases = data.get("edge_cases", [])
        cases = []

        for raw in raw_cases:
            steps = [
                TestStepModel(action=s["action"], expected=s.get("expected", ""))
                for s in raw.get("steps", [])
            ]

            test_type = TestType.BOUNDARY
            type_str = raw.get("type", "boundary").lower()
            for t in TestType:
                if t.value == type_str:
                    test_type = t
                    break

            cases.append(
                TestCaseModel(
                    title=raw.get("title", ""),
                    description=raw.get("description", ""),
                    type=test_type,
                    preconditions=raw.get("preconditions", []),
                    steps=steps,
                    expected_results=raw.get("expected_results", []),
                    test_data=raw.get("test_data", {}),
                    tags=raw.get("tags", []),
                    source_section=raw.get("source_section"),
                    requirement_ids=raw.get("requirement_ids", []),
                    business_rule_ids=raw.get("business_rule_ids", []),
                    exception_ids=raw.get("exception_ids", []),
                    reasoning=raw.get("reasoning"),
                    created_by_agent=self.agent_name,
                )
            )

        return cases

    def _execute_fallback(
        self,
        state: AgentState,
        reason: str,
        token_usage=None,
    ) -> dict:
        self._logger.warning("Fallback EdgeCases | raison=%s", reason)
        result = {
            "edge_cases": [],
            "errors": [f"{self.agent_name}: {reason}"],
        }
        if token_usage is not None:
            result["token_usage"] = token_usage
        return result