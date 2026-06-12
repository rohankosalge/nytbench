<div align="center">

# nytbench

**An apples-to-apples benchmark for LLM crossword solvers**

<svg xmlns="http://www.w3.org/2000/svg" width="720" height="384" viewBox="0 0 720 384" font-family="Helvetica, Arial, sans-serif" style="display:block;margin:0 auto;">
<rect width="720" height="384" fill="#ffffff"/>
<rect x="24" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="31" y="45" font-size="19" font-weight="500" fill="#1a1a1a">1</text>
<text x="66.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">N</text>
<rect x="108" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="150.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">Y</text>
<rect x="192" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="199" y="45" font-size="19" font-weight="500" fill="#1a1a1a">2</text>
<text x="234.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">T</text>
<rect x="276" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="318.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">B</text>
<rect x="360" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="367" y="45" font-size="19" font-weight="500" fill="#1a1a1a">3</text>
<text x="402.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">E</text>
<rect x="444" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="486.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">N</text>
<rect x="528" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="570.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">C</text>
<rect x="612" y="24" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="654.0" y="69.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">H</text>
<rect x="24" y="108" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="108" y="108" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="192" y="108" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="234.0" y="153.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">E</text>
<rect x="276" y="108" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="360" y="108" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="402.0" y="153.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">V</text>
<rect x="444" y="108" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="528" y="108" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="612" y="108" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="24" y="192" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="108" y="192" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="192" y="192" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="234.0" y="237.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">S</text>
<rect x="276" y="192" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="360" y="192" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="402.0" y="237.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">A</text>
<rect x="444" y="192" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="528" y="192" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="612" y="192" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="24" y="276" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="108" y="276" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="192" y="276" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="234.0" y="321.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">T</text>
<rect x="276" y="276" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="360" y="276" width="84" height="84" fill="#ffffff" stroke="#1a1a1a" stroke-width="1.5"/>
<text x="402.0" y="321.0" font-size="46" font-weight="700" fill="#1a1a1a" text-anchor="middle" dominant-baseline="central">L</text>
<rect x="444" y="276" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="528" y="276" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="612" y="276" width="84" height="84" fill="#1a1a1a" stroke="#1a1a1a" stroke-width="1.5"/>
<rect x="24" y="24" width="672" height="336" fill="none" stroke="#1a1a1a" stroke-width="3"/>
</svg>

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
