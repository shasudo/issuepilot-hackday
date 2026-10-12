from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from issuepilot.config import Settings
from issuepilot.fit import score_fit
from issuepilot.gateway import GitHubGateway
from issuepilot.github.client import GitHubNotFoundError
from issuepilot.github.models import Issue, PullRequest, RepoInfo
from issuepilot.github.resolver import ResolvedLink
from issuepilot.graph.nodes.history_investigation import investigate_history
from issuepilot.graph.nodes.issue_investigation import investigate_issue
from issuepilot.graph.nodes.pr_review import review_pull
from issuepilot.graph.nodes.repo_investigation import investigate_repo
from issuepilot.models.issue_context import IssueContext
from issuepilot.models.pr_context import PRContext
from issuepilot.models.repo_context import RelatedItem
from issuepilot.observability.trace_store import TraceStore
from issuepilot.profile import UserProfile
from issuepilot.reports import EntityReport
from issuepilot.rubric.scoring import RubricConfig, default_rubric_path, score

MAX_HISTORY_ITEMS = 5


class AnalysisState(TypedDict, total=False):
    link: ResolvedLink
    profile: UserProfile
    issue: Issue | None
    pull: PullRequest | None
    repo: RepoInfo | None
    context: IssueContext | PRContext | None
    repo_evidence: list[str]
    related_history: list[str]
    report: EntityReport


def build_analysis_graph(
    gateway: GitHubGateway,
    settings: Settings,
    profile: UserProfile,
    *,
    chat_model=None,
    trace_store: TraceStore | None = None,
    rubric: RubricConfig | None = None,
):
    """Compile the single-entity pipeline: fetch → investigate → evidence → finalize.

    Dependencies close over the builder arguments; the state carries only
    data. Node functions are shared with direct callers, so the graph is
    the single orchestration path, not a second implementation.
    """
    active_rubric = rubric or RubricConfig.load(default_rubric_path())

    def fetch_node(state: AnalysisState) -> dict:
        link = state["link"]
        assert link.repo is not None and link.number is not None
        owner, repo_name, number = link.owner, link.repo, link.number
        update: dict = {"repo": gateway.fetch_repo(owner, repo_name)}
        if link.kind == "pull":
            update["pull"] = gateway.fetch_pull(owner, repo_name, number)
            update["issue"] = None
        else:
            issue = gateway.fetch_issue(owner, repo_name, number)
            if issue.is_pull:
                update["issue"] = None
                update["pull"] = gateway.fetch_pull(owner, repo_name, number)
            else:
                update["issue"] = issue
                update["pull"] = None
        return update

    def investigate_node(state: AnalysisState) -> dict:
        if state.get("pull") is not None:
            pull = state["pull"]
            assert pull is not None
            return {
                "context": review_pull(
                    pull, chat_model=chat_model, settings=settings, trace_store=trace_store
                )
            }
        issue = state["issue"]
        assert issue is not None
        return {
            "context": investigate_issue(
                issue, chat_model=chat_model, settings=settings, trace_store=trace_store
            )
        }

    def evidence_node(state: AnalysisState) -> dict:
        # PRs already carry their diff as evidence; only issues get enrichment.
        if state.get("pull") is not None or state.get("issue") is None:
            return {}
        link = state["link"]
        context = state["context"]
        assert link.repo is not None and isinstance(context, IssueContext)
        repo = state["repo"]
        assert repo is not None
        update: dict = {}

        tree = gateway.list_repo_tree(link.owner, link.repo, repo.default_branch or "main")
        if tree:
            evidence = investigate_repo(
                context.analysis.summary, tree,
                chat_model=chat_model, settings=settings, trace_store=trace_store,
            )
            update["repo_evidence"] = [
                f"{item.path} — {item.reason}" for item in evidence.ranked_paths
            ]

        related: list[RelatedItem] = []
        for number in context.referenced_numbers[:MAX_HISTORY_ITEMS]:
            try:
                item = gateway.fetch_issue(link.owner, link.repo, number)
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
            update["related_history"] = [
                f"#{note.number} — {note.relevance}" for note in history.notes
            ]
        return update

    def finalize_node(state: AnalysisState) -> dict:
        link = state["link"]
        context = state["context"]
        repo = state["repo"]
        assert context is not None and repo is not None
        if isinstance(context, IssueContext):
            issue = state["issue"]
            assert issue is not None
            report = _report_for_issue(link, issue, context, state)
            labels = issue.labels
        else:
            pull = state["pull"]
            assert pull is not None
            report = _report_for_pull(link, pull, context)
            labels = pull.labels
        complexity = score(context.analysis.dimension_scores, active_rubric)
        fit = score_fit(
            difficulty=complexity.difficulty,
            labels=labels,
            languages=repo.languages,
            topics=repo.topics,
            profile=state["profile"],
        )
        object.__setattr__(report, "complexity", complexity)
        object.__setattr__(report, "fit", fit)
        return {"report": report}

    builder = StateGraph(AnalysisState)
    builder.add_node("fetch", fetch_node)
    builder.add_node("investigate", investigate_node)
    builder.add_node("evidence", evidence_node)
    builder.add_node("finalize", finalize_node)
    builder.add_edge(START, "fetch")
    builder.add_edge("fetch", "investigate")
    builder.add_edge("investigate", "evidence")
    builder.add_edge("evidence", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile()


def _report_for_issue(
    link: ResolvedLink, issue: Issue, context: IssueContext, state: AnalysisState
) -> EntityReport:
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
        repo_evidence=list(state.get("repo_evidence", [])),
        related_history=list(state.get("related_history", [])),
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
