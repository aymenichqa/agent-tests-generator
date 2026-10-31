"""
Conditions de routage du graphe LangGraph.
===========================================

Fonctions utilisées par les arêtes conditionnelles du StateGraph
pour décider du prochain nœud à exécuter.
"""

from src.models.graph_models import AgentState
from src.models.node_types import NodeType


def get_next_node(state: AgentState) -> str:
    """
    Détermine le prochain nœud à exécuter en fonction de la décision
    du Supervisor stockée dans le state.

    Args:
        state: État partagé du graphe.

    Returns:
        str — Identifiant du prochain nœud (ex: "requirement", "review", "__end__").
    """
    decision = getattr(state, "supervisor_decision", None)
    if decision is None:
        return NodeType.SUPERVISOR.value

    next_node = decision.next_node

    return next_node.value


def has_next_step(state: AgentState) -> str:
    """
    Vérifie s'il reste des étapes après le nœud courant.

    Args:
        state: État partagé du graphe.

    Returns:
        str — "continue" ou "__end__".
    """
    decision = getattr(state, "supervisor_decision", None)
    if decision is None:
        return "__end__"
    return "continue"
