# Demo script (under 2 minutes)

## Pre-flight (before stage)

- [ ] `uv sync` done, `.env` has `GITHUB_TOKEN` + model key + organizer model ID
- [ ] Prime the cache: click Seeded issue, Seeded PR, Seeded repo once each,
      spaced ~60s apart (free-tier quota is 16K input tokens/min)
- [ ] Sidebar preset: Beginner Python. Backup link ready: pytest#15124
- [ ] If the model API dies on stage: seeded results are cached — rerun from cache,
      then show the backup link. Last resort: Export tab markdown.

## The 2 minutes

| Time | Do | Say (one line) |
| --- | --- | --- |
| 0:00–0:20 | Analyze tab, click **Seeded issue** | "Newcomers drown in issues — paste any GitHub link, get a card tuned to you." |
| 0:20–0:50 | Point at difficulty pill + fit meter + reasons | "Rubric-backed difficulty, and a fit score where every point has a reason." |
| 0:50–1:20 | **Compare** tab, Compare | "Same repo, beginner vs advanced — different top picks, justified." |
| 1:20–1:50 | **Boards** tab, drill into one pick | "Boards rank opportunities; one click opens the full evidence card." |
| 1:50–2:00 | **Export** tab | "And it exports the whole triage as markdown." |

## If asked

- Model: open-weight via provider factory (`GOOGLE_MODEL`), structured outputs only.
- Why LangGraph: fetch → investigate → evidence → finalize as typed, traced stages.
- Skill: `issue-triage/SKILL.md` makes the whole flow reusable by any agent.
- Honest note: board ranks are fast label heuristics; cards are evidence-backed.
