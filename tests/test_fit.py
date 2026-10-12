from issuepilot.fit import quick_difficulty, score_fit
from issuepilot.profile import UserProfile


def beginner() -> UserProfile:
    return UserProfile(
        display_name="Ada",
        tech_stack=["python"],
        languages=["python"],
        level="beginner",
        interests=["docs"],
    )


def advanced() -> UserProfile:
    return UserProfile(
        display_name="Gus",
        tech_stack=["react", "typescript"],
        languages=["typescript"],
        level="advanced",
        interests=["performance"],
    )


def test_matching_stack_and_level_scores_high() -> None:
    result = score_fit(
        difficulty="Easy",
        labels=["good first issue", "docs"],
        languages=["Python"],
        topics=[],
        profile=beginner(),
    )
    assert result.score >= 75
    assert result.verdict == "great fit"
    assert any("python" in reason.lower() for reason in result.reasons)


def test_hard_work_penalized_for_beginners() -> None:
    result = score_fit(
        difficulty="Difficult", labels=[], languages=["Rust"], topics=[], profile=beginner()
    )
    assert result.score < 40
    assert any("stretch" in reason for reason in result.reasons)


def test_same_entity_ranks_differently_per_profile() -> None:
    kwargs = {"difficulty": "Medium", "labels": ["performance"], "languages": ["TypeScript"], "topics": []}
    assert score_fit(**kwargs, profile=advanced()).score > score_fit(
        **kwargs, profile=beginner()
    ).score


def test_empty_profile_stays_neutral() -> None:
    result = score_fit(
        difficulty="Medium", labels=[], languages=["Go"], topics=[], profile=UserProfile()
    )
    assert 35 <= result.score <= 75
    assert result.reasons


def test_quick_difficulty_from_labels() -> None:
    assert quick_difficulty(["good first issue"]) == "Easy"
    assert quick_difficulty(["security"]) == "Difficult"
    assert quick_difficulty(["bug"]) == "Medium"
    assert quick_difficulty([]) == "Medium"
