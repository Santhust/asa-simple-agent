#!/usr/bin/env python3
"""lab/tools_lab.py — poke ONE internal: the agent's first REAL hands.

Run it:  python lab/tools_lab.py

tool_lab.py used a stand-in hand; this lab holds the real ones —
calculator (pure) and clock (read-only) — the same build() factories M3.5
registers into the phonebook. Six beats:

  1. the golden call        -> the promised arithmetic, ints staying ints
  2. the float truth        -> '/' semantics, and 0.1+0.2 with NO rounding
  3. division by zero       -> a readable refusal at the crime scene
  4. malformed input        -> '2+' answered in human words
  5. the eval-probe         -> __import__ is refused: the tool is as narrow
                               as its documentation says, black on white
  6. the clock              -> one read-only look, local by default, UTC if asked

Beat 5 is why we built a parser instead of calling eval(): the catalogue
promises ARITHMETIC, and a tool must never be wider than its own page.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asa import narrate as N  # noqa: E402
from asa.registry import ToolRegistry  # noqa: E402
from asa.tools.calculator import build as build_calculator  # noqa: E402
from asa.tools.clock import build as build_clock  # noqa: E402


def show(beat: str, result, call: str) -> None:
    """One call, one narrated outcome."""
    N.h2(beat)
    N.kv("the call", call)
    if result.is_error:
        N.err(f"refused → {result.output}")
    else:
        N.ok(f"answer → {result.output}")
    print()


def main() -> None:
    N.h1("asa lab · tools — calculator (pure) + clock (read-only)")
    N.why(
        "The first REAL tools: every call below goes through Tool.run()'s "
        "validate-then-execute boundary and comes back as ToolResult data."
    )
    calc = build_calculator()

    show(
        "1 · the golden call — the promise kept",
        calc.run({"expression": "2*(3+4)"}),
        "calculator(expression='2*(3+4)')",
    )
    N.why(
        "Ints stayed ints ('14', not '14.0'). The Observation reads like "
        "arithmetic because it IS Python's real semantics, shown verbatim."
    )

    show(
        "2 · the float truth — including the 0.1+0.2 lesson",
        calc.run({"expression": "0.1+0.2"}),
        "calculator(expression='0.1+0.2')",
    )
    N.why(
        "No cosmetic rounding: 0.30000000000000004 is IEEE 754 truth. A "
        "model that SEES floating point teaches itself to not trust it blindly."
    )

    show(
        "3 · division by zero — refused in English, at the crime scene",
        calc.run({"expression": "1/0"}),
        "calculator(expression='1/0')",
    )
    N.why(
        "In M4 this exact text becomes the Observation the model reacts to — "
        "'pick a different expression' is an instruction, not a crash."
    )

    show(
        "4 · malformed input — the model WILL send this",
        calc.run({"expression": "2+"}),
        "calculator(expression='2+')",
    )

    show(
        "5 · the eval-probe — the tool is as narrow as its page",
        calc.run({"expression": "__import__('os')"}),
        "calculator(expression=\"__import__('os')\")",
    )
    N.why(
        "A character error, not a security breach: the parser's language is "
        "ground math, so python-shaped text fails loudly and harmlessly. "
        "Never eval() — the catalogue's promise must be the whole truth. "
        "(Real projects use Python's ast with a strict node whitelist; same "
        "lesson, industrial packaging.)"
    )

    N.h2("6 · the clock — a read-only look at the world")
    clock = build_clock()
    N.kv("the call", "clock()          # no arguments — nothing required")
    N.ok(f"answer → {clock.run({}).output}")
    N.kv("the call", "clock(utc=true)  # the optional parameter, exercised")
    N.ok(f"answer → {clock.run({'utc': True}).output}")
    N.why(
        "Same instant, two labelled representations; the tool only LOOKS. "
        "This hand cannot set the time — read-only means only reads."
    )

    print()
    N.h2("7 · both hands in the phonebook — the manual page itself")
    registry = ToolRegistry()
    registry.register(calc)
    registry.register(clock)
    N.code(registry.render_catalogue().rstrip())
    N.why(
        "This PAGE is all the model will ever know. Rendered from the schema, "
        "it cannot drift from the functions you just watched run."
    )
    print()
    N.ok("two hands, both as wide as their promises — and not one char wider.")


if __name__ == "__main__":
    main()
