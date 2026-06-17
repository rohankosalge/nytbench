"""
Executes the NYT-Agent against a stratified split and outputs benchmark scores.

Usage:
    python scripts/run_benchmark.py \\
        --day     monday \\
        --model   claude-sonnet-4-6 \\
        --puzzles 50 \\
        --out     results/monday_claude-sonnet.jsonl

Environment variables:
    ANTHROPIC_API_KEY  — required for Anthropic models (claude*)
    OPENAI_API_KEY     — required for OpenAI models (gpt*/o*)
    GOOGLE_API_KEY     — required for Google models (gemini*)
"""

import argparse
import json
import random
from pathlib import Path

from dotenv import load_dotenv

from src.agent.multi.orchestrator import run_episode
from src.evaluation.grader import grade
from src.evaluation.metrics import aggregate, print_report

load_dotenv()

SPLITS_DIR = Path("data/stratified_splits")


def load_llm(model: str, max_tokens: int = 4096, temperature: float | None = None):
    """Return a model-agnostic callable: llm(system, messages) -> str.

    The multi-agent solver talks to every backend through this one signature, so
    we wrap whichever LangChain chat model the identifier selects.

    Fairness notes
    --------------
    - `max_tokens` is applied identically across providers so no model is given
      a smaller (or unbounded) output budget than another. Keep it generous:
      reasoning models spend output tokens on internal thinking before emitting
      an action, and too small a cap truncates them mid-reasoning.
    - `temperature` is only forwarded when explicitly set. It is left unset by
      default because current Claude reasoning models (Opus 4.7/4.8, Fable 5)
      reject sampling parameters with a 400 — sending `temperature=0` to them
      would exclude the very models we want to evaluate. Pass it only for
      backends/models that accept it (OpenAI base chat, Gemini, Sonnet, etc.).
    """
    if model.startswith("claude"):
        from langchain_anthropic import ChatAnthropic
        kwargs = {"model": model, "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        chat = ChatAnthropic(**kwargs)
    elif model.startswith("gpt") or model.startswith("o"):
        from langchain_openai import ChatOpenAI
        kwargs = {"model": model, "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        chat = ChatOpenAI(**kwargs)
    elif model.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs = {"model": model, "max_output_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        chat = ChatGoogleGenerativeAI(**kwargs)
    else:
        raise ValueError(
            f"Unrecognised model prefix for: {model!r} "
            "(expected one of: claude*, gpt*/o*, gemini*)"
        )
    return _wrap_chat_model(chat)


def _wrap_chat_model(chat):
    """Adapt a LangChain chat model to the solver's llm(system, messages) form."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    def llm(system: str, messages: list[dict]) -> str:
        lc_messages = [SystemMessage(content=system)]
        for m in messages:
            role = m["role"]
            if role == "assistant":
                lc_messages.append(AIMessage(content=m["content"]))
            else:
                lc_messages.append(HumanMessage(content=m["content"]))
        return chat.invoke(lc_messages).content

    return llm


def main() -> None:
    parser = argparse.ArgumentParser(description="Run nytbench evaluation.")
    parser.add_argument("--day", required=True, help="Weekday split to evaluate (e.g. monday)")
    parser.add_argument("--model", required=True, help="Model identifier (e.g. claude-sonnet-4-6)")
    parser.add_argument("--puzzles", type=int, default=50, help="Number of puzzles to evaluate")
    parser.add_argument("--max-rounds", type=int, default=8, help="Max constraint-propagation rounds per puzzle")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Per-call output token budget, applied identically to every provider",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help=(
            "Sampling temperature. Omitted by default; only set it for models "
            "that accept sampling params (Claude Opus 4.7/4.8 and Fable 5 reject it)."
        ),
    )
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

    llm = load_llm(args.model, max_tokens=args.max_tokens, temperature=args.temperature)
    out_path = Path(args.out) if args.out else Path(f"results/{args.day}_{args.model}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    results = []
    with out_path.open("w") as f:
        for i, puz_path in enumerate(puzzle_paths, 1):
            print(f"[{i}/{len(puzzle_paths)}] {puz_path.stem}")
            puzzle_meta = json.loads(puz_path.read_text())
            episode = run_episode(llm, puzzle_meta, max_rounds=args.max_rounds)

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
