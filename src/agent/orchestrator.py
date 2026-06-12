"""
Placeholder for the future LangGraph orchestrator.

The current milestone uses a bare-bones loop (see `src.agent.loop.run_agent`)
rather than a LangGraph state machine. This module is kept as a stub so the
package layout matches the planned architecture; the LangGraph graph will live
here once the simple loop is validated.

Design note: whatever lands here must stay model-agnostic. The orchestration
talks to the model through a single generic callable and uses the neutral,
literal prompts in `src.agent.prompts` — no provider-specific formatting and no
model-specific prompt engineering.
"""

from __future__ import annotations

_NOT_BUILT = (
    "The LangGraph orchestrator is not built yet. Use "
    "src.agent.loop.run_agent for the current bare-bones loop."
)


def build_graph(*args, **kwargs):
    raise NotImplementedError(_NOT_BUILT)


def run_episode(*args, **kwargs):
    raise NotImplementedError(_NOT_BUILT)
