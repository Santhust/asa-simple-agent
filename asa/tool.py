"""Tool: the shape of the agent's HAND.

A model can only say words. A tool is how the agent's words turn into effects on
the world: a calculation, a clock reading, a note written down. This module holds
the vocabulary — and the vocabulary is deliberately tiny, because the whole loop
will later speak nothing but `ToolCall(name, args)`.

Three decisions worth reading twice, because they are the lesson:

1. **A tool is DATA + a function.** `name` + `description` + a `params` schema +
   the `func` that does the work. The data half is what the model READS (this is
   "documentation-first": the model can only use what it has been told exists);
   the function half is what the agent RUNS. Keeping both in one object means
   documentation and implementation can never drift apart.

2. **Failure is DATA, not an exception.** A missing argument, a wrong type, or a
   function that blows up all come back as `ToolResult(is_error=True, ...)`.
   That is not squeamishness — it is the difference between an agent that
   recovers and an agent that dies. Real models misspell arguments constantly;
   the whole point is to hand the model a readable error and let it try again.
   Python exceptions are for OUR bugs; tool misuse is the model's problem, and it
   is answered with text.

3. **Validate BEFORE executing.** `run()` checks the arguments against the schema
   first, and only then calls `func`. So garbage input can never half-run a tool
   that mutates state. (M4 hands these exact error strings back to the model.)

`params` is a deliberately small subset of JSON Schema — types number / integer /
string / boolean, plus `required` and `help` per parameter:

    params = {"x": {"type": "number", "required": True, "help": "first addend"}}

It is small because we refuse to build a JSON-Schema library inside a teaching
project, but it is shaped so M9's native protocol can mechanically convert it into
a real `{"type": "object", "properties": ..., "required": [...]}` payload.
Deciding that now means M9 never has to repaint this corner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# The mini-schema's vocabulary. A type we do not know is a bug in the tool
# definition, so we say so at import-time style (i.e. loudly, at validation time).
_TYPES = ("number", "integer", "string", "boolean")


@dataclass
class ToolCall:
    """What the protocol layer hands us: a tool's name plus its arguments.

    This is the ONLY vocabulary the core speaks. A textual ReAct `Action:` line
    and a Gemini functionCall payload both become one of these, which is why the
    same loop drives both (see the SEAM in agent.py).
    """

    name: str
    args: dict[str, object] = field(default_factory=dict)

    def render(self) -> str:
        return f"{self.name}({self.args})"


@dataclass
class ToolResult:
    """What a tool hands back — and whether it went wrong.

    `output` is the text destined for memory as the Observation. On failure it is
    the error message, phrased so a model can act on it ("expression: expected a
    number, got 'two plus two'").
    """

    output: str
    is_error: bool = False


def _check_type(value: object, expected: str) -> str | None:
    """Return an error message if value does not match expected, else None."""
    if expected == "number":
        # bool is a subclass of int in Python; a flag is not a number here.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"expected a number, got {value!r}"
        return None
    if expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"expected a whole number, got {value!r}"
        return None
    if expected == "string":
        return None if isinstance(value, str) else f"expected text, got {value!r}"
    if expected == "boolean":
        return None if isinstance(value, bool) else f"expected true/false, got {value!r}"
    return f"tool definition is broken: unknown type {expected!r}"


def validate_args(params: dict, args: dict) -> list[str]:
    """Check `args` against the mini-schema; return a list of human-readable errors.

    An empty list means "safe to execute". We check four things, in the order a
    confused caller would trip over them:
      * required parameters that are missing
      * arguments nobody declared (the classic model typo)
      * declared-but-omitted optional parameters (we default them, no error)
      * types of everything present
    """
    errors: list[str] = []
    declared = set(params)

    for key, spec in params.items():
        if spec.get("required") and key not in args:
            errors.append(f"{key} is required ({spec.get('help', 'no description')})")

    for key in args:
        if key not in declared:
            allowed = ", ".join(sorted(declared)) or "none"
            errors.append(f"unknown argument {key!r} (this tool accepts: {allowed})")

    for key, value in args.items():
        if key not in declared:
            continue  # already reported
        problem = _check_type(value, params[key].get("type", "string"))
        if problem:
            errors.append(f"{key}: {problem}")

    return errors


def coerce_args(params: dict, args: dict) -> dict:
    """Normalize values AFTER validation: every 'number' arrives as a Python float.

    Why bother: the model may send 2 where we documented "number". Python would
    happily do the int arithmetic, but a tool that divides or formats its inputs
    would then meet two different types for the same declared parameter. We
    normalize once, at the boundary, so each tool's function can trust its
    numbers. Types are never changed here beyond that (ints stay ints).
    """
    out = dict(args)
    for key, value in args.items():
        spec = params.get(key)
        if (
            spec is not None
            and spec.get("type") == "number"
            and isinstance(value, int)
            and not isinstance(value, bool)
        ):
            out[key] = float(value)
    return out


@dataclass
class Tool:
    """One capability the agent can be given: a documented function.

    func receives the validated arguments as keyword arguments and returns a
    ToolResult. Tool.run() is the front door — callers never touch func directly.
    """

    name: str
    description: str
    params: dict = field(default_factory=dict)
    func: Callable[..., ToolResult] = lambda **_: ToolResult("tool has no function yet")

    def run(self, args: dict | None = None) -> ToolResult:
        """Validate, then execute, then report — never raising at the caller.

        Returns a ToolResult whose `output` is either the tool's own answer or a
        precise, model-readable error. This is the method the registry will call
        in M4/M5; everything about tools funnels through it.
        """
        args = dict(args or {})

        errors = validate_args(self.params, args)
        if errors:
            return ToolResult(
                output=f"tool {self.name!r} rejected the call: " + "; ".join(errors),
                is_error=True,
            )

        try:
            result = self.func(**coerce_args(self.params, args))
        except Exception as exc:  # a tool's own bug must not kill the agent
            return ToolResult(
                output=f"tool {self.name!r} failed: {type(exc).__name__}: {exc}",
                is_error=True,
            )

        if not isinstance(result, ToolResult):  # a badly-behaved tool
            return ToolResult(
                output=f"tool {self.name!r} returned {type(result).__name__}, expected ToolResult",
                is_error=True,
            )
        return result

    def describe(self) -> str:
        return f"Tool({self.name!r}, params={list(self.params)})"
