"""
Classe de base pour tous les agents.
=====================================

AgentBase est une classe abstraite pure qui définit le contrat
que tous les agents du SMA doivent respecter.

Elle ne contient :
    - AUCUNE logique métier (c'est dans les agents concrets)
    - AUCUNE logique d'appel LLM (c'est dans AgentExecutor)
    - AUCUNE logique de retry/timeout (c'est dans AgentExecutor)

Elle définit uniquement :
    - L'interface commune (execute, agent_name)
    - Le typage partagé
"""

from abc import ABC, abstractmethod

from src.models.graph_models import AgentState


class AgentBase(ABC):
    """
    Interface commune pour tous les agents du SMA.

    Chaque agent concret doit :
        - Définir `agent_name` (propriété)
        - Implémenter `execute(state)` (méthode principale)

    Utilisation :
        class RequirementAgent(AgentBase):
            @property
            def agent_name(self) -> str:
                return "requirement"

            def execute(self, state: AgentState) -> dict:
                # Logique métier ici
                return {"requirement_report": report}
    """

    def __init__(self, dependencies: any = None) -> None:  # type: ignore[no-untyped-def]
        """
        Initialise l'agent avec ses dépendances.

        Args:
            dependencies: Dépendances partagées (AgentDependencies).
        """
        self._dependencies = dependencies

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """
        Nom unique de l'agent.

        Ce nom est utilisé pour :
            - Identifier l'agent dans les logs
            - Remplir le champ `created_by_agent` des TestCase
            - Router les appels via le futur ModelRouter
            - Tracer l'exécution dans `execution_trace`

        Returns:
            str — Nom de l'agent (ex: "requirement", "test_design").
        """

    @abstractmethod
    def execute(self, state: AgentState) -> dict:
        """
        Point d'entrée unique de l'agent.

        Chaque agent reçoit l'état partagé du graphe et retourne
        uniquement les champs qu'il modifie.

        Args:
            state: État partagé du graphe LangGraph.

        Returns:
            dict — Dictionnaire des champs à mettre à jour dans le state.
                   Exemple : {"requirement_report": RequirementReport(...)}

        Raises:
            Exception: Toute erreur métier est catchée par le nœud LangGraph.
        """
