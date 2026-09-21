# asa — "a simple agent" (educational)

Goal: learn agentic AI by implementing a ReAct-style agent from scratch in Python, with every
internal observable and an interactive HTML playground. Learning-paced, NOT a product.
(Originally "asca" = a simple coding agent; deferred as a possible later spin-off.)
Read the full game plan in `PLAN.md` before starting work; update it as the plan evolves.

## Architecture (two protocols, one core)
- Core speaks only `ToolCall(name, args)`. Two protocol adapters feed it:
  - `protocol_react.py`  : textual ReAct (`Thought:` / `Action:` / `Action Input:`) — universal
  - `protocol_native.py` : API function-calling (e.g. Gemini `tools=[...]` payloads)
- Loop: Task -> ContextWindow -> Brain -> text/native -> protocol -> ToolCall
       -> ToolRegistry -> tool runs -> observation back into context
       terminate on `Final Answer:` | max_steps | failure policy.
- `asa/` package: memory.py, tool.py, registry.py, protocol_react.py, protocol_native.py,
  brain.py, agent.py, trace.py, `tools/` + `lab/` (single-part learning scripts).

## Brain zoo (config-driven: model is a string; swappable, agent code identical)
- `MockBrain`   : deterministic, no deps (tests, offline demo, golden traces)
- `OllamaBrain` : local; llama3.2:1b default (Pi5 8GB ~7-18 tok/s); stdlib HTTP, no pip dep
- `GeminiBrain` : Google free tier, Gemini 3.1 / 3.5 Flash Lite
                  (15 RPM / 250K TPM / 500 RPD) + Gemma 4 26B / 31B by name; key available
- `GPT2Brain`   : INTENTIONAL FAILURE demo (base LM, not instruction-tuned)
- swapping brains IS the lesson: a model is a text-in/text-out box to the agent.

## Learning layers
- CLI narrator: every run explains what/how/why, color-coded; --verbose / --explain flags.
- `lab/*.py`: poke one internal at a time (e.g. lab/parser_lab.py).
- `playground/`: self-contained HTML doc: animated architecture diagram, trace player,
  breakage lab, two-protocol comparison, model zoo, glossary + self-check quiz.
  Plays shipped pre-recorded traces offline (no network needed).
- `docs/`: 7 illustrated topics, one lesson each.

## Habits (user-mandated)
- Small educative milestones; tests + a narrated demo at EVERY step; checkpoint with the user.
- Re-orient from PLAN.md / AGENTS.md in new sessions (context compaction erases the plan).
- Never skip tests; state what each test demonstrates and why it matters.
- Verbose outputs: explain what is happening, how, and why — all details.

## Commands
(CANONICAL to be frozen in Milestone 1)
- `python run.py --task "..." [--brain <name>] [--explain] [--trace out/t.jsonl]`
- `python bench.py --task "..." `         (same task across brains, side by side)
- `python serve.py`                        (live SSE mode for the HTML playground)
- `python -m pytest`                       (tests; run after every milestone)