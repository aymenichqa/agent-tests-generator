"""
Exceptions de la couche LLM.
=============================

Hiérarchie complète des erreurs pouvant survenir lors de la
communication avec un fournisseur de modèles de langage.

Toute erreur de la couche LLM hérite de LLMError.
Les appelants peuvent donc attraper toutes les erreurs LLM
avec un simple `except LLMError`.
"""


class LLMError(Exception):
    """
    Classe de base pour toutes les erreurs de la couche LLM.

    Toutes les exceptions spécifiques héritent de cette classe.
    Cela permet aux appelants d'attraper n'importe quelle erreur
    LLM avec un seul except, ou d'être plus précis si nécessaire.
    """

    pass


class LLMConfigurationError(LLMError):
    """
    Erreur de configuration.

    Levée lorsque Settings ne peut pas charger ou valider
    les variables d'environnement (LLM_BASE_URL, LLM_MODEL, etc.).
    """

    pass


class LLMConnectionError(LLMError):
    """
    Erreur de connexion réseau.

    Levée lorsque le client ne peut pas joindre le serveur :
    - DNS : le nom de domaine ne résout pas
    - SSL : certificat invalide ou expiré
    - Connexion : port fermé, serveur injoignable
    - Proxy / pare-feu : blocage réseau

    Cette exception est levée AVANT que le serveur n'ait répondu.
    Si le serveur répond avec un code d'erreur HTTP (4xx, 5xx),
    c'est LLMAPIError ou une de ses sous-classes qui est levée.
    """

    pass


class LLMAuthenticationError(LLMError):
    """
    Erreur d'authentification.

    Levée lorsque l'API retourne une erreur 401.
    Cela signifie que la clé API est invalide ou manquante.
    """

    pass


class LLMRateLimitError(LLMError):
    """
    Erreur de limite de débit.

    Levée lorsque l'API retourne une erreur 429 (too many requests).
    """

    pass


class LLMTimeoutError(LLMError):
    """
    Erreur de timeout.

    Levée lorsque la requête dépasse le temps d'attente configuré
    sans recevoir de réponse complète du serveur.
    """

    pass


class LLMAPIError(LLMError):
    """
    Erreur API générique.

    Levée pour les erreurs HTTP qui ne correspondent pas aux
    catégories précédentes (4xx non classifiés, 5xx, etc.)
    ou lorsque la réponse de l'API est inattendue / mal formée.
    """

    pass
