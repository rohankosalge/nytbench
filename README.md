<div align="center">

<img src="assets/logo.svg" alt="NYTBENCH" width="480">

**An apples-to-apples benchmark for LLM crossword solvers**

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://github.com/langchain-ai/langgraph)
[![Puzzles](https://img.shields.io/badge/puzzles-New%20York%20Times-000000?style=flat-square)](https://www.nytimes.com/crosswords)
[![License: MIT](https://img.shields.io/badge/license-MIT-22C55E?style=flat-square)](LICENSE)

</div>

---

## Overview

`nytbench` evaluates LLM-based agents on a curated, stratified set of NYT crossword puzzles under a controlled, reproducible environment. Every agent receives identical puzzle states, an identical action space, and is scored by an identical grader — eliminating prompt-format advantages and ensuring fair model comparison.

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

You will need a valid NYT Games subscription cookie to scrape puzzles (see [src/pipeline/scraper.py](src/pipeline/scraper.py)).

## Zero-Contamination Rules

1. **Date floor**: Only puzzles published **on or after February 1, 2026** are included. Puzzles before this date risk appearing in model training corpora and are excluded.
2. **No rebus puzzles**: Puzzles requiring multi-character squares are discarded to keep the action space uniform.
3. **No human hints**: The agent receives only the clue list and the current board state — no external puzzle databases or answer lists are injected.
4. **Frozen scaffolding**: The agent's action space (`GET_CLUE`, `WRITE`, `ERASE`) and system prompt are identical across all evaluated models.

## Quickstart

```bash
# Initial build — scrapes Feb 1 2026 → today, filters, and splits by weekday
python scripts/build_dataset.py

# Incremental update — only downloads puzzles not yet on disk, then re-runs all steps
python scripts/build_dataset.py --sync

# Run a benchmark against Monday puzzles
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

Puzzles are split by publication day (Monday–Sunday) as a proxy for difficulty. Each split targets at least 50 puzzles per day.

### Flow Metric

Each puzzle is annotated with a **Flow** score: the fraction of white squares that sit at the intersection of an Across and a Down answer. Higher Flow means denser crossing constraints — a useful continuous difficulty signal that complements the weekday proxy.

> Flow metric concept derived from statistics published by [XWord Info](https://www.xwordinfo.com), an indispensable reference for NYT crossword analysis. XWord Info is the work of Jim Horne and is not affiliated with this project.

## Attribution

Puzzle files are downloaded from the New York Times Games archive and require a valid NYT subscription. The NYT crossword is a registered trademark of The New York Times Company. This project is an independent research benchmark and is not affiliated with or endorsed by the New York Times.
