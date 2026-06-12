"""
Executes the NYT-Agent against a stratified split and outputs benchmark scores.

Usage:
    python scripts/run_benchmark.py \\
        --day     monday \\
        --model   claude-sonnet-4-6 \\
        --puzzles 50 \\
        --out     results/monday_claude-sonnet.jsonl

Environment variables:
    ANTHROPIC_API_KEY  — required for Anthropic models
    OPENAI_API_KEY     — required for OpenAI models
"""

import argparse
import json
import random
from pathlib import Path

from dotenv import load_dotenv

from src.agent.orchestrator import run_episode
from src.environment.simulator import CrosswordEnv
from src.evaluation.grader import grade
from src.evaluation.metrics import aggregate, print_report

load_dotenv()

SPLITS_DIR = Path("data/stratified_splits")


def load_llm(model: str):
    if model.startswith("claude"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, max_tokens=1024)
    if model.startswith("gpt") or model.startswith("o"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model)
    raise ValueError(f"Unrecognised model prefix for: {model!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run nytbench evaluation.")
    parser.add_argument("--day", required=True, help="Weekday split to evaluate (e.g. monday)")
    parser.add_argument("--model", required=True, help="Model identifier (e.g. claude-sonnet-4-6)")
    parser.add_argument("--puzzles", type=int, default=50, help="Number of puzzles to evaluate")
    parser.add_argument("--max-turns", type=int, default=200, help="Max agent turns per puzzle")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for puzzle sampling")
    parser.add_argument("--out", default=None, help="JSONL output file path")
    parser.add_argument("--splits-dir", default=str(SPLITS_DIR), help="Path to stratified splits")
    args = parser.parse_args()

    split_dir = Path(args.splits_dir) / args.day
    if not split_dir.exists():
        raise FileNotFoundError(f"Split not found: {split_dir}")

    puzzle_paths = sorted(split_dir.glob("*.json"))
    rng = random.Random(args.seed)
    rng.shuffle(puzzle_paths)
    puzzle_paths = puzzle_paths[: args.puzzles]

    if not puzzle_paths:
        print("No puzzles found. Run build_dataset.py first.")
        return

    llm = load_llm(args.model)
    out_path = Path(args.out) if args.out else Path(f"results/{args.day}_{args.model}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with out_path.open("w") as f:
        for i, puz_path in enumerate(puzzle_paths, 1):
            print(f"[{i}/{len(puzzle_paths)}] {puz_path.stem}")
            env = CrosswordEnv.from_json(puz_path)
            episode = run_episode(llm, env, max_turns=args.max_turns)

            puzzle_meta = json.loads(puz_path.read_text())
            grade_result = grade(episode["grid"], puzzle_meta["solution"])
            record = {
                **grade_result,
                "date": puzzle_meta.get("date"),
                "weekday": puzzle_meta.get("weekday"),
                "turns": episode["turns"],
                "tool_calls": episode["tool_calls"],
                "model": args.model,
            }
            results.append(record)
            f.write(json.dumps(record) + "\n")
            f.flush()

            status = "SOLVED" if record["solved"] else f"fill={record['fill_rate']:.0%}"
            print(f"   {status}  turns={record['turns']}")

    summary = aggregate(results)
    print_report(summary)
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Results written to {out_path}")
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
