from issuepilot.llm.schema import flatten_schema
from issuepilot.models.issue_context import IssueContextAnalysis
from issuepilot.models.pr_context import PRReviewAnalysis
from issuepilot.models.repo_context import HistoryEvidence, RepoEvidence


def _assert_flat(node) -> None:
    if isinstance(node, dict):
        assert "$ref" not in node and "$defs" not in node and "allOf" not in node
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
