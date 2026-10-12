from datetime import datetime

from issuepilot.config import Settings
from issuepilot.github.models import Issue, OrgInfo, PullRequest, RepoInfo
from issuepilot.models.issue_context import IssueContextAnalysis
from issuepilot.models.pr_context import PRReviewAnalysis
from issuepilot.models.repo_context import HistoryEvidence, HistoryNote, RankedPath, RepoEvidence
from issuepilot.profile import UserProfile
from issuepilot.rubric.scoring import DimensionScores, RubricConfig, default_rubric_path
from issuepilot.service import OrgReport, RepoReport, analyze_link


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


class SchemaStub:
    """Returns a different canned analysis per schema name."""

    def __init__(self, by_name: dict) -> None:
        self.by_name = by_name

    def with_structured_output(self, schema):
        return StubInvoker(self.by_name[schema.__name__])


class FakeGateway:
    """In-memory gateway: no network, deterministic payloads."""

    def __init__(
        self,
        issue: Issue | None = None,
        pull: PullRequest | None = None,
        issues: list[Issue] | None = None,
        repos: list[RepoInfo] | None = None,
        org: OrgInfo | None = None,
        tree: list[str] | None = None,
    ) -> None:
        self._issue = issue
        self._pull = pull
        self._issues = issues or []
        self._repos = repos or []
        self._org = org or OrgInfo(login="o")
        self._tree = tree or []

    def fetch_account_type(self, name: str) -> str:
        return "Organization"

    def fetch_issue(self, owner: str, repo: str, number: int) -> Issue:
        candidates = ([self._issue] if self._issue else []) + self._issues
        for candidate in candidates:
            if candidate.number == number:
                return candidate
        raise AssertionError(f"no canned issue #{number}")

    def fetch_pull(self, owner: str, repo: str, number: int) -> PullRequest:
        assert self._pull is not None
        return self._pull

    def fetch_repo(self, owner: str, repo: str) -> RepoInfo:
        return RepoInfo(
            owner=owner,
            name=repo,
            full_name=f"{owner}/{repo}",
            languages=["Python"],
            default_branch="main",
            updated_at=datetime(2026, 1, 1),
        )

    def fetch_org(self, org: str) -> OrgInfo:
        return self._org

    def list_repo_issues(self, owner: str, repo: str, limit: int = 30) -> list[Issue]:
        return self._issues[:limit]

    def list_org_repos(self, org: str, limit: int = 30) -> list[RepoInfo]:
        return self._repos[:limit]

    def list_repo_tree(self, owner: str, repo: str, branch: str, limit: int = 2000) -> list[str]:
        return self._tree[:limit]

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


def issue_analysis() -> IssueContextAnalysis:
    return IssueContextAnalysis(
        summary="Fix a docs typo",
        stated_requirements=["fix typo"],
        likely_relevant_paths=["README.md"],
        ambiguities=[],
        reasoning="trivial",
        dimension_scores=easy_scores(),
    )


def test_analyze_issue_link(tmp_path) -> None:
    report = analyze_link(
        "o/r#1",
        UserProfile(level="beginner", languages=["python"]),
        settings=make_settings(tmp_path),
        gateway=FakeGateway(issue=make_issue()),
        chat_model=StubModel(issue_analysis()),
        rubric=RubricConfig.load(default_rubric_path()),
    )
    assert report.title == "#1 Typo in docs"
    assert report.complexity is not None and report.complexity.difficulty == "Easy"
    assert report.fit is not None and report.fit.score >= 75
    assert report.bullets == ["fix typo"]
    assert report.repo_evidence == []  # empty tree: evidence skipped


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


def test_issue_evidence_attached(tmp_path) -> None:
    issue = make_issue(number=1, body="Same as #2")
    referenced = make_issue(number=2, title="Earlier report", state="closed")
    stub = SchemaStub(
        {
            "IssueContextAnalysis": issue_analysis(),
            "RepoEvidence": RepoEvidence(
                ranked_paths=[RankedPath(path="src/a.py", reason="matches")],
                reasoning="r",
            ),
            "HistoryEvidence": HistoryEvidence(
                notes=[HistoryNote(number=2, relevance="same bug")]
            ),
        }
    )
    report = analyze_link(
        "o/r#1",
        UserProfile(),
        settings=make_settings(tmp_path),
        gateway=FakeGateway(issue=issue, issues=[referenced], tree=["src/a.py", "src/b.py"]),
        chat_model=stub,
        rubric=RubricConfig.load(default_rubric_path()),
    )
    assert report.referenced_numbers == [2]
    assert report.repo_evidence == ["src/a.py — matches"]
    assert report.related_history == ["#2 — same bug"]


def test_analyze_repo_link_ranks_picks(tmp_path) -> None:
    issues = [
        make_issue(number=1, title="Docs typo", labels=["docs"]),
        make_issue(number=2, title="Racy core", labels=["security"]),
    ]
    report = analyze_link(
        "o/r",
        UserProfile(level="beginner", languages=["python"]),
        settings=make_settings(tmp_path),
        gateway=FakeGateway(issues=issues),
    )
    assert isinstance(report, RepoReport)
    assert report.scanned == 2
    assert [pick.number for pick in report.picks] == [1, 2]
    assert report.picks[0].difficulty == "Easy"


def test_analyze_org_link_aggregates(tmp_path) -> None:
    repos = [
        RepoInfo(owner="o", name="r1", full_name="o/r1", languages=["Python"]),
        RepoInfo(owner="o", name="r2", full_name="o/r2", languages=["Rust"]),
    ]
    issues = [make_issue(number=1, title="Docs typo", labels=["docs"])]
    report = analyze_link(
        "https://github.com/o",
        UserProfile(level="beginner", languages=["python"]),
        settings=make_settings(tmp_path),
        gateway=FakeGateway(issues=issues, repos=repos),
    )
    assert isinstance(report, OrgReport)
    assert report.scanned_repos == 2
    assert report.picks[0].repo == "o/r1"
