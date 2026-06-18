"""
Record a multi-agent solve as a replayable event log.

`run_benchmark.py` keeps only per-puzzle grades, and `visualize_episode.py`
renders one static end-state. Neither lets you *watch* the solve unfold. This
script runs the multi-agent solver with an event sink attached (see
`MultiAgentSolver(..., emit=...)`), capturing a board snapshot after every agent
action, then writes a self-contained recording JSON the browser viewer animates.

Usage:
    # No network, no API key — derive answers from the puzzle and watch the
    # four specialists fill it in. Great for trying the viewer.
    python scripts/record_solve.py --fake --day monday

    # Real model (makes the same calls a normal solve would — one puzzle):
    python scripts/record_solve.py --model ollama/llama3.2 --date 2026-02-02
    python scripts/record_solve.py --model claude-sonnet-4-6 --day monday

Then serve the viewer:
    uvicorn viz.server:app --reload     # open http://127.0.0.1:8000

Output: recordings/<label>_<model>.json  (git-ignored; embeds puzzle content).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.multi.orchestrator import MultiAgentSolver
from src.agent.observation import AgentBoard
from src.evaluation.grader import grade
from scripts.run_benchmark import load_llm
from scripts.visualize_episode import _find_puzzle

_CLUE_RE = re.compile(r'Clue:\s*"(.*?)"', re.DOTALL)


def build_fake_llm(puzzle: dict):
    """A no-network LLM that 'knows' the answers, for exercising the pipeline.

    It reads the ground-truth answer for whichever clue an agent is asking about
    and returns it at high confidence, so the solver fills the whole grid without
    any API calls. Routing is by the specialist's system prompt (each starts with
    'You are the <Role>.'):

      - Syntax Extractor -> a permissive spec (no suffix constraint);
      - Eraser           -> abstain (correct answers never conflict);
      - the three solvers -> the true answer for the clue in the message.
    """
    answer_by_clue: dict[str, str] = {}
    for direction in ("across", "down"):
        for e in puzzle["entries"][direction]:
            answer_by_clue[e["clue"]] = e["answer"]

    def llm(system: str, messages: list[dict]) -> str:
        if "You are the Syntax Extractor" in system:
            return "PART_OF_SPEECH: other\nTENSE: none\nPLURAL: false\nREQUIRED_SUFFIX: none"
        if "You are the Eraser" in system:
            return "ABSTAIN"
        m = _CLUE_RE.search(messages[-1]["content"])
        if m:
            answer = answer_by_clue.get(m.group(1))
            if answer:
                return f"ANSWER: {answer}\nCONFIDENCE: high"
        return "ABSTAIN"

    return llm


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a replayable multi-agent solve.")
    ap.add_argument("--model", help="e.g. claude-sonnet-4-6, ollama/llama3.2")
    ap.add_argument("--fake", action="store_true",
                    help="Use a no-network LLM that derives answers from the puzzle")
    ap.add_argument("--date", help="Puzzle date YYYY-MM-DD")
    ap.add_argument("--day", help="Weekday split to pick from (e.g. monday)")
    ap.add_argument("--puzzle", help="Explicit path to a puzzle JSON")
    ap.add_argument("--max-rounds", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--out", help="Output path (default recordings/<label>_<model>.json)")
    args = ap.parse_args()

    if not args.fake and not args.model:
        ap.error("provide --model <id>, or --fake to derive answers from the puzzle")

    path = _find_puzzle(args.date, args.day, args.puzzle)
    puzzle = json.loads(path.read_text())
    label = puzzle.get("date") or path.stem
    model = "fake" if args.fake else args.model

    if args.fake:
        llm = build_fake_llm(puzzle)
    else:
        llm = load_llm(args.model, max_tokens=args.max_tokens, temperature=args.temperature)

    print(f"Recording {label} ({puzzle.get('weekday')}) with {model}…")

    board = AgentBoard(puzzle)
    events: list[dict] = []
    start = time.monotonic()

    def collect(event: dict) -> None:
        event["i"] = len(events)
        event["t"] = round(time.monotonic() - start, 3)
        events.append(event)

    solver = MultiAgentSolver(llm, emit=collect)
    result = solver.solve(board, max_rounds=args.max_rounds)
    duration = round(time.monotonic() - start, 3)

    grade_result = grade(board.to_grid(), puzzle["solution"])

    slots = [
        {
            "key": f"{s.number}-{s.direction}",
            "number": s.number,
            "direction": s.direction,
            "clue": s.clue,
            "cells": [[x, y] for (x, y) in s.cells],
        }
        for s in board.slots
    ]

    recording = {
        "meta": {
            "date": puzzle.get("date"),
            "weekday": puzzle.get("weekday"),
            "model": model,
            "max_rounds": args.max_rounds,
            "width": board.width,
            "height": board.height,
            "duration_sec": duration,
            "llm_calls": result["llm_calls"],
            "complete": result["complete"],
            "result": grade_result,
        },
        "grid": puzzle["grid"],
        "solution": puzzle["solution"],
        "slots": slots,
        "events": events,
    }

    safe_model = model.replace("/", "_").replace(":", "-")
    out_path = Path(args.out) if args.out else Path(f"recordings/{label}_{safe_model}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(recording))

    r = grade_result
    print(
        f"  {len(events)} events · solved={result['complete']} "
        f"· accuracy={r['accuracy']:.0%} · fill={r['fill_rate']:.0%} "
        f"· llm_calls={result['llm_calls']} · {duration}s"
    )
    print(f"Recording written to {out_path}")
    print("View it:  uvicorn viz.server:app --reload   then open http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
