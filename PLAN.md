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

### Memory / eviction policy (decided 2026-09, from the M2.1 discussion)
- M2's trim() is **age-first** (system sacred · newest kept) — the right default and the
  cleanest first lesson. It stays for the teaching milestone.
- Future refinement when tool Observations enter context (M3+): (a) truncate/length-cap tool
  output **at ingestion**, (b) summarize old turns instead of deleting, (c) size-aware
  eviction as a fallback — one huge recent turn (e.g. a tool dump) can drown useful older
  turns, and then "drop the biggest" beats "drop the oldest".
- "LLM context is a cache" (token budget, eviction, redundancy) becomes a docs topic (M11).
| trace.py     | JSONL event for every internal step, timestamped | observability / glass-box |

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
- [ ] **M2** Loop skeleton: memory + brain interface + one-shot agent
- [ ] **M3** Tools & registry: Tool dataclass, JSON schema, catalogue, calculator + notes
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