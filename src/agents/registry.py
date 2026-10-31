"""
Registre des agents.
====================

Associe chaque NodeType a la classe d'agent correspondante.
Le NodeExecutor utilise ce registre pour instancier l'agent approprie.

Ajouter un nouvel agent = ajouter une entree dans le dictionnaire.
"""

from src.agents.base import AgentBase
from src.models.node_types import NodeType
from src.agents.supervisor import SupervisorAgent
from src.agents.store_memory import StoreMemoryAgent
from src.agents.knowledge import KnowledgeAgent
from src.agents.requirement import RequirementAgent
from src.agents.business_rules import BusinessRulesAgent
from src.agents.test_design import TestDesignAgent
from src.agents.edge_cases import EdgeCasesAgent
from src.agents.coverage import CoverageAgent
from src.agents.review import ReviewAgent

AGENT_REGISTRY: dict[NodeType, type[AgentBase]] = {
    NodeType.SUPERVISOR: SupervisorAgent,
    NodeType.STORE_MEMORY: StoreMemoryAgent,
    NodeType.KNOWLEDGE: KnowledgeAgent,
    NodeType.REQUIREMENT: RequirementAgent,
    NodeType.BUSINESS_RULES: BusinessRulesAgent,
    NodeType.TEST_DESIGN: TestDesignAgent,
    NodeType.EDGE_CASES: EdgeCasesAgent,
    NodeType.COVERAGE: CoverageAgent,
    NodeType.REVIEW: ReviewAgent,
}


class AgentRegistry:
    """
    Registre central des agents.

    Permet d'obtenir une instance d'agent a partir de son NodeType.
    """

    def __init__(self, dependencies: any = None) -> None:  # type: ignore
        self._dependencies = dependencies

    def register(self, node_type: NodeType, agent_class: type[AgentBase]) -> None:
        """Enregistre un agent pour un type de noeud."""
        AGENT_REGISTRY[node_type] = agent_class

    def get(self, node_type: NodeType) -> AgentBase:
        """Retourne une instance de l'agent pour le type de noeud demande."""
        if node_type not in AGENT_REGISTRY:
            raise KeyError(
                f"Aucun agent enregistre pour NodeType '{node_type.value}'. "
                f"Noeuds disponibles : {[n.value for n in AGENT_REGISTRY]}"
            )

        agent_class = AGENT_REGISTRY[node_type]
        return agent_class(dependencies=self._dependencies)

    @property
    def available_agents(self) -> list[str]:
        """Liste les agents disponibles."""
        return [n.value for n in AGENT_REGISTRY]
