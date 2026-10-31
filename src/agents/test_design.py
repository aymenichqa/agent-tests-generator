"""
TestDesign Agent — Conception de cas de tests.
"""

import logging

from src.agents.base import AgentBase
from src.models.node_types import TaskType
from src.agents.router import ModelRouter
from src.models.graph_models import AgentState
from src.models.node_types import AgentDependencies
from src.models.agent_models import TestCaseModel, TestStepModel, TestType
from src.agents.executor import TokenUsage
from src.prompts.manager import PromptManager
from src.utils.json_parser import extract_json, JSONParseError

logger = logging.getLogger("agents.test_design")


class TestDesignAgent(AgentBase):
    # Nombre d'appels LLM simultanes pour la micro-generation par element.
    # Valide sur qwen/qwen3.8-27b / ia.sofiasolutions.io dans l'etat ACTUEL
    # de l'infra (mesures 5 + 15 regles : 0 erreur, gain ~1.8x, pas de
    # saturation). A REVALIDER si le modele ou l'infra change — voir
    # docs/06-internals/known-issues.md.
    PARALLEL_CALLS = 3

    @property
    def agent_name(self) -> str:
        return "test_design"

    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.test_design")

    def execute(self, state: AgentState) -> dict:
        if not state.parsed_spec:
            self._logger.warning("Aucune spécification à analyser.")
            return {"draft_test_cases": []}

        if not state.requirement_report:
            self._logger.warning("Aucun RequirementReport disponible.")
            return {"draft_test_cases": []}

        deps = self._dependencies
        if deps is None:
            return self._execute_fallback(state, "Aucune dépendance injectée")

        prompt_manager: PromptManager = deps.prompt_manager
        executor = deps.executor
        router: ModelRouter = deps.router

        if prompt_manager is None or executor is None or router is None:
            return self._execute_fallback(state, "Dépendances insuffisantes")

        try:
            system_prompt = prompt_manager.get("test_design")
        except FileNotFoundError:
            return self._execute_fallback(
                state, "Prompt introuvable : prompts/v1/test_design.md"
            )

        # Micro-generation : UN appel LLM par element testable (REQ/RG/EX),
        # executes par vagues de PARALLEL_CALLS appels simultanes en
        # streaming SSE (filet anti-524). Les echecs restent isoles par
        # element : un appel en erreur ne compromet pas les autres.
        items = self._collect_items(state)
        if not items:
            return self._execute_fallback(
                state, "Aucun element testable detecte (0 REQ/RG/EX)"
            )

        model = router.select(TaskType.TEST_DESIGN)
        user_prompts = [
            self._build_item_prompt(state, kind, code, text)
            for kind, code, text in items
        ]

        results = executor.execute_parallel(
            system_prompt=system_prompt,
            user_prompts=user_prompts,
            model=model,
            task_type=TaskType.TEST_DESIGN,
            parallel=self.PARALLEL_CALLS,
        )

        all_cases: list[TestCaseModel] = []
        errors: list[str] = []
        token_usages: list[TokenUsage] = []
        for (kind, index, text), result in zip(items, results):
            item_id = f"{kind}{index}"
            if result.error:
                errors.append(
                    f"{self.agent_name}: échec de l'appel LLM pour {item_id} : "
                    f"{result.error}"
                )
                continue
            if isinstance(result.token_usage, TokenUsage):
                token_usages.append(result.token_usage)
            try:
                data = extract_json(result.content)
                cases = self._parse_cases(data)
            except (JSONParseError, KeyError, TypeError) as exc:
                errors.append(
                    f"{self.agent_name}: erreur de parsing JSON pour {item_id} : {exc}"
                )
                continue
            # Échec silencieux par élément : JSON valide mais 0 cas générés
            if not cases:
                errors.append(
                    f"{self.agent_name}: JSON valide mais vide (0 cas générés) "
                    f"pour {item_id}"
                )
                continue
            all_cases.extend(cases)

        # Détection d'une traçabilité incomplète : cas sans aucun ID de couverture
        cases_without_traceability = [
            tc
            for tc in all_cases
            if not (tc.requirement_ids or tc.business_rule_ids or tc.exception_ids)
        ]
        if cases_without_traceability:
            titles = ", ".join(
                f"'{tc.title}'" for tc in cases_without_traceability[:3]
            )
            suffix = (
                f" et {len(cases_without_traceability) - 3} autres"
                if len(cases_without_traceability) > 3
                else ""
            )
            errors.append(
                f"{self.agent_name}: {len(cases_without_traceability)} cas générés "
                f"sans aucun ID de traçabilité ({titles}{suffix})"
            )

        token_usage = self._aggregate_token_usage(token_usages, model)

        if not all_cases:
            # Aucun cas produit sur tous les elements : fallback global.
            reason = (
                errors[0].split(": ", 1)[1] if errors else "Aucun cas de test généré"
            )
            return self._execute_fallback(state, reason, token_usage)

        self._logger.info(
            "TestDesign terminé : %d cas générés pour %d éléments (%d erreur(s))",
            len(all_cases),
            len(items),
            len(errors),
        )
        result_payload = {
            "draft_test_cases": all_cases,
            "token_usage": token_usage,
        }
        if errors:
            result_payload["errors"] = errors
        return result_payload

    def _collect_items(self, state: AgentState) -> list[tuple[str, str, str]]:
        """
        Collecte les elements testables (REQ/RG/EX) avec leur unique_code.

        Utilise les unique_codes stables (ex: REQ-C01-02) pour garantir
        que le LLM reference les bons items dans requirement_ids/business_rule_ids/exception_ids.

        Raises:
            ValueError: Si un item n'a pas de unique_code (fail loudly).
        """
        from src.agents.spec_formatting import format_spec_items

        return format_spec_items(state.parsed_spec)

    def _build_item_prompt(
        self, state: AgentState, kind: str, code: str, item_text: str
    ) -> str:
        """
        Construit le prompt de micro-generation pour UN element testable.

        Sortie courte imposee (1 cas) : c'est la longueur de SORTIE, pas de
        l'entree, qui provoque les timeouts 524 (cf. known-issues.md).
        """
        spec = state.parsed_spec
        item_id = code

        lines = [f"# {spec.title}"]
        if spec.summary:
            lines.append(f"\nResume : {spec.summary}")
        if spec.main_flow:
            lines.append("\n## Flux principal")
            for step in spec.main_flow:
                lines.append(f"- {step}")

        lines.append(f"\n## Element a tester : {item_id}")
        lines.append(item_text)

        lines.append(
            "\n\nGenere EXACTEMENT UN cas de test pour cet element, au format JSON :\n"
            '{"test_cases": [{"title": "...", "description": "...", "type": "nominal", '
            '"preconditions": [], "steps": [{"action": "...", "expected": "..."}], '
            '"expected_results": [], "test_data": {}, "tags": [], '
            '"requirement_ids": [], "business_rule_ids": [], "exception_ids": [], '
            '"reasoning": "..."}]}'
            f"\nRenseigne \"{item_id}\" dans le champ de tracabilite correspondant "
            '("requirement_ids" si REQ, "business_rule_ids" si RG, "exception_ids" '
            "si EX) et laisse les autres listes vides."
        )
        return "\n".join(lines)

    @staticmethod
    def _aggregate_token_usage(
        usages: list[TokenUsage], model: str | None
    ) -> TokenUsage | None:
        """Somme les TokenUsage de tous les appels en un seul agregat."""
        if not usages:
            return None
        return TokenUsage(
            prompt_tokens=sum(u.prompt_tokens for u in usages),
            completion_tokens=sum(u.completion_tokens for u in usages),
            model=model or (usages[0].model or ""),
        )

    def _build_user_prompt(self, state: AgentState) -> str:
        from src.agents.spec_formatting import format_spec_items

        spec = state.parsed_spec
        report = state.requirement_report

        lines = [f"# {spec.title}"]
        if spec.summary:
            lines.append(f"\nResume : {spec.summary}")

        items = format_spec_items(spec)

        # Grouper par catégorie pour l'affichage
        current_kind = None
        for kind, code, text in items:
            if kind != current_kind:
                if kind == "REQ":
                    lines.append(f"\n## Exigences fonctionnelles detectees ({report.total_requirements})")
                elif kind == "RG":
                    lines.append("\n## Regles metier detectees")
                elif kind == "EX":
                    lines.append("\n## Exceptions et erreurs detectees")
                current_kind = kind
            lines.append(f"- {code}: {text}")

        if report.ambiguities:
            lines.append("\n## Ambiguites")
            for amb in report.ambiguities:
                lines.append(f"- {amb}")

        if report.missing:
            lines.append("\n## Exigences manquantes")
            for miss in report.missing:
                lines.append(f"- {miss}")

        # Injection du contexte RAG si disponible
        context = state.knowledge_context
        if context and (context.similar_specs or context.similar_test_suites):
            lines.append("\n\n## Contexte de specifications / suites similaires")
            lines.append(context.summary)
            for rec in context.recommendations[:3]:
                if rec.strip():
                    lines.append(f"\n- {rec.strip()}")

        return "\n".join(lines)

    def _parse_cases(self, data: dict) -> list[TestCaseModel]:
        """Parse les cas de tests depuis le dictionnaire JSON."""
        raw_cases = data.get("test_cases", [])
        cases = []

        for raw in raw_cases:
            steps = [
                TestStepModel(action=s["action"], expected=s.get("expected", ""))
                for s in raw.get("steps", [])
            ]

            test_type = TestType.NOMINAL
            type_str = raw.get("type", "nominal").lower()
            for t in TestType:
                if t.value == type_str:
                    test_type = t
                    break

            case = TestCaseModel(
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
            cases.append(case)

        return cases

    def _execute_fallback(
        self,
        state: AgentState,
        reason: str,
        token_usage=None,
    ) -> dict:
        self._logger.warning("Fallback TestDesign | raison=%s", reason)
        result = {
            "draft_test_cases": [],
            "errors": [f"{self.agent_name}: {reason}"],
        }
        if token_usage is not None:
            result["token_usage"] = token_usage
        return result
