#!/usr/bin/env python3
"""lab/tool_lab.py — poke ONE internal: what happens when a tool is called?

Run it:  python lab/tool_lab.py

Everything else in asa narrates a full agent run. This script goes the other way:
it takes a single ToolCall and shows, beat by beat, exactly what the agent does
with it — validate, execute, report. Five calls, five outcomes:

  1. a good call          -> the function's own answer
  2. a missing argument   -> a readable error, nothing executed
  3. a wrong-typed one    -> a readable error, nothing executed
  4. an invented argument -> a readable error that lists what IS allowed
  5. a function that raises -> caught, reported, and the lab carries on

That last pair is the point of the whole module. In M4 the model will be handed
these error strings and can correct itself on the next turn — the agent is never
the thing that dies.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asa import narrate as N  # noqa: E402
from asa.tool import Tool, ToolCall, ToolResult  # noqa: E402


def divider(step: int, title: str) -> None:
    N.h2(f"{step} · {title}")


def build_calc() -> Tool:
    """A tiny 'tool' that is a real one in every way that matters."""

    def calculate(expression: str) -> ToolResult:
        # Deliberately not using eval() — we evaluate ONE arithmetic expression
        # with a tiny recursive-descent parser instead (a lab-scale simplifier).
        node = _Parser(expression).parse()
        if node is None:
            return ToolResult(
                output=f"I can only read arithmetic like '2*(3+4)'. Try a number: {expression}",
                is_error=True,
            )
        return ToolResult(output=f"{expression} = {node}")

    return Tool(
        name="calculate",
        description="Evaluate a simple arithmetic expression, e.g. '2*(3+4)'.",
        params={"expression": {"type": "string", "required": True, "help": "the arithmetic to do"}},
        func=calculate,
    )


class _Parser:
    """A deliberately tiny arithmetic evaluator: numbers, + - * / and parentheses.

    It exists so the lab can show a *stateful-looking* success with a *safe*
    implementation. (A real Calculator tool in M3.3 will live in asa/tools/.)
    """

    def __init__(self, text: str) -> None:
        self.text = text.replace(" ", "")
        self.i = 0

    def parse(self) -> float | int | None:
        try:
            value = self._expr()
            return value if self.i == len(self.text) else None
        except (ValueError, ZeroDivisionError, IndexError):
            return None

    def _expr(self) -> float | int:
        value = self._term()
        while self.i < len(self.text) and self.text[self.i] in "+-":
            op = self.text[self.i]
            self.i += 1
            rhs = self._term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def _term(self) -> float | int:
        value = self._atom()
        while self.i < len(self.text) and self.text[self.i] in "*/":
            op = self.text[self.i]
            self.i += 1
            rhs = self._atom()
            value = value * rhs if op == "*" else value / rhs
        return value

    def _atom(self) -> float | int:
        char = self.text[self.i]
        if char == "(":
            self.i += 1
            value = self._expr()
            self.i += 1  # skip ')'
            return value
        if char == "-":
            self.i += 1
            return -self._atom()
        start = self.i
        while self.i < len(self.text) and self.text[self.i].isdigit():
            self.i += 1
        if start == self.i:
            raise ValueError("expected a number")
        return int(self.text[start:self.i])


def main() -> None:
    N.h1("asa lab · Tool — the shape of a hand")
    N.why(
        "A model can only say words. A Tool is how those words touch the world. "
        "Watch what the agent does with ONE call at a time."
    )

    calc = build_calc()
    N.kv("tool", repr(calc))
    N.kv("documented params", calc.params)
    print()

    def attempt(step: int, title: str, call: ToolCall) -> None:
        divider(step, title)
        N.kv("the call", call.render())
        N.info(f"  the agent validates first, executes second: {call.name}"
               f"({', '.join(f'{k}={v!r}' for k, v in call.args.items()) or 'no arguments'})")
        result = calc.run(call.args)
        if result.is_error:
            N.err(f"error → {result.output}")
        else:
            N.ok(f"ok → {result.output}")
        print()

    attempt(1, "a good call — the function answers", ToolCall("calculate", {"expression": "2*(3+4)"}))
    attempt(2, "a missing argument — refused, and WHY", ToolCall("calculate", {}))
    attempt(3, "a wrong-typed argument — refused, and WHY", ToolCall("calculate", {"expression": 7}))
    attempt(4, "an invented argument — refused, and WHAT IS ALLOWED", ToolCall("calculate", {"expression": "1+1", "precision": 2}))

    divider(5, "a function that raises — caught, reported, the lab continues")
    N.kv("the call", "explode()")
    N.info("  a function that divides by zero is a bug in the TOOL, not the agent")

    def explode() -> ToolResult:
        return 1 / 0  # type: ignore[return-value]  # the honest way to fail

    boom = Tool(name="explode", description="always fails", params={}, func=explode)
    result = boom.run()
    N.err(f"error → {result.output}")
    N.why(
        "Notice the agent is still standing. In M4 the model will SEE this text and "
        "can try something else. That is why failure is data, not an exception."
    )
    print()
    N.ok("the hand has a shape, a boundary, and a loud way to say no.")


if __name__ == "__main__":
    main()
