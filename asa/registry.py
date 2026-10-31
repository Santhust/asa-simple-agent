"""Registry: the agent's PHONEBOOK + the manual page the model reads.

Tool (M3.1) gave every hand a shape. This module answers the two questions the
loop keeps asking: *which tools exist?* and *what is tool X?* — plus one more
question that is easy to undervalue: *how does the model learn about them?*

That last one is the lesson of this module. A model cannot browse our code.
The ONLY documentation it will ever have is `render_catalogue()` — the text
that lands in the system prompt in M3.5. This is "documentation-first": the
model can only use what it has been told exists, so the catalogue is not
decoration, it is the model's entire world of capabilities. (And because the
Tool dataclass keeps documentation and implementation in one object, the two
can never drift apart — the catalogue is rendered FROM the schema, not typed
alongside it.)

Four decisions worth reading twice, because they are the lesson:

1. **Duplicate name -> ValueError. Loud, immediate, ours.** tool.py made
   "failure is data, never an exception" the rule — but that rule is for
   MODEL misuse at RUN time. A duplicate registration is OUR bug at BUILD
   time (like tool.py's unknown schema type), and our bugs must explode in
   tests, not silently shadow a working tool. Same philosophy, two timings.

2. **Unknown name -> None. Quiet, deferred, the model's.** `get("claculator")
   (one typo away) returns None, not an exception. Why? At build time a miss
   is data too: in M4 the loop will phrase that miss as an error Observation
   the model can read and self-correct from — exactly like
   ToolResult(is_error=True). The registry stays a dumb phonebook; nobody
   panics, the message is simply composed one layer up.

3. **The catalogue is sorted by name.** Registration order is an accident of
   how the builder's code happens to list tools; it must not leak into the
   prompt. Determinism now buys golden-trace tests in M5: identical knowledge
   => byte-identical prompt, no matter which order tools were registered in.

4. **Phonebook, not dispatcher.** The registry has NO run() convenience
   method. Resolution (`get`) and execution (`Tool.run`) are deliberately two
   doors in two modules: registry = who exists; the M4 loop = how calls
   happen and how misses become Observations. Keeping dispatch out keeps
   every layer small enough to see.

The catalogue FORMAT is deliberately minimal and protocol-agnostic — it
documents only WHAT exists:

    ## Available tools

    ### add
    Add two numbers.
    Params:
    - a (number, required): first addend
    - b (number, required): second addend

An empty registry is also a paragraph, never an empty string: a model hanging
on a blank section of its prompt is a bug we get to design away now. The
"how to call" instructions are the M4 protocol layer's job — this page stays
true whether the model calls tools in text or via a native API.
"""

from __future__ import annotations

from .tool import Tool

#: What the catalogue says when there is nothing to say — still a paragraph,
#: because a blank system-prompt section is a lie about the conversation.
_EMPTY_CATALOGUE = (
    "## Available tools\n"
    "\n"
    "You have no tools in this session. Work from your own knowledge alone.\n"
)


class ToolRegistry:
    """A named collection of Tools: register at build time, get at run time.

    One registry = one agent's hands. Nothing here talks to the brain or the
    loop — it stores, lists, and renders. (M3.5 will wire the catalogue into
    the Agent's system prompt; M4 will call get() to resolve ToolCalls.)
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Add a tool to the phonebook, rejecting imposter duplicates.

        Raises ValueError if a tool with the same name is already here. A
        duplicate is a build-time bug in OUR code (two modules named a tool
        "calculator"), and our bugs must be loud: silent shadowing would make
        one of the two tools undiscoverable while everything still "works".
        """
        if tool.name in self._tools:
            raise ValueError(
                f"a tool named {tool.name!r} is already registered "
                f"({self._tools[tool.name].description!r}); duplicates would shadow a tool"
            )
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up by exact name; a miss is None, never an exception.

        The None is DATA for the M4 layer: it means "the model named a tool
        that does not exist", which becomes a readable Observation the model
        can react to — the same failure-is-data philosophy as
        ToolResult(is_error=True), phrased one layer up.
        """
        return self._tools.get(name)

    def names(self) -> list[str]:
        """All tool names, sorted — the stable order everything renders in."""
        return sorted(self._tools)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def render_catalogue(self) -> str:
        """Render the manual page: one section per tool, sorted by name.

        This is the text that becomes the model's knowledge of its own hands
        (the system prompt in M3.5). It is rendered FROM the Tool's schema —
        never typed separately — so documentation and implementation cannot
        drift. Params render in declared order (a Tool's own, deterministic
        choice); sections render in name order (ours).
        """
        if not self._tools:
            return _EMPTY_CATALOGUE

        sections: list[str] = []
        for name in self.names():
            tool = self._tools[name]
            lines = [f"### {name}", tool.description]
            if tool.params:
                lines.append("Params:")
                for pname, spec in tool.params.items():
                    kind = spec.get("type", "string")
                    qualifier = "required" if spec.get("required") else "optional"
                    help_text = spec.get("help", "no description")
                    lines.append(f"- {pname} ({kind}, {qualifier}): {help_text}")
            sections.append("\n".join(lines))
        return "## Available tools\n\n" + "\n\n".join(sections) + "\n"
