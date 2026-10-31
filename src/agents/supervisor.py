"""
Supervisor Agent — Orchestrateur du workflow.
==============================================

Le Supervisor est le cerveau du systeme multi-agents.

Il recoit l'AgentState, analyse la progression, et decide
du prochain noeud a executer via une SupervisorDecision.

Pour le MVP, le Supervisor est deterministe (pas d'appel LLM).
Il suit un ordre de workflow pre-defini.
"""

from src.agents.base import AgentBase
from src.models.graph_models import AgentState
from src.models.node_types import NodeType, SupervisorDecision

# Sequence d'une passe de conception (rejouee a chaque iteration de correction)
_PASS_ORDER: list[NodeType] = [
    NodeType.TEST_DESIGN,
    NodeType.EDGE_CASES,
    NodeType.COVERAGE,
    NodeType.REVIEW,
]


class SupervisorAgent(AgentBase):
    """Agent superviseur qui orchestre le workflow."""

    @property
    def agent_name(self) -> str:
        return "supervisor"

    def execute(self, state: AgentState) -> dict:
        """Point d'entree du Supervisor dans le graphe."""
        decision, new_iteration = self._decide_next(state)
        out: dict = {"supervisor_decision": decision}
        if new_iteration is not None:
            out["iteration"] = new_iteration
        return out

    def _get_registered_nodes(self) -> set[str]:
        """Retourne les noeuds disponibles dans le registre (import differe)."""
        from src.agents.registry import AGENT_REGISTRY

        return {n.value for n in AGENT_REGISTRY}

    def _should_iterate(self, state: AgentState) -> bool:
        """Vrai si les scores couverture/review sont sous le seuil de qualite."""
        cov = (
            getattr(state.coverage_report, "score", 0.0)
            if state.coverage_report
            else 0.0
        )
        rev = (
            getattr(state.review_report, "quality_score", 0.0)
            if state.review_report
            else 0.0
        )
        return cov < 0.85 or rev < 0.75

    def _count_attempts(self, state: AgentState, node: str) -> int:
        """Compte les tentatives d'execution d'un noeud (succes ET echecs)."""
        return sum(
            1
            for step in (state.execution_trace or [])
            if getattr(step, "node", "") == node
        )

    def _decide_next(self, state: AgentState) -> tuple[SupervisorDecision, int | None]:
        """Decide du prochain noeud ; renvoie aussi une nouvelle iteration si besoin."""
        max_iter = state.max_iterations or 1
        passes_allowed = 1 + max_iter
        budget = passes_allowed * (len(_PASS_ORDER) + 4) + 6
        if len(state.execution_trace or []) > budget:
            return (
                SupervisorDecision(
                    next_node=NodeType.STORE_MEMORY,
                    reason="Garde terminaison : budget d'iterations depasse",
                    requires_iteration=False,
                ),
                None,
            )

        def _count(node: NodeType) -> int:
            return self._count_attempts(state, node.value)

        # KNOWLEDGE et REQUIREMENT ne s'executent qu'une seule fois
        for node in [NodeType.KNOWLEDGE, NodeType.REQUIREMENT]:
            if _count(node) == 0:
                return (
                    SupervisorDecision(
                        next_node=node,
                        reason=f"{node.value} initial de la specification",
                        requires_iteration=False,
                    ),
                    None,
                )

        if _count(NodeType.TEST_DESIGN) == 0:
            return (
                SupervisorDecision(
                    next_node=NodeType.TEST_DESIGN,
                    reason="Demarrage de la conception des cas de tests",
                    requires_iteration=False,
                ),
                None,
            )

        # Passe courante
        pass_index = _count(NodeType.TEST_DESIGN) - 1
        for node in _PASS_ORDER:
            if _count(node) == pass_index:
                return (
                    SupervisorDecision(
                        next_node=node,
                        reason=f"{node.value} de la passe {pass_index}",
                        requires_iteration=False,
                    ),
                    None,
                )

        # Passe complete terminee : iteration de correction si scores bas
        if state.iteration < max_iter and self._should_iterate(state):
            new_iter = state.iteration + 1
            return (
                SupervisorDecision(
                    next_node=NodeType.TEST_DESIGN,
                    reason=(
                        f"Correction qualite : cov="
                        f"{getattr(state.coverage_report, 'score', 0.0):.2f}, "
                        f"rev={getattr(state.review_report, 'quality_score', 0.0):.2f}, "
                        f"iteration={new_iter}"
                    ),
                    requires_iteration=True,
                ),
                new_iter,
            )

        return (
            SupervisorDecision(
                next_node=NodeType.STORE_MEMORY,
                reason="Workflow termine",
                requires_iteration=False,
            ),
            None,
        )
