"""asa.tools: the agent's actual HANDS — one module per tool, one build() each.

M3.3 plants the first pair, both of them STATELESS:
  * calculator — pure: same input, same answer, touches nothing
  * clock      — a read-only probe of the environment: it looks, never mutates

Why a package of small modules: tools are how the agent's words become
effects, and each one stays small enough to read whole. Every module exposes
exactly one `build() -> Tool` factory, so M3.5's wiring will be a loop over
factories — and the registry catalogue renders the same data the loop runs,
so the manual page can never lie about the hands.
"""
