import pytest

from issuepilot.config import Settings
from issuepilot.llm.factory import build_chat_model


def make_settings(tmp_path, **overrides) -> Settings:
    values = {
        "github_token": "x",
        "cache_db_path": tmp_path / "c.db",
        "trace_db_path": tmp_path / "t.db",
    }
    values.update(overrides)
    return Settings(**values)


def test_google_provider_builds(tmp_path) -> None:
    settings = make_settings(
        tmp_path, llm_provider="google", google_api_key="k", google_model="test-model"
    )
    model = build_chat_model(settings)
    assert model.model == "test-model"
    assert model.reasoning_effort is None


def test_gemma_models_get_minimal_thinking(tmp_path) -> None:
    settings = make_settings(
        tmp_path, llm_provider="google", google_api_key="k", google_model="gemma-4-26b-a4b-it"
    )
    assert build_chat_model(settings).reasoning_effort == "minimal"


def test_google_requires_key_and_model(tmp_path) -> None:
    # Explicit Nones: a real .env in the repo root must not leak into these cases.
    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        build_chat_model(
            make_settings(tmp_path, llm_provider="google", google_model="m", google_api_key=None)
        )
    with pytest.raises(ValueError, match="GOOGLE_MODEL"):
        build_chat_model(
            make_settings(tmp_path, llm_provider="google", google_api_key="k", google_model=None)
        )


def test_openai_provider_builds(tmp_path) -> None:
    settings = make_settings(
        tmp_path, llm_provider="openai", openai_api_key="k", openai_model="test-model"
    )
    assert build_chat_model(settings).model == "test-model"


def test_anthropic_provider_builds(tmp_path) -> None:
    settings = make_settings(
        tmp_path, llm_provider="anthropic", anthropic_api_key="k", anthropic_model="test-model"
    )
    assert build_chat_model(settings).model == "test-model"


def test_openrouter_provider_builds(tmp_path) -> None:
    settings = make_settings(
        tmp_path,
        llm_provider="openrouter",
        openrouter_api_key="k",
        openrouter_model="google/gemma-4-26b-a4b-it:free",
    )
    model = build_chat_model(settings)
    assert model.model == "google/gemma-4-26b-a4b-it:free"
    assert "openrouter.ai" in str(model.openai_api_base)


def test_groq_provider_builds(tmp_path) -> None:
    settings = make_settings(
        tmp_path, llm_provider="groq", groq_api_key="k", groq_model="test-model"
    )
    model = build_chat_model(settings)
    assert model.model == "test-model"
    assert "groq.com" in str(model.openai_api_base)


def test_groq_requires_key_and_model(tmp_path) -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        build_chat_model(
            make_settings(tmp_path, llm_provider="groq", groq_model="m", groq_api_key=None)
        )
    with pytest.raises(ValueError, match="GROQ_MODEL"):
        build_chat_model(
            make_settings(tmp_path, llm_provider="groq", groq_api_key="k", groq_model=None)
        )


def test_openrouter_requires_key_and_model(tmp_path) -> None:
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        build_chat_model(
            make_settings(
                tmp_path,
                llm_provider="openrouter",
                openrouter_model="m",
                openrouter_api_key=None,
            )
        )
    with pytest.raises(ValueError, match="OPENROUTER_MODEL"):
        build_chat_model(
            make_settings(
                tmp_path,
                llm_provider="openrouter",
                openrouter_api_key="k",
                openrouter_model=None,
            )
        )
