from __future__ import annotations

from typing import TYPE_CHECKING

from issuepilot.config import Settings, get_settings

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


def build_chat_model(settings: Settings | None = None, *, temperature: float = 0.0) -> BaseChatModel:
    """Build the chat model for the configured provider.

    Nodes never import provider SDKs directly: swapping or A/B-ing
    providers is a `.env` change (LLM_PROVIDER + key + model), never a
    code change.
    """
    settings = settings or get_settings()

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        if not settings.anthropic_model:
            raise ValueError("ANTHROPIC_MODEL is required when LLM_PROVIDER=anthropic")
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            timeout=60.0,
        )

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if not settings.openai_model:
            raise ValueError("OPENAI_MODEL is required when LLM_PROVIDER=openai")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            timeout=60.0,
        )

    if settings.llm_provider == "google":
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")
        if not settings.google_model:
            raise ValueError(
                "GOOGLE_MODEL is required when LLM_PROVIDER=google "
                "(use the organizer-confirmed model ID)"
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.google_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            timeout=60.0,
        )

    raise ValueError(f"unknown LLM provider: {settings.llm_provider}")
