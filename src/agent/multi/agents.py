"""
The four specialist agents and the parsing of their replies.

Each solver agent (Sprinter, PatternMatcher, LateralThinker) wraps the same
model-agnostic callable and exposes `propose(...)` -> `Proposal`. The Eraser is
the odd one out: it returns a verdict (which crossing answer to clear) rather
than a word.

All agents share the compact answer protocol documented in
`src.agent.multi.prompts`, so a single parser handles every solver reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from src.agent.multi import prompts

LLM = Callable[[str, list[dict]], str]

_CONFIDENCE_LEVELS = ("high", "medium", "low")

_ANSWER_RE = re.compile(r"ANSWER:\s*['\"]?([A-Za-z]+)['\"]?", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*(high|medium|low)", re.IGNORECASE)
_ABSTAIN_RE = re.compile(r"\bABSTAIN\b", re.IGNORECASE)
_CLEAR_RE = re.compile(
    r"CLEAR:\s*(\d+)\s*[- ]?\s*(across|down)", re.IGNORECASE
)

_POS_RE = re.compile(
    r"PART_OF_SPEECH:\s*(noun|verb|adjective|adverb|other)", re.IGNORECASE
)
_TENSE_RE = re.compile(r"TENSE:\s*(present|past|none)", re.IGNORECASE)
_PLURAL_RE = re.compile(r"PLURAL:\s*(true|false)", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"REQUIRED_SUFFIX:\s*([A-Za-z-]+)", re.IGNORECASE)


@dataclass
class SyntaxSpec:
    """The strict grammatical shape a clue's answer must take.

    Produced by the Syntax Extractor before the Sprinter runs. `required_suffix`
    is the hard, machine-checkable filter (e.g. "S"); the rest guide the model.
    An all-default spec (the parse-failure case) imposes no constraints.
    """

    part_of_speech: str = "other"
    tense: str = "none"
    plural: bool = False
    required_suffix: str = ""  # uppercase letters only, no leading dash; "" = none
    raw: str = ""

    def describe(self) -> str:
        """Render the spec as constraint lines for a solver prompt."""
        suffix = f"-{self.required_suffix.lower()}" if self.required_suffix else "none"
        return (
            "Grammatical constraints (absolute filters):\n"
            f"  PART_OF_SPEECH: {self.part_of_speech}\n"
            f"  TENSE: {self.tense}\n"
            f"  PLURAL: {str(self.plural).lower()}\n"
            f"  REQUIRED_SUFFIX: {suffix}"
        )


def _clean_suffix(raw: str) -> str:
    """Normalize a reported suffix to bare uppercase letters; 'none' -> ''."""
    cleaned = raw.strip().lstrip("-").upper()
    if cleaned in ("", "NONE"):
        return ""
    return cleaned if cleaned.isalpha() else ""


def parse_syntax_spec(text: str) -> SyntaxSpec:
    """Parse a Syntax Extractor reply; unmatched fields fall back to defaults."""
    pos = _POS_RE.search(text)
    tense = _TENSE_RE.search(text)
    plural = _PLURAL_RE.search(text)
    suffix = _SUFFIX_RE.search(text)
    return SyntaxSpec(
        part_of_speech=pos.group(1).lower() if pos else "other",
        tense=tense.group(1).lower() if tense else "none",
        plural=(plural.group(1).lower() == "true") if plural else False,
        required_suffix=_clean_suffix(suffix.group(1)) if suffix else "",
        raw=text.strip(),
    )


def spec_allows(answer: str, spec: SyntaxSpec) -> tuple[bool, str]:
    """Hard structural check of an answer against a spec.

    Only the required suffix is enforced programmatically — it is the one
    constraint that is unambiguous from the letters alone. Returns (ok, reason).
    """
    if spec.required_suffix and not answer.upper().endswith(spec.required_suffix):
        return False, f"missing required suffix -{spec.required_suffix.lower()}"
    return True, ""


@dataclass
class Proposal:
    """One specialist's answer for a slot.

    `answer` is None when the agent abstains (or produced nothing parseable).
    `confidence` is one of high/medium/low, or "none" when abstaining.
    """

    answer: str | None
    confidence: str
    reasoning: str
    raw: str

    @property
    def committed(self) -> bool:
        return self.answer is not None


def parse_proposal(text: str) -> Proposal:
    """Parse a solver reply into a Proposal.

    An explicit ABSTAIN, or the absence of a parseable ANSWER, yields an
    abstaining proposal. Confidence defaults to "low" when an answer is given
    without a stated level — an unstated commitment is treated as a weak one.
    """
    raw = text.strip()

    answer_match = _ANSWER_RE.search(text)
    # A bare ABSTAIN with no answer means decline.
    if _ABSTAIN_RE.search(text) and not answer_match:
        return Proposal(None, "none", raw, raw)
    if not answer_match:
        return Proposal(None, "none", raw, raw)

    conf_match = _CONFIDENCE_RE.search(text)
    confidence = conf_match.group(1).lower() if conf_match else "low"
    return Proposal(
        answer=answer_match.group(1).upper(),
        confidence=confidence,
        reasoning=raw,
        raw=raw,
    )


def confidence_rank(confidence: str) -> int:
    """Numeric ordering for confidence; higher is stronger."""
    try:
        return _CONFIDENCE_LEVELS.index(confidence.lower()) + 1
    except ValueError:
        return 0


def _format_crossings(crossings: list[str]) -> str:
    if not crossings:
        return ""
    joined = "\n".join(f"  - {c}" for c in crossings)
    return f"\nCrossing answers already on the board:\n{joined}"


class _SolverAgent:
    """Common machinery for the three answer-producing specialists."""

    name = "solver"
    system = ""

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def _ask(self, user_message: str) -> Proposal:
        reply = self._llm(self.system, [{"role": "user", "content": user_message}])
        return parse_proposal(reply)


class SyntaxExtractor:
    """Converts a raw clue into a strict `SyntaxSpec` before the Sprinter runs."""

    name = "syntax"
    system = prompts.SYNTAX_EXTRACTOR_PROMPT

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def extract(self, clue: str, length: int) -> SyntaxSpec:
        message = f'Clue: "{clue}"\nAnswer length: {length} letters.'
        reply = self._llm(self.system, [{"role": "user", "content": message}])
        return parse_syntax_spec(reply)


class Sprinter(_SolverAgent):
    """First pass: gimmes, fill-in-the-blanks, and short words only."""

    name = "sprinter"
    system = prompts.SPRINTER_PROMPT

    def propose(
        self,
        clue: str,
        length: int,
        pattern: str | None = None,
        spec: SyntaxSpec | None = None,
    ) -> Proposal:
        lines = [
            f'Clue: "{clue}"',
            f"Answer length: {length} letters.",
        ]
        if pattern and pattern.replace("_", "").replace(" ", ""):
            lines.append(f"Pattern: {pattern}")
        if spec is not None:
            lines.append(spec.describe())
        return self._ask("\n".join(lines))


class PatternMatcher(_SolverAgent):
    """Constraint pass: fit a clue to a fixed letter pattern."""

    name = "pattern"
    system = prompts.PATTERN_MATCHER_PROMPT

    def propose(
        self,
        clue: str,
        length: int,
        pattern: str,
        crossings: list[str] | None = None,
    ) -> Proposal:
        message = (
            f'Clue: "{clue}"\n'
            f"Pattern: {pattern}\n"
            f"Answer length: {length} letters."
            f"{_format_crossings(crossings or [])}"
        )
        return self._ask(message)


class LateralThinker(_SolverAgent):
    """Wordplay pass: decode the trick, then fit the pattern."""

    name = "lateral"
    system = prompts.LATERAL_THINKER_PROMPT

    def propose(
        self,
        clue: str,
        length: int,
        pattern: str,
        crossings: list[str] | None = None,
    ) -> Proposal:
        message = (
            f'Clue: "{clue}"\n'
            f"Pattern: {pattern}\n"
            f"Answer length: {length} letters."
            f"{_format_crossings(crossings or [])}"
        )
        return self._ask(message)


@dataclass
class EraserVerdict:
    """The Eraser's decision: which slot to clear, or None if undecided."""

    clear_number: int | None
    clear_direction: str | None
    raw: str

    @property
    def key(self) -> tuple[int, str] | None:
        if self.clear_number is None or self.clear_direction is None:
            return None
        return (self.clear_number, self.clear_direction)


def parse_verdict(text: str) -> EraserVerdict:
    match = _CLEAR_RE.search(text)
    if not match:
        return EraserVerdict(None, None, text.strip())
    return EraserVerdict(int(match.group(1)), match.group(2).lower(), text.strip())


class Eraser:
    """Conflict resolver: picks the weaker of two clashing crossing answers."""

    name = "eraser"
    system = prompts.ERASER_PROMPT

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def decide(
        self,
        a_number: int,
        a_direction: str,
        a_clue: str,
        a_word: str,
        a_confidence: str,
        b_number: int,
        b_direction: str,
        b_clue: str,
        b_word: str,
        b_confidence: str,
        conflict_square: tuple[int, int],
    ) -> EraserVerdict:
        x, y = conflict_square
        message = (
            "Two crossing answers disagree at square "
            f"(x={x}, y={y}).\n\n"
            f"A) {a_number}-{a_direction}: \"{a_clue}\"\n"
            f"   proposed {a_word} (confidence {a_confidence})\n\n"
            f"B) {b_number}-{b_direction}: \"{b_clue}\"\n"
            f"   proposed {b_word} (confidence {b_confidence})\n\n"
            "Clear exactly one."
        )
        reply = self._llm(self.system, [{"role": "user", "content": message}])
        return parse_verdict(reply)
