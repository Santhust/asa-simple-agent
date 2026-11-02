"""Protocol: parse a NATIVE function-call reply into the core's vocabulary.

The second protocol adapter (M9). Same contract as protocol_react — give it
a brain reply, get back a verdict — but the input is not prose, it is the
structured `functionCall` the API produced for us.

That is the whole lesson. Textual ReAct (M4) had to:
  * teach the model a grammar (Thought:/Action:/Action Input:)
  * parse it with regexes
  * repair the drift (M4.3 — and M7.3 showed real drift needing self-repair)
  * convert the text values into Python types safely (M4.2, no eval)

Native function calling does NONE of that. The API hands us:
    {name: "calculator", args: {"expression": "7*6"}}
with args already a JSON-typed dict — numbers as numbers, bools as bools,
strings as strings. There is no lossy text hop, so there is nothing to
repair and nothing to coerce. parse_function_call() is deliberately a thin
shim; its thinness IS the point.

Verdict shape mirrors ReActParsed (same kind vocabulary) so the agent loop
is unchanged by which protocol the brain speaks:
  - "thought_action" : saw a functionCall -> action should be used
  - "final_answer"    : the model answered in prose -> end of run
  - "error"           : no functionCall and no text -> gentle note back
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocol_react import ParseError, ReActParsed
from .tool import ToolCall

if TYPE_CHECKING:
    from .brain import Completion
    from .registry import ToolRegistry


# Our mini-schema's four types map 1:1 onto JSON Schema's primitive types.
# tool.py:34 promised this conversion would be mechanical, and so it is —
# no JSON-Schema library, four lines, and a broken tool definition raises
# loudly here (it is OUR bug at build time, not the model's at run time).
_JSON_SCHEMA_TYPES = {"number": "number", "integer": "integer",
                      "string": "string", "boolean": "boolean"}


def build_tools_payload(registry: "ToolRegistry", mode: str = "AUTO") -> dict:
    """Render the registry as Gemini's `tools` + `toolConfig` payload.

    One functionDeclaration per tool, built FROM the Tool's mini-schema —
    never typed separately — so the function the model is offered is the
    same capability it reads in the catalogue. The catalogue (registry.
    render_catalogue) and this declaration can never drift apart, because
    both are rendered from the same Tool object.

    Shape:
        {"tools": [{"functionDeclarations": [
            {"name": ..., "description": ..., "parameters": {
                "type": "object",
                "properties": {"x": {"type": "number", "description": "..."}},
                "required": ["x"]}}],
          "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}}}

    An empty registry yields no `tools` key at all — asking a model to call
    from an empty list is a worse error than not asking.
    """
    declarations = []
    for name in registry.names():
        tool = registry.get(name)
        properties: dict = {}
        required: list[str] = []
        for pname, spec in (tool.params or {}).items():
            prop = {"type": _json_schema_type(spec.get("type", "string"))}
            if spec.get("help"):
                prop["description"] = spec["help"]
            properties[pname] = prop
            if spec.get("required"):
                required.append(pname)
        parameters: dict = {"type": "object", "properties": properties}
        if required:
            parameters["required"] = required
        declarations.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": parameters,
        })

    payload: dict = {"toolConfig": {"functionCallingConfig": {"mode": mode}}}
    if declarations:
        payload["tools"] = [{"functionDeclarations": declarations}]
    return payload


def _json_schema_type(t: str) -> str:
    if t not in _JSON_SCHEMA_TYPES:
        raise ValueError(
            f"unknown schema type {t!r} — the tool definition is broken "
            f"(known: {sorted(_JSON_SCHEMA_TYPES)})"
        )
    return _JSON_SCHEMA_TYPES[t]


def parse_function_call(completion: "Completion"):
    """Read a native reply and return a verdict. Never raises.

    The happy path is two lines: pull the functionCall off the completion,
    wrap it in a ToolCall. That is all — no regex, no kwargs parser, no
    repair, because the API did the structuring for us.
    """
    raw = (completion.text or "").strip()
    fc = _first_function_call(completion)

    if fc is not None:
        name = (fc.get("name") or "").strip()
        args = fc.get("args")
        if not name:
            return ReActParsed(kind="error", error=ParseError(
                "functionCall with no name"
            ), raw=raw)
        if not isinstance(args, dict):
            return ReActParsed(kind="error", error=ParseError(
                f"functionCall args must be an object, got {type(args).__name__}"
            ), raw=raw)
        try:
            call = ToolCall(name=name, args=args)
        except Exception as e:
            return ReActParsed(kind="error", error=ParseError(
                f"could not form tool call: {e}"
            ), raw=raw)
        return ReActParsed(kind="thought_action", action=call, raw=raw)

    # No functionCall. Either the model answered in prose (native mode's
    # automatic text fallback) or it said nothing at all.
    if raw:
        return ReActParsed(kind="final_answer", answer=raw, raw=raw)
    return ReActParsed(kind="error", error=ParseError("empty reply"), raw=raw)


def _first_function_call(completion: "Completion") -> dict | None:
    """Pull the first functionCall off a completion, if the model made one."""
    calls = getattr(completion, "tool_calls", None) or []
    for fc in calls:
        if isinstance(fc, dict) and fc.get("name"):
            return fc
    return None