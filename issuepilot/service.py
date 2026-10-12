from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from issuepilot.config import Settings, get_settings
from issuepilot.fit import FitResult, score_fit
from issuepilot.github.client import GitHubClient
from issuepilot.github.models import Issue, PullRequest, RepoInfo
from issuepilot.github.resolver import ResolvedLink, resolve
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.graph.nodes.pr_review import review_pull
from issuepilot.models.issue_context import IssueContext
from issuepilot.models.pr_context import PRContext
from issuepilot.observability.trace_store import TraceStore
from issuepilot.profile import UserProfile
from issuepilot.rubric.scoring import (
    ComplexityResult,
    RubricConfig,
    default_rubric_path,
    score,
)


class GitHubGateway(Protocol):
    """The GitHub surface analysis needs — GitHubClient satisfies this."""

    def fetch_account_type(self, name: str) -> str: ...
    def fetch_issue(self, owner: str, repo: str, number: int) -> Issue: ...
    def fetch_pull(self, owner: str, repo: str, number: int) -> PullRequest: ...
    def fetch_repo(self, owner: str, repo: str) -> RepoInfo: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class EntityReport:
    """One analyzed entity, shaped for display (CLI card and UI card share it)."""

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
    complexity: ComplexityResult | None = None
    fit: FitResult | None = None


def analyze_link(
    text: str,
    profile: UserProfile,
    *,
    settings: Settings | None = None,
    gateway: GitHubGateway | None = None,
    chat_model=None,
    trace_store: TraceStore | None = None,
    rubric: RubricConfig | None = None,
) -> EntityReport:
    """Resolve any supported link and build its personalized report.

    M2 handles issues and PRs (issue URLs that are really PRs upgrade
    automatically); repo/org breadth lands in M3.
    """
    settings = settings or get_settings()
    owns_gateway = gateway is None
    gateway = gateway or GitHubClient(settings)
    try:
        link = resolve(text, gateway)
        if link.kind in ("repo", "org"):
            raise ValueError(
                f"{link.kind} analysis lands in M3 — paste an issue or PR link for now."
            )
        assert link.repo is not None and link.number is not None

        if link.kind == "pull":
            pull = gateway.fetch_pull(link.owner, link.repo, link.number)
            context: IssueContext | PRContext = review_pull(
                pull, chat_model=chat_model, settings=settings, trace_store=trace_store
            )
            report = _report_for_pull(link, pull, context)
            labels = pull.labels
        else:
            issue = gateway.fetch_issue(link.owner, link.repo, link.number)
            if issue.is_pull:
                pull = gateway.fetch_pull(link.owner, link.repo, link.number)
                context = review_pull(
                    pull, chat_model=chat_model, settings=settings, trace_store=trace_store
                )
                report = _report_for_pull(link, pull, context)
                labels = pull.labels
            else:
                context = investigate_issue(
                    issue, chat_model=chat_model, settings=settings, trace_store=trace_store
                )
                report = _report_for_issue(link, issue, context)
                labels = issue.labels

        repo = gateway.fetch_repo(link.owner, link.repo)
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
    finally:
        if owns_gateway:
            gateway.close()


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
