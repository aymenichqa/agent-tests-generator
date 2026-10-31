"""
Gestionnaire de prompts.
========================

Charge les prompts depuis des fichiers Markdown versionnés
(dossier prompts/v1/, prompts/v2/, etc.).

Les agents ne construisent pas leurs prompts dans le code.
Ils utilisent PromptManager pour charger le prompt approprié.
"""

from pathlib import Path


class PromptManager:
    """
    Charge et fournit les prompts des agents.

    Les prompts sont stockés dans des fichiers .md organisés par version :
        prompts/v1/supervisor.md
        prompts/v1/requirement.md
        prompts/v1/review.md
        ...

    Utilisation :
        pm = PromptManager(version="v1")
        prompt = pm.get("supervisor")
    """

    def __init__(
        self, prompts_dir: Path | str | None = None, version: str = "v1"
    ) -> None:
        """
        Args:
            prompts_dir: Dossier racine des prompts (défaut: prompts/ à côté de src/).
            version:     Version des prompts à utiliser (défaut: "v1").
        """
        if prompts_dir is None:
            # Chemin par défaut : prompts/ à la racine du projet
            prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
        self._base = Path(prompts_dir) / version
        self._version = version
        self._cache: dict[str, str] = {}

    @property
    def version(self) -> str:
        """Version actuelle des prompts."""
        return self._version

    def get(self, agent_name: str) -> str:
        """
        Charge le prompt d'un agent.

        Args:
            agent_name: Nom de l'agent (ex: "supervisor", "requirement").

        Returns:
            str — Contenu du prompt.

        Raises:
            FileNotFoundError: Si le fichier prompt n'existe pas.
        """
        # Vérifier le cache
        if agent_name in self._cache:
            return self._cache[agent_name]

        path = self._base / f"{agent_name}.md"

        if not path.exists():
            raise FileNotFoundError(
                f"Prompt introuvable : {path}. "
                f"Vérifie que le fichier prompts/{self._version}/{agent_name}.md existe."
            )

        content = path.read_text(encoding="utf-8")
        self._cache[agent_name] = content
        return content

    def list_available(self) -> list[str]:
        """
        Liste les prompts disponibles dans la version courante.

        Returns:
            list[str] — Noms des agents disponibles.
        """
        if not self._base.exists():
            return []
        return sorted(f.stem for f in self._base.iterdir() if f.suffix == ".md")
