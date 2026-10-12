from __future__ import annotations

from dataclasses import dataclass, field

from issuepilot.profile import UserProfile
from issuepilot.rubric.scoring import Difficulty

# Difficulty fit by level: positive rewards, negative penalizes.
_LEVEL_DIFFICULTY_SCORE: dict[tuple[str, str], int] = {
    ("beginner", "Easy"): 30,
    ("beginner", "Medium"): 5,
    ("beginner", "Difficult"): -25,
    ("intermediate", "Easy"): 15,
    ("intermediate", "Medium"): 25,
    ("intermediate", "Difficult"): -5,
    ("advanced", "Easy"): 10,
    ("advanced", "Medium"): 20,
    ("advanced", "Difficult"): 30,
}


@dataclass(frozen=True)
class FitResult:
    score: int  # 0-100, deterministic from the rules below
    verdict: str  # great fit / good fit / stretch / poor fit
    reasons: list[str] = field(default_factory=list)


def score_fit(
    *,
    difficulty: Difficulty,
    labels: list[str],
    languages: list[str],
    topics: list[str],
    profile: UserProfile,
) -> FitResult:
    """Score how well an entity fits a profile. Pure function, no LLM.

    Rules (transparent by design — every point has a stated reason):
    base 40 + level/difficulty match + stack overlap + interest overlap.
    """
    points = 40
    reasons: list[str] = []

    level_points = _LEVEL_DIFFICULTY_SCORE[(profile.level, difficulty)]
    points += level_points
    if level_points >= 20:
        reasons.append(f"{difficulty} work matches your {profile.level} level")
    elif level_points >= 0:
        reasons.append(f"{difficulty} work is approachable at {profile.level} level")
    else:
        reasons.append(f"{difficulty} work is a stretch for {profile.level} level")

    known = {item.lower() for item in [*profile.languages, *profile.tech_stack]}
    overlap = sorted({lang for lang in languages if lang.lower() in known})
    if overlap:
        bonus = min(10 * len(overlap), 20)
        points += bonus
        reasons.append(f"Uses {', '.join(overlap)} from your stack")
    elif known:
        points -= 10
        reasons.append("None of your stack languages detected")

    interests = [i.lower() for i in profile.interests]
    haystack = [t.lower() for t in [*labels, *topics]]
    hits = sorted({i for i in interests if any(i in h or h in i for h in haystack)})
    if hits:
        points += min(5 * len(hits), 15)
        reasons.append(f"Matches your interest in {', '.join(hits)}")

    final = max(5, min(98, points))
    if final >= 75:
        verdict = "great fit"
    elif final >= 55:
        verdict = "good fit"
    elif final >= 35:
        verdict = "stretch"
    else:
        verdict = "poor fit"
    return FitResult(score=final, verdict=verdict, reasons=reasons)
