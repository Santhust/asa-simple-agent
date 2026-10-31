"""calculator — the agent's arithmetic hand, PURE and deliberately manual.

One module, five decisions worth reading twice:

1. **NO eval() — a tool must be exactly as narrow as its documentation says.**
   The catalogue promises "arithmetic". `eval()` delivers arbitrary Python —
   which would mean a model writing `__import__('os')` inside a tool call
   could touch files, processes, anything. The documented narrowness would be
   a fiction. So the expression language is parsed from scratch: numbers,
   + - * /, parentheses, unary minus. Ground math only; nothing else exists.

2. **Failure is data at the boundary, readable vocabulary inside.** The
   parser raises `_ExpressionError` with a HUMAN message ("parentheses are
   unbalanced"), and the tool's function catches it and metaphorizes it into
   `ToolResult(is_error=True)` — the text a model reads and self-corrects
   from in M4+. (Python exceptions never reach the agent; M3.1's tool.py
   guards would turn them into generic "ZeroDivisionError" crumbs, and we
   can say better things.)

3. **Resource guards are TOOL business.** The mini-schema cannot say "at most
   200 characters", so the tool measures its own input: length cap (200) and
   parenthesis-depth cap (32). A hand-written recursive-descent parser runs
   out of Python stack on adversarial nesting — and a recursive-descent
   parser we refuse to crash is a tool that must say no as TEXT.

4. **Honest numerics.** Ints stay ints (`2+3 -> 5`, not `5.0`), `/` follows
   Python's real semantics (`7/2 -> 3.5`, `8/2 -> 4.0`), and there is no
   cosmetic rounding: `0.1+0.2` IS `0.30000000000000004` — floating point is
   exact IEEE 754 truth, and we prefer the model SEE the truth over a rounded
   story it would later trust wrongly.

5. **build() is a factory, not an instance.** The Tool dataclass (M3.1) is
   constructed fresh by `build()`; wiring in M3.5 will loop over factories
   like this one. The registry catalogue renders from THIS description,
   which is why it stays a promise the function keeps.

The parser itself: characters feed a classic recursive-descent descent —
_expr (terms with + -), _term (atoms with * /), _atom (numbers, parens, unary
minus). Every internal is visible; that is the point. (Real projects more
often walk Python's own `ast` tree with a strict node whitelist — a mention
for docs day, not the teaching pick here: those internals are invisible.)
"""

from __future__ import annotations

from asa.tool import Tool, ToolResult

#: Input guards: the mini-schema cannot express limits, so the tool measures
#: its own input — length of the expression, nesting depth of parentheses.
_MAX_CHARS = 200
_MAX_DEPTH = 32


class _ExpressionError(ValueError):
    """The parser's own refusal: a HUMAN-readable reason something didn't parse.

    Internal vocabulary only — the tool's function is the layer that turns
    this into the ToolResult text the model will actually read.
    """


def evaluate(expression: str) -> int | float:
    """Parse and compute one arithmetic expression; ints stay int, '/' is float.

    Raises _ExpressionError (readable) or ZeroDivisionError (specific) — the
    caller decides how those become model-facing text. This separation keeps
    the parser a pure MECHANISM and the tool function the MESSAGE policy.
    """
    return _Parser(expression).parse()


class _Parser:
    """One expression at a time; classic recursive descent over characters."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0      # reading cursor (byte of the input we are at)
        self.depth = 0  # current parenthesis nesting (for the depth guard)

    def parse(self) -> int | float:
        self._skip_ws()
        value = self._expr()
        self._skip_ws()
        if self.i != len(self.text):
            raise _ExpressionError(
                f"unexpected {self.text[self.i]!r} at position {self.i}"
            )
        return value

    def _skip_ws(self) -> None:
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    # _expr: addition level — terms joined by + and -
    def _expr(self) -> int | float:
        value = self._term()
        while True:
            self._skip_ws()
            if self.i < len(self.text) and self.text[self.i] in "+-":
                op = self.text[self.i]
                self.i += 1
                rhs = self._term()
                value = value + rhs if op == "+" else value - rhs
            else:
                return value

    # _term: multiplication level — atoms joined by * and /
    def _term(self) -> int | float:
        value = self._atom()
        while True:
            self._skip_ws()
            if self.i < len(self.text) and self.text[self.i] in "*/":
                op = self.text[self.i]
                self.i += 1
                rhs = self._atom()
                if op == "*":
                    value = value * rhs
                else:
                    if rhs == 0:
                        # the readable refusal happens HERE, at the crime scene
                        raise ZeroDivisionError
                    value = value / rhs
            else:
                return value

    # _atom: a number, a parenthesized sub-expression, or a unary minus
    def _atom(self) -> int | float:
        self._skip_ws()
        if self.i >= len(self.text):
            raise _ExpressionError(
                "the expression ends where a number or '(' was expected"
            )
        ch = self.text[self.i]

        if ch == "(":
            self.depth += 1
            if self.depth > _MAX_DEPTH:
                raise _ExpressionError(
                    f"parentheses nest more than {_MAX_DEPTH} deep — "
                    "that is beyond my patience, not a real sum"
                )
            self.i += 1
            value = self._expr()
            self._skip_ws()
            if self.i >= len(self.text) or self.text[self.i] != ")":
                raise _ExpressionError("parentheses are unbalanced: expected ')'")
            self.i += 1
            self.depth -= 1
            return value

        if ch == "-":
            self.i += 1
            return -self._atom()

        if ch.isdigit() or ch == ".":
            return self._number()

        raise _ExpressionError(
            f"unexpected character {ch!r} at position {self.i} — "
            "I read numbers, + - * / ( ) and that is all"
        )

    # _number: digits, an optional dot+more digits; plain ints or real floats
    def _number(self) -> int | float:
        start = self.i
        is_float = False
        while self.i < len(self.text) and self.text[self.i].isdigit():
            self.i += 1
        if self.i < len(self.text) and self.text[self.i] == ".":
            if (
                self.i + 1 >= len(self.text)
                or not self.text[self.i + 1].isdigit()
            ):
                raise _ExpressionError(
                    "a '.' needs digits after it, as in 3.14"
                )
            is_float = True
            self.i += 1
            while self.i < len(self.text) and self.text[self.i].isdigit():
                self.i += 1
        text = self.text[start:self.i]
        return float(text) if is_float else int(text)


def _calculate(expression: str) -> ToolResult:
    """The Tool's function: guard, parse/compute, and phrase every failure.

    All three failure roads end in readable ToolResult(is_error=True) text the
    model can act on — length overflow, unparisable syntax, division by
    zero. The happy road shows the model's own expression back next to the
    answer, so the Observation reads like a worked sum.
    """
    if len(expression) > _MAX_CHARS:
        return ToolResult(
            output=(
                f"calculator: expression is {len(expression)} characters; "
                f"I read at most {_MAX_CHARS}. Send a shorter one."
            ),
            is_error=True,
        )
    try:
        value = evaluate(expression)
    except _ExpressionError as exc:
        return ToolResult(output=f"calculator: {exc}", is_error=True)
    except ZeroDivisionError:
        return ToolResult(
            output=(
                "calculator: division by zero is undefined — "
                "pick a different expression"
            ),
            is_error=True,
        )
    return ToolResult(output=f"{expression.strip()} = {value}")


def build() -> Tool:
    """Fresh Tool, same promise every call — the M3.5 wiring loop's address."""
    return Tool(
        name="calculator",
        description=(
            "Evaluate an arithmetic expression with + - * /, parentheses"
            " and decimals, e.g. '2*(3+4)'."
        ),
        params={
            "expression": {
                "type": "string",
                "required": True,
                "help": "the arithmetic to do, e.g. '2*(3+4)' or '7/2'",
            }
        },
        func=_calculate,
    )
