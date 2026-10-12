from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parent.parent / "issue-triage"


def read_frontmatter() -> dict:
    text = (SKILL_DIR / "SKILL.md").read_text()
    assert text.startswith("---\n")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_skill_frontmatter_valid() -> None:
    frontmatter = read_frontmatter()
    assert frontmatter["name"] == "issue-triage" == SKILL_DIR.name
    assert 1 <= len(frontmatter["description"]) <= 1024
    assert frontmatter["license"] == "MIT"


def test_skill_scripts_present() -> None:
    assert (SKILL_DIR / "scripts" / "analyze.sh").exists()
    assert (SKILL_DIR / "references" / "profile-format.md").exists()
