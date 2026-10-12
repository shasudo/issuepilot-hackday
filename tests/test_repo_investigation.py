from issuepilot.graph.nodes.repo_investigation import investigate_repo
from issuepilot.models.repo_context import RankedPath, RepoEvidence


class StubInvoker:
    def __init__(self, evidence: RepoEvidence) -> None:
        self.evidence = evidence
        self.messages: list[tuple[str, str]] | None = None

    def invoke(self, messages: list[tuple[str, str]]) -> dict:
        self.messages = messages
        return self.evidence.model_dump()


class StubModel:
    def __init__(self, evidence: RepoEvidence) -> None:
        self.invoker = StubInvoker(evidence)

    def with_structured_output(self, schema) -> StubInvoker:
        assert isinstance(schema, dict)
        return self.invoker


def test_investigate_repo_returns_ranked_paths() -> None:
    evidence = RepoEvidence(
        ranked_paths=[RankedPath(path="a.py", reason="matches")], reasoning="r"
    )
    stub = StubModel(evidence)
    result = investigate_repo("crash on start", ["a.py", "b.py"], chat_model=stub)
    assert result.ranked_paths[0].path == "a.py"
    assert stub.invoker.messages is not None
    assert "a.py" in stub.invoker.messages[1][1]


def test_huge_tree_is_capped() -> None:
    stub = StubModel(RepoEvidence(ranked_paths=[], reasoning="none"))
    investigate_repo("x", [f"f{i}.py" for i in range(3000)], chat_model=stub)
    assert stub.invoker.messages is not None
    assert "more paths omitted" in stub.invoker.messages[1][1]
