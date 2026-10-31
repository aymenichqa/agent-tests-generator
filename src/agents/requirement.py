"""
RequirementAgent — Analyse des exigences fonctionnelles.
"""

import logging

from src.agents.base import AgentBase
from src.models.node_types import TaskType
from src.agents.router import ModelRouter
from src.models.graph_models import AgentState
from src.models.node_types import AgentDependencies
from src.prompts.manager import PromptManager
from src.reports.requirement import RequirementReport
from src.utils.json_parser import extract_json, JSONParseError

logger = logging.getLogger("agents.requirement")


class RequirementAgent(AgentBase):
    @property
    def agent_name(self) -> str:
        return "requirement"

    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.requirement")

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
            system_prompt = prompt_manager.get("requirement")
        except FileNotFoundError:
            return self._execute_fallback(state, "Prompt introuvable")

        user_prompt = self._build_user_prompt(state)
        model = router.select(TaskType.REQUIREMENT)

        result = executor.execute(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            task_type=TaskType.REQUIREMENT,
        )

        if result.error:
            return self._execute_fallback(
                state, f"Erreur LLM : {result.error}", result.token_usage
            )

        try:
            data = extract_json(result.content)
            report = RequirementReport(
                is_complete=data.get("is_complete", False),
                total_requirements=data.get("total_requirements", 0),
                ambiguities=data.get("ambiguities", []),
                missing=data.get("missing", []),
                summary=data.get("summary", ""),
            )
            self._logger.info(
                "RequirementReport généré | exigences=%d | ambiguïtés=%d",
                report.total_requirements,
                len(report.ambiguities),
            )
            return {
                "requirement_report": report,
                "token_usage": result.token_usage,
            }

        except JSONParseError as exc:
            return self._execute_fallback(
                state, f"Erreur de parsing JSON : {exc}", result.token_usage
            )

    def _build_user_prompt(self, state: AgentState) -> str:
        spec = state.parsed_spec
        lines = [f"# {spec.title}"]
        if spec.summary:
            lines.append(f"\nResume : {spec.summary}")
        if spec.actors:
            lines.append(f"\nActeurs : {', '.join(spec.actors)}")
        if spec.business_rules:
            lines.append("\nRegles metier :")
            for r in spec.business_rules:
                lines.append(f"  - {r}")
        if spec.requirements:
            lines.append("\nExigences :")
            for r in spec.requirements:
                lines.append(f"  - {r}")
        if spec.main_flow:
            lines.append("\nScenario principal :")
            for s in spec.main_flow:
                lines.append(f"  - {s}")
        if spec.alternative_flows:
            lines.append("\nScenarios alternatifs :")
            for alt in spec.alternative_flows:
                lines.append(f"  - {alt.title if hasattr(alt, 'title') else alt}")
        if spec.exceptions:
            lines.append("\nExceptions :")
            for exc in spec.exceptions:
                lines.append(f"  - {exc.name if hasattr(exc, 'name') else exc}")

        # Injection du contexte RAG si disponible
        context = state.knowledge_context
        if context and (context.similar_specs or context.similar_test_suites):
            lines.append("\n\n## Contexte de specifications similaires")
            lines.append(context.summary)
            for rec in context.recommendations[:3]:
                if rec.strip():
                    lines.append(f"\n- {rec.strip()}")

        return "\n".join(lines)

    def _execute_fallback(
        self,
        state: AgentState,
        reason: str,
        token_usage=None,
    ) -> dict:
        spec = state.parsed_spec
        reqs = spec.requirements or []
        fallback = RequirementReport(
            is_complete=False,
            total_requirements=len(reqs),
            ambiguities=["Analyse non réalisée : erreur lors de l'appel LLM"],
            missing=["Analyse non réalisée"],
            summary=f"Rapport de secours. Raison : {reason}",
        )
        self._logger.warning("Fallback RequirementReport | raison=%s", reason)
        result = {
            "requirement_report": fallback,
            "errors": [f"{self.agent_name}: {reason}"],
        }
        if token_usage is not None:
            result["token_usage"] = token_usage
        return result
