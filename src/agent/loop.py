"""
The bare-bones agent loop.

This is intentionally simple: no LangGraph, no sub-graphs, no provider-specific
client code. The loop is model-agnostic — it talks to the model through a single
injected callable so any backend can be plugged in:

    llm(system_prompt: str, messages: list[dict]) -> str

where each message is {"role": "user" | "assistant", "content": str} and the
return value is the model's text for this turn.

Each turn the loop renders the board, asks the model for one action, parses it,
applies it, and feeds the result back. It stops when the board is full, the
model emits DONE, or `max_turns` is reached.
"""

from __future__ import annotations

from typing import Callable

from src.agent.actions import Done, Erase, GetClue, NoOp, Write, parse_action
from src.agent.observation import AgentBoard
from src.agent.prompts import SYSTEM_PROMPT, build_user_message

LLM = Callable[[str, list[dict]], str]


def _apply(board: AgentBoard, action) -> tuple[str, bool]:
    """Apply one action to the board; return (feedback, stop)."""
    if isinstance(action, GetClue):
        slot = board.slot(action.number, action.direction)
        if slot is None:
            return f"No {action.number}-{action.direction} clue exists.", False
        return (
            f"{action.number}-{action.direction}: {slot.clue} — "
            f"{board.state_string(slot)}",
            False,
        )

    if isinstance(action, Write):
        ok, msg = board.write(action.word, action.x, action.y, action.direction)
        return ("OK: " if ok else "Rejected: ") + msg, False

    if isinstance(action, Erase):
        ok, msg = board.erase(action.x, action.y)
        return ("OK: " if ok else "Rejected: ") + msg, False

    if isinstance(action, Done):
        return "You declared the puzzle done.", True

    if isinstance(action, NoOp):
        return (
            "Could not parse an action. Emit exactly one, for example "
            "WRITE(APPLE, 1, 1) or GET_CLUE(1, across).",
            False,
        )

    return "Unknown action.", False


def run_agent(
    llm: LLM,
    board: AgentBoard,
    max_turns: int = 200,
    verbose: bool = False,
) -> dict:
    """Run the loop until completion, DONE, or max_turns.

    Returns a result dict with the final board, turn count, completion flag, and
    the full message transcript.
    """
    transcript: list[dict] = []
    feedback: str | None = "New puzzle. Read the clues and start filling answers."
    turns = 0

    for turn in range(1, max_turns + 1):
        turns = turn
        user_msg = build_user_message(board.render_observation(), feedback)
        transcript.append({"role": "user", "content": user_msg})

        reply = llm(SYSTEM_PROMPT, transcript)
        transcript.append({"role": "assistant", "content": reply})

        action = parse_action(reply)
        feedback, stop = _apply(board, action)

        if verbose:
            print(f"[turn {turn}] {reply.strip()!r} -> {feedback}")

        if stop or board.is_complete():
            break

    return {
        "board": board,
        "turns": turns,
        "complete": board.is_complete(),
        "transcript": transcript,
    }
