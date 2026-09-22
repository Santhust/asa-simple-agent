#!/usr/bin/env python3
"""asa · a simple agent — command-line front door.

Milestone 2 (the loop skeleton): run.py now drives the AGENT, not the hand-rolled
shell. The agent wires Task -> ContextWindow -> Brain -> memory; the CLI is the
mouthpiece that narrates what it sees: the memory BEFORE a run, the mid-run internals
the agent narrates itself, and the structured result with answer and outcome kept apart.

Tools, ReAct parsing and the real loop arrive M3-M5 — nothing in this file changes then,
because the agent is behind one stable interface (run(task) -> AgentResult).
"""

from __future__ import annotations

import argparse

import asa.narrate as N
from asa.agent import Agent
from asa.brain import Brain, MockBrain
from asa.memory import ContextWindow

BRAINS = {"mock": MockBrain}  # ollama -> M7, gemini -> M8, gpt2 -> M10


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="asa — a simple agent (M2: loop skeleton)")
    p.add_argument("--task", default="say hello to me", help="the task to discuss")
    p.add_argument("--brain", default="mock", choices=sorted(BRAINS), help="which brain to use")
    p.add_argument("--model", default=None, help="override the brain's default model tag")
    p.add_argument("--max-steps", type=int, default=1,
                   help="max loop turns — the loop guard (M2's only termination control)")
    p.add_argument("--script", nargs="+", default=None,
                   help="MockBrain scripted replies, one per brain call (deterministic demos)")
    p.add_argument("--explain", action="store_true", help="add the deeper 'why' annotations")
    p.add_argument("--no-color", action="store_true", help="plain output (also honors NO_COLOR)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    brain_cls = BRAINS[args.brain]
    brain: Brain = brain_cls(model=args.model) if args.model else brain_cls()
    if args.script:
        brain = MockBrain(script=args.script, model=brain.model)

    N.h1("asa — a simple agent · narrated run (Milestone 2: the loop skeleton)")
    N.kv("brain", brain.describe())
    N.kv("task", repr(args.task))
    N.kv("max_steps", args.max_steps)

    N.h2("1 · We build an Agent and its ContextWindow (the memory)")
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

    N.h2("What just happened — and what comes next")
    N.info("The Agent is a text-in/text-out machine with memory. No tools, no parsing,")
    N.info("no termination logic beyond the step budget. Those arrive one at a time:")
    N.info("  M3 tools & registry · M4 ReAct parser · M5 full loop with Final Answer")
    N.ok("loop skeleton ready.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())