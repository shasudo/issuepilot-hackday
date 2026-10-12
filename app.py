"""IssuePilot web UI: paste a GitHub link, get a personalized triage card."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from issuepilot.config import get_settings
from issuepilot.fit import FitResult
from issuepilot.github.client import GitHubAPIError, GitHubClient
from issuepilot.github.resolver import UnsupportedLinkError, resolve
from issuepilot.observability.trace_store import TraceStore
from issuepilot.profile import UserProfile, load_profile
from issuepilot.rubric.scoring import ComplexityResult
from issuepilot.service import EntityReport, analyze_link

st.set_page_config(page_title="IssuePilot", layout="wide")

SEED_ISSUE = "https://github.com/psf/requests/issues/7634"
SEED_PR = "https://github.com/psf/requests/pull/7586"
SEED_BACKUP = "https://github.com/pytest-dev/pytest/issues/15124"

DIFFICULTY_COLORS = {"Easy": "#34D399", "Medium": "#F59E0B", "Difficult": "#F87171"}
PROFILES_DIR = Path(__file__).parent / "profiles"


def _profile_from_sidebar() -> UserProfile:
    st.sidebar.header("Your profile")
    preset = st.sidebar.selectbox(
        "Preset", ["Beginner Python", "Advanced Web", "Custom"], key="preset"
    )
    if preset != "Custom":
        filename = "beginner-python.yaml" if preset == "Beginner Python" else "advanced-web.yaml"
        base = load_profile(PROFILES_DIR / filename)
    else:
        base = UserProfile()
    level = st.sidebar.selectbox(
        "Level", ["beginner", "intermediate", "advanced"], index=["beginner", "intermediate", "advanced"].index(base.level)
    )
    stack = st.sidebar.text_input("Tech stack (comma-separated)", ", ".join(base.tech_stack))
    languages = st.sidebar.text_input("Languages", ", ".join(base.languages))
    interests = st.sidebar.text_input("Interests", ", ".join(base.interests))
    return UserProfile(
        display_name=base.display_name,
        tech_stack=[s.strip() for s in stack.split(",") if s.strip()],
        languages=[s.strip() for s in languages.split(",") if s.strip()],
        level=level,  # type: ignore[arg-type]
        interests=[s.strip() for s in interests.split(",") if s.strip()],
        hours_per_week=base.hours_per_week,
    )


@st.cache_data(show_spinner=False)
def _cached_analyze(link: str, profile_json: str) -> EntityReport:
    settings = get_settings()
    profile = UserProfile.model_validate_json(profile_json)
    with GitHubClient(settings) as gateway:
        trace_store = TraceStore(settings.trace_db_path)
        try:
            return analyze_link(
                link, profile, settings=settings, gateway=gateway, trace_store=trace_store
            )
        finally:
            trace_store.close()


def _pill(label: str, value: str, color: str) -> str:
    return (
        f'<span style="background:#1C2530;border-radius:6px;padding:6px 12px;'
        f'font-size:15px;font-weight:600;">{label}: '
        f'<span style="color:{color};">{value}</span></span>'
    )


def _render_report(report: EntityReport) -> None:
    assert report.complexity is not None and report.fit is not None
    complexity: ComplexityResult = report.complexity
    fit: FitResult = report.fit

    st.markdown(f"### [{report.title}]({report.url})")
    st.write(report.summary)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            _pill(
                "Difficulty",
                f"{complexity.difficulty} · {complexity.overall_score}",
                DIFFICULTY_COLORS[complexity.difficulty],
            ),
            unsafe_allow_html=True,
        )
    with col_b:
        st.markdown(
            _pill("Fit", f"{fit.score}/100 · {fit.verdict}", "#F59E0B"),
            unsafe_allow_html=True,
        )
    st.progress(min(max(fit.score, 0), 100))

    with st.expander("Why this fits you", expanded=True):
        for reason in fit.reasons:
            st.write(f"- {reason}")
    for heading, items in (
        (report.bullets_title, report.bullets),
        (report.checklist_title, report.checklist),
        (report.notes_title, report.notes),
    ):
        if items:
            with st.expander(heading):
                for item in items:
                    st.write(f"- {item}")
    if report.referenced_numbers:
        refs = ", ".join(f"#{n}" for n in report.referenced_numbers)
        st.caption(f"Referenced: {refs}")
    st.caption(report.reasoning)


def main() -> None:
    profile = _profile_from_sidebar()
    if st.sidebar.button("Clear result cache"):
        st.cache_data.clear()

    st.title("IssuePilot")
    st.caption("Paste any GitHub issue or PR link. Get a triage card tuned to your profile.")

    if "link" not in st.session_state:
        st.session_state.link = ""
    link = st.text_input("GitHub link", key="link", placeholder="https://github.com/owner/repo/issues/123")

    seed_col_a, seed_col_b, go_col = st.columns([1, 1, 2])
    with seed_col_a:
        if st.button("Seeded issue"):
            st.session_state.link = SEED_ISSUE
            st.session_state.run = True
            st.rerun()
    with seed_col_b:
        if st.button("Seeded PR"):
            st.session_state.link = SEED_PR
            st.session_state.run = True
            st.rerun()
    with go_col:
        go = st.button("Analyze", type="primary")

    if not (go or st.session_state.pop("run", False)):
        st.info("Enter a link above, or start with a seeded example.")
        return
    if not link.strip():
        st.warning("Paste a link first.")
        return

    try:
        settings = get_settings()
    except ValidationError:
        st.error("Missing config — copy .env.example to .env and set GITHUB_TOKEN plus your model key.")
        return

    try:
        with st.status("Analyzing…", expanded=True) as status:
            st.write("Resolving link…")
            with GitHubClient(settings) as probe:
                resolved = resolve(link.strip(), probe)
            st.write(f"Found {resolved.kind}: {resolved.label}")
            st.write("Fetching from GitHub and running analysis…")
            report = _cached_analyze(link.strip(), profile.model_dump_json())
            status.update(label="Done", state="complete")
    except UnsupportedLinkError as exc:
        st.error(str(exc))
        return
    except GitHubAPIError as exc:
        st.error(f"{exc} — check the link visibility and your GITHUB_TOKEN.")
        return
    except ValueError as exc:
        st.info(str(exc))
        return
    except Exception as exc:  # model/API failures stay readable, never a traceback wall
        st.error(f"Analysis failed: {exc}")
        return

    _render_report(report)
    st.caption(f"Backup demo link: {SEED_BACKUP}")


if __name__ == "__main__":
    main()
