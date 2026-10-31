"""
ReviewAgent — Review qualité des cas de tests.
================================================

Cet agent joue le rôle d'un QA Senior Reviewer.

Responsabilités :
    - Évaluer la qualité globale des cas de tests proposés
    - Identifier les cas acceptables
    - Identifier les cas rejetés avec raisons
    - Calculer un score qualité global
    - Produire un ReviewReport

Flux :
    ReviewAgent
        → PromptManager (prompts/v1/review.md)
        → AgentExecutor (via ModelRouter pour TaskType.REVIEW)
        → Parsing JSON → ReviewReport
"""

import logging

from src.agents.base import AgentBase
from src.models.node_types import TaskType
from src.agents.router import ModelRouter
from src.models.graph_models import AgentState
from src.models.node_types import AgentDependencies
from src.prompts.manager import PromptManager
from src.reports.review import ReviewReport, RejectedCase
from src.utils.json_parser import extract_json, JSONParseError


class ReviewAgent(AgentBase):
    """
    Agent de review qualité.

    Utilisation :
        agent = ReviewAgent(dependencies)
        result = agent.execute(state)
        # → {"review_report": ReviewReport(...)}
    """

    @property
    def agent_name(self) -> str:
        return "review"

    def __init__(self, dependencies: AgentDependencies | None = None) -> None:
        """Initialise le ReviewAgent avec ses dépendances."""
        super().__init__(dependencies)
        self._logger = logging.getLogger("agents.review")

    def execute(self, state: AgentState) -> dict:
        """
        Évalue la qualité des cas de tests et produit un ReviewReport.

        Args:
            state: État partagé du graphe contenant parsed_spec,
                   requirement_report, coverage_report et draft_test_cases.

        Returns:
            dict — Contient le ReviewReport généré.
        """
        # Récupérer les dépendances
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

        # Charger le prompt
        try:
            system_prompt = prompt_manager.get("review")
        except FileNotFoundError:
            return self._execute_fallback(
                state, "Prompt introuvable : prompts/v1/review.md"
            )

        # Construire le message utilisateur à partir de l'état
        user_prompt = self._build_user_prompt(state)

        # Résoudre le modèle via le routeur
        model = router.select(TaskType.REVIEW)

        # Appeler le LLM via AgentExecutor
        result = executor.execute(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            task_type=TaskType.REVIEW,
        )

        if result.error:
            return self._execute_fallback(
                state, f"Erreur LLM : {result.error}", result.token_usage
            )

        # Parser la réponse JSON
        try:
            report = self._parse_response(result.content)
            self._logger.info(
                "ReviewReport généré | "
                f"score={report.quality_score} | "
                f"validés={len(report.validated)} | "
                f"rejetés={len(report.rejected)}"
            )
            return {
                "review_report": report,
                "token_usage": result.token_usage,
            }

        except (JSONParseError, KeyError, TypeError, ValueError) as exc:
            return self._execute_fallback(
                state, f"Erreur de parsing JSON : {exc}", result.token_usage
            )

    def _build_user_prompt(self, state: AgentState) -> str:
        """Construit le prompt utilisateur à partir de l'état."""
        spec = state.parsed_spec
        lines = [
            f"# {spec.title}",
        ]
        if spec.summary:
            lines.append(f"\nRésumé : {spec.summary}")
        if spec.actors:
            lines.append(f"\nActeurs : {', '.join(spec.actors)}")
        if spec.requirements:
            lines.append("\nExigences :")
            for r in spec.requirements:
                lines.append(f"  - {r}")
        if spec.business_rules:
            lines.append("\nRègles métier :")
            for r in spec.business_rules:
                lines.append(f"  - {r}")
        if spec.main_flow:
            lines.append("\nScénario principal :")
            for s in spec.main_flow:
                lines.append(f"  - {s}")

        # Ajouter le RequirementReport s'il existe
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

        # Ajouter le CoverageReport s'il existe
        if state.coverage_report:
            cov = state.coverage_report
            lines.append("\nRapport de couverture :")
            lines.append(f"  - Score : {cov.score}")
            lines.append(f"  - Exigences couvertes : {len(cov.covered)}")
            lines.append(f"  - Exigences non couvertes : {len(cov.uncovered)}")
            if cov.missing_scenarios:
                lines.append("  - Scénarios manquants :")
                for s in cov.missing_scenarios:
                    lines.append(f"    - {s}")

        # Ajouter les cas de tests draft
        if state.draft_test_cases:
            lines.append(f"\nCas de tests proposés ({len(state.draft_test_cases)}) :")
            for tc in state.draft_test_cases:
                lines.append(f"  - {tc.title} ({tc.type.value})")
                if tc.steps:
                    for step in tc.steps:
                        lines.append(f"    - {step.action} → {step.expected}")
                if tc.expected_results:
                    lines.append(
                        f"    Résultats attendus : {', '.join(tc.expected_results)}"
                    )
        else:
            lines.append("\nAucun cas de test proposé.")

        return "\n".join(lines)

    def _parse_response(self, content: str) -> ReviewReport:
        """Parse la réponse JSON du LLM en ReviewReport.

        Utilise le parseur JSON partagé (src.utils.json_parser.extract_json)
        pour une extraction robuste : gère les blocs Markdown, le texte
        parasite avant/après le JSON, et les objets imbriqués.

        Args:
            content: Réponse JSON brute du LLM.

        Returns:
            ReviewReport — Rapport parsé.

        Raises:
            JSONParseError: Si aucun JSON valide ne peut être extrait.
            KeyError: Si des champs obligatoires sont manquants.
        """
        data = extract_json(content)

        # Parser les cas rejetés
        rejected = []
        for item in data.get("rejected", []):
            if isinstance(item, dict):
                rejected.append(
                    RejectedCase(
                        title=item.get("title", ""),
                        reason=item.get("reason", ""),
                    )
                )
            elif isinstance(item, str):
                rejected.append(RejectedCase(title=item, reason="Raison non spécifiée"))

        return ReviewReport(
            quality_score=float(data.get("quality_score", 0.0)),
            validated=data.get("validated", []),
            rejected=rejected,
            is_acceptable=bool(data.get("is_acceptable", False)),
        )

    def _execute_fallback(
        self,
        state: AgentState,
        reason: str,
        token_usage=None,
    ) -> dict:
        """Fallback : crée un rapport minimal basé sur les données disponibles.

        Utilisé en cas d'erreur LLM ou de dépendances manquantes.
        """
        fallback = ReviewReport(
            quality_score=0.0,
            validated=[],
            rejected=[
                RejectedCase(
                    title=f"Cas : {tc.title}",
                    reason="Analyse non réalisée : erreur lors de l'appel LLM",
                )
                for tc in (state.draft_test_cases or [])
            ],
            is_acceptable=False,
        )
        self._logger.warning("Fallback ReviewReport utilisé | raison=%s", reason)
        result = {
            "review_report": fallback,
            "errors": [f"{self.agent_name}: {reason}"],
        }
        if token_usage is not None:
            result["token_usage"] = token_usage
        return result
