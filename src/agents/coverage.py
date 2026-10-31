"""
CoverageAgent — Analyse de couverture fonctionnelle.
"""

import logging

from src.agents.base import AgentBase
from src.models.node_types import TaskType
from src.agents.router import ModelRouter
from src.models.graph_models import AgentState
from src.models.node_types import AgentDependencies
from src.prompts.manager import PromptManager
from src.reports.coverage import CoverageBreakdown, CoverageReport
from src.utils.json_parser import extract_json, JSONParseError

logger = logging.getLogger("agents.coverage")


class CoverageAgent(AgentBase):

    @property
    def agent_name(self) -> str:
        return "coverage"

    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.coverage")

    def execute(self, state: AgentState) -> dict:
        deps = self._dependencies
        if deps is None:
            return self._execute_fallback(state, "Aucune dépendance injectée")

        prompt_manager: PromptManager = deps.prompt_manager
        executor = deps.executor
        router: ModelRouter = deps.router

        if prompt_manager is None or executor is None or router is None:
            return self._execute_fallback(
                state,
                "Dépendances insuffisantes (prompt_manager, executor, router requis)",
            )

        try:
            system_prompt = prompt_manager.get("coverage")
        except FileNotFoundError:
            return self._execute_fallback(
                state, "Prompt introuvable : prompts/v1/coverage.md"
            )

        user_prompt = self._build_user_prompt(state)
        model = router.select(TaskType.COVERAGE)

        result = executor.execute(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            task_type=TaskType.COVERAGE,
        )

        if result.error:
            return self._execute_fallback(
                state, f"Erreur LLM : {result.error}", result.token_usage
            )

        try:
            data = extract_json(result.content)
            report = self._parse_coverage_report(data, state=state)
            self._logger.info(
                "CoverageReport généré | score=%s | req=%.2f | rg=%.2f | ex=%.2f",
                report.score,
                report.requirements.score,
                report.business_rules.score,
                report.exceptions.score,
            )
            return {
                "coverage_report": report,
                "token_usage": result.token_usage,
            }

        except (JSONParseError, KeyError, TypeError) as exc:
            return self._execute_fallback(
                state, f"Erreur de parsing JSON : {exc}", result.token_usage
            )

    def _build_user_prompt(self, state: AgentState) -> str:
        spec = state.parsed_spec
        lines = [f"# {spec.title}"]
        if spec.summary:
            lines.append(f"\nRésumé : {spec.summary}")
        if spec.actors:
            lines.append(f"\nActeurs : {', '.join(spec.actors)}")
        from src.agents.spec_formatting import format_spec_items

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
                    lines.append("\nExceptions et cas d'erreur :")
                current_kind = kind
            lines.append(f"  - {code}: {text}")

        if state.requirement_report:
            req = state.requirement_report
            lines.append("\nRapport d'exigences :")
            lines.append(f"  - Total exigences : {req.total_requirements}")
            lines.append(f"  - Complète : {req.is_complete}")
            if req.ambiguities:
                lines.append("  - Ambiguïtés :")
                for a in req.ambiguities:
                    lines.append(f"    - {a}")
            if req.missing:
                lines.append("  - Manquantes :")
                for m in req.missing:
                    lines.append(f"    - {m}")

        if state.draft_test_cases:
            lines.append(f"\nCas de tests proposés ({len(state.draft_test_cases)}) :")
            for tc in state.draft_test_cases:
                refs = []
                if tc.requirement_ids:
                    refs.append(f"REQ: {', '.join(tc.requirement_ids)}")
                if tc.business_rule_ids:
                    refs.append(f"RG: {', '.join(tc.business_rule_ids)}")
                if tc.exception_ids:
                    refs.append(f"EX: {', '.join(tc.exception_ids)}")
                ref_str = f" [couvre: {' | '.join(refs)}]" if refs else ""
                lines.append(f"  - {tc.title} ({tc.type.value}){ref_str}")
                if tc.steps:
                    for step in tc.steps:
                        lines.append(f"    - {step.action} \u2192 {step.expected}")
        else:
            lines.append("\nAucun cas de test proposé.")

        return "\n".join(lines)

    @staticmethod
    def _parse_breakdown(data: dict | None) -> CoverageBreakdown:
        """Parse un bloc de couverture par catégorie."""
        if not isinstance(data, dict):
            return CoverageBreakdown()
        return CoverageBreakdown(
            score=float(data.get("score", 0.0)),
            covered=data.get("covered", []),
            uncovered=data.get("uncovered", []),
        )

    def _compute_category_coverage(
        self, state: AgentState, category: str
    ) -> CoverageBreakdown:
        from src.agents.spec_formatting import format_spec_items

        spec = state.parsed_spec
        cases = (state.draft_test_cases or []) + (state.edge_cases or [])

        category_map = {
            "requirements": "requirement_ids",
            "business_rules": "business_rule_ids",
            "exceptions": "exception_ids",
        }

        if category not in category_map:
            return CoverageBreakdown()

        case_field = category_map[category]

        # Get all items with their codes
        all_items = format_spec_items(spec)
        # Filter by category
        kind_map = {"requirements": "REQ", "business_rules": "RG", "exceptions": "EX"}
        target_kind = kind_map[category]
        category_items = [(kind, code, text) for kind, code, text in all_items if kind == target_kind]

        if not category_items:
            return CoverageBreakdown(score=0.0, covered=[], uncovered=[])

        # Collect all covered IDs from test cases
        covered_ids = set()
        for tc in cases:
            ids = getattr(tc, case_field, [])
            covered_ids.update(ids)

        # For each item, check if ANY of its codes is covered
        covered = []
        uncovered = []
        for kind, code, text in category_items:
            # Get all codes for this item (from the spec, read directly —
            # never reconstructed from text)
            item_codes = self._get_item_codes(spec, category, code)
            if any(c in covered_ids for c in item_codes):
                covered.append(code)
            else:
                uncovered.append(code)

        score = len(covered) / len(category_items) if category_items else 0.0
        return CoverageBreakdown(score=score, covered=covered, uncovered=uncovered)

    @staticmethod
    def _get_item_codes(spec, category: str, code: str) -> list[str]:
        """
        Retourne tous les codes associés à un item de la spec.

        L'item est identifié par son premier code stable (tel que produit
        par format_spec_items), et la liste complète de ses unique_codes
        est lue DIRECTEMENT sur l'objet — jamais reconstruite par
        comparaison de texte (fragile : deux fonctions devaient produire
        le même texte au caractère près).

        Pour les items fusionnés, cela inclut tous les codes de l'union.
        """
        from src.analysis.models import ExceptionSpec

        if category == "requirements":
            items = spec.requirements or []
        elif category == "business_rules":
            items = spec.business_rules or []
        elif category == "exceptions":
            items = spec.exceptions or []
        else:
            return []

        for item in items:
            if isinstance(item, dict):
                item_codes = item.get("unique_codes", []) or []
            elif isinstance(item, ExceptionSpec):
                item_codes = item.unique_codes or []
            else:
                continue
            # Un seul chemin de lecture pour les trois catégories :
            # le premier code est la clé d'identité de l'item.
            if item_codes and item_codes[0] == code:
                return list(item_codes)

        return []

    def _parse_coverage_report(
        self, data: dict, state: AgentState | None = None
    ) -> CoverageReport:
        req_breakdown = (
            self._compute_category_coverage(state, "requirements")
            if state
            else self._parse_breakdown(data.get("requirements"))
        )
        rg_breakdown = (
            self._compute_category_coverage(state, "business_rules")
            if state
            else self._parse_breakdown(data.get("business_rules"))
        )
        ex_breakdown = (
            self._compute_category_coverage(state, "exceptions")
            if state
            else self._parse_breakdown(data.get("exceptions"))
        )

        # Score global pondere par le nombre total d'elements dans chaque categorie.
        # Une categorie vide n'apporte ni point ni penalite (pas de 1.0 artificiel).
        total_items = (
            len(req_breakdown.covered) + len(req_breakdown.uncovered)
            + len(rg_breakdown.covered) + len(rg_breakdown.uncovered)
            + len(ex_breakdown.covered) + len(ex_breakdown.uncovered)
        )
        total_covered = (
            len(req_breakdown.covered)
            + len(rg_breakdown.covered)
            + len(ex_breakdown.covered)
        )
        global_score = total_covered / total_items if total_items else 0.0

        return CoverageReport(
            score=global_score,
            requirements=req_breakdown,
            business_rules=rg_breakdown,
            exceptions=ex_breakdown,
            covered=data.get("covered", []),
            uncovered=data.get("uncovered", []),
            missing_scenarios=data.get("missing_scenarios", []),
        )

    def _execute_fallback(
        self,
        state: AgentState,
        reason: str,
        token_usage=None,
    ) -> dict:
        spec = state.parsed_spec
        reqs = spec.requirements or []
        fallback = CoverageReport(
            score=0.0,
            covered=[],
            uncovered=list(reqs),
            missing_scenarios=["Analyse non réalisée : erreur lors de l'appel LLM"],
        )
        self._logger.warning("Fallback CoverageReport | raison=%s", reason)
        result = {
            "coverage_report": fallback,
            "errors": [f"{self.agent_name}: {reason}"],
        }
        if token_usage is not None:
            result["token_usage"] = token_usage
        return result
