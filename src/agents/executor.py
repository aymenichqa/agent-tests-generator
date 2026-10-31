"""
Executeur d'agents.
===================

AgentExecutor est un composant independant des agents metier.
Sa responsabilite est de formater et d'appeler le LLM via LLMClient,
de mesurer le temps d'execution et d'estimer la consommation de tokens.

Le retry reseau est centralise dans LLMClient (HTTP 524, etc.).
AgentExecutor ne fait PAS de retry supplementaire pour eviter les
attentes emboitees et les comportements impredictibles.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from src.llm import LLMClient
from src.models.node_types import TaskType


# Tarifs approximatifs par modele (USD / token).
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "qwen/qwen3.8-27b": (1.5e-6, 2.0e-6),
    "qwen/qwen3.6-35b-a3b": (1.5e-6, 2.0e-6),
    "qwen/qwen3-coder-next": (1.5e-6, 2.0e-6),
    "google/gemma-4-26b-a4b": (2.0e-6, 3.0e-6),
}

_DEFAULT_PROMPT_RATE = 1.5e-6
_DEFAULT_COMPLETION_RATE = 2.0e-6


@dataclass
class ExecutorConfig:
    """Configuration legere de l'AgentExecutor."""

    log_level: str = "INFO"
    default_model: str | None = None


@dataclass
class TokenUsage:
    """Consommation de tokens pour un appel LLM."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def estimated_cost(self) -> float:
        prompt_rate, completion_rate = _MODEL_RATES.get(
            self.model, (_DEFAULT_PROMPT_RATE, _DEFAULT_COMPLETION_RATE)
        )
        return (
            self.prompt_tokens * prompt_rate + self.completion_tokens * completion_rate
        )


@dataclass
class ExecutionResult:
    """Resultat d'un appel LLM via AgentExecutor."""

    content: str
    model: str
    token_usage: TokenUsage | None = None
    duration_ms: int = 0
    error: str | None = None


class AgentExecutor:
    """
    Executeur d'appels LLM pour les agents.

    Responsabilites :
        - Formater les prompts en messages OpenAI.
        - Appeler LLMClient.generate().
        - Mesurer la duree et estimer les tokens.
        - Retourner un ExecutionResult structure.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: ExecutorConfig | None = None,
    ) -> None:
        self._llm = llm_client
        self._config = config or ExecutorConfig()
        self._logger = logging.getLogger("agents.executor")
        self._logger.setLevel(self._config.log_level)

    def execute(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        task_type: TaskType | None = None,
        stream: bool = False,
    ) -> ExecutionResult:
        """
        Execute un appel LLM unique et retourne le resultat.

        Args:
            system_prompt: Prompt systeme.
            user_prompt:   Prompt utilisateur.
            model:         Modele a utiliser (None = defaut LLMClient).
            task_type:     Type de tache (pour logging/tracabilite).
            stream:        Si True, utilise le streaming SSE (sorties longues),
                           ce qui contourne les timeouts 524 Cloudflare.
        """
        active_model = self._resolve_model(model)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        start = time.monotonic()
        try:
            if stream:
                response = self._llm.generate_stream(
                    messages=messages, model=active_model
                )
            else:
                response = self._llm.generate(messages=messages, model=active_model)
            duration_ms = int((time.monotonic() - start) * 1000)

            prompt_tokens = len(system_prompt + user_prompt) // 4
            completion_tokens = len(response) // 4
            token_usage = TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model=active_model,
            )

            self._logger.info(
                "Appel LLM reussi | modele=%s | duree=%dms | tokens=%d",
                active_model,
                duration_ms,
                token_usage.total_tokens,
            )

            return ExecutionResult(
                content=response,
                model=active_model,
                token_usage=token_usage,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            error = f"{type(exc).__name__}: {exc}"
            self._logger.error(
                "Appel LLM echoue | modele=%s | duree=%dms | erreur=%s",
                active_model,
                duration_ms,
                error,
            )
            return ExecutionResult(
                content="",
                model=active_model,
                duration_ms=duration_ms,
                error=error,
            )

    def execute_parallel(
        self,
        system_prompt: str,
        user_prompts: list[str],
        model: str | None = None,
        task_type: TaskType | None = None,
        parallel: int = 3,
    ) -> list[ExecutionResult]:
        """
        Execute plusieurs appels LLM en parallele (micro-generation).

        Chaque appel passe par execute(stream=True) : streaming SSE (filet
        anti-524 Cloudflare) et retry 524 gere par LLMClient au niveau de
        chaque appel. Un echec isole l'element concerne (ExecutionResult.error)
        sans affecter les autres appels.

        Args:
            system_prompt: Prompt systeme partage par tous les appels.
            user_prompts:  Un prompt utilisateur par element testable.
            model:         Modele a utiliser (None = defaut LLMClient).
            task_type:     Type de tache (logging/tracabilite).
            parallel:      Nombre max d'appels simultanes. La valeur 3 est
                           validee sur qwen/qwen3.8-27b (mesures 5 + 15
                           regles : 0 erreur, gain ~1.8x, pas de saturation
                           serveur) pour l'etat ACTUEL de l'infra — a
                           revalider si le modele ou l'infra change.

        Returns:
            Liste de ExecutionResult, dans le meme ordre que user_prompts.
        """
        if not user_prompts:
            return []
        workers = max(1, min(parallel, len(user_prompts)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    self.execute,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    model=model,
                    task_type=task_type,
                    stream=True,
                )
                for user_prompt in user_prompts
            ]
            return [future.result() for future in futures]

    def _resolve_model(self, model: str | None) -> str:
        """Resout le modele a utiliser."""
        if model:
            return model
        if self._config.default_model:
            return self._config.default_model
        return self._llm.model
