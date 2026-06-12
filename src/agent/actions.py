"""
Parses raw LLM text output into structured action dicts.

Supported action types (case-insensitive):
  GET_CLUE <direction> <number>
  WRITE    <direction> <number> <answer>
  ERASE    <direction> <number>
  TOOL     search|define "<query>"
  DONE
"""

import re
from typing import Any

_GET_CLUE = re.compile(
    r"GET_CLUE\s+(across|down)\s+(\d+)", re.IGNORECASE
)
_WRITE = re.compile(
    r"WRITE\s+(across|down)\s+(\d+)\s+([A-Za-z]+)", re.IGNORECASE
)
_ERASE = re.compile(
    r"ERASE\s+(across|down)\s+(\d+)", re.IGNORECASE
)
_TOOL = re.compile(
    r'TOOL\s+(search|define)\s+"([^"]+)"', re.IGNORECASE
)
_DONE = re.compile(r"\bDONE\b", re.IGNORECASE)


def parse_action(text: str) -> dict[str, Any]:
    """Extract the first valid action from an LLM response string.

    Returns a dict with at least {"type": <str>}.
    Falls back to {"type": "NOOP"} when no action is recognised.
    """
    m = _WRITE.search(text)
    if m:
        return {
            "type": "WRITE",
            "direction": m.group(1).lower(),
            "number": int(m.group(2)),
            "answer": m.group(3).upper(),
        }

    m = _GET_CLUE.search(text)
    if m:
        return {
            "type": "GET_CLUE",
            "direction": m.group(1).lower(),
            "number": int(m.group(2)),
        }

    m = _ERASE.search(text)
    if m:
        return {
            "type": "ERASE",
            "direction": m.group(1).lower(),
            "number": int(m.group(2)),
        }

    m = _TOOL.search(text)
    if m:
        return {
            "type": "TOOL",
            "tool": m.group(1).lower(),
            "query": m.group(2),
            "uses_tool": True,
        }

    if _DONE.search(text):
        return {"type": "DONE"}

    return {"type": "NOOP"}
