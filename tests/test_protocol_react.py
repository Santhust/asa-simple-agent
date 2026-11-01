"""Tests for asa.protocol_react — the reader.

Each test demonstrates one idea: text → structure, values safely parsed (no
eval), broken letters give gentle notes (failure is data), Final Answer is its
own verdict. These pin the grammar so M4.5 (teach the format) and M4.6 (flip
the seam) stay honest.
"""

from asa.protocol_react import parse
from asa.tool import ToolCall


def test_happy_path_thought_action_input():
    """Demonstrates: a good letter becomes a command (ToolCall).

    Why it matters: this is the first time the agent can read what it wrote.
    The reader is pure/deterministic; no brain or tools involved.
    """
    text = """Thought: I should compute 2+2.
Action: calculator
Action Input: expression='2+2'
"""
    result = parse(text)
    assert result.kind == "thought_action"
    assert isinstance(result.action, ToolCall)
    assert result.action.name == "calculator"
    assert result.action.args == {"expression": "2+2"}


def test_happy_path_json_action_input():
    """Demonstrates: JSON dict is also accepted for Action Input.

    Why it matters: some models prefer JSON; being lenient (without eval)
    keeps the reader practical while still safe.
    """
    text = "Thought: add\nAction: notes_write\nAction Input: {\"text\": \"hello\"}\n"
    result = parse(text)
    assert result.kind == "thought_action"
    assert result.action.name == "notes_write"
    assert result.action.args == {"text": "hello"}


def test_args_no_eval_numbers_and_bools():
    """Demonstrates: values parsed safely via literal_eval, not eval().

    Why it matters: mirrors M3's 'no eval' stance; booleans/ints/floats
    come through as Python values correctly.
    """
    text = "Thought: x\nAction: something\nAction Input: count=3, enabled=true, ratio=1.5\n"
    result = parse(text)
    assert result.kind == "thought_action"
    assert result.action.args["count"] == 3
    assert result.action.args["enabled"] is True
    assert result.action.args["ratio"] == 1.5


def test_broken_missing_action_input_gives_gentle_note():
    """Demonstrates: damage is not a crash — it's a note back to the model.

    Why it matters: failure is data (same as ToolResult.is_error). The agent
    can put this note into memory so the model can retry.
    """
    text = "Thought: hmm\nAction: calculator\n"
    result = parse(text)
    assert result.kind == "error"
    assert result.error is not None
    assert "Action Input" in result.error.message


def test_broken_missing_action_gives_gentle_note():
    """Demonstrates: saw Action Input without Action -> gentle correction."""
    text = "Thought: oops\nAction Input: expression='1+1'\n"
    result = parse(text)
    assert result.kind == "error"
    assert "Action:" in result.error.message


def test_broken_thought_only_gives_gentle_note():
    """Demonstrates: thinking aloud with no action and no answer is not valid."""
    text = "Thought: I need to think more...\n"
    result = parse(text)
    assert result.kind == "error"
    assert result.error is not None


def test_final_answer_is_its_own_verdict():
    """Demonstrates: 'Final Answer:' ends the run (third verdict).

    Why it matters: vocabulary ready for M5's control layer without
    conflating 'answer' with 'command'.
    """
    text = "Thought: done.\nFinal Answer: The result is 42.\n"
    result = parse(text)
    assert result.kind == "final_answer"
    assert result.answer == "The result is 42."


def test_empty_reply_is_gentle_error():
    """Demonstrates: empty/whitespace -> gentle note, never crash."""
    result = parse("")
    assert result.kind == "error"
    result2 = parse("   \n\n  ")
    assert result2.kind == "error"
