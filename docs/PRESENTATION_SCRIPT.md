# Presentation script (2 minutes)

Setup before stage: app open at http://localhost:8501, sidebar on Beginner Python,
cache primed (each seed clicked once). Backup link ready: pytest#15124.

## 0:00–0:20 — The problem (click: Seeded issue)

> "Every open-source maintainer knows this pain: hundreds of open issues, and a
> newcomer has no idea which one fits them. They either pick something too hard and
> quit, or never start at all. IssuePilot fixes that — paste any GitHub link, get a
> triage card tuned to YOUR profile. Watch — this is a real issue from psf/requests."

Click **Seeded issue**. Let the status timeline play.

## 0:20–0:55 — The card (point at each element)

> "In about twenty seconds we get the full picture. A one-paragraph summary of what
> the issue actually asks. A difficulty rating — Easy, 1.5 — computed from an explicit
> six-dimension rubric, not vibes. And a fit score — 80 out of 100, great fit — because
> it matches a beginner Python profile. Every point has a stated reason you can read.
> Below that: the exact requirements, the likely files, and — my favorite — 'Where to
> look', ranked from the repo's actual file tree, plus related history from linked
> issues."

Open the "Why this fits you" and "Where to look" expanders.

## 0:55–1:25 — The twist (Compare tab → Compare)

> "But here's the moment that matters. Same repo — two different developers."

Click **Compare**, then **Compare**.

> "Left: a beginner Python dev. Right: an advanced web dev. Same repository, completely
> different top picks — each justified. This is personalized contribution matching, not
> a generic issue list."

## 1:25–1:50 — Breadth (Boards tab → Show board → drill down)

> "Zoom out, and whole repos or orgs become ranked opportunity boards. And any pick
> drills straight back into the full evidence card. It also reviews pull requests —
> what changed, what to verify, and the risks."

Click **Show board**, then one **Analyze** drill-down button.

## 1:50–2:00 — Close (Export tab)

> "Everything exports as markdown. Four agents, one LangGraph pipeline, fully
> open-weight AI at the center — and every line of it is open source. Thank you."

Click **Export**, show the download button. Stop. Take questions.

---

## If something fails on stage

- Spinner past 45s: "The free model pool is busy — this is exactly why we cache."
  Click **Clear result cache** off... no — instead: open Export tab, show the last
  exported markdown. Then try the backup link.
- Red error box: read it aloud calmly, switch to the backup seed (pytest#15124).
- Never debug code on stage. Narrate, switch input, keep moving.

## Likely judge Q&A (30 seconds each)

**"What AI does it use, and is it really central?"**
> "An open-weights model — currently gpt-oss-120b served by Groq, swappable to Gemma
> via our provider factory. It powers four agents: issue analysis, PR review, repo
> path ranking, and history relevance. Kill the model and there is no product — the
> demo card you just saw IS model output plus deterministic scoring."

**"Why LangGraph instead of one prompt?"**
> "One prompt is a black box. Our pipeline is fetch, investigate, gather evidence,
> then score — each stage typed with Pydantic, each LLM call traced in SQLite. You
> can see exactly what each agent contributed."

**"How is the difficulty computed?"**
> "The model estimates six dimensions one to five — code complexity, components
> affected, required knowledge, testing complexity, dependencies, ambiguity. Then
> plain weighted math maps it to Easy, Medium, or Difficult. The weights live in a
> YAML file, so anyone can audit or retune them."

**"What did you build vs reuse?"**
> "The pipeline, scoring, resolver, UI, and skill are ours, written during the Hack
> Day. We reuse LangChain, LangGraph, Streamlit, and the GitHub API as libraries —
> all credited in the README and submission."

**"What breaks at scale?"**
> "Honest answer: free-tier rate limits. We mitigate with ETag caching, tiny capped
> prompts, quota-aware retries, and stale-cache fallback — but production would need
> a paid tier. That's also why boards use cheap heuristic ranks and only opened
> picks run the full pipeline."
