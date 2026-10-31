"""
Types de noeuds et decisions du Supervisor.
===========================================

Definit :
    - NodeType : types de noeuds du graphe LangGraph
    - SupervisorDecision : decision de routage du Supervisor
    - ExecutionContext : contexte d'execution (separe de AgentState)
    - AgentDependencies : dependances injectees dans chaque agent
    - TaskType : types de taches pour le routage de modeles LLM
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NodeType(Enum):
    """Types de noeuds du graphe LangGraph."""

    SUPERVISOR = "supervisor"
    KNOWLEDGE = "knowledge"
    REQUIREMENT = "requirement"
    ANALYSIS = "analysis"
    BUSINESS_RULES = "business_rules"
    EDGE_CASES = "edge_cases"
    TEST_DESIGN = "test_design"
    COVERAGE = "coverage"
    REVIEW = "review"
    STORE_MEMORY = "store_memory"


class TaskType(Enum):
    """Type de tache pour le routage vers le modele LLM approprie."""

    SUPERVISOR = "supervisor"
    REQUIREMENT = "requirement"
    ANALYSIS = "analysis"
    BUSINESS_RULES = "business_rules"
    EDGE_CASES = "edge_cases"
    TEST_DESIGN = "test_design"
    COVERAGE = "coverage"
    REVIEW = "review"
    KNOWLEDGE = "knowledge"
    EMBEDDING = "embedding"


@dataclass
class SupervisorDecision:
    """Decision de routage prise par le Supervisor."""

    next_node: NodeType
    reason: str = ""
    requires_iteration: bool = False


@dataclass
class ExecutionContext:
    """Contexte d'execution du workflow (separe de AgentState)."""

    session_id: str = ""
    workflow_id: str = ""
    spec_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_model: str = ""
    debug: bool = False
    trace: list[str] = field(default_factory=list)


@dataclass
class AgentDependencies:
    """Dependances injectees dans chaque agent."""

    llm_client: Any = None
    prompt_manager: Any = None
    router: Any = None
    executor: Any = None
    rag_index: Any = None
    db_session: Any = None
    logger: Any = None
