from __future__ import annotations

from pydantic import BaseModel, Field


class RankedPath(BaseModel):
    path: str
    reason: str


class RepoEvidence(BaseModel):
    """Structured output of the Repository Investigation Agent."""

    ranked_paths: list[RankedPath] = Field(default_factory=list)
    reasoning: str = ""


class RelatedItem(BaseModel):
    """A referenced issue/PR, fetched deterministically (no LLM)."""

    number: int
    title: str
    state: str
    labels: list[str] = Field(default_factory=list)


class HistoryNote(BaseModel):
    number: int
    relevance: str


class HistoryEvidence(BaseModel):
    """Structured output of the History Investigation Agent."""

    notes: list[HistoryNote] = Field(default_factory=list)
