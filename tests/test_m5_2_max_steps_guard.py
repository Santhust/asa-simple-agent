"""Tests for M5.2 — max_steps guard policy.

Each test demonstrates how the step budget guards the loop and becomes the
primary termination control. Final Answer can still end earlier, but without
it, the agent must stop when steps run out.
"""

from asa.agent import Agent, AgentResult
from asa.brain import MockBrain


def make_agent(script_list, max_steps=3):
    """Create an agent with a scripted brain and explicit max_steps."""
    return Agent(MockBrain(script=script_list), narrate=False, max_steps=max_steps)


def test_max_steps_stops_loop_even_with_more_replies():
    """Demonstrates: when step budget exhausted, loop stops regardless.

    Why it matters: the step guard is the primary termination control;
    even with many model replies left, the agent must stop when budget runs out.
    """
    # Max steps = 2, but model has 3 plain replies (thoughts)
    agent = make_agent(["Thought: first", "Thought: second", "Thought: third"], max_steps=2)
    result = agent.run("task")
    assert result.terminate_reason == "max_steps"
    # The agent stops after 2 steps, the last assistant turn is "Thought: second"
    assert any("Thought: second" in m.content for m in agent.memory.messages if m.role == "assistant")
    assert result.steps == 2  # should have called brain twice


def test_max_steps_zero_is_refused():
    """Demonstrates: degenerate step budget is rejected at construction.

    Why it matters: zero steps is an invalid configuration; the agent
    constructor must refuse it.
    """
    from asa.agent import Agent
    import pytest

    with pytest.raises(ValueError):
        Agent(MockBrain(), max_steps=0)


def test_tools_run_because_steps_remain():
    """Demonstrates: with steps left, the agent reads and runs tools.

    Why it matters: the step guard is a brake, not a blanket stop; the
    agent should act when it has budget.
    """
    # Max steps = 3, model writes Final Answer early
    agent = make_agent(["Thought: done\nFinal Answer: answer", "wasted", "also wasted"], max_steps=3)
    result = agent.run("task")
    assert result.terminate_reason == "final_answer"
    assert result.text == "answer"
    assert result.steps == 1  # stopped early due to Final Answer


def test_max_steps_respects_tool_run_steps():
    """Demonstrates: each tool run consumes a step.

    Why it matters: the step budget is per loop iteration, not per
    tool call. The guard counts loop turns, not operations.
    """
    # Model writes Action that runs tool, counts as one step
    agent = make_agent(["Thought: add\nAction: calculator\nAction Input: expression='2+2'"], max_steps=1)
    result = agent.run("task")
    assert result.terminate_reason == "max_steps"  # no Final Answer, budget exhausted
    assert result.steps == 1  # one loop turn, tool ran
    # Memory should contain the Observation from the tool
    assert any("Observation:" in m.content for m in agent.memory.messages)


def test_max_steps_still_allows_loop_continuation_with_tools():
    """Demonstrates: agent can run multiple tools if steps allow.

    Why it matters: the loop is designed for multi-step reasoning; the
    step guard should not prevent normal tool-driven workflows.
    """
    # Max steps = 3, model writes 3 Actions that run tools
    agent = make_agent([
        "Thought: first\nAction: calculator\nAction Input: expression='1+1'",
        "Thought: second\nAction: calculator\nAction Input: expression='2+2'",
        "Thought: third\nAction: calculator\nAction Input: expression='3+3'",
    ], max_steps=3)
    result = agent.run("task")
    assert result.terminate_reason == "max_steps"
    assert result.steps == 3  # all three tool runs
    # When max_steps is reached, result.text is the last assistant content
    # which is the third Action (the tool call, not the tool result)
    assert any("Action: calculator" in m.content and "expression='3+3'" in m.content for m in agent.memory.messages if m.role == "assistant")
    # Memory should contain 3 tool Observations (user messages with Observation: prefix)
    tool_observations = [m for m in agent.memory.messages if m.role == "user" and "Observation:" in m.content]
    assert len(tool_observations) == 3