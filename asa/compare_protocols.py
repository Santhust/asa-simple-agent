"""asa.compare_protocols — M9.3 side-by-side benchmark lab.

Runs the SAME task through both protocols on the SAME brain and reports the
delta: drift rate, repair count, steps, tokens, wall time, final answer.

Purpose: make the "two protocols, one core" lesson MEASURABLE. ReAct (M4)
teaches the model a text grammar and repairs its drift (M4.3); native (M9)
lets the API do the structuring — no regex, no kwargs parser, no repair. This
lab puts numbers on that claim.

It is deterministic and offline-first: every metric is computed from the
trace (M6) and the AgentResult, never from model content semantics. "ok" is
procedural (a Final Answer landed), never a truth claim.
"""

from __future__ import annotations

import argparse
import time

from asa.agent import Agent
from asa.brain import Brain, MockBrain, OllamaBrain
from asa.trace import read_events

# Brain factories that speak BOTH protocols. Only Gemini is native-capable so
# far; MockBrain/OllamaBrain are text-only (supports_native() == False), so
# they contribute the ReAct side of the comparison and keep the lab runnable
# offline with zero credentials.
try:  # gemini is key-gated: never hardcode, never fail the lab without a key
    import os as _os
    from asa.brain import GeminiBrain
    if _os.environ.get("GEMINI_API_KEY"):
        BRAIN_CLASSES: dict[str, type[Brain]] = {
            "mock": MockBrain,
            "ollama": OllamaBrain,
            "gemini": GeminiBrain,
        }
    else:
        BRAIN_CLASSES = {"mock": MockBrain, "ollama": OllamaBrain}
except Exception:  # pragma: no cover — import-time guard only
    BRAIN_CLASSES = {"mock": MockBrain, "ollama": OllamaBrain}

#: Brain names that can speak native function calling (M9). Everything else
#: is text-only and contributes the ReAct side of the comparison only.
NATIVE_CAPABLE = {"gemini"}

PROTOCOLS = ("react", "native")


def _collect_metrics(result, run_events) -> dict:
    """Turn one run's AgentResult + trace events into a metrics dict."""
    drifts = [e for e in run_events if e.kind == "protocol.error"]
    drift_count = len(drifts)
    tool_calls = [e for e in run_events if e.kind == "tool.invoke"]
    tool_results = [e for e in run_events if e.kind == "tool.result"]
    return {
        "steps": result.steps,
        "tokens": result.tokens,
        "terminate_reason": result.terminate_reason,
        "answer": result.text,
        "drift_count": drift_count,
        "repair_count": drift_count,   # each drift met with one gentle note = one repair
        "tool_calls": len(tool_calls),
        "tool_results": len(tool_results),
    }


def run_once(brain: Brain, task: str, max_steps: int = 4,
             native: bool = False) -> dict:
    """Run one task through one protocol on one brain; return metrics.

    Clears the trace first so each run's metrics come from its own events
    (the trace file is shared global state — see M6/M8.4.1).
    """
    from asa.trace import clear_trace
    clear_trace()
    agent = Agent(brain, narrate=False, max_steps=max_steps)
    t0 = time.perf_counter()
    result = agent.run(task)
    wall = time.perf_counter() - t0
    events = read_events()
    metrics = _collect_metrics(result, events)
    metrics["wall_s"] = round(wall, 4)
    metrics["protocol"] = "native" if native else "react"
    metrics["brain"] = type(brain).__name__
    metrics["model"] = getattr(brain, "model", "-")
    return metrics


def _make_brain(brain_name: str, native: bool) -> Brain:
    """Construct a brain for the given protocol.

    Text brains are built plain. A native-capable brain (gemini) is built
    with native=True so it offers functionDeclarations + AUTO mode.
    """
    cls = BRAIN_CLASSES[brain_name]
    if native and brain_name in NATIVE_CAPABLE:
        return cls(native=True)
    return cls()


def compare(task: str, brain_name: str, runs: int = 3,
            max_steps: int = 4) -> dict:
    """Same task, same brain, both protocols; averages over `runs` trials.

    Returns a dict keyed by protocol, each holding a list of per-trial metrics
    plus the averaged summary. Text-only brains yield react metrics and a
    ``None`` native summary.
    """
    results: dict[str, list[dict]] = {p: [] for p in PROTOCOLS}
    for trial in range(runs):
        results["react"].append(
            run_once(_make_brain(brain_name, native=False), task, max_steps,
                     native=False))
        if brain_name in NATIVE_CAPABLE:
            results["native"].append(
                run_once(_make_brain(brain_name, native=True), task, max_steps,
                         native=True))
    summary = {}
    for proto, trials in results.items():
        if not trials:
            summary[proto] = None
            continue
        n = len(trials)
        summary[proto] = {
            "trials": n,
            "avg_steps": round(sum(t["steps"] for t in trials) / n, 2),
            "avg_tokens": round(sum(t["tokens"] for t in trials) / n, 1),
            "avg_wall_s": round(sum(t["wall_s"] for t in trials) / n, 3),
            "avg_drift": round(sum(t["drift_count"] for t in trials) / n, 2),
            "avg_repair": round(sum(t["repair_count"] for t in trials) / n, 2),
            "avg_tool_calls": round(sum(t["tool_calls"] for t in trials) / n, 2),
            "final_answers": sum(1 for t in trials if t["terminate_reason"] == "final_answer"),
            "sample_answer": trials[0]["answer"],
        }
    return {"task": task, "brain": brain_name, "runs": runs,
            "summary": summary, "trials": results}


# -- narration (CLI mouthpiece) ----------------------------------------------

def narrate(comparison: dict) -> str:
    """Render a human-readable comparison (no rich deps — script-first rule)."""
    lines = []
    lines.append("━━━ asa protocol comparison — same task, same brain, two protocols ━━━")
    lines.append(f"  task: {comparison['task']!r}")
    lines.append(f"  brain: {comparison['brain']}  ·  trials per protocol: {comparison['runs']}")
    lines.append("")
    heads = ("protocol", "trials", "steps", "tokens", "wall_s", "drift", "repair", "tool_calls", "final_answer")
    rows = []
    for proto in PROTOCOLS:
        s = comparison["summary"][proto]
        if s is None:
            rows.append((proto, "-", "-", "-", "-", "-", "-", "-", "n/a (text-only brain)"))
        else:
            rows.append((proto, s["trials"], s["avg_steps"], s["avg_tokens"],
                         s["avg_wall_s"], s["avg_drift"], s["avg_repair"],
                         s["avg_tool_calls"], f'{s["final_answers"]}/{s["trials"]}'))
    widths = [max(len(str(r[j])) for r in ([heads] + rows)) for j in range(len(heads))]
    lines.append("  " + "  ".join(str(h).ljust(w) for h, w in zip(heads, widths)))
    lines.append("  " + "  ".join("-" * w for w in widths))
    for r in rows:
        lines.append("  " + "  ".join(str(v).ljust(w) for v, w in zip(r, widths)))
    lines.append("")
    lines.append("  drift   = gentle notes sent back to the model (protocol drift / empty reply)")
    lines.append("  repair  = drift → observation → retry cycles (failure is data)")
    lines.append("  ok      = procedural success (a Final Answer landed), not truth")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="asa compare_protocols — ReAct vs native, side by side (M9.3)")
    p.add_argument("--task", default="What is 7*6? Use the calculator tool to "
                   "compute it, then give the final answer.",
                   help="the task every protocol must attempt identically")
    p.add_argument("--brain", default="mock", choices=sorted(BRAIN_CLASSES),
                   help="which brain to run both protocols on")
    p.add_argument("--runs", type=int, default=3,
                   help="trials per protocol (averaged into the summary)")
    p.add_argument("--max-steps", type=int, default=4,
                   help="step budget per run")
    args = p.parse_args(argv)

    if args.brain not in BRAIN_CLASSES:
        print(f"unknown brain: {args.brain} — available: {sorted(BRAIN_CLASSES)}")
        return 2
    if "gemini" not in BRAIN_CLASSES and args.brain == "gemini":
        print("gemini not available — set GEMINI_API_KEY for the cloud side of the lab.")
        return 2

    comparison = compare(args.task, args.brain, runs=args.runs,
                         max_steps=args.max_steps)
    print(narrate(comparison))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
