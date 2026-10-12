from __future__ import annotations

from typing import Any, Protocol

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

MAX_ATTEMPTS = 3

_TRANSIENT_KEYWORDS = (
    "deadline",
    "overloaded",
    "rate limit",
    "rate_limit",
    "timeout",
    "timed out",
    "temporarily",
    "try again",
    " 429",
    " 500",
    " 502",
    " 503",
    " 504",
)


class _Invoker(Protocol):
    def invoke(self, messages: list[tuple[str, str]]) -> Any: ...


def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        try:
            return int(value) if value is not None else None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return None


def is_transient(exc: BaseException) -> bool:
    """True when a model-call failure is worth retrying, across providers.

    Checks numeric status first (429 / 5xx, read off whichever attribute
    the provider SDK uses), then falls back to message keywords for
    deadline/overload phrasings.
    """
    code = _status_code(exc)
    if code is not None:
        return code == 429 or code >= 500
    message = str(exc).lower()
    return any(keyword in message for keyword in _TRANSIENT_KEYWORDS)


def invoke_with_retry(invoker: _Invoker, messages: list[tuple[str, str]]) -> Any:
    """Invoke a structured model, retrying transient provider failures."""

    @retry(
        retry=retry_if_exception(is_transient),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=2, min=2, max=15),
        reraise=True,
    )
    def _invoke() -> Any:
        return invoker.invoke(messages)

    return _invoke()
