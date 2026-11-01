# Decisions archive — M1/M2/M3 detail (read on demand)

Moved out of PLAN.md at M3.6 to keep the always-read plan small (token hygiene).
PLAN.md keeps the current milestone's decision index and one-line pointers; this
file holds the full rationale, verbatim. Nothing here is obsolete unless a later
entry says so.

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

## M3 — full rationale (2026-09/10)

### M3 progress & decisions (2026-09 · tools & registry — the agent's hands)
Same rhythm: one concept per step · tests + a narrated demo every step · atomic commit ·
SVG stage + frame for functional steps.
- [x] M3.0  this map + the two decisions written down (compaction insurance)
- [x] M3.1  asa/tool.py — Tool + ToolCall + ToolResult + mini-schema validation
           (validate before executing; failure is data, never an exception) + lab/tool_lab.py
- [x] M3.2  asa/registry.py — register/list/lookup + render_tool_catalogue() (documentation-first)
- [x] M3.3  asa/tools/ stateless pair — Calculator (pure) + clock (read-only env)
- [x] M3.4  asa/tools/ stateful pair — Notes (append/read) + plan-board (shared mutable)
- [x] M3.5  agent wiring — Agent(registry=...): the catalogue lands in the system prompt, so the
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
  `sys.path` bootstrap is the convention — noted in AGENTS.md in M3.2, once a second lab,
  lab/registry_lab.py, existed).
- **M3.2 recorded decisions (2026-10):**
  - Registry = **phonebook, not dispatcher**: `register/get/names/len/contains` only —
    no `registry.run()`; resolution (`get`) and execution (`Tool.run`) stay two doors in
    two modules, and the M4 loop composes them.
  - Two failure timings, two philosophies: **duplicate name → ValueError** (a duplicate is
    OUR build-time bug, like tool.py's unknown schema type — loud in tests, never silent
    shadowing); **missed lookup → None** (a miss is the MODEL's run-time event — M4 phrases
    it as an error Observation, the failure-is-data philosophy one layer up).
  - **Sorted catalogue** (`names()` + sections in name order): registration order must not
    leak into the prompt — golden-trace determinism for M5. Params render in the Tool's own
    declared order. Optional params are marked `optional` so the catalogue cannot lie.
  - **Catalogue format locked** (the M3.5 system-prompt section): `## Available tools` →
    one `### name` block with description + `Params:` lines `- p (type, required|optional): help`;
    zero-param tools get no Params stub; an EMPTY registry renders a sentence, never `""`.
    The "how to call" instructions stay OUT — that is M4's protocol layer's job; the page
    documents only WHAT exists. Exact format visible in lab/registry_lab.py beat 4.
- **M3.3 recorded decisions (2026-10):**
  - **No eval(), ever** — a tool must be exactly as wide as its documentation says. The
    catalogue promises arithmetic; `eval()` would deliver arbitrary Python, making the
    narrowness a fiction. Instead: a hand-rolled recursive-descent parser (numbers,
    + - * /, parens, unary minus) told as the "every internal visible" lesson; the
    real-world `ast`-whitelist idiom gets a `why()` mention, not the teaching pick.
  - **Honest numerics, zero cosmetic rounding**: ints stay ints (`2+3 = 5`), `/` is
    Python (`7/2 = 3.5`, `8/2 = 4.0`), `0.1+0.2` shows `0.30000000000000004` — the model
    sees IEEE truth rather than a rounded story it would later trust.
  - **Resource limits are tool business** (the mini-schema cannot say them): expression
    capped at 200 chars, paren nesting at 32 — a recursive parser can be stack-crashed
    by adversarial input, and "says no as text" preserves failure-is-data. Test lesson
    found live: size the depth-guard fixture UNDER the length cap, or the wrong guard
    fires first (the failed test caught the fixture, not the tool).
  - **Clock = first real optional param** (`utc` bool, default local); tests pin SHAPE
    (ISO regex + label), never a timestamp — the "assert structure, not wall-clock"
    philosophy written down before M5's golden traces lean on it.
  - Tool modules each expose **`build() -> Tool`**; M3.5's wiring will loop over factories.
  - Parser raises `_ExpressionError` (readable, internal); the tool function phrases it
    into `ToolResult(is_error=True)` — message policy lives at the boundary, the parser
    stays a pure mechanism.
- **M3.4 recorded decisions (2026-10, locked with the user in plan):**
  - **State lives OUTSIDE the hands, factory-injected** — `build(store=None)` constructs a
    fresh store per call; state lifetime becomes the M3.5 agent session; zero module
    globals; tests build fresh worlds and cannot leak. `build()` twice = two strangers.
  - **Stateful tools ship as BUNDLES** — notes = 2 hands (`notes_write`/`notes_read`);
    plan-board = 3 hands (`board_add`/`board_move`/`board_list`) over ONE Board. A store
    with only a writer can't be verified; splitting the trio lets them drift. M3.5's
    wiring flattens the bundles.
  - **Stable ids, never indices** — the board's ids (and notes' numbering) are monotonic
    and never reused; "move item 2" survives every later move. The index-shift bug is
    the narrated `why()` beat in lab/state_lab.py, not a live trap.
  - **Named store classes** — `NotesStore` (grow-only list, returns the entry number) and
    `Board` (text per id, place per id, insertion order per column, `(empty)` renderer).
    Readable structure over dict-magic.
  - **Enum vocab is the tool's business** — todo/doing/done (+ list's `all` view word)
    checked in the tool with refusals that NAME the vocabulary (the schema can't say
    enums; same lesson as calculator's caps). `board_move` is the first real `integer`
    param — bools/floats/strings refused at the M3.1 boundary before state mutates.
  - **No timestamps in notes** — entries are numbered plain text (the clock covers
    "when"); a refused write must not burn a number (asserted: numbering restarts at 1).
- **M3.5 recorded decisions (2026-10, locked with the user in plan):**
  - **`Agent(registry=None)` → `default_tools()`** — "an agent comes WITH its hands":
    one fresh world per agent, session-lifetime state (M3.4's rule automatic at the
    wiring layer). The no-tools lesson stays reachable by passing an explicit empty
    `ToolRegistry()` — which run.py's new `--no-tools` wires transparently.
  - **`default_tools()` is the bundle-flattener** (asa/tools/__init__.py): flattens the
    four factories into one registry over one fresh world; call it twice = two strangers.
  - **The catalogue is PASTED, not retyped** — `_compose_system_prompt()` appends
    `registry.render_catalogue()` after the caller's system text (composition, never
    replacement), byte-equality asserted so prompt-side and loop-side documentation
    can never drift. M4 extends THAT helper with "how to call" instructions.
  - **The SEAM stays honest, pinned by a test**: a MockBrain writing
    `Action: calculator(...)` is memorized verbatim — no tool runs, terminate_reason
    stays "max_steps". M4's flip of exactly this behavior will be test-visible.
  - Narration stays agent-side (M3.2's registry-stays-pure rule): run() announces
    "tools wired · N tools" and, honestly, that the loop cannot act on them yet.
  - M2-carryover fix: test_agent's "brain receives system then task" equality on the
    bare prompt became a startswith + catalogue-inclusion check — the prompt is
    composed now, and the test describes the new truth (role order still proven).

Session-start anchors after M3.5: git HEAD ≈ M3.5 commit · diagram badge "M3 · 5 of 7 done" ·
frames m3-stage-01..05 (out/, gitignored) · 86 tests green · next up = M3.6 close-out (badge
flip to "M3 complete ✓", timeline + journey.gif refresh, narrated run) — then M4 (ReAct parser).
