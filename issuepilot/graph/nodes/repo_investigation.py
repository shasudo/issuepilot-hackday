from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from issuepilot.config import Settings
from issuepilot.llm.factory import build_chat_model
from issuepilot.llm.prompts import load_prompt
from issuepilot.llm.retry import invoke_with_retry
from issuepilot.llm.schema import flatten_schema
from issuepilot.models.repo_context import RepoEvidence
from issuepilot.observability.trace_store import TraceStore, trace

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

MAX_TREE_PATHS = 250

_CODE_EXTENSIONS = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".swift", ".kt", ".kts", ".scala",
    ".vue", ".svelte", ".sol", ".md", ".mdx", ".rst", ".txt", ".yaml", ".yml", ".toml",
)


def prioritize_paths(paths: list[str], limit: int = MAX_TREE_PATHS) -> tuple[list[str], int]:
    """Code and docs first (stable order), capped — quota-friendly evidence."""
    code = [path for path in paths if path.lower().endswith(_CODE_EXTENSIONS)]
    rest = [path for path in paths if not path.lower().endswith(_CODE_EXTENSIONS)]
    ordered = code + rest
    return ordered[:limit], max(len(paths) - limit, 0)


class StructuredChatModel(Protocol):
    """What this node needs from a model — tests inject a stub."""

    def with_structured_output(self, schema: dict) -> _StructuredInvoker: ...


class _StructuredInvoker(Protocol):
    def invoke(self, messages: list[tuple[str, str]]) -> dict: ...


def investigate_repo(
    issue_summary: str,
    tree_paths: list[str],
    *,
    chat_model: BaseChatModel | StructuredChatModel | None = None,
    settings: Settings | None = None,
    trace_store: TraceStore | None = None,
) -> RepoEvidence:
    prompt = load_prompt("repo_investigation")
    model = chat_model or build_chat_model(settings)
    structured_model = model.with_structured_output(flatten_schema(RepoEvidence))

    shown, omitted = prioritize_paths(tree_paths)
    tree_text = "\n".join(shown)
    if omitted:
        tree_text += f"\n[... {omitted} more paths omitted]"
    user_message = f"Issue summary:\n{issue_summary}\n\nRepository tree:\n{tree_text or 'empty'}"

    messages = [("system", prompt.system), ("human", user_message)]
    if trace_store is not None:
        with trace(trace_store, "repo_investigation", prompt.version):
            raw = invoke_with_retry(structured_model, messages)
    else:
        raw = invoke_with_retry(structured_model, messages)
    return RepoEvidence(**raw)
