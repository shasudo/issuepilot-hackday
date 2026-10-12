from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from issuepilot.config import Settings, get_settings
from issuepilot.fit import FitResult, quick_difficulty, score_fit
from issuepilot.github.client import GitHubClient, GitHubNotFoundError
from issuepilot.github.models import Issue, OrgInfo, PullRequest, RepoInfo
from issuepilot.github.resolver import ResolvedLink, resolve
from issuepilot.graph.nodes.history_investigation import investigate_history
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.graph.nodes.pr_review import review_pull
from issuepilot.graph.nodes.repo_investigation import investigate_repo
from issuepilot.models.issue_context import IssueContext
from issuepilot.models.pr_context import PRContext
from issuepilot.models.repo_context import RelatedItem
from issuepilot.observability.trace_store import TraceStore
from issuepilot.profile import UserProfile
from issuepilot.rubric.scoring import (
    ComplexityResult,
    Difficulty,
    RubricConfig,
    default_rubric_path,
    score,
)

MAX_HISTORY_ITEMS = 5
REPO_SCAN_LIMIT = 15
REPO_PICKS = 8
ORG_REPO_LIMIT = 6
ORG_ISSUES_PER_REPO = 10
ORG_PICKS = 10


class GitHubGateway(Protocol):
    """The GitHub surface analysis needs — GitHubClient satisfies this."""

    def fetch_account_type(self, name: str) -> str: ...
    def fetch_issue(self, owner: str, repo: str, number: int) -> Issue: ...
    def fetch_pull(self, owner: str, repo: str, number: int) -> PullRequest: ...
    def fetch_repo(self, owner: str, repo: str) -> RepoInfo: ...
    def fetch_org(self, org: str) -> OrgInfo: ...
    def list_repo_issues(self, owner: str, repo: str, limit: int = 30) -> list[Issue]: ...
    def list_org_repos(self, org: str, limit: int = 30) -> list[RepoInfo]: ...
    def list_repo_tree(self, owner: str, repo: str, branch: str, limit: int = 2000) -> list[str]: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class EntityReport:
    """One analyzed issue/PR, shaped for display (CLI card and UI card share it)."""

    link: ResolvedLink
    title: str
    url: str
    summary: str
    bullets_title: str
    bullets: list[str] = field(default_factory=list)
    checklist_title: str = ""
    checklist: list[str] = field(default_factory=list)
    notes_title: str = ""
    notes: list[str] = field(default_factory=list)
    reasoning: str = ""
    referenced_numbers: list[int] = field(default_factory=list)
    repo_evidence: list[str] = field(default_factory=list)
    related_history: list[str] = field(default_factory=list)
    complexity: ComplexityResult | None = None
    fit: FitResult | None = None


@dataclass(frozen=True)
class QuickPick:
    repo: str
    number: int
    title: str
    url: str
    labels: list[str]
    difficulty: Difficulty
    fit: FitResult


@dataclass(frozen=True)
class RepoReport:
    link: ResolvedLink
    repo: RepoInfo
    picks: list[QuickPick]
    scanned: int


@dataclass(frozen=True)
class OrgReport:
    link: ResolvedLink
    org: OrgInfo
    repos: list[RepoInfo]
    picks: list[QuickPick]
    scanned_repos: int


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
    """Resolve any supported link and build its personalized report."""
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
        assert link.repo is not None and link.number is not None
        return _analyze_entity(
            link, profile, gateway,
            settings=settings, chat_model=chat_model, trace_store=trace_store, rubric=rubric,
        )
    finally:
        if owns_gateway:
            gateway.close()


def _analyze_entity(
    link: ResolvedLink,
    profile: UserProfile,
    gateway: GitHubGateway,
    *,
    settings: Settings,
    chat_model,
    trace_store: TraceStore | None,
    rubric: RubricConfig | None,
) -> EntityReport:
    assert link.repo is not None and link.number is not None
    owner, repo_name, number = link.owner, link.repo, link.number

    context: IssueContext | PRContext
    issue: Issue | None = None
    if link.kind == "pull":
        pull = gateway.fetch_pull(owner, repo_name, number)
        context = review_pull(pull, chat_model=chat_model, settings=settings, trace_store=trace_store)
        report = _report_for_pull(link, pull, context)
        labels = pull.labels
    else:
        issue = gateway.fetch_issue(owner, repo_name, number)
        if issue.is_pull:
            pull = gateway.fetch_pull(owner, repo_name, number)
            context = review_pull(pull, chat_model=chat_model, settings=settings, trace_store=trace_store)
            report = _report_for_pull(link, pull, context)
            labels = pull.labels
        else:
            issue_context = investigate_issue(
                issue, chat_model=chat_model, settings=settings, trace_store=trace_store
            )
            context = issue_context
            report = _report_for_issue(link, issue, issue_context)
            labels = issue.labels
            _attach_issue_evidence(
                report, issue_context, owner, repo_name,
                gateway=gateway, settings=settings, chat_model=chat_model, trace_store=trace_store,
            )

    repo = gateway.fetch_repo(owner, repo_name)
    rubric = rubric or RubricConfig.load(default_rubric_path())
    complexity = score(context.analysis.dimension_scores, rubric)
    fit = score_fit(
        difficulty=complexity.difficulty,
        labels=labels,
        languages=repo.languages,
        topics=repo.topics,
        profile=profile,
    )
    object.__setattr__(report, "complexity", complexity)
    object.__setattr__(report, "fit", fit)
    return report


def _attach_issue_evidence(
    report: EntityReport,
    context: IssueContext,
    owner: str,
    repo_name: str,
    *,
    gateway: GitHubGateway,
    settings: Settings,
    chat_model,
    trace_store: TraceStore | None,
) -> None:
    """Enrich an issue report with repo paths + related history.

    Skipped cheaply when there is nothing to enrich with (empty tree or
    no references) so tests and tiny repos stay fast.
    """
    repo = gateway.fetch_repo(owner, repo_name)
    branch = repo.default_branch or "main"
    tree = gateway.list_repo_tree(owner, repo_name, branch)
    if tree:
        evidence = investigate_repo(
            context.analysis.summary, tree,
            chat_model=chat_model, settings=settings, trace_store=trace_store,
        )
        object.__setattr__(
            report, "repo_evidence",
            [f"{item.path} — {item.reason}" for item in evidence.ranked_paths],
        )

    numbers = context.referenced_numbers[:MAX_HISTORY_ITEMS]
    if numbers:
        related: list[RelatedItem] = []
        for number in numbers:
            try:
                item = gateway.fetch_issue(owner, repo_name, number)
            except GitHubNotFoundError:
                continue
            related.append(
                RelatedItem(number=item.number, title=item.title, state=item.state, labels=item.labels)
            )
        if related:
            history = investigate_history(
                context.analysis.summary, related,
                chat_model=chat_model, settings=settings, trace_store=trace_store,
            )
            object.__setattr__(
                report, "related_history",
                [f"#{note.number} — {note.relevance}" for note in history.notes],
            )


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


def _quick_pick(repo: RepoInfo, issue: Issue, profile: UserProfile) -> QuickPick:
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


def _report_for_issue(link: ResolvedLink, issue: Issue, context: IssueContext) -> EntityReport:
    analysis = context.analysis
    return EntityReport(
        link=link,
        title=f"#{issue.number} {issue.title}",
        url=issue.html_url,
        summary=analysis.summary,
        bullets_title="Stated requirements",
        bullets=list(analysis.stated_requirements),
        checklist_title="Likely relevant paths",
        checklist=list(analysis.likely_relevant_paths),
        notes_title="Ambiguities",
        notes=list(analysis.ambiguities),
        reasoning=analysis.reasoning,
        referenced_numbers=list(context.referenced_numbers),
    )


def _report_for_pull(link: ResolvedLink, pull: PullRequest, context: PRContext) -> EntityReport:
    analysis = context.analysis
    return EntityReport(
        link=link,
        title=f"#{pull.number} {pull.title}",
        url=pull.html_url,
        summary=analysis.summary,
        bullets_title="What changed",
        bullets=list(analysis.what_changed),
        checklist_title="Review checklist",
        checklist=list(analysis.review_checklist),
        notes_title="Risks",
        notes=list(analysis.risks),
        reasoning=analysis.reasoning,
    )
