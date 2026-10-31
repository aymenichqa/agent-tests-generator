"""
Configuration de la couche LLM.
================================

Centralise la lecture et la validation des variables d'environnement
nécessaires au fonctionnement de la couche LLM.

Aucun autre module du projet ne doit lire le .env directement.
Tout passe par Settings.
"""

import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from src.llm.exceptions import LLMConfigurationError

# Domaines autorisés pour l'API LLM.
#
# Contrainte projet : les spécifications fonctionnelles Value IT sont
# confidentielles. Elles ne doivent JAMAIS être envoyées à un fournisseur
# LLM externe (OpenAI, Anthropic, etc.), volontairement ou par erreur de
# configuration du .env. Cette liste blanche est le seul mécanisme
# automatique qui empêche ça : si LLM_BASE_URL ne pointe pas vers un
# domaine autorisé, Settings refuse de démarrer.
_ALLOWED_LLM_DOMAINS: frozenset[str] = frozenset({"ia.sofiasolutions.io"})


class Settings:
    """
    Configuration de la couche LLM.

    Lit et valide les variables d'environnement au moment de la
    construction. Lève immédiatement LLMConfigurationError si une
    variable critique est absente ou invalide.

    Attributs exposés (lecture seule après construction) :
        base_url         : str   — URL de base de l'API LLM
        api_key          : str   — Clé d'authentification
        model            : str   — Modèle par défaut
        embedding_model  : str   — Modèle d'embedding (optionnel)
        user_agent       : str   — User-Agent pour les requêtes HTTP
    """

    def __init__(self) -> None:
        # Charger le fichier .env (ne fait rien s'il est déjà chargé)
        load_dotenv()

        # Lecture des variables
        base_url = os.getenv("LLM_BASE_URL")
        model = os.getenv("LLM_MODEL")
        api_key = os.getenv("LLM_API_KEY", "not-needed")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        timeout_str = os.getenv("LLM_TIMEOUT", "60")
        max_retries_str = os.getenv("LLM_MAX_RETRIES", "1")

        # Validation : base_url est obligatoire
        if not base_url or not base_url.strip():
            raise LLMConfigurationError(
                "LLM_BASE_URL must be set in .env (ex: https://ia.sofiasolutions.io/v1)"
            )

        # Validation : base_url doit pointer vers un domaine autorisé.
        #
        # Les spécifications fonctionnelles traitées par ce projet sont
        # confidentielles (données Value IT). Cette vérification empêche
        # tout envoi accidentel vers un fournisseur LLM externe, même si
        # le .env a été mal configuré (clé OpenAI collée par erreur, test
        # local avec un autre provider, etc.).
        hostname = urlparse(base_url).hostname
        if hostname not in _ALLOWED_LLM_DOMAINS:
            raise LLMConfigurationError(
                f"LLM_BASE_URL host '{hostname}' is not in the allowed domains "
                f"{sorted(_ALLOWED_LLM_DOMAINS)}. Les specifications Value IT sont "
                "confidentielles : seule l'API interne autorisee peut etre utilisee."
            )

        # Validation : model est obligatoire
        if not model or not model.strip():
            raise LLMConfigurationError(
                "LLM_MODEL must be set in .env (ex: qwen/qwen3.6-35b-a3b)"
            )

        # Validation : timeout doit être un entier positif
        try:
            timeout_value = int(timeout_str)
        except ValueError:
            raise LLMConfigurationError(
                f"LLM_TIMEOUT must be an integer, got '{timeout_str}'"
            )
        if timeout_value <= 0:
            raise LLMConfigurationError(
                f"LLM_TIMEOUT must be positive, got {timeout_value}"
            )

        # Validation : max_retries doit être un entier positif ou nul
        try:
            max_retries_value = int(max_retries_str)
        except ValueError:
            raise LLMConfigurationError(
                f"LLM_MAX_RETRIES must be an integer, got '{max_retries_str}'"
            )
        if max_retries_value < 0:
            raise LLMConfigurationError(
                f"LLM_MAX_RETRIES must be non-negative, got {max_retries_value}"
            )

        # Stockage des valeurs
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._embedding_model = embedding_model if embedding_model else None
        self._user_agent = "agent-tests-generator/0.1.0"
        self._timeout = timeout_value
        self._max_retries = max_retries_value

    # ── Propriétés publiques (lecture seule) ──

    @property
    def base_url(self) -> str:
        """URL de base de l'API LLM (sans slash final)."""
        return self._base_url

    @property
    def api_key(self) -> str:
        """Clé d'authentification pour l'API LLM."""
        return self._api_key

    @property
    def model(self) -> str:
        """Identifiant du modèle de langage par défaut."""
        return self._model

    @property
    def embedding_model(self) -> str | None:
        """
        Identifiant du modèle d'embedding (optionnel).
        Retourne None si non configuré.
        """
        return self._embedding_model

    @property
    def timeout(self) -> int:
        """
        Timeout en secondes pour les requêtes LLM.
        Configure la durée maximale d'attente d'une réponse.
        """
        return self._timeout

    @property
    def max_retries(self) -> int:
        """
        Nombre maximum de retries automatiques du SDK OpenAI.
        Par défaut 1 pour éviter les attentes silencieuses pendant le debug.
        """
        return self._max_retries

    @property
    def user_agent(self) -> str:
        """
        User-Agent envoyé dans les requêtes HTTP.
        Permet de contourner le blocage Cloudflare de l'API Value IT
        (le User-Agent par défaut du SDK OpenAI est bloqué).
        """
        return self._user_agent

    # ── Flags Phase B (chat LLM planner) ──
    # Les deux flags restent à False par défaut. L'activation pour la
    # démo/soutenance sera une décision séparée, prise consciemment.

    @property
    def llm_chat_planner_enabled(self) -> bool:
        """
        Active le planner LLM (intention → routage retrieval).
        False par défaut : le chat reste 100% déterministe.
        """
        return os.getenv("LLM_CHAT_PLANNER_ENABLED", "0").lower() in ("1", "true", "yes", "on")

    @property
    def llm_chat_synthesis_enabled(self) -> bool:
        """
        Active la synthèse LLM (réponse finale générée).
        False par défaut : utilise _build_local_reply (déterministe).
        Peut être False même si le planner est True (tester le routage seul).
        """
        return os.getenv("LLM_CHAT_SYNTHESIS_ENABLED", "0").lower() in ("1", "true", "yes", "on")

    def __repr__(self) -> str:
        """Représentation lisible (masque la clé API)."""
        key_masked = self._api_key[:4] + "****" if len(self._api_key) > 4 else "****"
        return (
            f"Settings(base_url='{self._base_url}', "
            f"model='{self._model}', "
            f"api_key='{key_masked}', "
            f"embedding_model={self._embedding_model})"
        )
