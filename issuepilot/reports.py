from __future__ import annotations

from dataclasses import dataclass, field

from issuepilot.fit import FitResult
from issuepilot.github.models import OrgInfo, RepoInfo
from issuepilot.github.resolver import ResolvedLink
from issuepilot.rubric.scoring import ComplexityResult, Difficulty


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
