"""
BusinessRulesAgent — Extraction des règles métier.
====================================================

Analyse de la spécification pour identifier les règles métier
explicites ET implicites, structurées dans un BusinessRulesReport.

L'agent alimente l'État du graphe :
    - `business_rules_report` : rapport structuré.
    - `business_rules`       : liste texte des règles (RG1, RG2, ...).
"""

import logging

from src.agents.base import AgentBase
from src.models.node_types import TaskType
from src.agents.router import ModelRouter
from src.models.graph_models import AgentState
from src.models.node_types import AgentDependencies
from src.prompts.manager import PromptManager
from src.reports.business_rules import BusinessRule, BusinessRulesReport
from src.utils.json_parser import extract_json, JSONParseError

logger = logging.getLogger("agents.business_rules")


class BusinessRulesAgent(AgentBase):

    @property
    def agent_name(self) -> str:
        return "business_rules"

    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.business_rules")

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
            system_prompt = prompt_manager.get("business_rules")
        except FileNotFoundError:
            return self._execute_fallback(state, "Prompt introuvable")

        spec = state.parsed_spec
        user_prompt = self._build_user_prompt(spec)
        model = router.select(TaskType.BUSINESS_RULES)

        result = executor.execute(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            task_type=TaskType.BUSINESS_RULES,
        )

        if result.error:
            return self._execute_fallback(
                state, f"Erreur LLM : {result.error}", result.token_usage
            )

        try:
            data = extract_json(result.content)
            report = self._parse_report(data)
            self._logger.info(
                "BusinessRulesReport généré | règles=%d | implicites=%d | complete=%s",
                report.total_rules,
                len(report.implicit_rules),
                report.is_complete,
            )

            state_rules = [f"{r.code}: {r.rule}" for r in report.rules]
            return {
                "business_rules_report": report,
                "business_rules": state_rules,
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
        if spec.actors:
            lines.append(f"\nActeurs : {', '.join(spec.actors)}")

        items = format_spec_items(spec)

        # Grouper par catégorie pour l'affichage
        current_kind = None
        for kind, code, text in items:
            if kind != current_kind:
                if kind == "REQ":
                    lines.append("\nExigences :")
                elif kind == "RG":
                    lines.append("\nRègles métier déjà détectées :")
                elif kind == "EX":
                    lines.append("\nExceptions :")
                current_kind = kind
            lines.append(f"  - {code}: {text}")

        if spec.main_flow:
            lines.append("\nScénario principal :")
            for s in spec.main_flow:
                lines.append(f"  - {s}")
        if spec.alternative_flows:
            lines.append("\nScénarios alternatifs :")
            for alt in spec.alternative_flows:
                lines.append(f"  - {alt.title if hasattr(alt, 'title') else alt}")

        return "\n".join(lines)

    def _parse_report(self, data: dict) -> BusinessRulesReport:
        """Parse le JSON LLM en BusinessRulesReport."""
        rules = []
        for raw in data.get("rules", []):
            rules.append(
                BusinessRule(
                    code=raw.get("code", ""),
                    rule=raw.get("rule", ""),
                    priority=raw.get("priority", "medium"),
                    source=raw.get("source", ""),
                )
            )

        return BusinessRulesReport(
            is_complete=bool(data.get("is_complete", False)),
            total_rules=data.get("total_rules", len(rules)),
            rules=rules,
            implicit_rules=data.get("implicit_rules", []),
            recommendations=data.get("recommendations", []),
            summary=data.get("summary", ""),
        )

    def _execute_fallback(
        self,
        state: AgentState,
        reason: str,
        token_usage=None,
    ) -> dict:
        fallback = BusinessRulesReport(
            is_complete=False,
            total_rules=0,
            recommendations=["Analyse non réalisée : erreur lors de l'appel LLM"],
            summary=f"Rapport de secours. Raison : {reason}",
        )
        self._logger.warning("Fallback BusinessRulesReport | raison=%s", reason)
        result = {
            "business_rules_report": fallback,
            "errors": [f"{self.agent_name}: {reason}"],
        }
        if token_usage is not None:
            result["token_usage"] = token_usage
        return result
