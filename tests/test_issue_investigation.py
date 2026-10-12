from datetime import datetime

from issuepilot.github.models import Issue
from issuepilot.graph.nodes.issue_investigation import (
    extract_referenced_numbers,
    investigate_issue,
)
from issuepilot.models.issue_context import IssueContextAnalysis
from issuepilot.observability.trace_store import TraceStore
from issuepilot.rubric.scoring import DimensionScores


def make_analysis() -> IssueContextAnalysis:
    return IssueContextAnalysis(
        summary="Fix the crash",
        stated_requirements=["no crash"],
        likely_relevant_paths=["app.py"],
        ambiguities=[],
        reasoning="clear repro",
        dimension_scores=DimensionScores(
            code_complexity=2,
            components_affected=1,
            required_technical_knowledge=2,
            testing_complexity=2,
            dependencies=1,
            requirement_ambiguity=1,
        ),
    )


class StubInvoker:
    def __init__(self, analysis: IssueContextAnalysis) -> None:
        self.analysis = analysis
        self.messages: list[tuple[str, str]] | None = None

    def invoke(self, messages: list[tuple[str, str]]) -> dict:
        self.messages = messages
        return self.analysis.model_dump()


class StubModel:
    def __init__(self, analysis: IssueContextAnalysis) -> None:
        self.invoker = StubInvoker(analysis)

    def with_structured_output(self, schema) -> StubInvoker:
        assert isinstance(schema, dict)
        return self.invoker


def make_issue() -> Issue:
    return Issue(
        number=1,
        title="Crash on start",
        body="It crashes, see #12 and #12 again",
        state="open",
        labels=["bug"],
        author="ada",
        comment_count=0,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
        html_url="https://github.com/o/r/issues/1",
    )


def test_investigate_issue_uses_structured_output(tmp_path) -> None:
    stub = StubModel(make_analysis())
    store = TraceStore(tmp_path / "t.db")
    try:
        context = investigate_issue(make_issue(), chat_model=stub, trace_store=store)
    finally:
        store.close()
    assert context.analysis.summary == "Fix the crash"
    assert context.referenced_numbers == [12]
    assert stub.invoker.messages is not None
    assert "Crash on start" in stub.invoker.messages[1][1]


def test_extract_referenced_numbers_dedupes_and_excludes() -> None:
    assert extract_referenced_numbers("see #3 and #3, also #1", exclude=1) == [3]
    assert extract_referenced_numbers(None, "") == []


def test_long_comments_truncated() -> None:
    from issuepilot.github.models import Comment

    stub = StubModel(make_analysis())
    issue = make_issue()
    issue.comments = [
        Comment(id=1, author="a", body="x" * 5000, created_at=issue.created_at)
    ]
    investigate_issue(issue, chat_model=stub)
    assert stub.invoker.messages is not None
    assert "[older comments truncated]" in stub.invoker.messages[1][1]
