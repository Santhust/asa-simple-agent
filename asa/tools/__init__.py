"""asa.tools: the agent's actual HANDS — one module per tool, one build() each.

M3.3 plants the first pair, both of them STATELESS:
  * calculator — pure: same input, same answer, touches nothing
  * clock      — a read-only probe of the environment: it looks, never mutates

M3.4 added the stateful pair:
  * notes      — a private numbered ledger (2 hands: notes_write/notes_read)
  * plan_board — a shared mutable board (3 hands: add/move/list, stable ids)

Why a package of small modules: tools are how the agent's words become
effects, and each one stays small enough to read whole. Every module exposes
exactly one `build()` factory; the stateful factories return BUNDLES of
tools over one injected store, because a store with only a writer can never
be verified and a mover nobody listed is meaningless. The registry catalogue
renders the same data the loop runs, so the manual page can never lie about
the hands.

`default_tools()` is the wiring helper: it flattens all four factories
into ONE registry built over ONE fresh world. Call it twice, get two
strangers — the lifetime of the state is the lifetime of the registry, which
is the lifetime of an agent session.
"""

from __future__ import annotations

from asa.registry import ToolRegistry
from asa.tools.calculator import build as build_calculator
from asa.tools.clock import build as build_clock
from asa.tools.notes import build as build_notes
from asa.tools.plan_board import build as build_board


def default_tools() -> ToolRegistry:
    """One fresh world — all the agent's hands, registered, nothing shared.

    This is the whole toolbox M4's loop will act through: calculator
    (pure), clock (read-only), notes x2 + plan-board x3 (stateful, private
    to THIS registry). Fresh per call: two agents each call default_tools()
    and get worlds that cannot see each other — same machinery the tests
    rely on, offered to the wiring for free.
    """
    registry = ToolRegistry()
    registry.register(build_calculator())
    registry.register(build_clock())
    for tool in build_notes() + build_board():
        registry.register(tool)
    return registry
