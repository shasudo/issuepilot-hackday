from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from issuepilot.config import Settings
from issuepilot.github.models import PullRequest
from issuepilot.llm.factory import build_chat_model
from issuepilot.llm.prompts import load_prompt
from issuepilot.llm.retry import invoke_with_retry
from issuepilot.llm.schema import flatten_schema
from issuepilot.models.pr_context import PRContext, PRReviewAnalysis
from issuepilot.observability.trace_store import TraceStore, trace

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

MAX_DIFF_CHARS = 20000


class StructuredChatModel(Protocol):
    """What this node needs from a model — tests inject a stub."""

    def with_structured_output(self, schema: dict) -> _StructuredInvoker: ...


class _StructuredInvoker(Protocol):
    def invoke(self, messages: list[tuple[str, str]]) -> dict: ...


def review_pull(
    pull: PullRequest,
    *,
    chat_model: BaseChatModel | StructuredChatModel | None = None,
    settings: Settings | None = None,
    trace_store: TraceStore | None = None,
) -> PRContext:
    prompt = load_prompt("pr_review")
    model = chat_model or build_chat_model(settings)
    structured_model = model.with_structured_output(flatten_schema(PRReviewAnalysis))

    comments_text = "\n\n".join(f"@{c.author}: {c.body}" for c in pull.comments)
    diff_text = _render_diff(pull)
    user_message = (
        f"Title: {pull.title}\n"
        f"State: {pull.state}{' (draft)' if pull.draft else ''} | "
        f"{pull.base_branch} <- {pull.head_branch}\n"
        f"Labels: {', '.join(pull.labels) or '(none)'}\n"
        f"Stats: +{pull.additions}/-{pull.deletions} across {pull.changed_files} files\n\n"
        f"Description:\n{pull.body or '(empty)'}\n\n"
        f"Comments:\n{comments_text or '(none)'}\n\n"
        f"Diff:\n{diff_text}"
    )

    messages = [("system", prompt.system), ("human", user_message)]
    if trace_store is not None:
        with trace(trace_store, "pr_review", prompt.version):
            raw = invoke_with_retry(structured_model, messages)
    else:
        raw = invoke_with_retry(structured_model, messages)
    analysis = PRReviewAnalysis(**raw)

    return PRContext(analysis=analysis)


def _render_diff(pull: PullRequest) -> str:
    parts: list[str] = []
    for item in pull.files:
        parts.append(f"--- {item.filename} ({item.status}, +{item.additions}/-{item.deletions})")
        if item.patch:
            parts.append(item.patch)
    text = "\n".join(parts) or "(no file data)"
    if len(text) > MAX_DIFF_CHARS:
        return text[:MAX_DIFF_CHARS] + "\n[diff truncated]"
    return text
