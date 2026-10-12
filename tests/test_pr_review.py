from datetime import datetime

from issuepilot.github.models import PullRequest, PullFile
from issuepilot.graph.nodes.pr_review import review_pull
from issuepilot.models.pr_context import PRReviewAnalysis
from issuepilot.rubric.scoring import DimensionScores


def make_analysis() -> PRReviewAnalysis:
    return PRReviewAnalysis(
        summary="Adds retry",
        what_changed=["retry loop"],
        review_checklist=["check backoff"],
        risks=[],
        reasoning="small diff",
        dimension_scores=DimensionScores(
            code_complexity=2,
            components_affected=2,
            required_technical_knowledge=2,
            testing_complexity=3,
            dependencies=1,
            requirement_ambiguity=2,
        ),
    )


class StubInvoker:
    def __init__(self, analysis: PRReviewAnalysis) -> None:
        self.analysis = analysis
        self.messages: list[tuple[str, str]] | None = None

    def invoke(self, messages: list[tuple[str, str]]) -> PRReviewAnalysis:
        self.messages = messages
        return self.analysis


class StubModel:
    def __init__(self, analysis: PRReviewAnalysis) -> None:
        self.invoker = StubInvoker(analysis)

    def with_structured_output(self, schema) -> StubInvoker:
        assert schema is PRReviewAnalysis
        return self.invoker


def make_pull(patch: str = "+\n") -> PullRequest:
    return PullRequest(
        number=9,
        title="Add retry",
        body="fixes #1",
        state="open",
        labels=[],
        author="ada",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
        html_url="https://github.com/o/r/pull/9",
        additions=10,
        deletions=1,
        changed_files=1,
        base_branch="main",
        head_branch="retry",
        files=[PullFile(filename="net.py", status="modified", additions=10, deletions=1, patch=patch)],
    )


def test_review_pull_returns_analysis() -> None:
    stub = StubModel(make_analysis())
    context = review_pull(make_pull(), chat_model=stub)
    assert context.analysis.summary == "Adds retry"
    assert stub.invoker.messages is not None
    assert "net.py" in stub.invoker.messages[1][1]


def test_huge_diff_is_truncated() -> None:
    stub = StubModel(make_analysis())
    review_pull(make_pull(patch="x" * 50000), chat_model=stub)
    assert stub.invoker.messages is not None
    assert "[diff truncated]" in stub.invoker.messages[1][1]
