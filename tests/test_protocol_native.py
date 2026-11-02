"""M9.1 tests — asa.protocol_native, the second protocol adapter.

Every test here is OFFLINE and KEYLESS: no network, no GEMINI_API_KEY,
instant and deterministic. They pin the two halves of the adapter:

  * build_tools_payload()   — our Tool registry -> Gemini's
                              functionDeclarations + toolConfig. Renders
                              FROM the Tool's mini-schema so catalogue and
                              declaration can never drift (M3's lesson, one
                              level deeper for M9).
  * parse_function_call()   — Gemini completion -> verdict. Deliberately
                              thin: no regex, no kwargs parser, no repair,
                              because the API did the structuring for us.

The lesson: native args are already typed (numbers as numbers, bools as
bools) — nothing to coerce, nothing to repair. That absence IS the point.
"""

from asa.brain import Completion
from asa.protocol_native import build_tools_payload, parse_function_call
from asa.registry import ToolRegistry
from asa.tool import Tool, ToolResult


def _registry_with(*tools: Tool) -> ToolRegistry:
    r = ToolRegistry()
    for t in tools:
        r.register(t)
    return r


# -- build_tools_payload -------------------------------------------------------

def test_payload_has_one_declaration_per_tool_sorted_by_name():
    clock = Tool(
        name="clock", description="read the time",
        params={"utc": {"type": "boolean", "required": False,
                        "help": "true for UTC, default local"}})
    calc = Tool(
        name="calculator", description="evaluate an expression",
        params={"expression": {"type": "string", "required": True,
                               "help": "the arithmetic to do"}})
    registry = _registry_with(clock, calc)

    payload = build_tools_payload(registry)
    decls = payload["tools"][0]["functionDeclarations"]
    names = [d["name"] for d in decls]
    assert names == ["calculator", "clock"]   # sorted by name

    calc_decl = decls[0]
    assert calc_decl["description"] == "evaluate an expression"
    assert calc_decl["parameters"]["type"] == "object"
    props = calc_decl["parameters"]["properties"]
    assert props["expression"] == {"type": "string",
                                   "description": "the arithmetic to do"}
    assert calc_decl["parameters"]["required"] == ["expression"]

    clock_decl = decls[1]
    props = clock_decl["parameters"]["properties"]
    assert props["utc"] == {"type": "boolean",
                            "description": "true for UTC, default local"}
    assert "required" not in clock_decl["parameters"]   # optional -> omitted


def test_schema_types_map_one_to_one():
    t = Tool(name="x", description="d", params={
        "a": {"type": "number", "required": True},
        "i": {"type": "integer", "required": True},
        "s": {"type": "string", "required": True},
        "b": {"type": "boolean", "required": True},
    })
    payload = build_tools_payload(_registry_with(t))
    props = payload["tools"][0]["functionDeclarations"][0]["parameters"]["properties"]
    assert props["a"]["type"] == "number"
    assert props["i"]["type"] == "integer"
    assert props["s"]["type"] == "string"
    assert props["b"]["type"] == "boolean"


def test_no_params_still_gives_an_empty_properties_object():
    t = Tool(name="clock2", description="no args", params={})
    payload = build_tools_payload(_registry_with(t))
    decl = payload["tools"][0]["functionDeclarations"][0]
    assert decl["parameters"] == {"type": "object", "properties": {}}


def test_tool_config_mode_is_auto():
    t = Tool(name="x", description="d", params={})
    payload = build_tools_payload(_registry_with(t))
    assert payload["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}


def test_empty_registry_omits_tools_key():
    payload = build_tools_payload(_registry_with())
    assert "tools" not in payload
    assert payload["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}


def test_unknown_schema_type_raises_loudly():
    t = Tool(name="x", description="d", params={
        "a": {"type": "mystery", "required": True},
    })
    try:
        build_tools_payload(_registry_with(t))
    except ValueError as e:
        assert "mystery" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown schema type")


# -- parse_function_call --------------------------------------------------------

def _completion(tool_calls: list[dict] | None = None,
                text: str = "") -> Completion:
    return Completion(text=text, model="gemini", tool_calls=tool_calls or [])


def test_parse_function_call_wraps_the_call():
    fc = {"name": "calculator", "args": {"expression": "7*6"}}
    verdict = parse_function_call(_completion(tool_calls=[fc]))
    assert verdict.kind == "thought_action"
    assert verdict.action.name == "calculator"
    assert verdict.action.args == {"expression": "7*6"}


def test_parse_native_args_are_already_typed():
    """THE lesson: args arrive as JSON-typed values — no literal_eval, no repair."""
    fc = {"name": "clock", "args": {"utc": True, "count": 3}}
    verdict = parse_function_call(_completion(tool_calls=[fc]))
    assert verdict.kind == "thought_action"
    assert verdict.action.args == {"utc": True, "count": 3}
    assert verdict.action.args["utc"] is True
    assert verdict.action.args["count"] == 3   # an int, not the string "3"


def test_parse_function_call_no_call_and_text_is_final_answer():
    """Native mode's automatic text fallback: prose with no functionCall
    terminates as a final answer — call or answer, nothing else."""
    verdict = parse_function_call(_completion(text="The result is 42."))
    assert verdict.kind == "final_answer"
    assert verdict.answer == "The result is 42."


def test_parse_function_call_empty_reply_is_gentle_error():
    verdict = parse_function_call(_completion(text=""))
    assert verdict.kind == "error"
    assert "empty" in verdict.error.message.lower()
    assert verdict.action is None


def test_parse_function_call_args_must_be_a_dict():
    fc = {"name": "calculator", "args": "7*6"}
    verdict = parse_function_call(_completion(tool_calls=[fc]))
    assert verdict.kind == "error"
    assert "args must be an object" in verdict.error.message
    assert verdict.action is None


def test_parse_function_call_no_name_is_gentle_error():
    fc = {"name": "", "args": {}}
    verdict = parse_function_call(_completion(tool_calls=[fc]))
    assert verdict.kind == "error"
    assert verdict.action is None


def test_parse_function_call_never_raises_on_garbage():
    garbage = Completion(text=None, model="gemini",
                         tool_calls=[{"name": None, "args": None}])
    verdict = parse_function_call(garbage)
    assert verdict.kind == "error"
    assert verdict.action is None   # never propagates an exception


def test_round_trip_declaration_to_toolcall_to_toolrun():
    """End-to-end, offline, with REAL tools: declaration -> parsed -> run."""
    calc = Tool(name="calculator", description="evaluate",
                params={"expression": {"type": "string", "required": True}},
                func=lambda expression: ToolResult(output=f"{expression} = 42", is_error=False))
    registry = _registry_with(calc)
    payload = build_tools_payload(registry)
    decls = payload["tools"][0]["functionDeclarations"]
    assert len(decls) == 1
    assert decls[0]["parameters"]["properties"]["expression"]["type"] == "string"

    # The model offered 'calculator' -> replies with exactly that functionCall.
    fc = {"name": "calculator", "args": {"expression": "2+2"}}
    verdict = parse_function_call(_completion(tool_calls=[fc]))
    assert verdict.kind == "thought_action"

    # Tool.run validates and coerces against the SAME schema — no repaint.
    result = registry.get("calculator").run(verdict.action.args)
    assert result.output == "2+2 = 42"
    assert result.is_error is False


def test_toolcall_args_skip_parse_coercion():
    """Native args arrive already typed: a declared 'number' param receives an
    int from the API, and parse_function_call does not coerce it. coerce_args
    in tool.py still normalises ints->floats later, at the execution boundary."""
    num_tool = Tool(name="calc2", description="e", params={
        "n": {"type": "number", "required": True},
    })
    registry = _registry_with(num_tool)
    build_tools_payload(registry)   # proves the declaration accepts 'n'

    fc = {"name": "calc2", "args": {"n": 7}}
    verdict = parse_function_call(_completion(tool_calls=[fc]))
    assert verdict.kind == "thought_action"
    assert verdict.action.args["n"] == 7
    assert isinstance(verdict.action.args["n"], int)

