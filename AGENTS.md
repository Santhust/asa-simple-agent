# asa — "a simple agent" (educational)

Goal: learn agentic AI by implementing a ReAct-style agent from scratch in Python, with every
internal observable and an interactive HTML playground. Learning-paced, NOT a product.
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
  Convention (from M3.1, once a second lab existed): each lab starts with the
  two-line `sys.path` bootstrap — labs are script-first, never installed.
- `playground/`: self-contained HTML doc: animated architecture diagram, trace player,
  breakage lab, two-protocol comparison, model zoo, glossary + self-check quiz.
  Plays shipped pre-recorded traces offline (no network needed).
- `docs/`: 7 illustrated topics, one lesson each.

## Habits (user-mandated)
- Small educative milestones; tests + a narrated demo at EVERY step; checkpoint with the user.
- Re-orient from PLAN.md / AGENTS.md in new sessions (context compaction erases the plan).
- Never skip tests; state what each test demonstrates and why it matters.
- Verbose outputs: explain what is happening, how, and why — all details.

### Working rhythm (user-mandated · addendum 2026-09)
Learning-paced, never product-paced. Rules that must not be shortcut:
- Sub-milestones: every milestone is split into concept-based sub-milestones. In ONE step,
  implement a single concept, explain what/how/why, then STOP — the user reads the
  generated file(s), we build understanding together, then start the next sub-milestone.
  Never batch several concepts at once.
- Session-start ritual (self-healing after compaction): re-read AGENTS.md + PLAN.md's
  milestone status and per-milestone progress blocks. The journey picture lives in
  `docs/m1-diagram.svg` (plus `out/frames/` PNGs and `git log` per-step commits); the
  current in-flight step is recorded in PLAN.md.
- Commit after EVERY sub-milestone: small, atomic, one-concept commits.
- The story diagram is a living artifact: refresh `docs/m1-diagram.svg` whenever functionality
  changes (solid = built, dashed = planned) so every step has a graphical before/after.
  Rasterize one PNG frame per stage into `out/frames/` (gitignored; rsvg-convert), and stitch
  the journey with `magick -delay 150 out/frames/*.png journey.gif`. The git history of the
  SVG is the durable timeline.
- At milestone close, regenerate `docs/timeline.html` — an offline prev/next slideshow of the
  frames with one caption per stage (seed of the playground's animated trace player, M12).

## Commands
(CANONICAL to be frozen in Milestone 1)
- `python run.py --task "..." [--brain <name>] [--explain] [--trace out/t.jsonl]`
- `python bench.py --task "..." `         (same task across brains, side by side)
- `python serve.py`                        (live SSE mode for the HTML playground)
- `python -m pytest`                       (tests; run after every milestone)
