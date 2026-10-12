import pytest

from issuepilot.llm.prompts import load_prompt


def test_issue_prompt_loads() -> None:
    prompt = load_prompt("issue_investigation")
    assert prompt.version == "v1"
    assert "dimension_scores" in prompt.system


def test_pr_prompt_loads() -> None:
    prompt = load_prompt("pr_review")
    assert prompt.version == "v1"
    assert "review_checklist" in prompt.system


def test_missing_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("nope")


def test_evidence_prompts_load() -> None:
    assert "ranked_paths" in load_prompt("repo_investigation").system
    assert "relevance" in load_prompt("history_investigation").system
