"""
Exécuteur de nœuds.
===================

Le NodeExecutor est responsable d'exécuter un nœud du graphe LangGraph.
Il utilise l'AgentRegistry pour trouver l'agent approprié, exécute l'agent,
et trace automatiquement l'exécution (durée, tokens, modèle, succès/échec).

Les agents n'ont PAS à gérer le tracing. C'est le NodeExecutor qui le fait.
"""

import logging
import time

from src.models.graph_models import AgentState, ExecutionStep
from src.models.node_types import NodeType, ExecutionContext
from src.agents.registry import AgentRegistry


class NodeExecutor:
    """
    Exécute un nœud du graphe avec traçage automatique.

    Utilisation :
        executor = NodeExecutor(registry)
        state, decision = executor.execute(NodeType.REQUIREMENT, state)
    """

    def __init__(
        self,
        registry: AgentRegistry,
        execution_context: ExecutionContext | None = None,
    ) -> None:
        """
        Args:
            registry:          Registre des agents.
            execution_context: Contexte d'exécution (optionnel).
        """
        self._registry = registry
        self._ctx = execution_context or ExecutionContext()
        self._logger = logging.getLogger("agents.node_executor")

    def execute(
        self,
        node_type: NodeType,
        state: AgentState,
    ) -> dict:
        """
        Exécute le nœud demandé et retourne les champs modifiés.

        Args:
            node_type: Type de nœud à exécuter.
            state:     État partagé du graphe (lecture).

        Returns:
            dict — Champs modifiés à appliquer au state.
        """
        agent = self._registry.get(node_type)
        step = ExecutionStep(node=node_type.value)
        updates: dict = {}

        start = time.monotonic()
        try:
            result = agent.execute(state)

            step.success = True
            step.duration_ms = int((time.monotonic() - start) * 1000)
            step.model = getattr(self._ctx, "active_model", "")

            # Récupérer la consommation de tokens si l'agent l'a fournie
            token_usage = result.pop("token_usage", None)
            if token_usage is not None:
                step.prompt_tokens = getattr(token_usage, "prompt_tokens", 0)
                step.completion_tokens = getattr(token_usage, "completion_tokens", 0)
                step.estimated_cost = getattr(token_usage, "estimated_cost", 0.0)

            # Merger les erreurs retournées par l'agent avec les erreurs existantes
            if "errors" in result:
                existing = getattr(state, "errors", [])
                updates["errors"] = existing + result.pop("errors")

            # Ajouter les résultats de l'agent aux mises à jour
            updates.update(result)

            self._logger.info(
                "Nœud %s exécuté avec succès | durée=%dms",
                node_type.value,
                step.duration_ms,
            )

        except Exception as exc:
            step.success = False
            step.duration_ms = int((time.monotonic() - start) * 1000)
            existing = getattr(state, "errors", [])
            updates["errors"] = existing + [f"{node_type.value}: {exc}"]

            self._logger.error(
                "Échec du nœud %s | durée=%dms | erreur=%s",
                node_type.value,
                step.duration_ms,
                exc,
            )

        # Ajouter la trace d'exécution
        updates["execution_trace"] = getattr(state, "execution_trace", []) + [step]
        updates["current_node"] = node_type.value

        return updates
