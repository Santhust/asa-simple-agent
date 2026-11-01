"""Protocol: parse textual ReAct into the core's vocabulary.

The reader is dumb on purpose. Give it a string, it returns a verdict:
(1) a command (turn into a ToolCall) — ready for the agent to act on
(2) broken — a gentle note back to the model, not a crash
(3) an answer — end of run

This is pure text → structure. No brain, no tools, no loop. M5 will flip the
loop to actually run commands; M4 just teaches the agent to read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .tool import ToolCall


@dataclass
class ParseError:
    message: str


@dataclass
class ReActParsed:
    """Verdict from reading the model's reply.

    kind:
      - "thought_action": saw Thought/Action/Action Input → action should be used
      - "final_answer":    saw Final Answer: → run ends (M5 wires the switch)
      - "error":           broken letter → error.message is the gentle note back
    """
    kind: Literal["thought_action", "final_answer", "error"]
    thought: str | None = None
    action: ToolCall | None = None
    answer: str | None = None
    error: ParseError | None = None
    raw: str = ""


def parse(text: str) -> ReActParsed:
    """Read a model reply and return a verdict. Never raises."""
    if text is None:
        text = ""
    raw = text
    s = text.strip()
    if not s:
        return ReActParsed(kind="error", error=ParseError("empty reply"), raw=raw)

    # Look for Final Answer first (M4.4) — third verdict
    fa = _extract_final_answer(s)
    if fa is not None:
        return ReActParsed(kind="final_answer", answer=fa, raw=raw)

    # Otherwise expect Thought / Action / Action Input
    thought = _extract_block(s, "Thought")
    action_name = _extract_block(s, "Action")
    action_input = _extract_block(s, "Action Input")

    # Be gentle about missing pieces (M4.3) — failure is data
    if action_name is None and action_input is None and thought is None:
        return ReActParsed(kind="error", error=ParseError(
            "Could not read this reply as ReAct. Expected lines like:\n"
            "Thought: ...\n"
            "Action: tool_name\n"
            "Action Input: key=value  (or as shown in the instructions)\n"
            "Or use 'Final Answer: ...' to end."
        ), raw=raw)

    if action_name is None and action_input is not None:
        return ReActParsed(kind="error", error=ParseError(
            "Saw 'Action Input:' but no 'Action:'. Add an Action line naming the tool."
        ), raw=raw)
    if action_input is None and action_name is not None:
        return ReActParsed(kind="error", error=ParseError(
            f"Saw 'Action: {action_name}' but missing 'Action Input:'. "
            f"Give arguments as shown in the instructions."
        ), raw=raw)
    if action_name is None and thought is not None and action_input is None:
        return ReActParsed(kind="error", error=ParseError(
            "Saw 'Thought:' but no 'Action:' and no 'Final Answer:'. "
            "Either call a tool with Action/Action Input, or end with 'Final Answer: ...'."
        ), raw=raw)

    # We have Action + Action Input — parse args (M4.2)
    args, err = _parse_action_input(action_input)
    if err is not None:
        return ReActParsed(kind="error", error=ParseError(err), raw=raw)

    try:
        call = ToolCall(name=action_name.strip(), args=args)
    except Exception as e:
        return ReActParsed(kind="error", error=ParseError(f"Could not form tool call: {e}"), raw=raw)

    return ReActParsed(kind="thought_action", thought=thought, action=call, raw=raw)


def _extract_final_answer(s: str) -> str | None:
    # Case-insensitive keyword, take rest of line(s) after colon
    # Look for "Final Answer:" possibly after whitespace/newlines
    import re

    m = re.search(r"(?is)^\s*Final\s+Answer\s*:\s*(.+)$", s, flags=re.M)
    if not m:
        return None
    ans = m.group(1).strip()
    # If there's more content after on same conceptual block, take until next known keyword? Keep simple for now.
    return ans if ans else ""


def _extract_block(s: str, key: str) -> str | None:
    import re

    # Match `Thought:` / `Action:` / `Action Input:` (case-insensitive)
    pattern = rf"(?is)^\s*{re.escape(key)}\s*:\s*(.+?)(?=^\s*(?:Thought|Action|Action\s+Input|Final\s+Answer)\s*:|\Z)"
    m = re.search(pattern, s, flags=re.M | re.S)
    if not m:
        return None
    val = m.group(1).strip()
    return val if val != "" else None


def _parse_action_input(s: str) -> tuple[dict, str | None]:
    """Turn Action Input text into args dict safely (no eval)."""
    if s is None:
        return {}, "missing Action Input"
    s = s.strip()
    if not s:
        return {}, "Action Input is empty"

    # Try JSON first (common, safe)
    import json

    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj, None
            if isinstance(obj, list):
                # treat as positional? keep simple: require dict for kwargs
                return {}, "Action Input JSON array not supported; use key: value or a dict"
            return {}, "Action Input must be an object/dict"
        except Exception as e:
            return {}, f"Could not parse Action Input as JSON: {e}"

    # Try simple kw style: key=value, key='val', key="val", comma or newline separated
    args = _parse_kwargs(s)
    if args == {} and s:
        # Maybe it's a plain string value passed as a single positional-like arg?
        # Try to be lenient: if it doesn't look like kwargs, treat as {"expression": s} only in special cases?
        # But better to require kwargs format we document. For now, see if there's '='
        if "=" not in s:
            # Could be a bare string for a single-param tool? We'll let caller decide; but safer to ask for kwargs.
            # But M4.1 wants good letters to parse - let's be a bit flexible for common case like expression
            # Try to guess common single-arg name? No - better to require explicit form. But test may vary.
            # For now, return error asking for kwargs
            return {}, "Action Input must be key=value pairs (or JSON object)."
    return args, None


def _parse_kwargs(s: str) -> dict:
    import ast

    args = {}
    parts = _split_args(s)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Be gentle: accept JSON-style true/false/null in unquoted form too
        vl = v.lower()
        if vl == "true":
            args[k] = True
            continue
        if vl == "false":
            args[k] = False
            continue
        if vl == "null" or vl == "none":
            args[k] = None
            continue
        try:
            val = ast.literal_eval(v)
        except Exception:
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                val = v[1:-1]
            else:
                val = v
        args[k] = val
    return args


def _split_args(s: str) -> list[str]:
    parts = []
    cur = []
    in_single = False
    in_double = False
    depth = 0
    for ch in s:
        if ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
            continue
        if not in_single and not in_double:
            if ch in "([{":
                depth += 1
                cur.append(ch)
                continue
            if ch in ")]}":
                depth -= 1
                cur.append(ch)
                continue
            if (ch == "," or ch == "\n" or ch == ";") and depth == 0:
                parts.append("".join(cur))
                cur = []
                continue
        cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts
