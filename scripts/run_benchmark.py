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
    OPENROUTER_API_KEY — required for OpenRouter passthrough models (openrouter/*)
    OLLAMA_BASE_URL    — optional; local Ollama endpoint (default localhost:11434)

Local (free, no key, no rate limits) via Ollama — pass `ollama/<model-tag>`:

    --model ollama/qwen2.5:7b        # after: ollama pull qwen2.5:7b
    --model ollama/llama3.2          # any already-pulled model

OpenRouter passthrough lets you evaluate almost any hosted model (Grok,
DeepSeek, Llama, Qwen, Mistral, ...) through one OpenAI-compatible endpoint.
Pass the model as `openrouter/<provider>/<model>`, e.g.:

    --model openrouter/x-ai/grok-4
    --model openrouter/qwen/qwen-2.5-72b-instruct
"""

import argparse
import json
import os
import random
from datetime import datetime
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
    if model.startswith("ollama/"):
        # Local, free, no rate limits: everything after the prefix is the Ollama
        # model tag (e.g. "ollama/qwen2.5:7b" -> "qwen2.5:7b"). Ollama exposes an
        # OpenAI-compatible API, so we reuse ChatOpenAI pointed at the local
        # daemon. The api_key is required by the client but ignored by Ollama.
        # Override the host with OLLAMA_BASE_URL (default http://localhost:11434/v1).
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": model.split("/", 1)[1],
            "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "api_key": "ollama",  # placeholder; Ollama does not check it
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        chat = ChatOpenAI(**kwargs)
    elif model.startswith("openrouter/"):
        # Passthrough: everything after the prefix is the OpenRouter model id
        # (e.g. "openrouter/x-ai/grok-4" -> "x-ai/grok-4"). OpenRouter speaks the
        # OpenAI-compatible API, so we reuse ChatOpenAI with a custom base_url and
        # reach dozens of models (Grok, DeepSeek, Llama, Qwen, Mistral, ...)
        # through a single dependency.
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": model.split("/", 1)[1],
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": os.environ["OPENROUTER_API_KEY"],
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        chat = ChatOpenAI(**kwargs)
    elif model.startswith("claude"):
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
            "(expected one of: ollama/*, openrouter/*, claude*, gpt*/o*, gemini*)"
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
    parser.add_argument("--splits-dir", default=str(SPLITS_DIR), help="Path to stratified splits")
    parser.add_argument(
        "--results-root",
        default="results",
        help="Root directory under which each run gets its own subfolder",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Subfolder name for this run under --results-root "
        "(default: <day>_<model>_<timestamp>)",
    )
    parser.add_argument(
        "--save-trace",
        action="store_true",
        help="Write a per-puzzle trace sidecar (puzzle + grid + placements + log) "
        "that scripts/visualize_episode.py can render without re-running the model",
    )
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

    # Every run gets its own designated subfolder under results/, holding the
    # JSONL, the summary, and (optionally) the per-puzzle traces. Default name is
    # <day>_<model>_<timestamp> with a filesystem-safe model (e.g. ollama/qwen2.5:7b
    # -> ollama_qwen2.5-7b), so repeated runs never overwrite each other.
    safe_model = args.model.replace("/", "_").replace(":", "-")
    run_name = args.run_name or f"{args.day}_{safe_model}_{datetime.now():%Y%m%d-%H%M%S}"
    run_dir = Path(args.results_root) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "results.jsonl"

    trace_dir = None
    if args.save_trace:
        trace_dir = run_dir / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)

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

            if trace_dir is not None:
                # Self-contained sidecar: stringify the tuple placement keys so it
                # is JSON-serialisable, and embed the puzzle so the visualizer can
                # render without re-running the model. (Lives under git-ignored
                # results/, so the embedded puzzle content is never committed.)
                trace = {
                    "model": args.model,
                    "max_rounds": args.max_rounds,
                    "grade": grade_result,
                    "episode": {
                        "grid": episode["grid"],
                        "complete": episode["complete"],
                        "turns": episode["turns"],
                        "placements": {
                            f"{k[0]}-{k[1]}": v for k, v in episode["placements"].items()
                        },
                        "log": episode["log"],
                    },
                    "puzzle": puzzle_meta,
                }
                (trace_dir / f"{puz_path.stem}.json").write_text(json.dumps(trace))

            status = "SOLVED" if record["solved"] else f"fill={record['fill_rate']:.0%}"
            print(f"   {status}  turns={record['turns']}")

    summary = aggregate(results)
    print_report(summary)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nRun folder: {run_dir}/")
    print(f"  results.jsonl  ({len(results)} puzzles)")
    print(f"  summary.json")
    if trace_dir is not None:
        print(f"  traces/        (view with scripts/visualize_episode.py --trace {trace_dir}/<date>.json)")


if __name__ == "__main__":
    main()
