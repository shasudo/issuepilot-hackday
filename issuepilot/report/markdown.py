from __future__ import annotations

from issuepilot.reports import EntityReport, OrgReport, QuickPick, RepoReport


def report_to_markdown(report: EntityReport | RepoReport | OrgReport) -> str:
    """Render any report as a shareable markdown document. Pure function."""
    if isinstance(report, RepoReport):
        return _repo_markdown(report)
    if isinstance(report, OrgReport):
        return _org_markdown(report)
    return _entity_markdown(report)


def _entity_markdown(report: EntityReport) -> str:
    assert report.complexity is not None and report.fit is not None
    lines = [
        f"# {report.title}",
        "",
        f"Link: {report.url}",
        "",
        report.summary,
        "",
        f"- Difficulty: **{report.complexity.difficulty}** ({report.complexity.overall_score})",
        f"- Fit: **{report.fit.score}/100 — {report.fit.verdict}**",
        *[f"  - {reason}" for reason in report.fit.reasons],
        "",
    ]
    for heading, items in (
        (report.bullets_title, report.bullets),
        (report.checklist_title, report.checklist),
        (report.notes_title, report.notes),
        ("Where to look", report.repo_evidence),
        ("Related history", report.related_history),
    ):
        if items:
            lines.append(f"## {heading}")
            lines.append("")
            lines.extend(f"- {item}" for item in items)
            lines.append("")
    if report.referenced_numbers:
        refs = ", ".join(f"#{n}" for n in report.referenced_numbers)
        lines.append(f"Referenced: {refs}")
        lines.append("")
    lines.append(f"*{report.reasoning}*")
    lines.append("")
    return "\n".join(lines)


def _pick_lines(pick: QuickPick) -> list[str]:
    return [
        f"### [{pick.repo}#{pick.number} {pick.title}]({pick.url})",
        "",
        f"- Difficulty: **{pick.difficulty}**",
        f"- Fit: **{pick.fit.score}/100 — {pick.fit.verdict}**",
        *[f"  - {reason}" for reason in pick.fit.reasons],
        "",
    ]


def _repo_markdown(report: RepoReport) -> str:
    repo = report.repo
    lines = [
        f"# {repo.full_name}",
        "",
        repo.description or "(no description)",
        "",
        f"Stars: {repo.stars} · Scanned {report.scanned} open issues",
        "",
    ]
    for pick in report.picks:
        lines.extend(_pick_lines(pick))
    return "\n".join(lines)


def _org_markdown(report: OrgReport) -> str:
    lines = [
        f"# {report.org.login}",
        "",
        report.org.description or "(no description)",
        "",
        f"Scanned {report.scanned_repos} repos",
        "",
    ]
    for pick in report.picks:
        lines.extend(_pick_lines(pick))
    return "\n".join(lines)
