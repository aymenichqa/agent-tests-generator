"""
Client LLM.
============

Point d'accès unique au LLM pour tout le projet.

Encapsule le SDK OpenAI et les spécificités d'infrastructure
(User-Agent Cloudflare, traduction des erreurs, etc.).

Aucun autre module ne doit importer openai directement.
"""

import logging
import time

from openai import OpenAI
from openai import (
    APIConnectionError as OpenAIAPIConnectionError,
    AuthenticationError as OpenAIAuthenticationError,
    RateLimitError as OpenAIRateLimitError,
    APITimeoutError as OpenAITimeoutError,
    APIStatusError as OpenAIAPIStatusError,
)

from src.llm.settings import Settings
from src.llm.exceptions import (
    LLMAuthenticationError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAPIError,
)


# Retry configuration for Cloudflare HTTP 524 (origin timeout).
# The server returns 524 when it cannot produce a first token within 120 s.
# We wait the same 120 s before retrying, up to 3 times, on top of the SDK retry.
_MAX_524_RETRIES = 3
_BACKOFF_524_SECONDS = 120


class LLMClient:
    """
    Client de communication avec un fournisseur de LLM.

    Utilisation :
        settings = Settings()
        client = LLMClient(settings)
        reponse = client.generate([
            {"role": "user", "content": "Bonjour"}
        ])
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialise le client LLM.

        Args:
            settings: Configuration injectée (URL, modèle, clé, User-Agent).
        """
        self._settings = settings

        # Création du client OpenAI avec User-Agent personnalisé
        # pour contourner le blocage Cloudflare de l'API Value IT.
        self._client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            default_headers={
                "User-Agent": settings.user_agent,
            },
            timeout=settings.timeout,
            max_retries=settings.max_retries,
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> str:
        """
        Envoie une conversation au LLM et retourne la réponse textuelle.

        Args:
            messages: Conversation au format standard des APIs de chat.
                      Chaque message est un dict avec deux clés :
                      - "role": "system" | "user" | "assistant"
                      - "content": str (le texte du message)

                      Exemple :
                      [
                          {"role": "system", "content": "Sois bref."},
                          {"role": "user", "content": "Dis OK"},
                      ]

            model:   Modèle à utiliser pour cet appel.
                     Si None, utilise le modèle par défaut des Settings.

        Returns:
            str — Le contenu textuel de la réponse du LLM.

        Raises:
            LLMAuthenticationError : Clé API invalide (401).
            LLMRateLimitError      : Trop de requêtes (429).
            LLMTimeoutError        : Timeout dépassé.
            LLMConnectionError     : Problème réseau (DNS, SSL, connexion).
            LLMAPIError            : Autre erreur API (4xx, 5xx, réponse
                                     inattendue).
        """
        # Déterminer le modèle à utiliser
        active_model = model if model is not None else self._settings.model

        # Validation minimale : messages ne doit pas etre vide
        if not messages:
            raise LLMAPIError("messages must not be empty")

        # Appel au LLM avec retry manuel sur 524 (serveur lent / Cloudflare).
        # Note : le SDK OpenAI possede son propre mecanisme de retry ; cette
        # boucle ne s'execute que si le SDK remonte l'erreur 524 a notre code.
        for _attempt in range(_MAX_524_RETRIES + 1):
            try:
                response = self._client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                )
                break

            # --- Traduction des erreurs OpenAI vers nos exceptions ---

            except OpenAIAuthenticationError as exc:
                raise LLMAuthenticationError(f"Authentication failed: {exc}") from exc

            except OpenAIRateLimitError as exc:
                raise LLMRateLimitError(f"Rate limit exceeded: {exc}") from exc

            except OpenAITimeoutError as exc:
                raise LLMTimeoutError(f"Request timed out: {exc}") from exc

            except OpenAIAPIConnectionError as exc:
                raise LLMConnectionError(f"Connection failed: {exc}") from exc

            except OpenAIAPIStatusError as exc:
                if (
                    getattr(exc, "status_code", None) == 524
                    and _attempt < _MAX_524_RETRIES
                ):
                    logging.getLogger("llm.client").warning(
                        "Erreur 524 (serveur lent) - nouvelle tentative dans "
                        "%ds (essai %d/%d)",
                        _BACKOFF_524_SECONDS,
                        _attempt + 1,
                        _MAX_524_RETRIES,
                    )
                    time.sleep(_BACKOFF_524_SECONDS)
                    continue
                raise LLMAPIError(f"API error {exc.status_code}: {exc}") from exc

        else:
            # Sortie de boucle sans break -> abandon apres plusieurs 524.
            raise LLMAPIError(
                "API error 524: le serveur n'a pas repondu dans les "
                f"{_MAX_524_RETRIES} tentatives (backoff 120s)."
            )

        # --- Extraction du texte de la reponse ---

        try:
            content = response.choices[0].message.content
        except (IndexError, AttributeError) as exc:
            raise LLMAPIError(f"Unexpected response format: {exc}") from exc

        # Si le contenu est None (reponse vide), retourner une chaine vide
        return content if content is not None else ""

    def generate_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> str:
        """
        Envoie une conversation au LLM en mode STREAMING (SSE) et retourne le
        texte complet une fois la generation terminee.

        Pourquoi :
            L'API via Cloudflare renvoie une erreur 524 quand le serveur ne
            produit pas une reponse complete dans ~120 s. En streaming, les
            tokens arrivent au fur et a mesure (SSE) : Cloudflare ne coupe pas
            tant que des donnees continuent d'arriver, ce qui contourne le 524
            pour les sorties longues (ex. plusieurs cas de test detailles).

        Args:
            messages: Conversation au format standard (role/content).
            model:    Modele a utiliser (None = defaut des Settings).

        Returns:
            str — Le contenu textuel complet de la reponse du LLM.

        Raises:
            Memes exceptions que `generate()` (LLMAPIError, 524 retries, etc.).
        """
        active_model = model if model is not None else self._settings.model

        if not messages:
            raise LLMAPIError("messages must not be empty")

        # Retry manuel sur 524 : en streaming, l'erreur survient avant le
        # premier token si le serveur met trop de temps a demarrer la reponse.
        for _attempt in range(_MAX_524_RETRIES + 1):
            try:
                stream = self._client.chat.completions.create(
                    model=active_model,
                    messages=messages,
                    stream=True,
                )
                break

            except OpenAIAuthenticationError as exc:
                raise LLMAuthenticationError(f"Authentication failed: {exc}") from exc
            except OpenAIRateLimitError as exc:
                raise LLMRateLimitError(f"Rate limit exceeded: {exc}") from exc
            except OpenAITimeoutError as exc:
                raise LLMTimeoutError(f"Request timed out: {exc}") from exc
            except OpenAIAPIConnectionError as exc:
                raise LLMConnectionError(f"Connection failed: {exc}") from exc
            except OpenAIAPIStatusError as exc:
                if (
                    getattr(exc, "status_code", None) == 524
                    and _attempt < _MAX_524_RETRIES
                ):
                    logging.getLogger("llm.client").warning(
                        "Streaming - Erreur 524 (serveur lent) - nouvelle "
                        "tentative dans %ds (essai %d/%d)",
                        _BACKOFF_524_SECONDS,
                        _attempt + 1,
                        _MAX_524_RETRIES,
                    )
                    time.sleep(_BACKOFF_524_SECONDS)
                    continue
                raise LLMAPIError(f"API error {exc.status_code}: {exc}") from exc

        else:
            # Sortie de boucle sans break -> abandon apres plusieurs 524.
            raise LLMAPIError(
                "API error 524: le serveur n'a pas repondu (streaming) dans les "
                f"{_MAX_524_RETRIES} tentatives (backoff 120s)."
            )

        # --- Collecte des morceaux (tokens) du flux SSE ---
        chunks: list[str] = []
        try:
            for chunk in stream:
                # Le premier chunk peut etre un role (delta vide) ou les choix.
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    chunks.append(content)
        except OpenAIAPIStatusError as exc:
            # 524 pendant le streaming (perte du flux) : on retente une fois si
            # on n'a encore rien recu, sinon on retourne ce qui a deja ete recu.
            if (
                getattr(exc, "status_code", None) == 524
                and not chunks
            ):
                raise LLMAPIError(
                    "API error 524: flux coupe avant le premier token (streaming)."
                ) from exc
            raise LLMAPIError(f"API error {exc.status_code}: {exc}") from exc
        except UnicodeDecodeError:
            raise LLMAPIError("Streaming: reponse illisible (decodage UTC-8).")

        return "".join(chunks)

    def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """
        Génère les embeddings vectoriels pour une liste de textes.

        Args:
            texts: Liste de chaînes à encoder.
            model: Modèle d'embedding à utiliser.
                   Si None, utilise l'embedding_model des Settings.

        Returns:
            list[list[float]] — Vecteurs d'embedding, dans le même ordre.

        Raises:
            LLMAuthenticationError : Clé API invalide (401).
            LLMRateLimitError      : Trop de requêtes (429).
            LLMTimeoutError        : Timeout dépassé.
            LLMConnectionError     : Problème réseau.
            LLMAPIError            : Autre erreur API.
        """
        active_model = model if model is not None else self._settings.embedding_model
        if not active_model:
            raise LLMAPIError("Aucun modèle d'embedding configuré")

        if not texts:
            return []

        try:
            response = self._client.embeddings.create(
                model=active_model,
                input=texts,
            )
        except OpenAIAuthenticationError as exc:
            raise LLMAuthenticationError(f"Authentication failed: {exc}") from exc
        except OpenAIRateLimitError as exc:
            raise LLMRateLimitError(f"Rate limit exceeded: {exc}") from exc
        except OpenAITimeoutError as exc:
            raise LLMTimeoutError(f"Request timed out: {exc}") from exc
        except OpenAIAPIConnectionError as exc:
            raise LLMConnectionError(f"Connection failed: {exc}") from exc
        except OpenAIAPIStatusError as exc:
            raise LLMAPIError(f"API error {exc.status_code}: {exc}") from exc

        try:
            return [item.embedding for item in response.data]
        except (AttributeError, IndexError) as exc:
            raise LLMAPIError(f"Unexpected embedding response format: {exc}") from exc

    @property
    def model(self) -> str:
        """Modèle de langage actif (lecture seule)."""
        return self._settings.model
