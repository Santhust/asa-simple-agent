#!/usr/bin/env python3
"""asa · a simple agent — command-line front door.

Milestones 3.5–3.6 (hands wired, M3 closed out): run.py builds the agent WITH
its hands — the ToolRegistry lands in the system prompt (the model reads the
catalogue) and --no-tools demonstrably builds the honest empty one. The loop
still cannot ACT: parsing model text into ToolCall is M4; termination beyond
the step budget is M5. The CLI is the mouthpiece that narrates what it sees: the
memory BEFORE a run, the mid-run internals the agent narrates itself, and
the structured result with answer and outcome kept apart.
"""

from __future__ import annotations

import argparse

import asa.narrate as N
from asa.agent import Agent
from asa.brain import Brain, GeminiBrain, MockBrain, OllamaBrain
from asa.memory import ContextWindow
from asa.registry import ToolRegistry

# The brain zoo, wired one member at a time per milestone:
#   mock   = deterministic (M2)   |   ollama = first REAL local brain (M7)
#   gemini = first CLOUD brain (M8)   |   coming: gpt2 -> M10
BRAINS = {"mock": MockBrain, "ollama": OllamaBrain, "gemini": GeminiBrain}


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="asa — a simple agent (M3: tools & registry wired)")
    p.add_argument("--task", default="say hello to me", help="the task to discuss")
    p.add_argument("--brain", default="mock", choices=sorted(BRAINS), help="which brain to use")
    p.add_argument("--model", default=None, help="override the brain's default model tag")
    p.add_argument("--max-steps", type=int, default=1,
                   help="max loop turns — the loop guard (M2's only termination control)")
    # --script = the TEACHING override. Its intent: rehearsal before reality.
    # Instead of invoking any (possibly real) model, it swaps the selected brain
    # for a scripted, deterministic MockBrain — so the exact CLI that will later
    # drive Ollama/Gemini (M7/M8) can first be rehearsed offline with canned
    # replies. The swap is reported loudly in main(); it is never silent.
    p.add_argument("--script", nargs="+", default=None,
                   help="scripted MockBrain replies, one per brain call — OVERRIDES "
                        "--brain with a deterministic offline stand-in (teaching/demo mode)")
    p.add_argument("--no-tools", action="store_true",
                   help="wire an explicitly EMPTY registry — the agent reads the "
                        "honest 'you have no tools' paragraph (M3.2's empty catalogue)")
    p.add_argument("--explain", action="store_true", help="add the deeper 'why' annotations")
    p.add_argument("--no-color", action="store_true", help="plain output (also honors NO_COLOR)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    brain_cls = BRAINS[args.brain]
    brain: Brain = brain_cls(model=args.model) if args.model else brain_cls()
    if args.script:
        brain = MockBrain(script=args.script, model=brain.model)

    N.h1("asa — a simple agent · narrated run (real brains: mock · ollama · gemini)")
    N.kv("brain", brain.describe())
    N.kv("task", repr(args.task))
    N.kv("max_steps", args.max_steps)
    if args.script:
        N.warn(
            f"--script is active: selected brain {args.brain!r} is replaced by a "
            f"scripted MockBrain — offline, deterministic, zero real model calls."
        )

    N.h2("1 · We build an Agent and its ContextWindow (the memory)")
    if args.no_tools:
        registry = ToolRegistry()  # explicitly empty — the honest no-hands agent
        agent = Agent(brain, max_steps=args.max_steps, narrate=True, registry=registry)
        N.warn("--no-tools is active: an explicitly EMPTY registry is wired; the "
               "system prompt carries 'You have no tools…' (the M3.2 empty catalogue)")
    else:
        agent = Agent(brain, max_steps=args.max_steps, narrate=True)
    N.info(
        f"memory before run: {len(agent.memory)} message · "
        f"~{agent.memory.token_count()} tokens (budget {agent.memory.budget_tokens})"
    )
    if args.explain:
        N.why("Memory is an ordered, token-counted transcript. The system prompt is "
              "sacred; on overflow trim() forgets the OLDEST turn first — age-first.")

    N.h2("2 · Agent.run(task) — Task -> Memory -> Brain -> memory")
    result = agent.run(args.task)  # the agent narrates each internal step itself

    N.h2("3 · The structured result — answer and outcome, kept apart")
    N.kv("answer", repr(result.text))
    N.kv("terminate_reason", result.terminate_reason)
    N.kv("steps", result.steps)
    N.kv("tokens", result.tokens)
    N.info(
        f"memory after run: {len(agent.memory)} messages · "
        f"~{agent.memory.token_count()} tokens"
    )
    if args.explain:
        N.why("'answer' is model text; 'terminate_reason' is OUR bookkeeping about how "
              "the loop ended. M2 stops every run on the step budget; M5 adds "
              "'Final Answer:' as another reason — same shape, new cases.")

    if args.explain:
        N.h2("4 · Loose end: what trim() would do on a tight budget")
        demo = ContextWindow(system=agent.memory.messages[0].content)
        for m in agent.memory.messages[1:]:
            demo.add(m.role, m.content)
        budget = max(1, demo.token_count() // 3)
        forgotten = demo.trim(budget=budget)
        N.info(
            f"trim(budget={budget}) forgot {forgotten} oldest turn(s); system + "
            f"newest survived ({demo.token_count()} tokens now)."
        )
        N.why("Forgetting is explicit and visible, never silent — that is how real "
              "platforms run 'context on a budget'.")

    N.h2("What just happened — and what the run left behind")
    N.info("Full loop, live: Task -> memory -> brain -> the M4 ReAct reader turns the")
    N.info("model text into ToolCall / gentle-repair / Final Answer (M5). Every internal")
    N.info("step was written to the M6 flight recorder: asa/traces/trace.jsonl.")
    N.ok("the loop ran end to end — scripted or real, the seam is identical.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())