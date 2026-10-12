from __future__ import annotations

from pydantic import BaseModel, Field

from issuepilot.rubric.scoring import DimensionScores


class PRReviewAnalysis(BaseModel):
    """Structured output of the PR Review Agent."""

    summary: str = Field(description="Concise 1-3 sentence restatement of the change")
    what_changed: list[str] = Field(
        default_factory=list, description="Concrete behavior/code changes"
    )
    review_checklist: list[str] = Field(
        default_factory=list, description="Specific things a reviewer should verify"
    )
    risks: list[str] = Field(
        default_factory=list, description="Risky, missing, or questionable points"
    )
    reasoning: str = Field(description="Brief rationale for the analysis")
    dimension_scores: DimensionScores = Field(description="1-5 complexity estimates per dimension")


class PRContext(BaseModel):
    """Full node output for a pull request."""

    analysis: PRReviewAnalysis
