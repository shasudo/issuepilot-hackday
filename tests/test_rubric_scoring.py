import pytest

from issuepilot.rubric.scoring import (
    DIMENSIONS,
    DimensionScores,
    RubricConfig,
    default_rubric_path,
    score,
)


def uniform(value: int) -> DimensionScores:
    return DimensionScores(**{dim: value for dim in DIMENSIONS})


def test_uniform_scores_map_to_labels() -> None:
    rubric = RubricConfig.load(default_rubric_path())
    assert score(uniform(1), rubric).difficulty == "Easy"
    assert score(uniform(3), rubric).difficulty == "Medium"
    assert score(uniform(5), rubric).difficulty == "Difficult"


def test_weights_normalize() -> None:
    rubric = RubricConfig(
        weights={dim: 2.0 for dim in DIMENSIONS}, easy_max=2.0, medium_max=3.5
    )
    result = score(uniform(2), rubric)
    assert result.overall_score == 2.0
    assert result.difficulty == "Easy"


def test_out_of_range_rejected() -> None:
    values = {dim: 1 for dim in DIMENSIONS}
    values["code_complexity"] = 9
    with pytest.raises(ValueError):
        DimensionScores(**values)


def test_missing_dimension_rejected(tmp_path) -> None:
    bad = tmp_path / "rubric.yaml"
    bad.write_text("dimensions:\n  code_complexity:\n    weight: 1.0\nthresholds:\n  easy_max: 2\n  medium_max: 3\n")
    with pytest.raises(ValueError, match="missing dimension"):
        RubricConfig.load(bad)
