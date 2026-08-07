"""LLM model registry with pre-initialized instances.

Ported from the fastapi-langgraph-agent template. Unlike the template — which
hardcodes its model list — the registry is built from configuration, because
this project talks to an OpenAI-compatible endpoint (DeepSeek by default) whose
model names differ per deployment.

The fallback chain is ``DEFAULT_LLM_MODEL`` followed by ``LLM_FALLBACK_MODELS``.
"""

from typing import (
    Any,
    Dict,
    List,
)

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_API_KEY = SecretStr(settings.LLM_API_KEY or "dummy")


def _build_model(model_name: str, **overrides: Any) -> BaseChatModel:
    """Construct a ChatOpenAI instance pointed at the configured endpoint."""
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "api_key": _API_KEY,
        "temperature": settings.DEFAULT_LLM_TEMPERATURE,
        "max_tokens": settings.MAX_TOKENS,
        "timeout": settings.LLM_TOTAL_TIMEOUT,
    }
    if settings.LLM_BASE_URL:
        kwargs["base_url"] = settings.LLM_BASE_URL
    kwargs.update(overrides)
    return ChatOpenAI(**kwargs)


def _model_names() -> List[str]:
    """Return the ordered, de-duplicated fallback chain."""
    names = [settings.DEFAULT_LLM_MODEL, *settings.LLM_FALLBACK_MODELS]
    seen: set[str] = set()
    ordered: List[str] = []
    for name in names:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


class LLMRegistry:
    """Registry of available LLM models with pre-initialized instances."""

    LLMS: List[Dict[str, Any]] = [{"name": name, "llm": _build_model(name)} for name in _model_names()]

    @classmethod
    def get(cls, model_name: str, **kwargs) -> BaseChatModel:
        """Get an LLM by name, optionally with per-call overrides.

        Args:
            model_name: Name of the model to retrieve.
            **kwargs: Overrides applied to a fresh instance, leaving the shared
                registry entry untouched.

        Returns:
            A chat model instance.

        Raises:
            ValueError: When the model is not registered.
        """
        entry = next((e for e in cls.LLMS if e["name"] == model_name), None)
        if not entry:
            available = ", ".join(e["name"] for e in cls.LLMS)
            raise ValueError(f"model '{model_name}' not found in registry. available models: {available}")

        if kwargs:
            logger.debug("creating_llm_with_custom_args", model_name=model_name, custom_args=list(kwargs.keys()))
            return _build_model(model_name, **kwargs)

        return entry["llm"]

    @classmethod
    def get_all_names(cls) -> List[str]:
        """Return all registered model names in fallback order."""
        return [e["name"] for e in cls.LLMS]

    @classmethod
    def get_model_at_index(cls, index: int) -> Dict[str, Any]:
        """Return the registry entry at an index, wrapping to 0 when out of range."""
        if 0 <= index < len(cls.LLMS):
            return cls.LLMS[index]
        return cls.LLMS[0]
