"""
Modèles du graphe LangGraph.
=============================

Définit l'état partagé du graphe (AgentState) et les objets de suivi
d'exécution (ExecutionStep).

AgentState est le cœur du workflow LangGraph. Chaque nœud (agent) lit
et écrit dans le state. Seuls les champs modifiés sont retournés par
chaque nœud.
"""

from dataclasses import dataclass, field

from src.analysis import ParsedSpecification
from src.models.agent_models import TestCaseModel, TestSuiteModel
from src.memory.models import KnowledgeContext
from src.models.node_types import SupervisorDecision
from src.reports.requirement import RequirementReport
from src.reports.analysis import AnalysisReport
from src.reports.coverage import CoverageReport
from src.reports.review import ReviewReport


@dataclass
class ExecutionStep:
    """
    Trace d'une étape d'exécution dans le workflow.

    Attributes:
        node:              Nom du nœud exécuté (ex: "requirement", "review").
        model:             Modèle LLM utilisé (None si pas d'appel LLM).
        prompt_tokens:     Tokens de prompt consommés.
        completion_tokens: Tokens de complétion consommés.
        estimated_cost:    Coût estimé de l'appel.
        duration_ms:       Durée d'exécution en millisecondes.
        success:           Vrai si l'exécution s'est déroulée sans erreur.
    """

    node: str
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    duration_ms: int = 0
    success: bool = True


@dataclass
class AgentState:
    """
    État partagé du graphe LangGraph.

    Chaque nœud lit les champs dont il a besoin et retourne uniquement
    les champs qu'il modifie. LangGraph fusionne automatiquement les
    mises à jour.

    Attributes:
        parsed_spec:         Spécification analysée (entrée unique du SMA).
        knowledge_context:   Contexte RAG (rempli par KnowledgeAgent).
        requirement_report:  Rapport d'analyse des exigences.
        analysis_report:     Rapport d'analyse fonctionnelle.
        business_rules:      Règles métier extraites (liste textuelle).
        edge_cases:          Cas limites générés par EdgeCasesAgent.
        draft_test_cases:    Cas de tests en cours de génération.
        coverage_report:     Rapport de couverture fonctionnelle.
        review_report:       Rapport de review qualité.
        test_suite:          Suite de tests finale (après validation).
        iteration:           Numéro d'itération courante.
        max_iterations:      Nombre maximum d'itérations autorisées.
        errors:              Erreurs rencontrées pendant l'exécution.
        current_node:        Nom du nœud en cours d'exécution.
        supervisor_decision: Dernière décision du Supervisor.
        execution_trace:     Historique des étapes d'exécution.
    """

    parsed_spec: ParsedSpecification
    knowledge_context: KnowledgeContext | None = None
    requirement_report: RequirementReport | None = None
    analysis_report: AnalysisReport | None = None
    business_rules: list[str] = field(default_factory=list)
    edge_cases: list[TestCaseModel] = field(default_factory=list)
    draft_test_cases: list[TestCaseModel] = field(default_factory=list)
    coverage_report: CoverageReport | None = None
    review_report: ReviewReport | None = None
    test_suite: TestSuiteModel | None = None
    iteration: int = 0
    max_iterations: int = 3
    errors: list[str] = field(default_factory=list)
    current_node: str | None = None
    supervisor_decision: SupervisorDecision | None = None
    execution_trace: list[ExecutionStep] = field(default_factory=list)
