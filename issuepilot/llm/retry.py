from __future__ import annotations

import re
from typing import Any, Protocol

from tenacity import retry, retry_if_exception, stop_after_attempt

MAX_ATTEMPTS = 3
MAX_RETRY_WAIT_SECONDS = 90.0

_RETRY_IN_RE = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)
_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?([\d.]+)s", re.IGNORECASE)

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


def retry_after_seconds(exc: BaseException) -> float | None:
    """Server-suggested wait, parsed from quota error messages (RetryInfo)."""
    message = str(exc)
    for pattern in (_RETRY_IN_RE, _RETRY_DELAY_RE):
        match = pattern.search(message)
        if match:
            return float(match.group(1))
    return None


def _wait_time(retry_state) -> float:
    outcome = retry_state.outcome
    exc = outcome.exception() if outcome is not None else None
    if exc is not None:
        suggested = retry_after_seconds(exc)
        if suggested is not None:
            return min(suggested, MAX_RETRY_WAIT_SECONDS)
    return float(min(2 ** max(retry_state.attempt_number, 1), 15))


def invoke_with_retry(invoker: _Invoker, messages: list[tuple[str, str]]) -> Any:
    """Invoke a structured model, retrying transient provider failures.

    Honors the server's own retry delay on quota errors (retrying early
    just burns quota faster) and backs off exponentially otherwise.
    """

    @retry(
        retry=retry_if_exception(is_transient),
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=_wait_time,
        reraise=True,
    )
    def _invoke() -> Any:
        return invoker.invoke(messages)

    return _invoke()
