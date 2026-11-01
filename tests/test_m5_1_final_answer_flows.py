"""Tests for M5.1 — Final Answer flows.

Each test demonstrates one claim about how the agent stops immediately
when the model writes a 'Final Answer:' line. The loop should break, not
continue to the next iteration.
"""

from asa.agent import Agent, AgentResult
from asa.brain import MockBrain


def make_agent(script_list):
    """Create an agent with a scripted brain."""
    return Agent(MockBrain(script=script_list), narrate=False, max_steps=5)


def test_final_answer_stops_loop_immediately():
    """Demonstrates: when model writes Final Answer:, the loop ends instantly.

    Why it matters: the agent should not keep calling the brain after
    seeing 'Final Answer:'; it must stop the run and return the answer.
    """
    # Model writes Final Answer on the FIRST turn
    agent = make_agent(["Thought: done\nFinal Answer: 42"])
    result = agent.run("any task")
    assert result.terminate_reason == "final_answer"
    assert result.text == "42"
    assert result.steps == 1  # should not increment after final answer


def test_final_answer_still_counts_as_a_step():
    """Demonstrates: Final Answer consumes the turn count, but loop stops.

    Why it matters: the step budget is the primary guard; seeing a Final
    Answer in step N ends the run, regardless of remaining budget.
    """
    # Model writes Final Answer on the SECOND turn (after a non-answer)
    agent = make_agent(["Hello", "Thought: final\nFinal Answer: 99"])
    result = agent.run("task")
    assert result.terminate_reason == "final_answer"
    assert result.text == "99"
    assert result.steps == 2  # step 1 was the "Hello", step 2 had Final Answer


def test_final_answer_takes_precedence_over_max_steps():
    """Demonstrates: even with many steps left, Final Answer stops the run.

    Why it matters: the answer is complete; further brain calls would be
    redundant. The agent must not waste steps after seeing a Final Answer.
    """
    # Model writes Final Answer early, but max_steps is large
    agent = make_agent(["Thought: done\nFinal Answer: answer", "wasted reply"])
    result = agent.run("task")
    assert result.terminate_reason == "final_answer"
    assert result.text == "answer"
    assert result.steps == 1  # should stop immediately, not call brain again


def test_final_answer_respects_memory_and_reporting():
    """Demonstrates: Final Answer leaves proper trace in memory and reports.

    Why it matters: the run's bookkeeping (tokens, steps, reason) must be
    honest; the answer should be exactly what the model wrote.
    """
    agent = make_agent(["Thought: reasoning\nFinal Answer: 3.14"])
    result = agent.run("calculate pi")
    assert result.terminate_reason == "final_answer"
    assert result.text == "3.14"
    assert result.steps == 1
    assert result.tokens == agent.memory.token_count()
    # Verify memory contains the assistant turn with Final Answer
    assert any("Final Answer: 3.14" in m.content for m in agent.memory.messages)