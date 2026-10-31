"""
Modèles métier des agents.
==========================

Définit les objets qui circulent entre les agents du SMA :
    - TestCase, TestStep, TestSuite
    - TestType, TestStatus

Ces modèles sont indépendants de tout framework (LangGraph, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.reports.coverage import CoverageReport
    from src.reports.review import ReviewReport

# ── Énumérations ────────────────────────────────────────────────────


class TestType(Enum):
    """Type de cas de test."""

    NOMINAL = "nominal"
    ALTERNATIVE = "alternative"
    ERROR = "error"
    BOUNDARY = "boundary"
    BUSINESS_RULE = "business_rule"


class TestCaseStatus(Enum):
    """Statut d'un cas de test dans le workflow."""

    DRAFT = "draft"
    VALIDATED = "validated"
    REJECTED = "rejected"


# ── Modèles ─────────────────────────────────────────────────────────


@dataclass
class TestStepModel:
    """
    Une étape d'un cas de test.

    Attributes:
        action:   Action à effectuer (ex: "Saisir 'admin' dans le champ login").
        expected: Résultat attendu après cette action.
        data:     Données spécifiques à cette étape (optionnel).
    """

    action: str
    expected: str
    data: dict | None = None


@dataclass
class TestCaseModel:
    """
    Un cas de test individuel.

    Attributes:
        title:            Titre du cas de test.
        description:      Description courte.
        type:             Type de test (nominal, alternatif, erreur…).
        preconditions:    Liste des préconditions.
        steps:            Étapes détaillées (action + résultat attendu).
        expected_results: Résultats attendus globaux.
        test_data:        Données de test (dict libre).
        tags:             Tags (performance, sécurité…).
        source_section:   Section de la spécification d'origine.
        status:           Statut dans le workflow (DRAFT, VALIDATED, REJECTED).
        created_by_agent: Nom de l'agent qui a généré ce test.
        confidence:       Score de confiance de l'agent (0.0 à 1.0).
    requirement_ids:   IDs des exigences fonctionnelles couvertes (REQ-C{chunk}-{idx}).
        business_rule_ids: IDs des règles métier couvertes (RG-C{chunk}-{idx}).
        exception_ids:     IDs des exceptions couvertes (EX-C{chunk}-{idx}).
        reasoning:         Justification de la création du test.
    """

    title: str
    description: str
    type: TestType
    preconditions: list[str] = field(default_factory=list)
    steps: list[TestStepModel] = field(default_factory=list)
    expected_results: list[str] = field(default_factory=list)
    test_data: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    source_section: str | None = None
    status: TestCaseStatus = TestCaseStatus.DRAFT
    created_by_agent: str = ""
    confidence: float = 1.0
    requirement_ids: list[str] = field(default_factory=list)
    business_rule_ids: list[str] = field(default_factory=list)
    exception_ids: list[str] = field(default_factory=list)
    reasoning: str | None = None


@dataclass
class TestSuiteModel:
    """
    Ensemble complet de cas de tests pour une spécification.

    Attributes:
        specification_title: Titre de la spécification source.
        specification_id:    Identifiant de la ParsedSpecification.
        test_cases:          Tous les cas de tests (validés ou non).
        coverage_report:     Rapport de couverture (optionnel).
        review_report:       Rapport de review (optionnel).
        metrics:             Indicateurs (nb_tests, score qualité…).
        created_at:          Date de création.
        metadata:            Métadonnées libres.
    """

    specification_title: str
    specification_id: str
    test_cases: list[TestCaseModel] = field(default_factory=list)
    coverage_report: "CoverageReport | None" = None  # type: ignore[name-defined]
    review_report: "ReviewReport | None" = None  # type: ignore[name-defined]
    metrics: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
