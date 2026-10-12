from tests.test_service import (
    FakeGateway,
    SchemaStub,
    StubModel,
    issue_analysis,
    make_issue,
    make_settings,
)
from issuepilot.github.resolver import ResolvedLink
from issuepilot.graph.builder import build_analysis_graph
from issuepilot.models.repo_context import HistoryEvidence, HistoryNote, RankedPath, RepoEvidence
from issuepilot.profile import UserProfile
from issuepilot.reports import EntityReport
from issuepilot.rubric.scoring import RubricConfig, default_rubric_path
from issuepilot.service import analyze_link


def test_graph_runs_issue_end_to_end(tmp_path) -> None:
    settings = make_settings(tmp_path)
    profile = UserProfile(level="beginner", languages=["python"])
    graph = build_analysis_graph(
        FakeGateway(issue=make_issue()),
        settings,
        profile,
        chat_model=StubModel(issue_analysis()),
        rubric=RubricConfig.load(default_rubric_path()),
    )
    state = graph.invoke({"link": ResolvedLink("issue", "o", "r", 1), "profile": profile})
    report: EntityReport = state["report"]
    assert report.title == "#1 Typo in docs"
    assert report.complexity is not None and report.complexity.difficulty == "Easy"
    assert report.fit is not None and report.fit.score >= 75


def test_graph_attaches_evidence(tmp_path) -> None:
    settings = make_settings(tmp_path)
    issue = make_issue(number=1, body="Same as #2")
    referenced = make_issue(number=2, title="Earlier report", state="closed")
    stub = SchemaStub(
        {
            "IssueContextAnalysis": issue_analysis(),
            "RepoEvidence": RepoEvidence(
                ranked_paths=[RankedPath(path="src/a.py", reason="matches")], reasoning="r"
            ),
            "HistoryEvidence": HistoryEvidence(notes=[HistoryNote(number=2, relevance="same")]),
        }
    )
    graph = build_analysis_graph(
        FakeGateway(issue=issue, issues=[referenced], tree=["src/a.py"]),
        settings,
        UserProfile(),
        chat_model=stub,
        rubric=RubricConfig.load(default_rubric_path()),
    )
    state = graph.invoke({"link": ResolvedLink("issue", "o", "r", 1), "profile": UserProfile()})
    report: EntityReport = state["report"]
    assert report.repo_evidence == ["src/a.py — matches"]
    assert report.related_history == ["#2 — same"]


def test_repo_ranking_is_deterministic(tmp_path) -> None:
    issues = [
        make_issue(number=1, title="Docs typo", labels=["docs"]),
        make_issue(number=2, title="Racy core", labels=["security"]),
        make_issue(number=3, title="Small bug", labels=["bug"]),
    ]
    settings = make_settings(tmp_path)
    profile = UserProfile(level="beginner", languages=["python"])
    first = analyze_link("o/r", profile, settings=settings, gateway=FakeGateway(issues=issues))
    second = analyze_link("o/r", profile, settings=settings, gateway=FakeGateway(issues=issues))
    assert [p.number for p in first.picks] == [p.number for p in second.picks]
