from datetime import datetime

import pytest

from issuepilot.config import Settings
from issuepilot.github.models import Issue, PullRequest, RepoInfo
from issuepilot.models.issue_context import IssueContextAnalysis
from issuepilot.models.pr_context import PRReviewAnalysis
from issuepilot.profile import UserProfile
from issuepilot.rubric.scoring import DimensionScores, RubricConfig, default_rubric_path
from issuepilot.service import analyze_link


def easy_scores() -> DimensionScores:
    return DimensionScores(
        code_complexity=1,
        components_affected=1,
        required_technical_knowledge=2,
        testing_complexity=1,
        dependencies=1,
        requirement_ambiguity=1,
    )


class StubInvoker:
    def __init__(self, analysis) -> None:
        self.analysis = analysis

    def invoke(self, messages):
        return self.analysis


class StubModel:
    def __init__(self, analysis) -> None:
        self.analysis = analysis

    def with_structured_output(self, schema):
        return StubInvoker(self.analysis)


class FakeGateway:
    """In-memory gateway: no network, deterministic payloads."""

    def __init__(self, issue: Issue | None = None, pull: PullRequest | None = None) -> None:
        self._issue = issue
        self._pull = pull

    def fetch_account_type(self, name: str) -> str:
        return "Organization"

    def fetch_issue(self, owner: str, repo: str, number: int) -> Issue:
        assert self._issue is not None
        return self._issue

    def fetch_pull(self, owner: str, repo: str, number: int) -> PullRequest:
        assert self._pull is not None
        return self._pull

    def fetch_repo(self, owner: str, repo: str) -> RepoInfo:
        return RepoInfo(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            languages=["Python"],
            updated_at=datetime(2026, 1, 1),
        )

    def close(self) -> None:
        pass


def make_settings(tmp_path) -> Settings:
    return Settings(
        github_token="x", cache_db_path=tmp_path / "c.db", trace_db_path=tmp_path / "t.db"
    )


def make_issue(**overrides) -> Issue:
    values = {
        "number": 1,
        "title": "Typo in docs",
        "body": "Fix the typo",
        "state": "open",
        "labels": ["docs"],
        "author": "ada",
        "comment_count": 0,
        "created_at": datetime(2026, 1, 1),
        "updated_at": datetime(2026, 1, 2),
        "html_url": "https://github.com/o/r/issues/1",
    }
    values.update(overrides)
    return Issue(**values)


def test_analyze_issue_link(tmp_path) -> None:
    analysis = IssueContextAnalysis(
        summary="Fix a docs typo",
        stated_requirements=["fix typo"],
        likely_relevant_paths=["README.md"],
        ambiguities=[],
        reasoning="trivial",
        dimension_scores=easy_scores(),
    )
    report = analyze_link(
        "o/r#1",
        UserProfile(level="beginner", languages=["python"]),
        settings=make_settings(tmp_path),
        gateway=FakeGateway(issue=make_issue()),
        chat_model=StubModel(analysis),
        rubric=RubricConfig.load(default_rubric_path()),
    )
    assert report.title == "#1 Typo in docs"
    assert report.complexity is not None and report.complexity.difficulty == "Easy"
    assert report.fit is not None and report.fit.score >= 75
    assert report.bullets == ["fix typo"]


def test_issue_link_upgrades_to_pull(tmp_path) -> None:
    pr_analysis = PRReviewAnalysis(
        summary="Fix",
        what_changed=["typo"],
        review_checklist=["read"],
        risks=[],
        reasoning="tiny",
        dimension_scores=easy_scores(),
    )
    pull = PullRequest(
        number=3,
        title="Fix typo",
        body="",
        state="open",
        labels=[],
        author="ada",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 2),
        html_url="https://github.com/o/r/pull/3",
    )
    report = analyze_link(
        "https://github.com/o/r/issues/3",
        UserProfile(),
        settings=make_settings(tmp_path),
        gateway=FakeGateway(issue=make_issue(number=3, is_pull=True), pull=pull),
        chat_model=StubModel(pr_analysis),
        rubric=RubricConfig.load(default_rubric_path()),
    )
    assert report.bullets_title == "What changed"


def test_repo_link_rejected_until_m3(tmp_path) -> None:
    with pytest.raises(ValueError, match="lands in M3"):
        analyze_link(
            "o/r",
            UserProfile(),
            settings=make_settings(tmp_path),
            gateway=FakeGateway(),
        )
