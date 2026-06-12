"""
LangGraph-based agent orchestrator.

Implements a ReAct loop: the LLM reasons over the current board observation,
selects an action from the rigid action space, the environment executes it,
and the result is appended to the message history.

The graph topology is:
    [START] -> agent_node -> action_node -> agent_node -> ... -> [END]
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from src.agent.actions import parse_action
from src.agent.prompts import build_system_prompt
from src.environment.simulator import CrosswordEnv


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    observation: dict
    done: bool
    total_turns: int
    total_tool_calls: int


def build_graph(llm, env: CrosswordEnv, max_turns: int = 200):
    """Construct and compile the LangGraph agent graph."""
    system_prompt = build_system_prompt(env.puzzle)

    def agent_node(state: AgentState) -> dict:
        from langchain_core.messages import SystemMessage

        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response: AIMessage = llm.invoke(messages)
        return {
            "messages": [response],
            "total_turns": state["total_turns"] + 1,
        }

    def action_node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]
        action = parse_action(last_msg.content)

        tool_calls = state["total_tool_calls"]
        if action.get("type") in {"GET_CLUE"} or action.get("uses_tool"):
            tool_calls += 1

        obs, _reward, done, info = env.step(action)

        result_text = _format_result(action, obs, info)
        return {
            "messages": [HumanMessage(content=result_text)],
            "observation": obs,
            "done": done,
            "total_tool_calls": tool_calls,
        }

    def should_continue(state: AgentState) -> str:
        if state["done"] or state["total_turns"] >= max_turns:
            return END
        return "action_node"

    graph = StateGraph(AgentState)
    graph.add_node("agent_node", agent_node)
    graph.add_node("action_node", action_node)
    graph.add_edge(START, "agent_node")
    graph.add_conditional_edges("agent_node", should_continue)
    graph.add_edge("action_node", "agent_node")
    return graph.compile()


def run_episode(llm, env: CrosswordEnv, max_turns: int = 200) -> dict:
    """Run a full benchmark episode and return the episode result dict."""
    obs = env.reset()
    graph = build_graph(llm, env, max_turns)

    init_state: AgentState = {
        "messages": [HumanMessage(content=_format_obs(obs))],
        "observation": obs,
        "done": False,
        "total_turns": 0,
        "total_tool_calls": 0,
    }

    final_state = graph.invoke(init_state)
    return {
        "grid": final_state["observation"]["grid"],
        "turns": final_state["total_turns"],
        "tool_calls": final_state["total_tool_calls"],
        "done": final_state["done"],
    }


def _format_obs(obs: dict) -> str:
    unsolved_a = ", ".join(str(n) for n in sorted(obs["unsolved_across"]))
    unsolved_d = ", ".join(str(n) for n in sorted(obs["unsolved_down"]))
    return (
        f"Current board updated.\n"
        f"Unsolved Across: {unsolved_a or 'none'}\n"
        f"Unsolved Down:   {unsolved_d or 'none'}\n"
    )


def _format_result(action: dict, obs: dict, info: dict) -> str:
    parts = []
    if "clue" in info:
        parts.append(f"Clue: {info['clue']}")
    if "error" in info:
        parts.append(f"Error: {info['error']}")
    parts.append(_format_obs(obs))
    return "\n".join(parts)
