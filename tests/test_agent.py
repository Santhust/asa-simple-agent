"""Tests for asa.agent.Agent — the orchestration around a brain.

Each test pins down one claim about procedure: what the brain actually sees, what gets
memorized, how the step budget guards the loop, and how the outcome (AgentResult) is
reported separately from the answer.
"""

import pytest

from asa.agent import Agent, AgentResult
from asa.brain import MockBrain


def make_agent(brain=None, **kwargs):
    return Agent(brain or MockBrain(), narrate=False, **kwargs)


def test_run_returns_agent_result():
    """Demonstrates: run() returns the structured outcome, not a bare string.

    Why it matters: the caller needs to know BOTH the answer and how the loop ended;
    folding status into the answer text would pollute model output (M2.3 discussion).
    """
    result = make_agent(MockBrain(script=["Hello."])).run("hi")
    assert isinstance(result, AgentResult)


class RecordingBrain(MockBrain):
    """A MockBrain that also keeps a copy of every transcript it was handed.

    MockBrain.last_params only captures the completion params, not the messages —
    recording the transcript is the honest way to assert what the brain saw.
    """

    def complete(self, messages, **params):
        self.seen_messages = list(messages)
        return super().complete(messages, **params)


def test_agent_result_fields_one_shot():
    """Demonstrates: text/steps/tokens/reason are correct for a single one-shot."""
    agent = make_agent(MockBrain(script=["Thought: done\nFinal Answer: Hi there."]))
    result = agent.run("say hi")
    assert result.text == "Hi there."
    assert result.steps == 1
    assert result.tokens == agent.memory.token_count()
    assert result.terminate_reason == "final_answer"


def test_brain_receives_system_then_task():
    """Demonstrates: the brain sees the system prompt first, then the task as user.

    Why it matters: the transcript order (standing instructions, then request) is
    exactly what the model depends on for context — this is the agent's only job
    before the loop starts doing real work.
    """
    brain = RecordingBrain(script=["ok"])
    agent = make_agent(brain)
    agent.run("count to ten")
    roles = [m.role for m in brain.seen_messages]
    assert roles == ["system", "user"]
    # M3.5: the bare system text now heads the COMPOSED prompt, which also
    # carries the tool catalogue — so equality becomes a prefix check:
    assert brain.seen_messages[0].content.startswith(
        "You are 'asa', a teaching agent built from scratch."
    )
    assert "## Available tools" in brain.seen_messages[0].content
    assert brain.seen_messages[1].content == "count to ten"


def test_assistant_turn_recorded_in_memory():
    """Demonstrates: the brain's reply is stored back as an assistant turn."""
    agent = make_agent(MockBrain(script=["Thought: done\nFinal Answer: the reply"]))
    result = agent.run("go")
    assert [m.role for m in agent.memory.messages] == ["system", "user", "assistant"]
    assert agent.memory.messages[-1].content == "Thought: done\nFinal Answer: the reply"
    assert result.text == "the reply"


def test_max_steps_guard_limits_brain_calls():
    """Demonstrates: the loop runs at most max_steps times, then stops.

    Why it matters: without a budget a runaway loop calls the brain forever; the
    guard limits iterations (M5 tightens control semantics).
    """
    brain = MockBrain(script=["one", "two", "three"])
    result = make_agent(brain, max_steps=3).run("task")
    assert brain.call_count == 3
    assert result.steps == 3


def test_terminate_reason_is_max_steps_in_m2():
    """Demonstrates the documented sentinel: M2 always ends on the step budget.

    Why it matters: this is the seam for M5 — 'final_answer' becomes the normal exit;
    until then every run honestly reports it was cut off by the budget.
    """
    result = make_agent(MockBrain(script=["x"]), max_steps=1).run("t")
    assert result.terminate_reason == "max_steps"


def test_swapability_same_agent_code_different_brains():
    """Demonstrates: the same Agent class works unchanged with any Brain.

    Why it matters: THIS is the project's core lesson — a model is a text-in/text-out
    box. Scripted (deterministic) and default (canned) MockBrains differ in output
    but not in how the agent drives them.
    """
    scripted = make_agent(MockBrain(script=["Thought: done\nFinal Answer: scripted answer"]))
    canned = make_agent(MockBrain())
    assert scripted.run("q").text == "scripted answer"
    # canned may produce ReAct or not; just ensure swapability works
    res = canned.run("q")
    assert res is not None
    assert len(canned.memory.messages) >= 3


def test_run_twice_grows_memory():
    """Demonstrates: one agent = one session — memory persists across run() calls.

    Why it matters: the ContextWindow outlives a single task, which is what allows
    follow-up turns later (and is what trim() will have to manage).
    """
    brain = MockBrain(script=["Thought: done\nFinal Answer: first reply", "Thought: done\nFinal Answer: second reply"])
    agent = make_agent(brain)
    r1 = agent.run("question one")
    r2 = agent.run("question two")
    assert r1.text == "first reply"
    assert r2.text == "second reply"
    assert [m.role for m in agent.memory.messages] == [
        "system", "user", "assistant", "user", "assistant",
    ]
    assert agent.step_count == 2


def test_tokens_reported():
    """Demonstrates: AgentResult.tokens equals the live memory accounting."""
    agent = make_agent(MockBrain(script=["Thought: done\nFinal Answer: yep"]))
    result = agent.run("a short task")
    assert result.tokens == agent.memory.token_count()
    assert result.tokens > 0


def test_rejects_max_steps_zero():
    """Demonstrates: a degenerate step budget is refused at construction time."""
    with pytest.raises(ValueError):
        make_agent(max_steps=0)