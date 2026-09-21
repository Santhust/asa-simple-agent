#!/usr/bin/env python3
"""asa · a simple agent — command-line front door.

Milestone 1 (the shell): prove the tooling works end to end and run the very first
narrated conversation against the MockBrain. There is no agent loop yet — that arrives
in Milestone 2. Right now we just:

  1. build a tiny conversation (Message list),
  2. hand it to a Brain (a text-in/text-out box),
  3. print everything, narrated, so the abstraction is visible before any agent exists.
"""

from __future__ import annotations

import argparse
import time

import asa.narrate as N
from asa.brain import Brain, Message, MockBrain

BRAINS = {"mock": MockBrain}  # ollama -> M7, gemini -> M8, gpt2 -> M10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="asa — a simple agent (M1 shell)")
    p.add_argument("--task", default="say hello to me", help="the task to discuss")
    p.add_argument("--brain", default="mock", choices=sorted(BRAINS), help="which brain to use")
    p.add_argument("--model", default=None, help="override the brain's default model tag")
    p.add_argument("--explain", action="store_true", help="add the deeper 'why' annotations")
    p.add_argument("--no-color", action="store_true", help="plain output (also honors NO_COLOR)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    brain_cls = BRAINS[args.brain]
    brain: Brain = brain_cls(model=args.model) if args.model else brain_cls()

    N.h1(f"asa — a simple agent · first narrated run (Milestone 1: the shell)")
    N.kv("brain", brain.describe())
    N.kv("task", repr(args.task))

    N.h2("1 · We build a conversation (a list of Message objects)")
    messages = [
        Message(role="system", content="You are 'asa', a teaching agent built from scratch."),
        Message(role="user", content=args.task),
    ]
    for m in messages:
        N.info(m.render())
    if args.explain:
        N.why("An agent conversation is just a list of role-tagged texts. The system message"
              " is permanent standing instruction; the task goes in the user message.")

    N.h2("2 · We hand the conversation to the Brain (a text-in/text-out box)")
    N.why("To the agent, a model is nothing but this: messages in, one string out. No tokens,"
          " no embeddings, no parameters — we do not micromanage the model; we only talk to it.")
    t0 = time.time()
    completion = brain.complete(messages, temperature=0.7, max_tokens=64)
    elapsed = time.time() - t0

    N.h2("3 · The Brain answered")
    N.code(repr(completion.text))
    N.kv("model", completion.model)
    N.kv("prompt_tokens (est.)", completion.prompt_tokens)
    N.kv("completion_tokens (est.)", completion.completion_tokens)
    N.kv("elapsed", f"{elapsed * 1000:.0f} ms")

    N.h2("What just happened — and what comes next")
    N.info("The Brain abstraction is in place. There is no agent yet: no memory, no tools,")
    N.info("no loop. Those arrive one small milestone at a time:")
    N.info("  M2 loop skeleton · M3 tools & registry · M4 ReAct parser · M5 full loop")
    if args.explain:
        N.why("MockBrain returns a canned string every time, so the shell runs offline with"
              " zero dependencies. Every later milestone keeps working against it via the "
              "same Brain interface — then real brains (Ollama, Gemini) slot in unchanged.")
    N.ok("shell ready.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())