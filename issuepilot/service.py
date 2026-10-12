from __future__ import annotations

from issuepilot.config import Settings, get_settings
from issuepilot.fit import quick_difficulty, score_fit
from issuepilot.gateway import GitHubGateway
from issuepilot.github.client import GitHubClient
from issuepilot.github.models import RepoInfo
from issuepilot.github.resolver import ResolvedLink, resolve
from issuepilot.graph.builder import build_analysis_graph
from issuepilot.observability.trace_store import TraceStore
from issuepilot.profile import UserProfile
from issuepilot.reports import EntityReport, OrgReport, QuickPick, RepoReport
from issuepilot.rubric.scoring import RubricConfig

# Re-exported so callers keep one import surface for reports.
__all__ = [
    "EntityReport",
    "GitHubGateway",
    "OrgReport",
    "QuickPick",
    "RepoReport",
    "analyze_link",
]

REPO_SCAN_LIMIT = 15
REPO_PICKS = 8
ORG_REPO_LIMIT = 6
ORG_ISSUES_PER_REPO = 10
ORG_PICKS = 10


def analyze_link(
    text: str,
    profile: UserProfile,
    *,
    settings: Settings | None = None,
    gateway: GitHubGateway | None = None,
    chat_model=None,
    trace_store: TraceStore | None = None,
    rubric: RubricConfig | None = None,
) -> EntityReport | RepoReport | OrgReport:
    """Resolve any supported link and build its personalized report.

    Single entities run through the LangGraph pipeline; repos/orgs use
    cheap label-based ranking (opening any pick runs the full pipeline).
    """
    settings = settings or get_settings()
    owns_gateway = gateway is None
    gateway = gateway or GitHubClient(settings)
    try:
        link = resolve(text, gateway)
        if link.kind == "repo":
            assert link.repo is not None
            return _analyze_repo(link, profile, gateway)
        if link.kind == "org":
            return _analyze_org(link, profile, gateway)
        graph = build_analysis_graph(
            gateway, settings, profile,
            chat_model=chat_model, trace_store=trace_store, rubric=rubric,
        )
        return graph.invoke({"link": link, "profile": profile})["report"]
    finally:
        if owns_gateway:
            gateway.close()


def _analyze_repo(link: ResolvedLink, profile: UserProfile, gateway: GitHubGateway) -> RepoReport:
    assert link.repo is not None
    repo = gateway.fetch_repo(link.owner, link.repo)
    issues = gateway.list_repo_issues(link.owner, link.repo, limit=REPO_SCAN_LIMIT)
    picks = sorted(
        (_quick_pick(repo, issue, profile) for issue in issues),
        key=lambda pick: pick.fit.score,
        reverse=True,
    )[:REPO_PICKS]
    return RepoReport(link=link, repo=repo, picks=picks, scanned=len(issues))


def _analyze_org(link: ResolvedLink, profile: UserProfile, gateway: GitHubGateway) -> OrgReport:
    org = gateway.fetch_org(link.owner)
    repos = gateway.list_org_repos(link.owner, limit=ORG_REPO_LIMIT)
    picks: list[QuickPick] = []
    for repo in repos:
        for issue in gateway.list_repo_issues(repo.owner, repo.name, limit=ORG_ISSUES_PER_REPO):
            picks.append(_quick_pick(repo, issue, profile))
    picks.sort(key=lambda pick: pick.fit.score, reverse=True)
    return OrgReport(link=link, org=org, repos=repos, picks=picks[:ORG_PICKS], scanned_repos=len(repos))


def _quick_pick(repo: RepoInfo, issue, profile: UserProfile) -> QuickPick:
    difficulty = quick_difficulty(issue.labels)
    fit = score_fit(
        difficulty=difficulty,
        labels=issue.labels,
        languages=repo.languages,
        topics=repo.topics,
        profile=profile,
    )
    return QuickPick(
        repo=repo.full_name,
        number=issue.number,
        title=issue.title,
        url=issue.html_url,
        labels=list(issue.labels),
        difficulty=difficulty,
        fit=fit,
    )
