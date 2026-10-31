"""
Routeur de modèles.
===================

Associe chaque type de tâche (TaskType) au modèle LLM le plus approprié.
Les agents ne connaissent jamais les noms des modèles.
"""

from src.models.node_types import TaskType

# ── Table de routage ────────────────────────────────────────────────

_ROUTING: dict[TaskType, str] = {
    TaskType.SUPERVISOR: "qwen/qwen3.6-35b-a3b",
    TaskType.REQUIREMENT: "qwen/qwen3.6-35b-a3b",
    TaskType.ANALYSIS: "qwen/qwen3.6-35b-a3b",
    TaskType.BUSINESS_RULES: "qwen/qwen3.6-35b-a3b",
    TaskType.EDGE_CASES: "qwen/qwen3.6-35b-a3b",
    TaskType.TEST_DESIGN: "qwen/qwen3.6-35b-a3b",
    TaskType.COVERAGE: "qwen/qwen3.6-35b-a3b",
    TaskType.REVIEW: "google/gemma-4-26b-a4b",
    TaskType.KNOWLEDGE: "qwen/qwen3.6-35b-a3b",
    TaskType.EMBEDDING: "text-embedding-nomic-embed-text-v1.5",
}


class ModelRouter:
    """
    Routeur de modèles LLM.

    À partir d'un TaskType, retourne l'identifiant du modèle
    le plus adapté pour cette tâche.

    Utilisation :
        router = ModelRouter()
        model = router.select(TaskType.REVIEW)
        # → "google/gemma-4-26b-a4b"
    """

    def select(self, task_type: TaskType) -> str:
        """
        Retourne le modèle approprié pour un type de tâche.

        Args:
            task_type: Type de tâche à router.

        Returns:
            str — Identifiant du modèle LLM.

        Raises:
            KeyError: Si le type de tâche n'est pas référencé.
        """
        if task_type not in _ROUTING:
            raise KeyError(
                f"Aucun modèle configuré pour TaskType '{task_type.value}'. "
                f"Types disponibles : {[t.value for t in _ROUTING]}"
            )
        return _ROUTING[task_type]

    @property
    def available_routes(self) -> dict[str, str]:
        """Retourne la table de routage complète (pour debug)."""
        return {t.value: m for t, m in _ROUTING.items()}
