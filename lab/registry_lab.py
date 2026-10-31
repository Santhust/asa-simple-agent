#!/usr/bin/env python3
"""lab/registry_lab.py — poke ONE internal: what does the registry actually do?

Run it:  python lab/registry_lab.py

tool_lab.py watched ONE hand work. This lab watches the phonebook that ties
all hands together — and, crucially, the manual page it renders for the
model. Four beats:

  1. register two tools, list them      -> sorted, order-of-registration gone
  2. register a duplicate               -> ValueError: OUR build-time bug
  3. look up a misspelled name          -> None: the MODEL'S run-time miss
  4. render the catalogue               -> the text the model will live on

Beat 3 next to beat 2 is the lesson: two "failures", two philosophies.
Ours explode at build time (tests); the model's become text it can read.

Then beat 4 prints the whole catalogue as the model will see it in M3.5 —
this lab doubles as the FORMAT DESIGN REVIEW for that page.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asa import narrate as N  # noqa: E402
from asa.registry import ToolRegistry  # noqa: E402
from asa.tool import Tool, ToolResult  # noqa: E402


def build_adder() -> Tool:
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


def build_clock() -> Tool:
    def now() -> ToolResult:
        return ToolResult(output="12:00 (lab time — clocks are M3.3's business)")

    return Tool(name="clock", description="Read the current time.", params={}, func=now)


def main() -> None:
    N.h1("asa lab · ToolRegistry — the phonebook + the manual page")
    N.why(
        "A model cannot browse our code. The catalogue is the ONLY documentation "
        "it will ever have — watch the phonebook and the page it writes."
    )

    registry = ToolRegistry()

    # ---- beat 1 · register + list ------------------------------------------
    N.h2("1 · register two tools, list them")
    registry.register(build_clock())  # registered FIRST...
    registry.register(build_adder())  # ...but add sorts FIRST
    N.kv("registered in order", "clock, add")
    N.kv("names() gives", registry.names())
    N.why(
        "Sorted, not registered-order: identical knowledge must render byte-identical "
        "text so M5's golden-trace tests never diff on a registration accident."
    )

    # ---- beat 2 · duplicate = OUR build-time bug ----------------------------
    N.h2("2 · register 'add' again — the same-named imposter")
    try:
        registry.register(build_adder())
    except ValueError as exc:
        N.err(f"ValueError → {exc}")
    N.why(
        "Loud, immediate, exception: a duplicate is OUR bug, one that would otherwise "
        "shadow a working tool forever. (tool.py's failure-is-data rule is for the "
        "MODEL's run-time misuse — different failure, different timing, different rule.)"
    )

    # ---- beat 3 · miss = the MODEL'S run-time miss --------------------------
    N.h2("3 · look up a misspelled name — the model will do this")
    found = registry.get("claculator")  # one typo away, as all models are
    N.kv("registry.get('claculator')", repr(found))
    N.why(
        "None, not an exception: in M4 this miss becomes an error Observation the "
        "model reads and self-corrects from — the same failure-is-data philosophy, "
        "phrased one layer up. The registry never panics; it just has no entry."
    )
    N.ok(f"len={len(registry)} · 'add' in registry → {'add' in registry}")

    # ---- beat 4 · the catalogue — the model's whole world of tools ----------
    N.h2("4 · render the catalogue — exactly what the model will read")
    N.why(
        "Rendered FROM the schema, never typed alongside it: Tool documentation and "
        "implementation live in one object, so this page cannot lie. In M3.5 this "
        "block lands in the system prompt; M4 adds the 'how to call' instructions."
    )
    N.code(registry.render_catalogue().rstrip())

    print()
    N.ok("the phonebook is small, sorted, and loud about OUR bugs, quiet about the model's.")


if __name__ == "__main__":
    main()
