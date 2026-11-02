#!/usr/bin/env python3
"""asa · bench — the same task across brains, side by side (M7.4).

What bench measures — and what it honestly does NOT:

MEASURES
  * wall-clock seconds for a full agent.run()      — speed reality on THIS machine
  * steps, tokens, terminate_reason                — loop behavior per brain
  * tok/s from Ollama's own counters               — hardware pin for the stage note
    (eval_count / eval_duration, aggregated over the run — not our stopwatch)

DOES NOT MEASURE
  * semantic truth. `terminate_reason == final_answer` is PROCEDURAL success:
    the model obeyed the loop protocol and produced A final answer. A model
    can reach final_answer with a wrong number. Correctness of content is a
    human judgement (or, later, a grader) — bench refuses to fake it.

The through-line: brains are swappable text-in/text-out boxes; the LOOP —
memory, protocol, tools, trace — is identical. Bench makes the cost of the
swap visible, brain being the only variable.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Callable

from asa.agent import Agent
from asa.brain import GeminiBrain, MockBrain, OllamaBrain

# The brain zoo, same mapping as run.py (gemini -> M8/M9, gpt2 -> M10).
# gemini is included only when a key is available — bench never hardcodes
# credentials and never fails the whole run because one brain can't reach the net.
BRAIN_FACTORIES: dict[str, Callable[[], object]] = {
    "mock": MockBrain,
    "ollama": OllamaBrain,
}

if __import__("os").environ.get("GEMINI_API_KEY"):
    BRAIN_FACTORIES["gemini"] = lambda: GeminiBrain(native=False)


def run_bench(task: str, factories: dict[str, Callable[[], object]],
              max_steps: int = 4, native: bool = False) -> list[dict]:
    """Run the SAME task through each brain; one honest record per brain.

    `native` flips GeminiBrain into function-calling mode (M9): it offers
    functionDeclarations + AUTO mode and reads structured functionCalls instead
    of parsing ReAct letters. Every other brain stays on the text path.
    """
    records = []
    for name, factory in factories.items():
        brain = factory()
        if name == "gemini" and native:
            brain = GeminiBrain(native=True, model=brain.model)
        agent = Agent(brain, narrate=False, max_steps=max_steps)
        t0 = time.perf_counter()
        result = agent.run(task)
        wall = time.perf_counter() - t0
        record = {
            "brain": name,
            "model": getattr(brain, "model", "-"),
            "protocol": "native" if (name == "gemini" and native) else "react",
            "ok": result.terminate_reason == "final_answer",  # procedural ONLY
            "steps": result.steps,
            "tokens": result.tokens,
            "wall_s": round(wall, 2),
            "terminate_reason": result.terminate_reason,
            "answer": result.text,
        }
        # Throughput from the model's own counters, if the brain reports any.
        # OllamaBrain aggregates eval_count/eval_duration across the whole run.
        total_tok = getattr(brain, "total_eval_count", 0)
        total_dur = getattr(brain, "total_eval_duration", 0.0)
        if total_tok and total_dur:
            record["tok_per_s"] = round(total_tok / total_dur, 1)
        records.append(record)
    return records


def format_table(records: list[dict]) -> str:
    """A plain-text comparison table (no rich deps — script-first rule)."""
    if not records:
        return "(no records)"
    heads = ("#", "brain", "model", "proto", "ok", "steps", "tokens", "tok/s", "wall_s", "terminate")

    def fields(i: int, r: dict) -> tuple:
        return (i, r["brain"], r["model"], r["protocol"], "✓" if r["ok"] else "✗",
                r["steps"], r["tokens"], r.get("tok_per_s", "-"),
                r["wall_s"], r["terminate_reason"])

    rows = [fields(i, r) for i, r in enumerate(records, 1)]
    longest = [max(len(str(h)), max(len(str(f[j])) for f in rows))
               for j, h in enumerate(heads)]
    out = ["  ".join(str(h).ljust(w) for h, w in zip(heads, longest))]
    out.append("  ".join("-" * w for w in longest))
    for f in rows:
        out.append("  ".join(str(v).ljust(w) for v, w in zip(f, longest)))
    return "\n".join(out)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="bench — same task across brains, side by side (M7.4)")
    p.add_argument("--task", default="What is 7*6? Use the calculator tool to "
                   "compute it, then give the final answer.",
                   help="the task every brain must attempt identically")
    p.add_argument("--brains", default="mock,ollama",
                   help="comma-separated brain names (see BRAIN_FACTORIES)")
    p.add_argument("--max-steps", type=int, default=4,
                   help="step budget per brain run")
    p.add_argument("--native", action="store_true",
                   help="M9: run Gemini through native function calling instead of ReAct text")
    p.add_argument("--json", action="store_true", help="print records as JSON (for tooling)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    names = [n.strip() for n in args.brains.split(",") if n.strip()]
    unknown = [n for n in names if n not in BRAIN_FACTORIES]
    if unknown:
        print(f"unknown brain(s): {', '.join(unknown)} — available: {sorted(BRAIN_FACTORIES)}")
        return 2
    if args.native and "gemini" not in names:
        print("--native requires --brains gemini — available: "
              + ", ".join(sorted(BRAIN_FACTORIES)))
        return 2
    factories = {n: BRAIN_FACTORIES[n] for n in names}

    records = run_bench(args.task, factories, max_steps=args.max_steps, native=args.native)

    if args.json:
        print(json.dumps(records, indent=2))
    else:
        print()
        print("━━━ asa bench — same task, different brains ━━━")
        print(f"  task: {args.task!r}")
        print(f"  ok column means PROCEDURAL success (a Final Answer landed), not truth.")
        print()
        print(format_table(records))
        print()
        print("  note: mock is scripted; ollama is a real model on this machine —")
        print("  speed differences are the hardware+model reality, not a bug.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
