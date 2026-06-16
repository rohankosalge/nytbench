"""
A multi-agent crossword solver.

Where `src.agent.loop` runs a single model through one neutral prompt, this
package splits the work across four specialists that mirror how a human solves a
grid:

  - SyntaxExtractor — runs before the Sprinter; converts a raw clue into a strict
                      grammatical spec (part of speech, tense, plural, required
                      suffix) used as an absolute filter on candidate answers.
  - Sprinter        — first pass; only the gimmes, fill-in-the-blanks, and short
                      (<=4 letter) words. Refuses to guess.
  - PatternMatcher  — constraint pass; given a clue and a strict letter pattern
                      (e.g. "I P _ _ _") it retrieves the word that fits.
  - LateralThinker  — wordplay specialist; reasons step by step through clues
                      that end in "?", carry abbreviations, or signal a theme.
  - Eraser          — conflict resolver; when two crossing answers clash it
                      decides which is weaker (ambiguity, crosswordese) and
                      clears it.

The `MultiAgentSolver` orchestrates these over an `AgentBoard`, talking to the
model through the same model-agnostic callable the bare-bones loop uses:

    llm(system_prompt: str, messages: list[dict]) -> str
"""

from src.agent.multi.agents import (
    Eraser,
    LateralThinker,
    PatternMatcher,
    Proposal,
    Sprinter,
    SyntaxExtractor,
    SyntaxSpec,
)
from src.agent.multi.orchestrator import (
    MultiAgentSolver,
    run_episode,
    solve_puzzle,
)

__all__ = [
    "Eraser",
    "LateralThinker",
    "MultiAgentSolver",
    "PatternMatcher",
    "Proposal",
    "Sprinter",
    "SyntaxExtractor",
    "SyntaxSpec",
    "run_episode",
    "solve_puzzle",
]
