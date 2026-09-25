# PLAN — asa: build your own agent, and see inside it

> Living document. Read on session start / context compaction. Update as the plan evolves.
> Status: each milestone has a check ( [x] done, [ ] next-up, [~] in progress ).

## Why this project exists
Learn how agentic AI actually works by implementing a simple agent from scratch and making
every internal observable — then build a teaching artifact (interactive HTML) that explains it.
Not a shippable product; pace is tuned for learning: small steps, tests at every step,
verbose narration, checkpointing with the user after each milestone.

## Recorded decisions (from planning Q&A)
1. **LLM depth**: thin wrapper over real LLM APIs (not building a model from scratch).
2. **Language**: Python. **Viz**: HTML doc + live viz (trace playback, step-through animation).
3. **Capability**: ReAct loop with tools (reason -> act -> observe -> repeat).
4. **Backend unknown upfront** -> build a swappable "brain zoo" + `bench.py` comparison rig.
5. **Local model**: llama3.2:1b via Ollama (Pi5, 8GB RAM, ~7-18 tok/s). qwen2.5:1.5b = backup.
6. **Cloud model**: Google free tier. Key already available. Rate limits (per user's AI Studio):
   - Gemini 3.1 / 3.5 Flash Lite: **15 RPM / 250K TPM / 500 RPD**
   - Gemma 4 26B / 31B (via Google API): **30 RPM / 16K TPM / 14.4K RPD**
   (pin exact current numbers from the AI Studio rate-limits page at Milestone 8)
7. **Protocols**: learn BOTH — textual ReAct (universal) AND native function calling.
   Agent core speaks only `ToolCall(name, args)`; adapters convert model output.
8. **gpt2-medium locally**: revisit as an INTENTIONAL-FAILURE demo — base (non-instruction-
   tuned) LM cannot follow the ReAct protocol; demonstrating why is a core lesson.
9. **Naming**: `asa` = "a simple agent". `asca` = "a simple coding agent": possibly later.

## Architecture
```
┌────────────────────────────── REACT LOOP ──────────────────────────────┐
│ Task ─▶ ContextWindow ─▶ Brain ─▶ text↔native ─▶ protocol ─▶ ToolCall  │
│                ▲                                      │                │
│                │                                      ▼                │
│   Observation ◀── tool result ◀── Tool runs ◀── ToolRegistry ◀─────────│
│                                                                        │
│   terminate on: Final Answer: | max_steps | failure policy             │
└────────────────────────────────────────────────────────────────────────┘
```
- The brain is a text-in/text-out box; swapping brains never changes agent code.
- `protocol_react.py` parses textual ReAct; `protocol_native.py` consumes API FunctionCall
  payloads. Both emit `ToolCall`; agent core stays protocol-agnostic.

### Modules (`asa/`)
| Module | Role | Lesson |
|---|---|---|
| memory.py    | ContextWindow: append, token estimate, trim-on-overflow | how an agent "remembers" |
| brain.py     | Brain interface + zoo (Mock/Ollama/Gemini/GPT2) | engine-agnostic design |
| protocol_react.py  | parse Thought:/Action:/Action Input: (+ error repair) | text -> structure |
| protocol_native.py | native tool declarations + FunctionCall -> ToolCall | API function calling |
| tool.py / tools/   | Tool dataclass, JSON-schema params; Calculator, Notes, clock, plan-board | the agent's "hands" |
| registry.py  | register/list/lookup; renders catalogue into prompt | documentation-first tools |
| agent.py     | the loop; termination control; narration hooks | orchestration |
| trace.py     | JSONL event for every internal step, timestamped | observability / glass-box |

### Memory / eviction policy (decided 2026-09, from the M2.1 discussion)
- M2's trim() is **age-first** (system sacred · newest kept) — the right default and the
  cleanest first lesson. It stays for the teaching milestone.
- Future refinement when tool Observations enter context (M3+): (a) truncate/length-cap tool
  output **at ingestion**, (b) summarize old turns instead of deleting, (c) size-aware
  eviction as a fallback — one huge recent turn (e.g. a tool dump) can drown useful older
  turns, and then "drop the biggest" beats "drop the oldest".
- "LLM context is a cache" (token budget, eviction, redundancy) becomes a docs topic (M11).

### M2 progress & decisions (2026-09 · session-compaction safety)
Running as concept sub-milestones (working-rhythm addendum in AGENTS.md); every step = an
atomic commit + (for functional steps) an SVG stage + PNG frame in `out/frames/`:
- [x] M2.0  working-rhythm addendum written to AGENTS.md
- [x] M2.1  asa/memory.py — ContextWindow (append · token_count · trim, age-first)
- [x] M2.2  tests/test_memory.py (10 tests) + conftest.py
- [x] M2.3  asa/agent.py — Agent skeleton: full hop Task→Memory→Brain→memory + loop seam
- [x] M2.4  AgentResult(text, terminate_reason, steps, tokens) + tests/test_agent.py (10)
- [x] M2.5  run.py rewritten agent-driven (+ --max-steps, --script, main(argv)) + tests/test_cli.py
- [x] M2.5b --script now declares + *reports louder* the MockBrain override (see below)
- [x] M2.6  close-out — pytest 26 green · PLAN.md M2→[x] · docs/timeline.html (5 stages,
           self-contained) · SVG badge "M2 complete ✓" · one narrated `--explain` run · journey.gif
Recorded decisions:
- **AgentResult**: run() returns answer AND outcome, kept apart (status bookkeeping never
  pollutes model text). M2 always reports terminate_reason="max_steps"; M5 adds
  "final_answer"/failure cases without changing the shape.
- **--script policy**: a TEACHING override. Today it swaps the selected brain for a
  scripted MockBrain with a loud warning; decided 2026-09: when real brains exist
  (M7/M8), keep **warn + override** (lowest surprise) rather than a hard error —
  revisit only if a silent misuse actually bites.
- **CLI narration voice**: the Agent narrates its own mid-run internals; run.py adds only
  gauges + the result block (no duplicated transcript).
Session-start anchors after M2: git HEAD ≈ close-out commit · diagram badge "M2 complete ✓" ·
frames m1-stage-00 + m2-stage-01/03/05/06 (out/, gitignored) · journey.gif in out/.

### M3 progress & decisions (2026-09 · tools & registry — the agent's hands)
Same rhythm: one concept per step · tests + a narrated demo every step · atomic commit ·
SVG stage + frame for functional steps.
- [x] M3.0  this map + the two decisions written down (compaction insurance)
- [ ] M3.1  asa/tool.py — Tool + ToolCall + ToolResult + mini-schema validation
           (validate before executing; failure is data, never an exception) + lab/tool_lab.py
- [ ] M3.2  asa/registry.py — register/list/lookup + render_tool_catalogue() (documentation-first)
- [ ] M3.3  asa/tools/ stateless pair — Calculator (pure) + clock (read-only env)
- [ ] M3.4  asa/tools/ stateful pair — Notes (append/read) + plan-board (shared mutable)
- [ ] M3.5  agent wiring — Agent(registry=...): the catalogue lands in the system prompt, so the
           agent SEES its hands; the loop still cannot act on them (that is M4's parser)
- [ ] M3.6  close-out — pytest green · PLAN M3→[x] · SVG pass (Registry + tools turn solid in the
           loop row; protocol/ToolCall stay dashed until M4/M5) · frame + timeline regen ·
           journey.gif · one narrated run · final commit
Recorded decisions (2026-09):
- **Where tools live**: package `asa/tools/`, one module per tool (Calculator, clock, Notes,
  plan-board) — matches the module table and M12's playground.
- **M3.5 is IN**: the registry is wired into the Agent inside M3 (catalogue → system prompt).
  Rationale: it completes the registry lesson ("the model learns what exists") without
  needing the ReAct parser; the agent touching tools is a *seam*, not a lie.
- **Schema shape**: `params` is a mini JSON-schema subset (types number/integer/string/boolean
  + required + help), deliberately convertible into a real
  `{"type":"object","properties":…,"required":[…]}` for M9's native protocol — decide now,
  repaint never.
- **Failure is data**: a bad arg or a tool that raises returns `ToolResult(is_error=True)`;
  the error text becomes an Observation the model can react to. The agent never dies from a
  tool call (real models typo).
- `number` accepts int|float and coerces to float; unknown args are errors (typo guard).
- `lab/` layer opens in M3.1 with lab/tool_lab.py (narrated, one internal per script; a 2-line
  `sys.path` bootstrap is the convention — note it in AGENTS once a second lab exists).

### Trace-event schema (JSONL; one JSON per line)
`{ts, iter, kind, payload}` with kinds: session.start, context.add, context.trim,
brain.request, brain.response, protocol.raw, protocol.parsed, protocol.error,
tool.lookup, tool.invoke, tool.result, loop.turn, loop.terminate, agent.answer.
Same stream feeds the narrated CLI and the HTML playground player.

## Brain zoo (config-driven; model name is a string)
| Brain      | Where  | Notes |
|------------|--------|-------|
| MockBrain  | local  | deterministic, no deps; tests / offline / golden traces |
| OllamaBrain| local  | llama3.2:1b default; stdlib HTTP (no pip); zero-cost path |
| GeminiBrain| cloud  | Gemini 3.1/3.5 Flash Lite (15 RPM...) + Gemma 4 by name |
| GPT2Brain  | local  | INTENTIONAL-FAILURE demo: why instruction-tuning matters |

## Learning layers
- CLI narrator: color-coded stages, what/how/why annotations, timings. --verbose / --explain.
- `lab/*.py`: one script per internal, exercise a single part, print every intermediate.
- `playground/` HTML: animated diagram (click component -> anatomy), trace player
  (scrub/step; context gutter + token gauge; model req<->resp; tool cards firing),
  breakage lab (unknown tool / malformed action / context overflow / loop exhaustion),
  two-protocol comparison, model zoo, glossary + quiz. Offline via shipped traces.
- `docs/m1-diagram.svg`: state-of-functionality diagram after M1 (proto of the SVG tooling/docs series)
- `docs/`: 7 illustrated topics: (1) what is an agent, (2) the loop, (3) context/memory,
  (4) tools & registry & prompt-craft, (5) parsing / two protocols, (6) the brain zoo,
  (7) observability & failure modes. Hand-authored SVGs; self-check quiz each.

## Milestones (status)
- [x] **M0** Rename dir to `asa`; write AGENTS.md + PLAN.md
- [x] **M1** Shell: venv, requirements, run script, first narrated MockBrain hello
- [x] **M2** Loop skeleton: memory + brain interface + one-shot agent (six concept sub-milestones · closed out)
- [~] **M3** Tools & registry: Tool dataclass, JSON schema, catalogue, calculator + notes (7 concept sub-milestones · map below, started)
- [ ] **M4** protocol_react: parser w/ error repair; unit tests; lab/parser_lab.py
- [ ] **M5** Full loop + control: Final Answer / max_steps / termination; golden-trace tests
- [ ] **M6** Trace layer: JSONL event schema (CLI + playground share it)
- [ ] **M7** OllamaBrain + llama3.2:1b: real local run; bench vs Mock
- [ ] **M8** GeminiBrain (text protocol): free-key run; 429/rate-limit handling; pin limits
- [ ] **M9** protocol_native: Gemini function calling; side-by-side same task vs ReAct
- [ ] **M10** GPT2Brain failure demo
- [ ] **M11** Docs: 7 illustrated topics
- [ ] **M12** HTML playground (offline via pre-recorded traces)
- [ ] **M13** Live mode (serve.py SSE) + README quickstart + final walkthrough

## Publishing to GitHub (decision: option 1 — defer the scrub)
- Keep `PLAN.md` + `AGENTS.md` tracked and versioned locally for now (revertable history).
- On the day of the FIRST push, scrub them from history once:
  `git filter-repo --path PLAN.md --path AGENTS.md --invert-paths`
  (or `git filter-branch` if filter-repo isn't installed), then add both to `.gitignore`
  so future edits never leak.
- Public scope = `asa/`, tests, `docs/`, `playground/`, `README.md` (educational front door).
- Private scope = `PLAN.md`, `AGENTS.md`, `NOTES.md`.

## Session continuity (why this file exists)
- opencode context window ~200K tokens; compaction may mangle earlier discussion.
- On any new session / drift: re-read AGENTS.md (auto-loaded) + this PLAN.md;
  check milestone status above; resume at the oldest unchecked milestone.
- Commit nothing unless the user asks; keep tests green after every milestone.