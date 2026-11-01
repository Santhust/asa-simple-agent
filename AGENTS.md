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
- `asa/` package: memory.py, tool.py, registry.py, brain.py, agent.py, `tools/` + `lab/`
  (single-part scripts). Planned: protocol_react.py (M4), protocol_native.py (M9), trace.py (M6).

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
- Re-orient from PLAN.md / AGENTS.md in new sessions (context compaction erases the plan);
  `docs/decisions-archive.md` holds M1/M2/M3 detail — read it only on demand.
- Never skip tests; state what each test demonstrates and why it matters.
- Verbose outputs: explain what is happening, how, and why — all details.

### Working rhythm (user-mandated · addendum 2026-09)
Learning-paced, never product-paced. Rules that must not be shortcut:
- **Story first, names second**: When explaining a milestone/step/intern or laying out work, start with a plain-language story — situation → what changes → in one breath. Steps come as nouns/verbs, not jargon. Technical names (classes/modules/tests) are a quiet second layer. The value is the narrative style, not any particular analogy.
- **Pause after each sub-milestone**: After implementing one concept and committing, stop. Let the user read the generated files, confirm understanding, and approve before the next sub-milestone starts. Never batch multiple concepts into one edit or commit. The pause is the learning rhythm — one step, one check, one build.
- **Commit after EVERY sub-milestone**: small, atomic, one-concept commits; never bundle steps.
- **Pause after each sub-milestone**: After implementing one concept and committing, stop. Let the user read the generated files, confirm understanding, and approve before the next sub-milestone starts. Never batch multiple concepts into one edit or commit. The pause is the learning rhythm — one step, one check, one build.
- **Commit after EVERY sub-milestone**: small, atomic, one-concept commits; never bundle steps.
- Sub-milestones: every milestone is split into concept-based sub-milestones. In ONE step,
  implement a single concept, explain what/how/why, then STOP — the user reads the
  generated file(s), we build understanding together, then start the next sub-milestone.
  Never batch several concepts at once.
- Session-start ritual (self-healing after compaction): re-read AGENTS.md + PLAN.md's
  milestone status and per-milestone progress blocks. The journey picture lives in
  `docs/m1-diagram.svg` (plus `out/frames/` PNGs and `git log` per-step commits); the
  current in-flight step is recorded in PLAN.md.
- The story diagram is a living artifact, refreshed at MILESTONE CLOSE (and when the
  architecture gains a box) — not after every sub-milestone: pixels are cheap, re-reading the
  SVG is not. Each step instead appends a one-line `stage:` note to PLAN.md; those notes
  become the SVG stage-log rows at close-out. (Why: token hygiene, M3.6.)
- Close-out picture pass: refresh `docs/m1-diagram.svg` (solid = built, dashed = planned),
  rasterize one PNG frame per stage into `out/frames/` (gitignored; `rsvg-convert`), sync them
  into `docs/frames/` (committed), stitch
  `magick -delay 150 out/frames/*.png -background '#fbfbf9' -gravity north -extent 1060x882
  out/journey.gif`, and regenerate `docs/timeline.html` — a small offline prev/next deck that
  links `docs/frames/` (seed of the playground's animated trace player, M12). The SVG's git
  history is the durable timeline.

### Token hygiene (user-mandated · M3.6)
- Generated artifacts are OPAQUE: `docs/timeline.html`, `docs/frames/*.png`, `out/journey.gif`,
  `out/frames/*.png` — never Read/Grep them; verify with `wc -c`, slide counts, `identify`.
- Never re-read a file after editing: prove the edit with `git diff --stat`, `wc -l`,
  `grep -c`, or `sed -n`. Reading generated blobs is the one unrecoverable token sink.
- Cap narrated/`--explain` output (`| sed -n '1,20p'`) unless the full transcript IS the lesson.
- Commit bodies: why-paragraph + ≤3 bullets. Verify with `git show --stat`, not by re-reading.
- Full `pytest -q` once per close-out; targeted tests while iterating.

## Commands
(CANONICAL — kept true at every close-out)
- `python run.py --task "..." [--brain mock] [--model TAG] [--max-steps N] [--script "…" …]
  [--no-tools] [--explain] [--no-color]`   (today's real flags; `--trace` lands in M6)
- `python bench.py --task "..."`           (planned M7+ — same task across brains, side by side)
- `python serve.py`                        (planned M13 — live SSE mode for the playground)
- `python -m pytest`                       (86 tests; run after every sub-milestone)
