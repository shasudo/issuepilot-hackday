from issuepilot.profile import UserProfile, load_profile


def test_default_profile() -> None:
    profile = load_profile(None)
    assert profile.level == "intermediate"
    assert profile.tech_stack == []
    assert profile.languages == []


def test_missing_file_yields_default() -> None:
    assert load_profile("/nonexistent/profile.yaml") == UserProfile()


def test_yaml_profile_parses(tmp_path) -> None:
    file_path = tmp_path / "profile.yaml"
    file_path.write_text(
        "display_name: Ada\n"
        "tech_stack: [python, react]\n"
        "languages: [python]\n"
        "level: beginner\n"
        "interests: [docs]\n"
        "hours_per_week: 4\n"
    )
    profile = load_profile(file_path)
    assert profile.display_name == "Ada"
    assert profile.tech_stack == ["python", "react"]
    assert profile.level == "beginner"
    assert profile.hours_per_week == 4
