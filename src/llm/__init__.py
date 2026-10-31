"""
Couche LLM — API publique.
===========================

Point d'entrée unique pour toute interaction avec les modèles de langage.

Exporte uniquement les classes et fonctions que les autres modules
du projet sont autorisés à utiliser. Tout le reste est privé.

Utilisation :
    from src.llm import LLMClient, Settings
    from src.llm import LLMError, LLMConfigurationError
"""

from src.llm.client import LLMClient
from src.llm.settings import Settings

from src.llm.exceptions import (
    LLMError,
    LLMConfigurationError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMAPIError,
)

__all__ = [
    # Clients
    "LLMClient",
    "Settings",
    # Exceptions
    "LLMError",
    "LLMConfigurationError",
    "LLMConnectionError",
    "LLMAuthenticationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMAPIError",
]
