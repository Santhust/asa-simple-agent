"""Tests for M5.3 — golden-trace tests.

Each test records a perfect run for documentation and M11 docs.
The golden trace should be deterministic and useful for teaching.
"""

from asa.agent import Agent, AgentResult
from asa.brain import MockBrain


def make_golden_agent(script, max_steps=1):
    """Create an agent with a script that produces a golden trace."""
    return Agent(MockBrain(script=script), narrate=False, max_steps=max_steps)


def test_golden_trace_single_tool_call():
    """Demonstrates: a perfect single-tool run can be recorded.

    Why it matters: golden traces are the foundation for M11 documentation.
    This trace shows a clean, deterministic workflow.
    """
    # Perfect workflow: one tool call, no errors, max_steps=1 to stop immediately
    agent = make_golden_agent([
        "Thought: calculate total\nAction: calculator\nAction Input: expression='42'",
    ], max_steps=1)
    result = agent.run("total")
    # Record the golden trace
    golden_trace = {
        "steps": result.steps,
        "terminate_reason": result.terminate_reason,
        "text": result.text,
        "memory": [
            {"role": m.role, "content": m.content}
            for m in agent.memory.messages
        ],
    }
    # Verify it's a clean success
    assert golden_trace["terminate_reason"] == "max_steps"
    assert golden_trace["steps"] == 1
    assert golden_trace["text"] == "Observation: 42 = 42"
    assert len(golden_trace["memory"]) == 4  # system + user(task) + assistant + user(obs)
    print("Golden trace recorded:", golden_trace)


def test_golden_trace_multi_tool_with_final_answer():
    """Demonstrates: a perfect multi-step workflow with Final Answer.

    Why it matters: golden traces should include both tool-using and
    final-answer patterns, showing complete agent capabilities.
    """
    # Perfect workflow: tools + Final Answer
    agent = make_golden_agent([
        "Thought: first step\nAction: calculator\nAction Input: expression='10+10'",
        "Thought: second step\nAction: calculator\nAction Input: expression='5*2'",
        "Thought: done\nFinal Answer: 20 + 10 = 30",
    ], max_steps=3)
    result = agent.run("compute")
    golden_trace = {
        "steps": result.steps,
        "terminate_reason": result.terminate_reason,
        "text": result.text,
        "memory": [
            {"role": m.role, "content": m.content}
            for m in agent.memory.messages
        ],
    }
    # Verify it's a clean success
    assert golden_trace["terminate_reason"] == "final_answer"
    assert golden_trace["steps"] == 3
    assert golden_trace["text"] == "20 + 10 = 30"
    assert len(golden_trace["memory"]) == 7  # system + user + 2*(assistant + user) + assistant
    print("Golden trace recorded:", golden_trace)


def test_golden_trace_broken_letter_handled_gracefully():
    """Demonstrates: golden traces should include error recovery.

    Why it matters: showing how the agent handles malformed input is
    valuable for teaching failure modes.
    """
    # Workflow: model makes mistake, gets gentle note, corrects and succeeds
    agent = make_golden_agent([
        "Thought: add\nAction: calculator\n",  # missing Action Input
        "Thought: I need arguments\nAction: calculator\nAction Input: expression='3+4'",
        "Thought: done\nFinal Answer: 7",
    ], max_steps=3)
    result = agent.run("sum")
    golden_trace = {
        "steps": result.steps,
        "terminate_reason": result.terminate_reason,
        "text": result.text,
        "memory": [
            {"role": m.role, "content": m.content}
            for m in agent.memory.messages
        ],
    }
    # Verify error recovery happened
    assert golden_trace["terminate_reason"] == "final_answer"
    assert golden_trace["steps"] == 3
    assert golden_trace["text"] == "7"
    # Memory should show the progression: mistake → correction → success
    assistant_contents = [m.content for m in agent.memory.messages if m.role == "assistant"]
    assert any("Action: calculator" in content and "Action Input" not in content for content in assistant_contents)
    assert any("Action: calculator" in content and "expression='3+4'" in content for content in assistant_contents)
    print("Golden trace recorded:", golden_trace)


def test_golden_trace_multiple_agents_same_task():
    """Demonstrates: golden traces can be compared across brain types.

    Why it matters: M5.3 prepares for M7/M8 where different brains
    (Mock, Ollama, Gemini) produce different traces for same task.
    """
    # Create two agents with same script but different narrations
    agent1 = make_golden_agent([
        "Thought: compute\nAction: calculator\nAction Input: expression='6+8'",
    ])
    agent2 = make_golden_agent([
        "Thought: compute\nAction: calculator\nAction Input: expression='6+8'",
    ])
    result1 = agent1.run("compute")
    result2 = agent2.run("compute")
    
    # Golden traces should be identical for same brain (MockBrain)
    assert result1.terminate_reason == result2.terminate_reason
    assert result1.text == result2.text
    assert result1.steps == result2.steps
    print("Golden trace comparison:", result1.terminate_reason, result2.terminate_reason)