"""
Visualize what the multi-agent solver actually did on one puzzle.

The benchmark only persists per-puzzle *grades*, which hide the solving
behavior. This script re-solves a single puzzle and renders the trace that
`run_episode` already produces but `run_benchmark.py` discards:

  - a board overlay (agent fill vs. ground truth, colour-coded);
  - a per-clue table (what each agent committed, vs. the true answer);
  - the chronological agent action log (spec / place / reject / abstain).

It re-runs the model (the original run's trace was not saved), so it makes the
same model calls a normal solve would — keep it to one puzzle.

Usage:
    # Re-run the model on one puzzle and render the live trace:
    python scripts/visualize_episode.py --model ollama/llama3.2 --date 2026-05-11
    python scripts/visualize_episode.py --model ollama/qwen2.5:7b --day monday --max-rounds 2

    # Render a saved sidecar (run_benchmark.py --save-trace) — no model, no re-run:
    python scripts/visualize_episode.py --trace results/traces/ollama_llama3.2/2026-05-11.json --html out.html
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.observation import AgentBoard
from src.agent.multi.orchestrator import run_episode
from scripts.run_benchmark import load_llm

GREEN, RED, DIM, BOLD, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"


def _find_puzzle(date: str | None, day: str | None, path: str | None) -> Path:
    if path:
        return Path(path)
    roots = [Path("data/stratified_splits"), Path("data/filtered_json")]
    if day:
        roots.insert(0, Path("data/stratified_splits") / day)
    for root in roots:
        if date:
            hits = list(root.rglob(f"{date}.json"))
        else:
            hits = sorted(root.rglob("*.json"))
        if hits:
            return hits[0]
    raise FileNotFoundError("No matching puzzle found. Pass --date, --day, or --puzzle.")


def _slot_letters(grid: list[str], cells, width: int) -> str:
    """Read the agent's current letters for a slot from the flat grader grid."""
    out = []
    for (x, y) in cells:
        ch = grid[(y - 1) * width + (x - 1)]
        out.append(ch if ch != " " else "·")
    return "".join(out)


def _truth_map(puzzle: dict) -> dict:
    truth = {}
    for direction in ("across", "down"):
        for e in puzzle["entries"][direction]:
            truth[(e["num"], direction)] = e["answer"]
    return truth


# ── terminal rendering ────────────────────────────────────────────────────

def render_board(puzzle: dict, grid: list[str], color: bool) -> str:
    w, h, sol = puzzle["width"], puzzle["height"], puzzle["solution"]
    g, r, d, x = (GREEN, RED, DIM, RESET) if color else ("", "", "", "")
    lines = []
    for y in range(h):
        row = []
        for cx in range(w):
            i = y * w + cx
            a, s = grid[i], sol[i]
            if s == ".":
                row.append(f"{d}▓▓{x}")
            elif a == " ":
                row.append(f"{d} ·{x}")
            elif a == s:
                row.append(f"{g} {a}{x}")
            else:
                row.append(f"{r} {a.lower()}{x}")
        lines.append("".join(row))
    return "\n".join(lines)


def render_clue_table(puzzle: dict, grid: list[str], placements: dict, color: bool) -> str:
    truth = _truth_map(puzzle)
    board = AgentBoard(puzzle)  # fresh board: numbering + slot cells, no LLM
    g, r, d, b, x = (GREEN, RED, DIM, BOLD, RESET) if color else ("", "", "", "", "")
    rows = [f"{b}{'CLUE':<6} {'AGENT':<16} {'TRUTH':<16} {'BY':<8} CLUE TEXT{x}"]
    for slot in sorted(board.slots, key=lambda s: (s.direction, s.number)):
        key = (slot.number, slot.direction)
        agent_word = _slot_letters(grid, slot.cells, puzzle["width"])
        true_word = truth.get(key, "?")
        placed = placements.get(f"{slot.number}-{slot.direction}") or placements.get(key)
        by = (placed or {}).get("agent", "") if isinstance(placed, dict) else ""
        ok = agent_word == true_word
        mark = f"{g}✓{x}" if ok else (f"{r}✗{x}" if "·" not in agent_word else f"{d}·{x}")
        label = f"{slot.number}{slot.direction[0].upper()}"
        clue = slot.clue if len(slot.clue) <= 40 else slot.clue[:37] + "..."
        rows.append(f"{mark} {label:<4} {agent_word:<16} {true_word:<16} {by:<8} {d}{clue}{x}")
    return "\n".join(rows)


def render_log(log: list[dict], color: bool) -> str:
    g, r, d, x = (GREEN, RED, DIM, RESET) if color else ("", "", "", "")
    tint = {"place": g, "reject": r, "abstain": d}
    rows = []
    for e in log:
        c = tint.get(e["action"], "")
        word = f" {e['word']}" if e.get("word") else ""
        detail = f" {d}({e['detail']}){x}" if e.get("detail") else ""
        rows.append(f"  {c}{e['agent']:<9}{x} {c}{e['action']:<8}{x} {e['slot']:<7}{word}{detail}")
    return "\n".join(rows)


# ── HTML export ───────────────────────────────────────────────────────────

def render_html(puzzle: dict, grid: list[str], episode: dict, title: str) -> str:
    w, h, sol = puzzle["width"], puzzle["height"], puzzle["solution"]
    cells = []
    for y in range(h):
        for cx in range(w):
            i = y * w + cx
            a, s = grid[i], sol[i]
            if s == ".":
                bg, txt = "#222", ""
            elif a == " ":
                bg, txt = "#fff", ""
            elif a == s:
                bg, txt = "#bbf7d0", a
            else:
                bg, txt = "#fecaca", a
            cells.append(f'<td style="background:{bg}">{txt}</td>')
    grid_rows = "".join(
        "<tr>" + "".join(cells[y * w:(y + 1) * w]) + "</tr>" for y in range(h)
    )
    log_rows = "".join(
        f"<tr><td>{e['agent']}</td><td>{e['action']}</td><td>{e['slot']}</td>"
        f"<td>{e.get('word') or ''}</td><td>{e.get('detail') or ''}</td></tr>"
        for e in episode["log"]
    )
    return f"""<!doctype html><meta charset=utf-8><title>{title}</title>
<style>
body{{font:14px system-ui;margin:2rem;color:#111}}
table.grid{{border-collapse:collapse}}
table.grid td{{width:26px;height:26px;border:1px solid #999;text-align:center;
  font-weight:600;text-transform:uppercase}}
table.log{{border-collapse:collapse;margin-top:1rem}}
table.log td,table.log th{{border:1px solid #ddd;padding:2px 8px;font-size:12px}}
.legend span{{display:inline-block;padding:2px 8px;margin-right:6px;border-radius:3px}}
</style>
<h2>{title}</h2>
<p>solved={episode['complete']} · llm_calls={episode['turns']}</p>
<div class=legend>
  <span style="background:#bbf7d0">correct</span>
  <span style="background:#fecaca">wrong</span>
  <span style="background:#fff;border:1px solid #999">empty</span>
  <span style="background:#222;color:#fff">block</span>
</div>
<table class=grid>{grid_rows}</table>
<h3>Agent action log</h3>
<table class=log><tr><th>agent</th><th>action</th><th>slot</th><th>word</th><th>detail</th></tr>
{log_rows}</table>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Visualize a multi-agent solve.")
    ap.add_argument(
        "--trace",
        help="Render a saved trace sidecar (from run_benchmark.py --save-trace) "
        "with no model re-run. Mutually exclusive with --model.",
    )
    ap.add_argument("--model", help="e.g. ollama/llama3.2 (re-runs the model)")
    ap.add_argument("--date", help="Puzzle date YYYY-MM-DD")
    ap.add_argument("--day", help="Weekday split to pick from (e.g. monday)")
    ap.add_argument("--puzzle", help="Explicit path to a puzzle JSON")
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--temperature", type=float, default=None)
    ap.add_argument("--html", help="Also write an HTML visualization to this path")
    ap.add_argument("--no-color", action="store_true", help="Disable ANSI colour")
    args = ap.parse_args()
    color = sys.stdout.isatty() and not args.no_color

    if args.trace:
        # Render a saved sidecar — no model, no re-run.
        trace = json.loads(Path(args.trace).read_text())
        puzzle, episode, model = trace["puzzle"], trace["episode"], trace["model"]
        label = puzzle.get("date", Path(args.trace).stem)
    elif args.model:
        path = _find_puzzle(args.date, args.day, args.puzzle)
        puzzle = json.loads(path.read_text())
        model, label = args.model, path.stem
        print(f"Solving {label} ({puzzle.get('weekday')}) with {model} — re-runs the model…")
        llm = load_llm(args.model, max_tokens=args.max_tokens, temperature=args.temperature)
        episode = run_episode(llm, puzzle, max_rounds=args.max_rounds)
    else:
        ap.error("provide either --trace <sidecar.json> or --model <id> (+ --date/--day/--puzzle)")

    grid, sol = episode["grid"], puzzle["solution"]
    white = sum(1 for s in sol if s != ".")
    correct = sum(1 for a, s in zip(grid, sol) if s != "." and a == s)
    filled = sum(1 for a, s in zip(grid, sol) if s != "." and a != " ")

    bar = "=" * 60
    print(f"\n{bar}\n  {label}  ·  {model}")
    print(f"  solved={episode['complete']}  accuracy={correct}/{white} ({correct/white:.0%})  "
          f"filled={filled}/{white} ({filled/white:.0%})  llm_calls={episode['turns']}\n{bar}\n")
    print(render_board(puzzle, grid, color))
    print(f"\nPER-CLUE (agent commit vs truth):\n")
    print(render_clue_table(puzzle, grid, episode["placements"], color))
    print(f"\nAGENT ACTION LOG ({len(episode['log'])} events):\n")
    print(render_log(episode["log"], color))

    if args.html:
        out = Path(args.html)
        out.write_text(render_html(puzzle, grid, episode, f"{label} · {model}"))
        print(f"\nHTML written to {out}  (open in a browser)")


if __name__ == "__main__":
    main()
