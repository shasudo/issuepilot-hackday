from issuepilot.graph.nodes.history_investigation import investigate_history
from issuepilot.models.repo_context import HistoryEvidence, HistoryNote, RelatedItem


class StubInvoker:
    def __init__(self, evidence: HistoryEvidence) -> None:
        self.evidence = evidence
        self.messages: list[tuple[str, str]] | None = None

    def invoke(self, messages: list[tuple[str, str]]) -> dict:
        self.messages = messages
        return self.evidence.model_dump()


class StubModel:
    def __init__(self, evidence: HistoryEvidence) -> None:
        self.invoker = StubInvoker(evidence)

    def with_structured_output(self, schema, **kwargs) -> StubInvoker:
        assert isinstance(schema, dict)
        assert kwargs == {"method": "json_schema"}
        return self.invoker


def test_investigate_history_returns_notes() -> None:
    evidence = HistoryEvidence(notes=[HistoryNote(number=2, relevance="same bug")])
    stub = StubModel(evidence)
    related = [RelatedItem(number=2, title="Earlier report", state="closed", labels=["bug"])]
    result = investigate_history("crash on start", related, chat_model=stub)
    assert result.notes[0].relevance == "same bug"
    assert stub.invoker.messages is not None
    assert "#2" in stub.invoker.messages[1][1]
