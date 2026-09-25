"""Tests for the Tool abstraction — proving the three M3.1 lessons.

Each test names the lesson it demonstrates and why it matters for the agent loop
that M4/M5 will build on top of this.
"""

import pytest

from asa.tool import Tool, ToolCall, ToolResult, validate_args


def _adder() -> Tool:
    """A tiny well-behaved tool: adds two numbers."""

    def add(a: float, b: float) -> ToolResult:
        return ToolResult(output=f"{a} + {b} = {a + b}")

    return Tool(
        name="add",
        description="Add two numbers.",
        params={
            "a": {"type": "number", "required": True, "help": "first addend"},
            "b": {"type": "number", "required": True, "help": "second addend"},
        },
        func=add,
    )


def test_valid_args_run_the_function_and_return_its_answer():
    """Demonstrates the happy path: a documented call produces a ToolResult.

    Why it matters: this is the ONLY behavior the loop will rely on in M4/M5 —
    if a correct call cannot reach the function, nothing else in the design
    matters.
    """
    result = _adder().run({"a": 2, "b": 3})
    assert result.is_error is False
    assert result.output == "2.0 + 3.0 = 5.0"  # ints normalized to float by the boundary


def test_missing_required_argument_is_a_readable_error_not_an_exception():
    """Demonstrates failure-as-data: a missing required arg returns an error result.

    Why it matters: real models forget arguments. The agent must survive that
    and hand the model a message it can act on, not crash.
    """
    result = _adder().run({"a": 2})
    assert result.is_error is True
    assert "b is required" in result.output
    assert "second addend" in result.output  # the help text travels with the error


def test_wrong_type_is_rejected_before_the_function_ever_runs():
    """Demonstrates validate-before-execute.

    Why it matters: a tool that mutates state must never half-run on garbage
    input. The spy proves validation happens BEFORE func is called.
    """
    calls: list[dict] = []

    def spy(**kwargs) -> ToolResult:
        calls.append(kwargs)
        return ToolResult(output="should never happen")

    tool = Tool(name="spy", description="records calls", params=_adder().params, func=spy)
    result = tool.run({"a": 1, "b": "two"})

    assert result.is_error is True
    assert "expected a number" in result.output
    assert calls == [], "the function must not be entered on invalid input"


def test_unknown_argument_is_rejected_and_lists_what_is_allowed():
    """Demonstrates typo-guarding — the most common real-world model mistake.

    Why it matters: models invent plausible parameter names ('expr' for
    'expression'). Failing loudly with the allowed set is how the model can
    self-correct on the next turn instead of silently getting wrong data.
    """
    result = _adder().run({"a": 1, "b": 2, "c": 3})
    assert result.is_error is True
    assert "unknown argument 'c'" in result.output
    assert "a, b" in result.output  # tells the model what it may pass


def test_a_function_that_raises_becomes_an_error_result_not_a_crash():
    """Demonstrates the safety net around func.

    Why it matters: a tool's own bug (ZeroDivisionError, KeyError, whatever)
    must not take the agent down. The message keeps the exception type so a
    developer can debug, while the agent stays alive.
    """
    def boom(**kwargs) -> ToolResult:
        raise ZeroDivisionError("division by zero")

    tool = Tool(name="boom", description="always explodes", params={}, func=boom)
    result = tool.run()

    assert result.is_error is True
    assert "ZeroDivisionError" in result.output
    assert "division by zero" in result.output


def test_number_accepts_int_and_float_and_coerces_to_float():
    """Demonstrates the 'number' type rule.

    Why it matters: models emit 2 where we documented "number" and 2.0 where we
    documented nothing in particular. Accepting both and normalizing keeps the
    function's arithmetic honest (no int/float surprises) without the model
    having to guess a format.
    """
    result = _adder().run({"a": 2, "b": 3.5})
    assert result.is_error is False
    assert result.output == "2.0 + 3.5 = 5.5"  # coerced to float, so a+b reads float


def test_bool_is_not_accepted_as_a_number():
    """Demonstrates a Python subtlety that would otherwise bite us.

    Why it matters: in Python `True` IS an int, so a naive isinstance check
    would happily accept a flag as the number 1. We reject bool-as-number
    explicitly, because a model sending `true` where a number is documented is
    confused, and we would rather tell it so.
    """
    result = _adder().run({"a": True, "b": 1})
    assert result.is_error is True
    assert "expected a number" in result.output


def test_validate_args_returns_empty_list_for_a_clean_call():
    """Demonstrates the validator's contract in isolation.

    Why it matters: an empty list means 'safe to execute' — that literal
    meaning is what Tool.run() and (later) the registry rely on.
    """
    tool = _adder()
    assert validate_args(tool.params, {"a": 1, "b": 2}) == []


def test_a_function_returning_the_wrong_type_is_caught():
    """Demonstrates the 'badly-behaved tool' guard.

    Why it matters: ToolResult is the contract between a tool and the loop. A
    tool that returns a bare string instead would otherwise blow up deep in the
    agent, far from the actual mistake. We catch it at the boundary.
    """
    def wrong(**kwargs):
        return "just a string, not a ToolResult"

    tool = Tool(name="wrong", description="misbehaves", params={}, func=wrong)  # type: ignore[arg-type]
    result = tool.run()
    assert result.is_error is True
    assert "expected ToolResult" in result.output


def test_toolcall_is_plain_comparable_vocabulary():
    """Demonstrates that ToolCall is a plain, comparable value.

    Why it matters: both protocols (textual ReAct and native function-calling)
    must produce identical objects so the core loop is protocol-agnostic. That
    only works if ToolCall is a boring dataclass with value equality — this
    test pins that down before M4/M9 depend on it.
    """
    a = ToolCall(name="add", args={"a": 1, "b": 2})
    b = ToolCall(name="add", args={"a": 1, "b": 2})
    assert a == b
    assert a.render() == "add({'a': 1, 'b': 2})"
    assert a.name == "add" and a.args == {"a": 1, "b": 2}
