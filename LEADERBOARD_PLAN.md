# Live Leaderboard — Implementation Plan

> Status: **plan only — not yet implemented.** This document describes the steps to stand up a live, public leaderboard for `nytbench`. No code has been written against it.

## Grounding fact: leaderboard data is safe to publish

The benchmark's result records contain **only grades** — `solved`, `fill_rate`, `accuracy`, `date`, `weekday`, `model`, `turns`, `tool_calls` (see `scripts/run_benchmark.py` → `results/{day}_{model}.jsonl`). They carry **no clues, answers, or puzzle content**. Unlike the puzzle corpus (which is git-ignored and must never be committed — licensed NYT content), the leaderboard scores themselves are publishable. This makes a static public site viable.

## Prerequisites / current gaps to settle first

1. **Define the canonical leaderboard record.** Each run should contribute an immutable record with:
   - `model`, `provider`, `track` (`baseline` | `multi`)
   - `dataset_version`, `nytbench_commit`
   - config: `max_tokens`, `temperature`, `max_rounds`, `seed`
   - per-weekday + overall metrics
   - **recommended additions:** `cost_usd`, `tokens`, `latency` (not captured today)
2. **Version the dataset.** The corpus grows daily via `build_dataset.py --sync`, so a "solve rate" is meaningless unless the puzzle set is pinned. Freeze a snapshot with a hash / season id (e.g. `2026-Q1`) and stamp it on every result.
3. **Populate both tracks.** `run_benchmark.py` only drives the multi-agent track today; the baseline board stays empty until a `--track` switch is added. Report the two as **separate** boards (cross-track comparison is agent-vs-agent, not model-vs-model).
4. **Decide the statistics for small n.** ~15 puzzles/weekday → wide confidence intervals. Plan to show CIs, pool weekdays, or wait for the corpus to grow.

## Phased build

### Phase 1 — Aggregation layer (no frontend yet)
- Write an aggregator that scans all `results/*.jsonl` across models/tracks and emits a single `leaderboard.json` (model × track, overall + by-weekday, with CIs). This is the missing cross-model step — `src/evaluation/metrics.py` is single-run only today.
- Establish an append-only results store. Start with committed JSON files (scores are publishable); move to SQLite or managed Postgres/KV at scale.

### Phase 2 — Serving layer
- **Recommended (simplest):** a static site. A build step renders `leaderboard.json` → HTML/Markdown and publishes to **GitHub Pages** (or Vercel / Netlify / HF Spaces). "Live" = rebuilt whenever new results land. No server to run.
- **If interactivity is wanted** (filter by weekday/track, sortable tables, cost-vs-accuracy plots): a small app — Streamlit or FastAPI + JS frontend — reading the store.

### Phase 3 — Automation (the "live" part)
- A scheduled job that:
  1. `build_dataset.py --sync`
  2. run the benchmark for each registered model/track
  3. append results
  4. regenerate `leaderboard.json`
  5. redeploy the site
- Options: **GitHub Actions cron** (simplest, integrates with Pages), this project's `/schedule` cloud agent, or a cron on a small VM.
- Store provider keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`) as CI/secret-manager secrets — never in the repo.
- Add cost/runtime guards: cap `--puzzles`, a per-run budget ceiling, and idempotency (don't re-run the same model × `dataset_version`).

### Phase 4 — Governance & trust (do not skip)
- Pin config per run via the existing flags (`--max-tokens`, opt-in `--temperature`) and record them in each record — otherwise the board silently mixes settings.
- Publish a methodology page: dataset version, contamination floor (Feb 1 2026), the English/US-centric corpus caveat, two-track separation, and the exact config used.
- Make results immutable / append-only with provenance (`nytbench_commit`, `dataset_version`, timestamp) so any row is reproducible.

## Minimum viable path (fastest credible v1)

1. Freeze a dataset snapshot.
2. Run the registered models once per track.
3. Write the aggregator → `leaderboard.json`.
4. Render to a static page on GitHub Pages.
5. Add a weekly GitHub Actions cron to re-run and redeploy.

Add cost/latency capture and interactivity later.

## The two genuinely blocking items

Everything else can start crude and harden over time, but these two are required for the numbers to mean anything:

- **Dataset versioning** (Prerequisite 2)
- **Cross-model aggregator** (Phase 1)

## Related references

- `scripts/run_benchmark.py` — run protocol, `load_llm` provider routing, fairness flags
- `src/evaluation/metrics.py` — current (single-run) aggregation
- `README.md` → "Models" — supported providers and fair-comparison flags
- `.gitignore` — puzzle data exclusions (results scores are not excluded and are safe to publish)
