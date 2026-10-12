from pathlib import Path

import typer
from rich.console import Console

from issuepilot.service import EntityReport

app = typer.Typer(
    name="issuepilot",
    help="Universal GitHub contribution assistant.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Print the installed IssuePilot version."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as dist_version

    try:
        print(dist_version("issuepilot-hackday"))
    except PackageNotFoundError:
        print("0.0.0-dev")


@app.command()
def analyze(
    link: str = typer.Argument(..., help="GitHub issue/PR link, or shorthand like owner/repo#123"),
    profile: Path | None = typer.Option(None, "--profile", help="Path to a profile YAML file"),
    stack: str = typer.Option("", "--stack", help="Comma-separated tech stack (overrides profile)"),
    level: str | None = typer.Option(None, "--level", help="beginner, intermediate, or advanced"),
    interests: str = typer.Option("", "--interests", help="Comma-separated interests"),
) -> None:
    """Analyze one issue or PR and print its personalized triage card."""
    from pydantic import ValidationError
    from rich.panel import Panel

    from issuepilot.config import get_settings
    from issuepilot.github.client import GitHubAPIError, GitHubClient
    from issuepilot.github.resolver import UnsupportedLinkError
    from issuepilot.observability.trace_store import TraceStore
    from issuepilot.profile import load_profile
    from issuepilot.service import analyze_link

    try:
        settings = get_settings()
    except ValidationError:
        console.print(
            "[red]error:[/red] missing config — copy .env.example to .env and "
            "fill in GITHUB_TOKEN plus your model key."
        )
        raise typer.Exit(1)

    prof = load_profile(profile)
    if stack.strip():
        prof.tech_stack = [item.strip() for item in stack.split(",") if item.strip()]
    if interests.strip():
        prof.interests = [item.strip() for item in interests.split(",") if item.strip()]
    if level is not None:
        if level not in ("beginner", "intermediate", "advanced"):
            console.print(f"[red]error:[/red] --level must be beginner, intermediate, or advanced.")
            raise typer.Exit(1)
        prof.level = level  # type: ignore[assignment]

    try:
        with GitHubClient(settings) as client:
            trace_store = TraceStore(settings.trace_db_path)
            try:
                report = analyze_link(
                    link, prof, settings=settings, gateway=client, trace_store=trace_store
                )
            finally:
                trace_store.close()
    except (GitHubAPIError, UnsupportedLinkError, ValueError) as exc:
        console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(1)

    _render_report(report)


def _render_report(report: EntityReport) -> None:
    from rich.panel import Panel

    assert report.complexity is not None and report.fit is not None
    console.print(Panel(f"[bold]{report.title}[/bold]\n{report.url}", title="Triage card"))
    console.print(f"[bold]Summary:[/bold] {report.summary}\n")
    console.print(
        f"[bold]Difficulty:[/bold] {report.complexity.difficulty} "
        f"({report.complexity.overall_score})   "
        f"[bold]Fit:[/bold] {report.fit.score}/100 — {report.fit.verdict}"
    )
    for reason in report.fit.reasons:
        console.print(f"  • {reason}")
    for heading, items in (
        (report.bullets_title, report.bullets),
        (report.checklist_title, report.checklist),
        (report.notes_title, report.notes),
    ):
        if items:
            console.print(f"\n[bold]{heading}:[/bold]")
            for item in items:
                console.print(f"  • {item}")
    if report.referenced_numbers:
        refs = ", ".join(f"#{n}" for n in report.referenced_numbers)
        console.print(f"\n[bold]Referenced:[/bold] {refs}")
    console.print(f"\n[dim]{report.reasoning}[/dim]")


if __name__ == "__main__":
    app()
