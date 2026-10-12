---
name: issue-triage
description: Analyzes GitHub issues and PRs into personalized triage cards with difficulty and fit scores. Use when the user pastes a GitHub issue, PR, repo, or org link and wants to know what it is, how hard it is, or whether it fits their stack and level.
license: MIT
---

# Issue Triage

Turn any GitHub link into a personalized triage card: summary, difficulty
(Easy/Medium/Difficult from an explicit weighted rubric), and a 0–100 fit
score against the user's profile — with stated reasons.

## When to use

- The user pastes a GitHub issue or PR link and asks what it is or whether to take it on.
- The user pastes a repo or org link and asks what to contribute to.
- The user mentions their stack/level and wants matching open-source work.

## Quick start

Run from the repository root. Requires `.env` with `GITHUB_TOKEN` and a model key
(see `.env.example`).

```bash
uv run issuepilot analyze "https://github.com/owner/repo/issues/123" --stack python --level beginner
uv run issuepilot recommend psf/requests --profile profiles/beginner-python.yaml
```

Or use the bundled script, which forwards all arguments:

```bash
./issue-triage/scripts/analyze.sh "https://github.com/owner/repo/pull/45" --level advanced
```

For an interactive session, launch the web UI instead:

```bash
uv run streamlit run app.py
```

## Profiles

Personalization comes from a user profile: stack, languages, level
(beginner/intermediate/advanced), interests. See
[references/profile-format.md](references/profile-format.md) and the examples in
`profiles/`. CLI flags override file values.

## Reading the output

- **Difficulty** is rubric-backed (six 1–5 dimensions, weighted average), not a guess.
- **Fit** is deterministic profile matching; every point has a stated reason.
- **Where to look** ranks repo paths from the actual file tree.
- **Related history** explains referenced issues/PRs in one line each.
- Board rankings (`recommend`, Boards tab) use fast label heuristics; opening any
  pick runs the full evidence-backed analysis.

## Limits

- Public GitHub content only; private links fail with a clear error.
- No network? Primed SQLite caches serve stale results instead of failing.
- The skill triages and guides — it never writes fixes.
