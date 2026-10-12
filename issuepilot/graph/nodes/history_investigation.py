from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from issuepilot.config import Settings
from issuepilot.llm.factory import build_chat_model
from issuepilot.llm.prompts import load_prompt
from issuepilot.llm.retry import invoke_with_retry
from issuepilot.llm.schema import flatten_schema
from issuepilot.models.repo_context import HistoryEvidence, RelatedItem
from issuepilot.observability.trace_store import TraceStore, trace

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


class StructuredChatModel(Protocol):
    """What this node needs from a model — tests inject a stub."""

    def with_structured_output(self, schema: dict) -> _StructuredInvoker: ...


class _StructuredInvoker(Protocol):
    def invoke(self, messages: list[tuple[str, str]]) -> dict: ...


def investigate_history(
    issue_summary: str,
    related: list[RelatedItem],
    *,
    chat_model: BaseChatModel | StructuredChatModel | None = None,
    settings: Settings | None = None,
    trace_store: TraceStore | None = None,
) -> HistoryEvidence:
    prompt = load_prompt("history_investigation")
    model = chat_model or build_chat_model(settings)
    structured_model = model.with_structured_output(flatten_schema(HistoryEvidence))

    lines = [
        f"#{item.number} [{item.state}] {item.title}"
        + (f" (labels: {', '.join(item.labels)})" if item.labels else "")
        for item in related
    ]
    user_message = (
        f"Current issue summary:\n{issue_summary}\n\nReferenced items:\n" + "\n".join(lines)
    )

    messages = [("system", prompt.system), ("human", user_message)]
    if trace_store is not None:
        with trace(trace_store, "history_investigation", prompt.version):
            raw = invoke_with_retry(structured_model, messages)
    else:
        raw = invoke_with_retry(structured_model, messages)
    return HistoryEvidence(**raw)
