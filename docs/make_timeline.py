#!/usr/bin/env python3
"""Regenerate docs/timeline.html — the offline journey slideshow.

Reads every stage frame in ../out/frames/ (m?-stage-*.png), SYNCS them into
docs/frames/ (committed, so the deck travels with any clone and needs no
network), and writes a small HTML deck that links each PNG relatively. Titles
and captions each stage. Run it at every milestone close (or after any SVG
refresh) so the picture story stays in sync with the drawing.

Why not base64: embedding frames made timeline.html a single 4 MB line — one
accidental Read/Grep would cost ~1M tokens, and every regeneration rewrote the
whole blob. Frames-as-files keeps the HTML ~5 KB, makes diffs readable, and the
generated artifact stays opaque to the agent (verify with wc/slide count, never
read it).

Usage: python docs/make_timeline.py
"""

import html
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMES_DIR = ROOT / "out" / "frames"
DEST_DIR = Path(__file__).resolve().parent / "frames"
OUT = Path(__file__).resolve().parent / "timeline.html"

TITLE = "asa — the journey in pictures · M1 → M7 (complete)"

CAPTIONS = {
    "m1-stage-00.png": "M1 — the shell: run.py → Message → Brain (→ MockBrain) → Completion → Narrator",
    "m2-stage-01.png": "M2·1 — memory: a ContextWindow appears (token-budgeted transcript; system sacred, oldest evicted first)",
    "m2-stage-03.png": "M2·3 — agent: a full hop Task→Memory→Brain→reply-stored, the loop seam + max_steps guard",
    "m2-stage-05.png": "M2·5 — CLI: run.py becomes the mouthpiece (narrated memory gauges, answer/outcome result block)",
    "m2-stage-06.png": "M2 close-out — the loop skeleton is complete; next up M3 tools & registry",
    "m3-stage-01.png": "M3·1 — the hand gets a shape: Tool(data + func) · ToolCall · ToolResult, with failure as data",
    "m3-stage-02.png": "M3·2 — the phonebook + the manual page: ToolRegistry (dup→ValueError · miss→None · sorted) and a catalogue rendered FROM the schema",
    "m3-stage-03.png": "M3·3 — the first real hands: calculator (pure, hand parser, no eval, length+depth guards) + clock (read-only, optional utc)",
    "m3-stage-04.png": "M3·4 — the stateful pair: notes (numbered ledger, ×2 hands) + plan-board (stable ids, ×3 hands); state lives OUTSIDE the hands in injected stores",
    "m3-stage-05.png": "M3·5 — the wiring: default_tools() builds one fresh world per agent, and the catalogue (the model's manual page) rides the system prompt — the loop still cannot act",
    "m3-stage-06.png": "M3 close-out — tools & registry complete: 7 hands, a catalogue in the prompt, one fresh world per agent; the parser is M4's job",
    "m7-stage-00.png": ("M7 close-out — the first REAL brain: OllamaBrain (lfm3:latest, 1.7B) behind the same "
                        "seam; M4 protocol reader, M5 control and M6 trace drawn into the diagram retroactively "
                        "(their close-outs skipped the picture pass — code+tests were real); bench pin: 7.2 tok/s on the Pi5"),
}

CSS = """
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; background: #eef1f5; color: #1f2430; }
  header { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; padding: 0.9rem 1.2rem; background: #1f2430; color: #dce0ea; }
  header strong { font-size: 1.05rem; letter-spacing: 0.02em; }
  header span { color: #8f97aa; font-size: 0.85rem; }
  .deck { max-width: 1060px; margin: 0 auto; }
  figure { margin: 1.2rem auto 0; }
  img { display: block; width: 100%; height: auto; background: #fff; border: 1px solid #c9cfda; border-radius: 8px; }
  figcaption { margin-top: 0.5rem; font-size: 0.92rem; color: #3c4456; font-style: italic; }
  .nav { display: flex; justify-content: center; gap: 0.6rem; padding: 1.2rem 0 1.6rem; }
  button { font: inherit; font-size: 0.95rem; padding: 0.45rem 1.1rem; border: 1px solid #8f97aa; border-radius: 6px; background: #fff; color: #1f2430; cursor: pointer; }
  button:hover:not(:disabled) { background: #dce0ea; }
  button:disabled { opacity: 0.4; cursor: default; }
"""


def sync_frames(frames: list) -> None:
    """Copy the gitignored renders into docs/frames/ and drop stale ones."""
    DEST_DIR.mkdir(exist_ok=True)
    wanted = {p.name for p in frames}
    for path in frames:
        shutil.copyfile(path, DEST_DIR / path.name)
    for old in DEST_DIR.glob("m?-stage-*.png"):
        if old.name not in wanted:
            old.unlink()


def src(path: Path) -> str:
    return f"frames/{path.name}"


def render(frames: list) -> str:
    slides = []
    for n, path in enumerate(frames, start=1):
        caption = CAPTIONS.get(path.name) or path.stem
        slides.append(
            f'<figure class="slide" data-idx="{n}">'
            f'<img src="{src(path)}" alt="stage {n}">'
            f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        )
    js = "let i=1;const s=document.querySelectorAll('.slide');const nav=()=>{" \
         "s.forEach(f=>f.style.display=f.dataset.idx==i?'block':'none');" \
         "document.getElementById('idx').textContent='stage '+i+' / '+s.length;" \
         "document.getElementById('prev').disabled=i===1;" \
         "document.getElementById('next').disabled=i===s.length;};" \
         "const go=d=>{i=Math.min(Math.max(1,i+d),s.length);nav();};" \
         "document.addEventListener('keydown',e=>{if(e.key==='ArrowLeft')go(-1);" \
         "if(e.key==='ArrowRight')go(1);});" \
         "document.getElementById('prev').onclick=()=>go(-1);" \
         "document.getElementById('next').onclick=()=>go(1);nav();"
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>{html.escape(TITLE)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f"<header><strong>{html.escape(TITLE)}</strong><span id=\"idx\"></span></header>\n"
        f"<div class=\"deck\">\n{''.join(slides)}\n</div>\n"
        "<div class=\"nav\"><button id=\"prev\" type=\"button\">← prev</button>"
        "<button id=\"next\" type=\"button\">next →</button></div>\n"
        "<script>" + js + "</script>\n</body>\n</html>\n"
    )


def main() -> int:
    frames = sorted(FRAMES_DIR.glob("m?-stage-*.png"))
    if not frames:
        print(f"no stage frames found in {FRAMES_DIR} — render them first (rsvg-convert)", file=sys.stderr)
        return 1
    sync_frames(frames)
    OUT.write_text(render(frames))
    size_kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT} with {len(frames)} stage(s) ({size_kb:.1f} KB) + {len(frames)} PNGs in {DEST_DIR.name}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
