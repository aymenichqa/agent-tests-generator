"""
Workflow LangGraph.
===================

Definit le StateGraph du systeme multi-agents.

Le graphe orchestre l'execution des agents via le Supervisor
et le NodeExecutor.
"""

from langgraph.graph import StateGraph, END

from src.models.graph_models import AgentState
from src.models.node_types import NodeType
from src.agents.registry import AgentRegistry
from src.agents.node_executor import NodeExecutor
from src.graph.conditions import get_next_node


def create_workflow(registry: AgentRegistry, executor: NodeExecutor) -> StateGraph:
    """Cree et configure le StateGraph du systeme multi-agents."""
    builder = StateGraph(AgentState)

    def _make_node(node_type: NodeType):
        """Cree une fonction de noeud qui utilise le NodeExecutor."""

        def node_fn(state: AgentState) -> dict:
            if not isinstance(state, dict):
                state = vars(state)
            if isinstance(state, dict):
                from src.models.graph_models import AgentState
                from src.analysis import ParsedSpecification

                state = dict(state)
                parsed = state.get("parsed_spec")
                if isinstance(parsed, dict):
                    state["parsed_spec"] = ParsedSpecification(**parsed)

                state = AgentState(**state)
            return executor.execute(node_type, state)

        node_fn.__name__ = node_type.value
        return node_fn

    # Ajouter tous les noeuds du workflow
    builder.add_node(NodeType.SUPERVISOR.value, _make_node(NodeType.SUPERVISOR))

    for node_type in [
        NodeType.KNOWLEDGE,
        NodeType.REQUIREMENT,
        NodeType.TEST_DESIGN,
        NodeType.EDGE_CASES,
        NodeType.COVERAGE,
        NodeType.REVIEW,
        NodeType.STORE_MEMORY,
    ]:
        builder.add_node(node_type.value, _make_node(node_type))

    # Point d'entree
    builder.set_entry_point(NodeType.SUPERVISOR.value)

    # Aretes conditionnelles
    builder.add_conditional_edges(
        NodeType.SUPERVISOR.value,
        get_next_node,
    )

    for node_type in [
        NodeType.KNOWLEDGE,
        NodeType.REQUIREMENT,
        NodeType.TEST_DESIGN,
        NodeType.EDGE_CASES,
        NodeType.COVERAGE,
        NodeType.REVIEW,
    ]:
        # Chaque noeud retourne vers le Supervisor pour la decision suivante
        builder.add_edge(node_type.value, NodeType.SUPERVISOR.value)

    # Le noeud STORE_MEMORY termine le workflow
    builder.add_edge(NodeType.STORE_MEMORY.value, END)

    return builder.compile()

