from issuepilot.llm.schema import flatten_schema
from issuepilot.models.issue_context import IssueContextAnalysis
from issuepilot.models.pr_context import PRReviewAnalysis
from issuepilot.models.repo_context import HistoryEvidence, RepoEvidence


def _assert_flat(node) -> None:
    if isinstance(node, dict):
        for banned in ("$ref", "$defs", "allOf", "title", "description"):
            assert banned not in node
        for value in node.values():
            _assert_flat(value)
    elif isinstance(node, list):
        for value in node:
            _assert_flat(value)


def test_all_analysis_schemas_flatten() -> None:
    for model in (IssueContextAnalysis, PRReviewAnalysis, RepoEvidence, HistoryEvidence):
        _assert_flat(flatten_schema(model))


def test_flat_schema_keeps_nested_shape() -> None:
    flat = flatten_schema(IssueContextAnalysis)
    scores = flat["properties"]["dimension_scores"]
    assert scores["type"] == "object"
    assert "code_complexity" in scores["properties"]
    assert set(flat["required"]) >= {"summary", "reasoning", "dimension_scores"}


class RecordingModel:
    def __init__(self) -> None:
        self.calls: list = []

    def with_structured_output(self, schema, **kwargs):
        self.calls.append((schema, kwargs))
        return "bound"


def test_bind_structured_wraps_for_openai_models() -> None:
    from langchain_openai import ChatOpenAI

    from issuepilot.llm.schema import bind_structured

    model = ChatOpenAI(model="x", api_key="k")
    bound = bind_structured(model, {"type": "object", "properties": {}})
    assert bound is not None  # binding builds locally; no network involved


def test_bind_structured_passes_raw_dict_through() -> None:
    from issuepilot.llm.schema import bind_structured

    model = RecordingModel()
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    assert bind_structured(model, schema) == "bound"
    sent, kwargs = model.calls[0]
    assert sent == schema
    assert kwargs == {"method": "json_schema"}


def test_flat_schema_round_trips() -> None:
    payload = {
        "summary": "s",
        "stated_requirements": [],
        "likely_relevant_paths": [],
        "ambiguities": [],
        "reasoning": "r",
        "dimension_scores": {
            "code_complexity": 1,
            "components_affected": 1,
            "required_technical_knowledge": 1,
            "testing_complexity": 1,
            "dependencies": 1,
            "requirement_ambiguity": 1,
        },
    }
    assert IssueContextAnalysis(**payload).summary == "s"
