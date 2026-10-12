from __future__ import annotations

from pydantic import BaseModel, Field

from issuepilot.rubric.scoring import DimensionScores


class IssueContextAnalysis(BaseModel):
    """Structured output of the Issue Investigation Agent.

    Bound via with_structured_output — never parsed from free text.
    """

    summary: str = Field(description="Concise 1-3 sentence restatement of the ask")
    stated_requirements: list[str] = Field(
        default_factory=list, description="Explicit requirements from the text"
    )
    likely_relevant_paths: list[str] = Field(
        default_factory=list, description="Paths/modules/symbols explicitly mentioned"
    )
    ambiguities: list[str] = Field(
        default_factory=list, description="Underspecified points needing clarification"
    )
    reasoning: str = Field(description="Brief rationale for the analysis")
    dimension_scores: DimensionScores = Field(description="1-5 complexity estimates per dimension")


class IssueContext(BaseModel):
    """Full node output: qualitative analysis plus deterministic references."""

    analysis: IssueContextAnalysis
    referenced_numbers: list[int] = Field(
        default_factory=list,
        description="#N references extracted from the text by regex, not the model",
    )
