# nytbench

An apples-to-apples agent benchmark for solving New York Times crossword puzzles.

---

## Overview

`nytbench` evaluates LLM-based agents on a curated, stratified set of NYT crossword puzzles under a controlled, reproducible environment. Every agent receives identical puzzle states, an identical action space, and is scored by an identical grader — eliminating prompt-format advantages and ensuring fair comparison.

## Project Structure

```
nytbench/
├── data/
│   ├── raw_puz/              # Downloaded .puz files (not committed)
│   ├── processed_json/       # Machine-readable JSON puzzle states
│   └── stratified_splits/    # Puzzles organized by weekday difficulty
├── src/
│   ├── pipeline/             # Data curation and preprocessing
│   ├── environment/          # Custom crossword referee/simulator
│   ├── agent/                # Standardized LangGraph agent scaffolding
│   └── evaluation/           # Grading and metrics
└── scripts/
    ├── build_dataset.py      # End-to-end dataset construction
    └── run_benchmark.py      # Agent evaluation entry point
```

## Setup

```bash
pip install -r requirements.txt
```

You will need a valid NYT Games subscription cookie to scrape puzzles (see `src/pipeline/scraper.py`).

## Zero-Contamination Rules

1. **Date cutoff**: Only puzzles published on or before **February 1, 2026** are included. Any puzzle after this date may appear in a model's training data and is excluded.
2. **No rebus puzzles**: Puzzles requiring multi-character squares are discarded to keep the action space uniform.
3. **No human hints**: The agent receives only the clue list and the current board state — no external puzzle databases or answer lists are injected.
4. **Frozen scaffolding**: The agent's action space (`GET_CLUE`, `WRITE`, `ERASE`) and system prompt are identical across all evaluated models.

## Quickstart

```bash
# 1. Build the dataset (requires NYT credentials in env)
python scripts/build_dataset.py --start 2020-01-01 --end 2026-02-01 --out data/

# 2. Run a benchmark against Monday puzzles
python scripts/run_benchmark.py --day monday --model claude-sonnet-4-6 --puzzles 50
```

## Metrics

| Metric | Description |
|---|---|
| `solve_rate` | Fraction of puzzles solved with 100% correct squares |
| `fill_rate` | Average fraction of squares correctly filled |
| `turns` | Mean number of agent turns per puzzle |
| `tool_calls` | Mean number of external tool invocations per puzzle |

## Stratified Splits

Puzzles are split by publication day (Monday–Sunday) as a proxy for difficulty. Each split contains at least 50 puzzles. The `flow` metric (graph-theoretic crossing density) is logged per puzzle to enable finer difficulty analysis.
