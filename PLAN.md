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
   - *(Change of plan 2026-11-02: **lfm3** replaces llama3.2:1b as the local default. User has
     it installed and tested under Ollama. Facts from `ollama show`: tag `lfm3:latest`, 1.7B
     params, Q4_K_M quant, 256K context, temp 0.1 default. Two capability surprises with
     design weight: (a) native **tools** — M9 function-calling can ALSO be taught locally,
     not only via Gemini; (b) **thinking** mode ON by default — interacts with ReAct text
     parsing; policy decided at M7.0.)*
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
| brain.py     | Brain interface + MockBrain (Ollama/Gemini/GPT2 planned M7/M8/M10) | engine-agnostic design |
| protocol_react.py  | parse Thought:/Action:/Action Input: (+ error repair) — **planned M4** | text -> structure |
| protocol_native.py | native tool declarations + FunctionCall -> ToolCall — **planned M9** | API function calling |
| tool.py / tools/   | Tool dataclass, JSON-schema params; Calculator, Notes, clock, plan-board | the agent's "hands" |
| registry.py  | register/list/lookup; renders catalogue into prompt | documentation-first tools |
| agent.py     | the loop; termination control; narration hooks | orchestration |
| trace.py     | JSONL event for every internal step, timestamped — **planned M6** | observability / glass-box |

### Memory / eviction policy (decided 2026-09, from the M2.1 discussion)
- M2's trim() is **age-first** (system sacred · newest kept) — the right default and the
  cleanest first lesson. It stays for the teaching milestone.
- Future refinement when tool Observations enter context (M3+): (a) truncate/length-cap tool
  output **at ingestion**, (b) summarize old turns instead of deleting, (c) size-aware
  eviction as a fallback — one huge recent turn (e.g. a tool dump) can drown useful older
  turns, and then "drop the biggest" beats "drop the oldest".
- "LLM context is a cache" (token budget, eviction, redundancy) becomes a docs topic (M11).

### M2 (closed) — decisions archived
Full progress + decisions: `docs/decisions-archive.md`. Contracts that still bind:
run() returns **answer and outcome separately** (AgentResult); `--script` is a loud,
warn-and-override teaching switch; the Agent narrates its internals, run.py only gauges.

### M3 progress & decisions (2026-09/11 · tools & registry — the agent's hands)
Closed 2026-11 · 7 concept sub-milestones · 86 tests / 10 modules · 4 narrated labs.
Full rationale: `docs/decisions-archive.md` (this section is the index M4 needs).
- [x] M3.0 map + decisions · M3.1 Tool/ToolCall/ToolResult · M3.2 ToolRegistry + catalogue
- [x] M3.3 calculator + clock · M3.4 notes + plan-board (state outside the hands)
- [x] M3.5 wiring: default_tools → system prompt (the seam; the loop still cannot act)
- [x] M3.6 close-out — pytest green · PLAN tick · SVG final pass (canvas 882) · timeline
       split (11 stages) · journey.gif · narrated run · truth sweep · token-hygiene policy

Contracts M4/M5 depend on (one line each; why in the archive):
- Tools live in `asa/tools/`, one module per tool, each exposing `build() -> Tool`.
- Schema: mini JSON-schema subset (number/integer/string/boolean + required + help),
  convertible to real JSON Schema for M9.
- Failure is data: bad args / raising tools → `ToolResult(is_error=True)`; the text becomes
  an Observation. `number` accepts int|float→float; unknown args are errors.
- Registry = phonebook, not dispatcher: register/get/names/len/contains only; duplicate
  name → ValueError (build-time bug), missed lookup → None (the model's run-time event).
- Catalogue: sorted by name, params in declared order, optional marked, empty renders a
  sentence; format locked in `registry.py`; "how to call" is M4's job.
- No eval(): calculator is a hand-rolled recursive-descent parser; honest numerics; caps
  (200 chars / 32 parens) are tool business, refused as text.
- State lives OUTSIDE the hands (`build(store=None)`); stateful bundles (notes ×2,
  board ×3); stable ids, never indices; enum vocab checked in the tool.
- `Agent(registry=None)` → `default_tools()` (one fresh world per agent); an explicit empty
  registry is the no-tools agent (`run.py --no-tools`).
- Catalogue is PASTED into the system prompt (`_compose_system_prompt`), never retyped;
  byte-equality asserted. **M4 extends THAT helper with "how to call" instructions.**
- The SEAM is pinned by a test: an `Action: …` reply is memorized verbatim, no tool runs,
  `terminate_reason` stays `max_steps` — M4's flip will be test-visible.

M3.6 recorded decisions (2026-11):
- A close-out is a truth sweep (picture, anchors, AGENTS.md, docstrings) in one atomic
  commit — no behaviour change, no new tests.
- Token hygiene is policy: the SVG/frame/timeline picture refreshes at MILESTONE CLOSE (or
  when a box is added), not per sub-milestone; each step leaves a one-line `stage:` note.
  Generated artifacts are opaque (verify with wc/identify, never read); never re-read a
  file after editing; the timeline is a small HTML + committed `docs/frames/`.

Session-start anchors after M3.6: git HEAD ≈ M3.6 commit · diagram badge "M3 complete ✓"
(canvas 882) · frames m3-stage-01..06 (out/, gitignored) · `docs/frames/` 11 PNGs · timeline
11 stages · 86 tests green · next up = **M4** (`protocol_react.py`; the SEAM is the landing
site; one-line stage notes go in PLAN.md).

### Trace-event schema (JSONL; one JSON per line)
`{ts, iter, kind, payload}` with kinds: session.start, context.add, context.trim,
brain.request, brain.response, protocol.raw, protocol.parsed, protocol.error,
tool.lookup, tool.invoke, tool.result, loop.turn, loop.terminate, agent.answer.
Same stream feeds the narrated CLI and the HTML playground player.

## Brain zoo (config-driven; model name is a string)
| Brain      | Where  | Notes |
|------------|--------|-------|
| MockBrain  | local  | deterministic, no deps; tests / offline / golden traces |
| OllamaBrain| local  | lfm3:latest default (1.7B, Q4_K_M, 256K ctx; native tools+thinking); stdlib HTTP (no pip); zero-cost path |
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
- [x] **M3** Tools & registry: Tool dataclass, JSON schema, catalogue, calculator + notes (7 concept sub-milestones · closed out)
- [x] **M4** **Reading the reply.** Taught the agent to read: parse good commands, handle values safely, treat broken letters as gentle notes, recognize Final Answer, teach the format, and flip the seam so it actually runs tools and feeds observations back.  
  **Sub-milestones (one concept each):**
  - [x] **M4.1** _Read a good letter_ — `asa/protocol_react.py` parses a correct `Thought:`/`Action:`/`Action Input:` block into a command the core can understand. Pure function, tests + demo.
  - [x] **M4.2** _Make sense of the values_ — turn the text inside `Action Input:` into real Python values safely (no `eval`), handling simple keyword-style args and the plain-string case.
  - [x] **M4.3** _A damaged letter isn't a crash_ — malformed/missing pieces produce a gentle "fix your letter" note (failure is data), not an exception. Model can retry.
  - [x] **M4.4** _The letter can be an answer_ — recognize `Final Answer:` as its own verdict (end the run) so the vocabulary is ready for M5.
  - [x] **M4.5** _Teach the format_ — extend `_compose_system_prompt` with a short "how to write the letter" block (catalogue stays pasted as-is).
  - [x] **M4.6** _Open the drawer_ — flip the seam: parse every reply; command → run tool via registry → put result back; broken → put the gentle note back; answer → stop. First real tool run through the loop.
  - [x] **M4.7** _Poke the reader_ — `lab/parser_lab.py` (script-first, two-line sys.path) to feed good/broken letters and watch every step; narrated demo.
  - [x] **M4.8** _Close-out_ — PLAN tick + `stage:` notes, refreshed journey picture at close, full `pytest -q`, truth sweep.  
    - stage: M4.1 reader parses good letter (Thought/Action/Action Input) → ToolCall
    - stage: M4.2 args parsed safely without eval (kwargs/JSON)
    - stage: M4.3 broken letters → gentle notes (failure is data)
    - stage: M4.4 Final Answer becomes third verdict
    - stage: M4.5 how-to-call block added to system prompt
    - stage: M4.6 seam flipped → agent reads and acts (tools run, observations back)
    - stage: M4.7 parser lab + narrated demo
    - stage: M4.8 close-out
- [x] **M5** Full loop + control: Final Answer / max_steps / termination; golden-trace tests  
  *(Closed 2026-11 (honest tick 2026-11-02): tests were committed in the M5 sessions but the checkbox ticks were missed — the code and 113 green tests were already real.)*
  **Sub-milestones (one concept each):**
  - [x] **M5.1** _Final Answer flows_ — when parser sees "Final Answer:", the loop stops immediately; tests verify proper termination.
  - [x] **M5.2** _max_steps guard policy_ — step budget becomes the authoritative termination control; tests verify loop stops on budget.
  - [x] **M5.3** _golden-trace tests_ — record perfect runs for documentation and M11 docs.
  - [x] **M5.4** _Close-out_ — PLAN tick + `stage:` notes, full `pytest -q` green.
  - stage: M5.1 Final Answer flows (parser verdict → immediate termination)
  - stage: M5.2 max_steps guard policy (step budget stops loops)
  - stage: M5.3 golden-trace tests (record perfect runs for M11 docs)
  - stage: M5.4 close-out (PLAN tick, full tests)
- [x] **M6** Trace layer: JSONL event schema — every internal step becomes one JSON line
  (`asa/trace.py`; agent.py instruments the whole loop). *(Closed 2026-11 · honest tick 2026-11-02.)*
  **Sub-milestones (one concept each):**
  - [x] **M6.1** _Event kinds + schema_ — 14 kinds (session.start … agent.answer), each event `{ts, iter, kind, payload}`; JSONL roundtrip proven.
  - [x] **M6.2** _Writer + reader_ — `write_event()` (atomic append), `read_events(since=, kind_filter=)`, `clear_trace()`; pure, no brain/tools dependency.
  - [x] **M6.3** _Agent wiring_ — agent.py emits brain.request/response, protocol.raw/parsed/error, tool.lookup/invoke/result, loop.turn, loop.terminate, agent.answer.
  - [x] **M6.4** _Test harness_ — `tests/conftest.py` fixture resets trace state between tests; 6 trace tests + full suite green (113).
  - [~] **M6.5** _Close-out_ — PLAN tick + full pytest done; journey-picture refresh + AGENTS.md test-count refresh **deferred to the M7 close-out pass** (one picture pass covers both).
  - stage: M6.1 14 event kinds, {ts,iter,kind,payload} schema
  - stage: M6.2 write/read/clear trace (pure JSONL layer)
  - stage: M6.3 agent loop instrumented (requests, responses, tools, termination)
  - stage: M6.4 conftest fixture + 113 tests green
  - stage: M6.5 close-out (picture + count refresh deferred to M7 close)
- [ ] **M7** OllamaBrain + **lfm3**: first real local model; bench vs Mock
  *(Model change 2026-11-02: lfm3 replaces llama3.2:1b — user has it installed and tested under Ollama,
  same `localhost:11434`. Facts from `ollama show`: tag `lfm3:latest`, 1.7B params, Q4_K_M quant,
  256K context, temp 0.1 default, license LFM Open v1.0. Capability surprises: native **tools**
  (M9 function-calling teachable locally too, not only Gemini) and **thinking** ON by default
  (interacts with ReAct text parsing — policy decided at M7.0).)*
  **Sub-milestones (one concept each):**
  - [x] **M7.0** _Map + decisions_ (no code): endpoint localhost:11434; `/api/chat` to match our
        message-list → Completion shape; thinking policy for ReAct (off? captured separately?);
        model tag as config string `lfm3:latest`; stdlib HTTP only (no pip); timeout/retry for slow local inference.
        **Decisions pinned (2026-11-02):**
        - endpoint `http://localhost:11434` (user-confirmed); model tag = config string, default `lfm3:latest`
        - API: `/api/chat` (message-list in → text out; matches `Message.render()` → `Completion` shape)
        - **thinking policy: OFF for ReAct** (`think: false`) — user chose predictability + speed;
          thinking capture stays a one-flag later toggle, no re-architecture.
          *(AMENDED 2026-11-02 at M7.3, reality check: the live exam falsified this pin —
          lfm3 is thinking-native and produced EMPTY content under think=false in real agent
          contexts. Default is now think=True; Ollama answers thinking in a separate
          `message.thinking` field, so `content` stays a clean ReAct letter regardless.)*
        - stdlib `urllib.request` only (zero pip deps); long timeout + 1 gentle retry (local inference is slow)
        - `num_predict` output cap ~512 default, overridable (bounds runaway on slow hardware)
  - stage: M7.0 decisions pinned (chat API, think:false, urllib, retry, num_predict)
  - stage: M7.1 OllamaBrain skeleton (chat payload, think:false, transport seam, fail-soft; live smoke ran)
  - stage: M7.2 --brain ollama wired; first narrated real run (proper ReAct letter, final_answer)
  - stage: M7.3 reality check: think=false falsified (empty content) -> amended to True; drift self-repaired on real run; trace-isolation bug fixed
  - [x] **M7.1** _OllamaBrain skeleton_ — `complete()` speaks HTTP to Ollama; offline unit tests
        with a fake transport + live smoke test that SKIPS when Ollama isn't running.
        *(Built 2026-11-02: transport injectable, 8 offline tests + live smoke (RAN — Ollama
        was up); 122 tests green.)*
  - [x] **M7.2** _First real words_ — narrated live run `--brain ollama`; observe thinking behavior
        in practice, decide where it goes (trace? memory? nowhere?). *(Built 2026-11-02: flag wired
        to OllamaBrain; narrated demo on real lfm3 produced a proper ReAct letter — parsed to Final
        Answer at step 1; think:false worked silently as decided at M7.0; 5 trace events record it.)*
  - [x] **M7.3** _Does the real model write a parseable letter?_ — one-step calculator task;
        watch M4.3's gentle repair catch real-world format drift. *(Built 2026-11-02: YES — but
        only on retake. Run 1 (think=false): empty letters x3, honest max_steps stop, then the
        contained-context replay pointed at thinking-nativeness. Retake (think=True): drift
        `Action Input: "7*6"` → gentle note → SELF-REPAIR to `{"expression": "7*6"}` → tool →
        Final Answer: 42. Real letters frozen as offline regressions. Also exposed + fixed a
        latent conftest isolation bug (reset_session never cleared the trace FILE).)*
  - [ ] **M7.4** _bench.py_ — same task through MockBrain vs OllamaBrain side-by-side; timing,
        tokens, success; pin lfm3 throughput on this Pi5 (stage note).
  - [ ] **M7.5** _Close-out_ — PLAN tick + stage notes; journey-picture pass (also covers M6.5 debt);
        full `pytest -q`; refresh AGENTS.md test count (currently stale: says 86, actual 113+).
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
- Deep history (M1/M2/M3 rationale) is in `docs/decisions-archive.md` — read on demand,
  not every session. The M3 section above is the compressed index M4 needs.
- Each sub-milestone leaves a one-line `stage:` note here; the SVG/timeline picture is
  refreshed at milestone close (token hygiene, M3.6).
- Commit nothing unless the user asks; keep tests green after every milestone.