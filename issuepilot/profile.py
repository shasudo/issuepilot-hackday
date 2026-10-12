from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "advanced"]


class UserProfile(BaseModel):
    """Who the recommendations are for.

    Everything is optional: an empty profile yields impersonal,
    difficulty-only ranking instead of personalized fit.
    """

    display_name: str = "you"
    tech_stack: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    level: Level = "intermediate"
    interests: list[str] = Field(default_factory=list)
    hours_per_week: int | None = None


def load_profile(path: str | Path | None) -> UserProfile:
    """Load a profile from YAML; missing/None path yields the default profile."""
    if path is None:
        return UserProfile()
    file_path = Path(path)
    if not file_path.exists():
        return UserProfile()
    raw = yaml.safe_load(file_path.read_text()) or {}
    return UserProfile(**raw)
