from datetime import datetime

from issuepilot.fit import FitResult
from issuepilot.github.models import RepoInfo
from issuepilot.github.resolver import ResolvedLink
from issuepilot.report.markdown import report_to_markdown
from issuepilot.reports import EntityReport, QuickPick, RepoReport
from issuepilot.rubric.scoring import ComplexityResult, DimensionScores


def easy_complexity() -> ComplexityResult:
    scores = DimensionScores(
        code_complexity=1,
        components_affected=1,
        required_technical_knowledge=2,
        testing_complexity=1,
        dependencies=1,
        requirement_ambiguity=1,
    )
    return ComplexityResult(scores=scores, overall_score=1.17, difficulty="Easy")


def test_entity_markdown() -> None:
    report = EntityReport(
        link=ResolvedLink("issue", "o", "r", 1),
        title="#1 Typo",
        url="https://github.com/o/r/issues/1",
        summary="Fix it",
        bullets_title="Stated requirements",
        bullets=["fix typo"],
        checklist_title="Likely relevant paths",
        checklist=["README.md"],
        reasoning="trivial",
        complexity=easy_complexity(),
        fit=FitResult(score=80, verdict="great fit", reasons=["Matches your level"]),
    )
    text = report_to_markdown(report)
    assert "#1 Typo" in text
    assert "80/100" in text
    assert "README.md" in text


def test_repo_markdown() -> None:
    repo = RepoInfo(owner="o", name="r", full_name="o/r", stars=3, updated_at=datetime(2026, 1, 1))
    report = RepoReport(
        link=ResolvedLink("repo", "o", "r", None),
        repo=repo,
        picks=[
            QuickPick(
                repo="o/r",
                number=1,
                title="Typo",
                url="https://github.com/o/r/issues/1",
                labels=["docs"],
                difficulty="Easy",
                fit=FitResult(score=80, verdict="great fit", reasons=[]),
            )
        ],
        scanned=1,
    )
    text = report_to_markdown(report)
    assert "o/r" in text
    assert "Scanned 1 open issues" in text
