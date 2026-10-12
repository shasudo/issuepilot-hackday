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
from issuepilot.report.markdown import report_to_markdown
from issuepilot.reports import EntityReport, OrgReport, RepoReport
from issuepilot.rubric.scoring import ComplexityResult
from issuepilot.service import analyze_link

st.set_page_config(page_title="IssuePilot", layout="wide")

SEED_ISSUE = "https://github.com/psf/requests/issues/7634"
SEED_PR = "https://github.com/psf/requests/pull/7586"
SEED_REPO = "https://github.com/psf/requests"
SEED_BACKUP = "https://github.com/pytest-dev/pytest/issues/15124"

DIFFICULTY_COLORS = {"Easy": "#34D399", "Medium": "#F59E0B", "Difficult": "#F87171"}
PROFILES_DIR = Path(__file__).parent / "profiles"
PRESETS = {
    "Beginner Python": PROFILES_DIR / "beginner-python.yaml",
    "Advanced Web": PROFILES_DIR / "advanced-web.yaml",
}


def _profile_from_sidebar() -> UserProfile:
    st.sidebar.header("Your profile")
    preset = st.sidebar.selectbox("Preset", ["Beginner Python", "Advanced Web", "Custom"])
    base = load_profile(PRESETS[preset]) if preset in PRESETS else UserProfile()
    levels = ["beginner", "intermediate", "advanced"]
    level = st.sidebar.selectbox("Level", levels, index=levels.index(base.level))
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


def _run_cached(link: str, profile: UserProfile) -> EntityReport | RepoReport | OrgReport:
    return _cached_analyze(link, profile.model_dump_json())


@st.cache_data(show_spinner=False)
def _cached_analyze(link: str, profile_json: str) -> EntityReport | RepoReport | OrgReport:
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


def _render_entity(report: EntityReport) -> None:
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
        st.markdown(_pill("Fit", f"{fit.score}/100 · {fit.verdict}", "#F59E0B"), unsafe_allow_html=True)
    st.progress(min(max(fit.score, 0), 100))

    with st.expander("Why this fits you", expanded=True):
        for reason in fit.reasons:
            st.write(f"- {reason}")
    for heading, items in (
        (report.bullets_title, report.bullets),
        (report.checklist_title, report.checklist),
        (report.notes_title, report.notes),
        ("Where to look", report.repo_evidence),
        ("Related history", report.related_history),
    ):
        if items:
            with st.expander(heading):
                for item in items:
                    st.write(f"- {item}")
    if report.referenced_numbers:
        refs = ", ".join(f"#{n}" for n in report.referenced_numbers)
        st.caption(f"Referenced: {refs}")
    st.caption(report.reasoning)


def _render_repo(report: RepoReport, picks_limit: int = 8) -> None:
    repo = report.repo
    st.markdown(f"### [{repo.full_name}]({repo.html_url})")
    if repo.description:
        st.write(repo.description)
    st.caption(
        f"Stars: {repo.stars} · Languages: {', '.join(repo.languages) or 'unknown'} · "
        f"Scanned {report.scanned} open issues"
    )
    if not report.picks:
        st.info("No open issues found.")
        return
    for pick in report.picks[:picks_limit]:
        st.markdown(f"**[#{pick.number} {pick.title}]({pick.url})**")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                _pill("Difficulty", pick.difficulty, DIFFICULTY_COLORS[pick.difficulty]),
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                _pill("Fit", f"{pick.fit.score} · {pick.fit.verdict}", "#F59E0B"),
                unsafe_allow_html=True,
            )


def _render_org(report: OrgReport) -> None:
    st.markdown(f"### [{report.org.login}]({report.org.html_url})")
    if report.org.description:
        st.write(report.org.description)
    st.caption(f"Scanned {report.scanned_repos} repos")
    for pick in report.picks:
        st.markdown(f"**[{pick.repo}#{pick.number} {pick.title}]({pick.url})**")
        st.caption(f"{pick.difficulty} · {pick.fit.score}/100 {pick.fit.verdict}")


def _analyze_tab(profile: UserProfile) -> None:
    st.caption("Paste any GitHub issue, PR, repo, or org link. Get a card tuned to your profile.")

    if "link" not in st.session_state:
        st.session_state.link = ""
    link = st.text_input(
        "GitHub link", key="link", placeholder="https://github.com/owner/repo/issues/123"
    )

    seed_col_a, seed_col_b, seed_col_c, go_col = st.columns([1, 1, 1, 2])
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
    with seed_col_c:
        if st.button("Seeded repo"):
            st.session_state.link = SEED_REPO
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
            report = _run_cached(link.strip(), profile)
            status.update(label="Done", state="complete")
    except UnsupportedLinkError as exc:
        st.error(str(exc))
        return
    except GitHubAPIError as exc:
        st.error(f"{exc} — check the link visibility and your GITHUB_TOKEN.")
        return
    except Exception as exc:  # model/API failures stay readable, never a traceback wall
        st.error(f"Analysis failed: {exc}")
        return

    if isinstance(report, RepoReport):
        _render_repo(report)
    elif isinstance(report, OrgReport):
        _render_org(report)
    else:
        _render_entity(report)
    st.session_state.last_report = report
    st.caption(f"Backup demo link: {SEED_BACKUP}")


def _compare_tab() -> None:
    st.caption("Same repo, two profiles — see how the top picks change.")
    repo_link = st.text_input("Repo link", value=SEED_REPO, key="compare_link")
    col_a, col_b = st.columns(2)
    with col_a:
        preset_a = st.selectbox("Profile A", list(PRESETS), index=0, key="preset_a")
    with col_b:
        preset_b = st.selectbox("Profile B", list(PRESETS), index=1, key="preset_b")

    if not st.button("Compare", type="primary"):
        return
    if not repo_link.strip():
        st.warning("Paste a repo link first.")
        return

    try:
        get_settings()
    except ValidationError:
        st.error("Missing config — copy .env.example to .env and set GITHUB_TOKEN.")
        return

    try:
        with st.spinner("Ranking for both profiles…"):
            profile_a = load_profile(PRESETS[preset_a])
            profile_b = load_profile(PRESETS[preset_b])
            report_a = _run_cached(repo_link.strip(), profile_a)
            report_b = _run_cached(repo_link.strip(), profile_b)
    except UnsupportedLinkError as exc:
        st.error(str(exc))
        return
    except GitHubAPIError as exc:
        st.error(f"{exc} — check the link visibility and your GITHUB_TOKEN.")
        return
    except Exception as exc:
        st.error(f"Compare failed: {exc}")
        return

    if not isinstance(report_a, RepoReport) or not isinstance(report_b, RepoReport):
        st.warning("Compare needs a repo link.")
        return
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader(profile_a.display_name)
        _render_repo(report_a, picks_limit=5)
    with col_b:
        st.subheader(profile_b.display_name)
        _render_repo(report_b, picks_limit=5)


def _boards_tab(profile: UserProfile) -> None:
    st.caption("Ranked opportunity boards across a repo or org — for your profile.")
    link = st.text_input("Repo or org link", value=SEED_REPO, key="board_link")
    if not st.button("Show board", type="primary"):
        return
    if not link.strip():
        st.warning("Paste a link first.")
        return

    try:
        get_settings()
    except ValidationError:
        st.error("Missing config — copy .env.example to .env and set GITHUB_TOKEN.")
        return

    try:
        with st.spinner("Building board…"):
            report = _run_cached(link.strip(), profile)
    except UnsupportedLinkError as exc:
        st.error(str(exc))
        return
    except GitHubAPIError as exc:
        st.error(f"{exc} — check the link visibility and your GITHUB_TOKEN.")
        return
    except Exception as exc:
        st.error(f"Board failed: {exc}")
        return

    if isinstance(report, RepoReport):
        _render_repo(report)
        picks = report.picks
    elif isinstance(report, OrgReport):
        _render_org(report)
        picks = report.picks
    else:
        st.warning("Boards need a repo or org link — this one opened as a single card.")
        _render_entity(report)
        return
    st.session_state.last_report = report

    st.divider()
    st.subheader("Drill down")
    st.caption("Pick one to open its full card in the Analyze tab.")
    for pick in picks:
        if st.button(f"Analyze {pick.repo}#{pick.number}", key=f"drill-{pick.repo}-{pick.number}"):
            st.session_state.link = pick.url
            st.session_state.run = True
            st.success("Loaded — switch to the Analyze tab.")


def _export_tab() -> None:
    st.caption("Download the latest analysis as markdown.")
    report = st.session_state.get("last_report")
    if report is None:
        st.info("Run an analysis first — the export will appear here.")
        return
    text = report_to_markdown(report)
    st.download_button("Download markdown", data=text, file_name="triage.md", mime="text/markdown")
    with st.expander("Preview", expanded=True):
        st.markdown(text)


def main() -> None:
    profile = _profile_from_sidebar()
    if st.sidebar.button("Clear result cache"):
        st.cache_data.clear()

    st.title("IssuePilot")
    analyze_tab, compare_tab, boards_tab, export_tab = st.tabs(
        ["Analyze", "Compare", "Boards", "Export"]
    )
    with analyze_tab:
        _analyze_tab(profile)
    with compare_tab:
        _compare_tab()
    with boards_tab:
        _boards_tab(profile)
    with export_tab:
        _export_tab()


if __name__ == "__main__":
    main()
