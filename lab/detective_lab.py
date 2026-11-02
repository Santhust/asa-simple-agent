#!/usr/bin/env python3
"""lab/detective_lab.py — replay probe for the M6 trace (M8.4.3).

Reads asa/traces/trace.jsonl, groups events by run_id, finds failing runs,
extracts the brain.request context that preceded each failure, converts it
back to native API format, and replays it against a brain to bisect the
cause. This automates the archaeology we did by hand during M8.2's think-pin
falsification.

This is a LAB script — script-first, never installed. It starts with the
two-line sys.path bootstrap from the M3.1 convention.

Usage:
    python lab/detective_lab.py                 # report all failing runs
    python lab/detective_lab.py --brain ollama  # replay against real Ollama
    python lab/detective_lab.py --brain gemini  # replay against real Gemini
    python lab/detective_lab.py --bisect think  # try think on/off per context

Exit code: 0 if no failing runs found, 1 if failures remain (or replay fails).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Lab bootstrap (M3.1 convention): script-first, never installed.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from collections import defaultdict

from asa.brain import Message, MockBrain, OllamaBrain, GeminiBrain
from asa.trace import read_events, clear_trace, get_run_id

# Failure kinds we know how to name (M8.4.2 taxonomy)
FAILURE_KINDS = {
    "empty_reply", "protocol_drift", "tool_error", "network",
    "budget_exhausted", "rate_limited",
}


def group_events_by_run(events: list) -> dict[str, list]:
    """Group trace events by their run_id."""
    groups: dict[str, list] = defaultdict(list)
    for ev in events:
        groups[ev.run_id or "(no run_id)"].append(ev)
    return dict(groups)


def is_failing_run(events: list) -> bool:
    """A run fails if it ended without a Final Answer (budget, network, ...)."""
    terminates = [e for e in events if e.kind == "loop.terminate"]
    if not terminates:
        return False
    return terminates[-1].payload.get("reason") != "final_answer"


def has_failure_events(events: list) -> bool:
    """A run has failure events if any event carries a 'failure' payload key."""
    return any(
        isinstance(e.payload, dict) and e.payload.get("failure")
        for e in events
    )


def extract_failure_contexts(events: list) -> list[dict]:
    """For each failure event, find the brain.request context that preceded it.

    Returns a list of {"turn": int, "failure_kind": str, "context": list[dict]}
    where context is the message list in render() format (<role> content).
    """
    contexts = []
    last_request: dict | None = None
    last_turn = 0

    for ev in events:
        if ev.kind == "brain.request":
            last_request = ev.payload.get("prompt", [])
            last_turn = ev.iter
        elif ev.kind in ("protocol.error", "tool.result", "loop.terminate"):
            failure_kind = ev.payload.get("failure")
            if failure_kind and last_request is not None:
                contexts.append({
                    "turn": last_turn,
                    "failure_kind": failure_kind,
                    "context": last_request,
                })
                # Don't clear last_request — the same context may precede
                # multiple related failures (e.g. protocol.error then continue)
    return contexts


def render_to_native_ollama(messages_rendered: list[str]) -> list[dict]:
    """Convert '<role> content' render() format to Ollama chat format."""
    native = []
    for rendered in messages_rendered:
        # render() produces "<role> content" — split on first '>'
        gt = rendered.find(">")
        if gt < 0:
            native.append({"role": "user", "content": rendered})
            continue
        role = rendered[1:gt]  # strip leading '<'
        content = rendered[gt + 1:].lstrip()
        native.append({"role": role, "content": content})
    return native


def render_to_native_gemini(messages_rendered: list[str]) -> dict:
    """Convert '<role> content' render() format to Gemini generateContent format."""
    system_parts = []
    contents = []
    for rendered in messages_rendered:
        gt = rendered.find(">")
        if gt < 0:
            contents.append({"role": "user", "parts": [{"text": rendered}]})
            continue
        role = rendered[1:gt]
        content = rendered[gt + 1:].lstrip()
        if role == "system":
            system_parts.append(content)
        else:
            gemini_role = "user" if role == "user" else "model"
            contents.append({"role": gemini_role, "parts": [{"text": content}]})
    result = {"contents": contents}
    if system_parts:
        result["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
    return result


def make_brain(brain_name: str):
    """Construct a brain by name. Real Ollama/Gemini need network/key."""
    if brain_name == "mock":
        return MockBrain()
    if brain_name == "ollama":
        return OllamaBrain()  # needs localhost:11434
    if brain_name == "gemini":
        return GeminiBrain()  # needs GEMINI_API_KEY
    raise ValueError(f"unknown brain: {brain_name}")


def replay_context(brain, context_native) -> str:
    """Replay a context against a brain and return the reply text.

    For Ollama: context_native is a list of {"role", "content"} dicts.
    For Gemini: context_native is a dict with "contents" (+ optional systemInstruction).
    For MockBrain: context_native is ignored (scripted).
    """
    if isinstance(brain, MockBrain):
        return brain.complete([]).text

    if isinstance(brain, OllamaBrain):
        messages = [Message(role=m["role"], content=m["content"]) for m in context_native]
        return brain.complete(messages).text

    if isinstance(brain, GeminiBrain):
        # Gemini needs Message objects for its own payload builder
        messages = []
        for c in context_native.get("contents", []):
            role = c["role"]
            text = c["parts"][0]["text"] if c.get("parts") else ""
            our_role = "user" if role == "user" else "assistant"
            messages.append(Message(role=our_role, content=text))
        if "systemInstruction" in context_native:
            sys_text = context_native["systemInstruction"]["parts"][0]["text"]
            messages.insert(0, Message(role="system", content=sys_text))
        return brain.complete(messages).text

    raise ValueError(f"unknown brain type: {type(brain)}")


def report_failing_runs(groups: dict[str, list]) -> None:
    """Print a narrated report of every failing run."""
    failing = {rid: evs for rid, evs in groups.items() if is_failing_run(evs) or has_failure_events(evs)}
    if not failing:
        print("No failing runs found — every run ended with Final Answer.")
        return

    print(f"\n{'='*60}")
    print(f"DETECTIVE REPORT: {len(failing)} failing run(s)")
    print(f"{'='*60}")

    for run_id, events in failing.items():
        terminates = [e for e in events if e.kind == "loop.terminate"]
        reason = terminates[-1].payload.get("reason", "unknown") if terminates else "no terminate event"
        failure_events = [e for e in events if isinstance(e.payload, dict) and e.payload.get("failure")]
        failure_kinds = sorted({e.payload.get("failure") for e in failure_events})

        print(f"\n--- Run {run_id} ---")
        print(f"  termination reason: {reason}")
        print(f"  failure kinds: {', '.join(failure_kinds) if failure_kinds else '(none recorded)'}")
        print(f"  total events: {len(events)}")

        contexts = extract_failure_contexts(events)
        print(f"  failure contexts to replay: {len(contexts)}")
        for ctx in contexts:
            print(f"    turn {ctx['turn']}: {ctx['failure_kind']}")
            for msg in ctx["context"]:
                print(f"      {msg[:80]}{'…' if len(msg) > 80 else ''}")


def replay_all(groups: dict[str, list], brain_name: str) -> int:
    """Replay every failure context against the given brain. Returns exit code."""
    brain = make_brain(brain_name)
    all_ok = True

    for run_id, events in groups.items():
        if not (is_failing_run(events) or has_failure_events(events)):
            continue

        contexts = extract_failure_contexts(events)
        if not contexts:
            continue

        print(f"\n--- Replaying run {run_id} against {brain_name} ---")
        for ctx in contexts:
            print(f"  turn {ctx['turn']} ({ctx['failure_kind']}): ", end="", flush=True)
            try:
                if isinstance(brain, OllamaBrain):
                    native = render_to_native_ollama(ctx["context"])
                elif isinstance(brain, GeminiBrain):
                    native = render_to_native_gemini(ctx["context"])
                else:
                    native = ctx["context"]

                reply = replay_context(brain, native)
                if reply.strip():
                    print(f"OK — {reply[:80]}{'…' if len(reply) > 80 else ''}")
                else:
                    print(f"SILENT — empty reply (same failure mode)")
                    all_ok = False
            except Exception as e:
                print(f"FAILED — {type(e).__name__}: {e}")
                all_ok = False

    return 0 if all_ok else 1


def bisect_think(groups: dict[str, list]) -> int:
    """Try think on/off for each failure context (Ollama only).

    Returns exit code: 0 if all contexts produce non-empty replies under
    at least one think setting.
    """
    brain = OllamaBrain()  # real Ollama
    all_ok = True

    for run_id, events in groups.items():
        if not (is_failing_run(events) or has_failure_events(events)):
            continue

        contexts = extract_failure_contexts(events)
        for ctx in contexts:
            native = render_to_native_ollama(ctx["context"])
            messages = [Message(role=m["role"], content=m["content"]) for m in native]

            results = {}
            for think in (False, True):
                try:
                    brain.think = think
                    reply = brain.complete(messages).text
                    results[think] = reply
                except Exception as e:
                    results[think] = f"ERROR: {e}"

            any_ok = any(isinstance(v, str) and v.strip() for v in results.values())
            if not any_ok:
                all_ok = False

            print(f"\n  Run {run_id}, turn {ctx['turn']} ({ctx['failure_kind']}):")
            for think, reply in results.items():
                tag = "OK " if isinstance(reply, str) and reply.strip() else "FAIL"
                print(f"    think={think}: {tag} {reply[:60]}{'…' if len(reply) > 60 else ''}")

    return 0 if all_ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Detective Kit: replay probe for the M6 trace")
    parser.add_argument("--brain", choices=["mock", "ollama", "gemini"],
                        default="mock", help="brain to replay against (default: mock)")
    parser.add_argument("--bisect", choices=["think"],
                        help="one-variable bisect: try think on/off (Ollama only)")
    args = parser.parse_args(argv)

    events = read_events()

    if not events:
        print("No trace events found — run the agent first.")
        return 1

    groups = group_events_by_run(events)
    print(f"Trace contains {len(events)} events across {len(groups)} run(s)")

    report_failing_runs(groups)

    if args.bisect:
        return bisect_think(groups)

    return replay_all(groups, args.brain)


if __name__ == "__main__":
    raise SystemExit(main())
