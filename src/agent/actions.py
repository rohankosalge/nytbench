"""
The agent action space.

This module defines the rigid set of actions the LLM is allowed to emit, plus a
parser that turns a raw model response into one structured action object. It is
deliberately model-agnostic: the action syntax is plain function-call text that
any model can produce, with no provider-specific formatting.

Action syntax (case-insensitive keyword and direction):

    GET_CLUE(number, direction)      e.g.  GET_CLUE(1, across)
    WRITE(word, x, y)                e.g.  WRITE(APPLE, 1, 1)
    WRITE(word, x, y, direction)     e.g.  WRITE(ALOFT, 1, 1, down)
    ERASE(x, y)                      e.g.  ERASE(3, 2)
    DONE

Coordinate convention: x is the column (1..width), y is the row (1..height),
both 1-indexed with the origin at the top-left square.

WRITE direction defaults to "across" when omitted, so the three-argument form
behaves predictably; pass an explicit "down" to fill a Down answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class GetClue:
    number: int
    direction: str  # "across" | "down"


@dataclass
class Write:
    word: str
    x: int
    y: int
    direction: str = "across"  # "across" | "down"


@dataclass
class Erase:
    x: int
    y: int


@dataclass
class Done:
    """The agent declares the puzzle finished."""


@dataclass
class NoOp:
    """No valid action could be parsed from the model output."""

    raw: str


Action = GetClue | Write | Erase | Done | NoOp


# Patterns are anchored to the function-call form. Whitespace is flexible and
# the answer word may be optionally quoted.
_GET_CLUE = re.compile(
    r"GET_CLUE\s*\(\s*(\d+)\s*,\s*(across|down)\s*\)", re.IGNORECASE
)
_WRITE = re.compile(
    r"WRITE\s*\(\s*['\"]?([A-Za-z]+)['\"]?\s*,\s*(\d+)\s*,\s*(\d+)\s*"
    r"(?:,\s*(across|down)\s*)?\)",
    re.IGNORECASE,
)
_ERASE = re.compile(r"ERASE\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE)
_DONE = re.compile(r"\bDONE\b", re.IGNORECASE)


def parse_action(text: str) -> Action:
    """Return the first recognised action in `text`, or NoOp if none is found.

    WRITE is checked before GET_CLUE/ERASE because it is the most specific
    pattern; only one action is returned per call.
    """
    m = _WRITE.search(text)
    if m:
        direction = (m.group(4) or "across").lower()
        return Write(
            word=m.group(1).upper(),
            x=int(m.group(2)),
            y=int(m.group(3)),
            direction=direction,
        )

    m = _GET_CLUE.search(text)
    if m:
        return GetClue(number=int(m.group(1)), direction=m.group(2).lower())

    m = _ERASE.search(text)
    if m:
        return Erase(x=int(m.group(1)), y=int(m.group(2)))

    if _DONE.search(text):
        return Done()

    return NoOp(raw=text.strip())
