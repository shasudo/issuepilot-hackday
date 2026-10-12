# IssuePilot

Universal GitHub contribution assistant: paste any GitHub link (issue, PR, repo, or org),
add your context (tech stack, skill level, interests), and get a personalized triage card:
what it is, how hard it is, whether it fits you, where to start.

Built fresh for Hacktoberfest Hack Day 2026 (NIAT-KKH × MLH), Track 1: Best Open-Source AI
Project. Inspired by a prior private prototype; every line here was written for the Hack Day.

## Problem

Open-source issues are overwhelming: newcomers can't tell which issue matches their stack
and level, and PRs take long to review because context is scattered across threads and diffs.

## Solution

One link in, one triage card out — tuned to a user profile:

- **Issues** → summary, stated requirements, likely relevant paths, ambiguities, difficulty
- **PRs** → summary, what changed, review checklist, risks, review complexity
- **Everything** → transparent fit score (0–100) with stated reasons, never black-box vibes

## How It Works

```text
GitHub link
  → Resolver (issue / PR / repo / org detection)
  → GitHub fetch (cached, retried, rate-limit aware)
  → Investigation agent (structured LLM output)
  → Rubric scoring (explicit weighted 1–5 dimensions → Easy/Medium/Difficult)
  → Fit scoring (deterministic profile match with reasons)
  → Triage card (web UI or CLI)
```

Deterministic where exactness matters (link parsing, reference extraction, scoring math);
the model only does qualitative judgment — and every model call is traced.

## AI / Partner Technology Used

- **Open-weight model** (Hack Day default) selected via `LLM_PROVIDER` + `GOOGLE_MODEL` in
  `.env` — use the organizer-confirmed model ID. Anthropic/OpenAI providers also supported
  for comparison, but the open-weight path is the product.
- **Structured outputs throughout** (`with_structured_output` + Pydantic schemas) — the
  product never parses free-text model output.
- **Prompts as versioned data** (`config/prompts/v1/*.yaml`) so tuning is a diff, not a deploy.
- **Explicit rubric** (`config/rubric.yaml`): six weighted dimensions, normalized average,
  Easy ≤ 2.0 / Medium ≤ 3.5.

## Setup

```bash
uv sync
cp .env.example .env   # fill in GITHUB_TOKEN and your model key + model ID
```

Requirements: Python 3.12 (managed automatically by `uv`), a GitHub token with
`public_repo` scope, and one LLM provider key.

## How to Run

Web UI (the demo):

```bash
uv run streamlit run app.py
```

Then open the printed local URL (usually http://localhost:8501), pick a profile preset in
the sidebar, and click a seeded example.

Web UI tabs: Analyze (single card), Compare (two profiles, one repo), Boards (ranked
opportunities + drill-down), Export (markdown download).

CLI:

```bash
uv run issuepilot analyze "https://github.com/owner/repo/issues/123" --stack python --level beginner
uv run issuepilot analyze owner/repo#123 --profile profiles/beginner-python.yaml
uv run issuepilot recommend psf/requests --stack python --level beginner
```

Tests:

```bash
uv run pytest -q
```

## Seeded demo

- Issue: https://github.com/psf/requests/issues/7634
- PR: https://github.com/psf/requests/pull/7586
- Backup: https://github.com/pytest-dev/pytest/issues/15124

Profiles: `profiles/beginner-python.yaml`, `profiles/advanced-web.yaml`.

## Project Status

- M0–M4 (done): scaffold, GitHub layer + resolver, issue/PR analysis + fit, repo/org
  flows, evidence agents, LangGraph orchestration, 4-tab web UI, markdown export
- M5 (next): demo lock, Agent Skill wrapper, submission

## Team Members

- shasudo (builds; teammates TBD)

## License

MIT — see [LICENSE](LICENSE).
