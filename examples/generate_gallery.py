#!/usr/bin/env python3
"""Regenerate the mdlout examples gallery.

Walks ``examples/out/`` for every committed ``*.pdf`` reference rendering,
extracts a thumbnail of page 1 (via ``pdftoppm`` + ImageMagick ``convert``),
pulls the title and description from the matching ``examples/*.md`` source,
and writes a self-contained ``examples/out/index.html`` gallery page.

Idempotent: running it again replaces the thumbnails and HTML in place.
Stdlib only -- shells out to ``pdftoppm`` and ``convert``.

Usage:
    python3 examples/generate_gallery.py
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES_DIR = HERE
OUT_DIR = HERE / "out"

# Examples that are known not to render to PDF at the moment.  Listed here so
# the gallery can flag them with a banner if/when their .pdf is regenerated.
KNOWN_BROKEN = {"02_typography"}

# One-line fallback descriptions, used when no description can be lifted
# directly from the .md source (e.g. files that open with frontmatter and a
# heading but no leading prose).  Mirrors the table in examples/README.md.
FALLBACK_DESCRIPTIONS: dict[str, str] = {
    "01_hello": "Smallest possible smoke test - one paragraph.",
    "02_typography": "Inline spans: bold, italic, code, strikethrough, superscript, escapes.",
    "03_lists_and_tables": "Bullet, numbered, task, definition lists; pipe and grid tables.",
    "04_math": "Block and inline math: integrals, sums, fractions, matrices, aligned eqs.",
    "05_music": "Three ABC fenced blocks, including a harp grand-staff via %%score.",
    "06_report": "type: report with cover, TOC, @Section nesting, code, math, raw Lout.",
    "07_raw_lout_and_svg": "Raw passthrough fences for arbitrary Lout and SVG snippets.",
    "08_kitchen_sink": "Two-column report combining every feature - canonical regression target.",
    "book_chapter": "type: book sample chapter (~A5) with @Chapter, footnotes, pull-quote.",
    "complex_diag": "Railroad grammars, BSTs, flowcharts - pushes @Diag harder than the gallery.",
    "cv": "Two-column CV: raw-Lout header, @TaggedList of skills, markdown prose.",
    "diag_gallery": "Every @Diag arrowstyle, shape macro, and @Tree example in one document.",
    "letter": "Formal US business letter built on type: doc plus raw-Lout passthrough.",
    "scientific_paper": "Workshop paper comparing trapezoidal vs Simpson's rules for quadrature.",
    "slides_basic": "type: slides six-slide intro to Lout.",
}


@dataclass
class Example:
    basename: str
    md_path: Path | None
    pdf_path: Path
    html_path: Path | None
    thumb_path: Path | None
    title: str
    description: str
    broken: bool


# ---------------------------------------------------------------------------
# Title / description extraction
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return ``(frontmatter_dict, body)``.

    Recognises the same ``--- ... ---`` YAML frontmatter convention that
    ``mdlout.py`` does.  This is a deliberately tiny parser: only top-level
    ``key: value`` scalar lines are extracted.  Anything more exotic is
    ignored -- the gallery just needs the title.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}, text
    fm: dict[str, str] = {}
    for raw in lines[1:end_idx]:
        if ":" not in raw:
            continue
        key, _, val = raw.partition(":")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key:
            fm[key] = val
    body = "\n".join(lines[end_idx + 1 :])
    return fm, body


# Inline-formatting characters we want to strip from extracted titles /
# descriptions before they land in the HTML.  We deliberately don't try to
# render markdown -- this is a one-liner caption.
_INLINE_RE = re.compile(r"[*_`~]+")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_inline(text: str) -> str:
    text = _LINK_RE.sub(r"\1", text)
    text = _INLINE_RE.sub("", text)
    return " ".join(text.split())


def extract_title_and_description(md_path: Path, basename: str) -> tuple[str, str]:
    """Pull a human-readable title and one-line description from an .md file."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return basename, FALLBACK_DESCRIPTIONS.get(basename, "")

    fm, body = parse_frontmatter(text)
    body = _HTML_COMMENT_RE.sub("", body)

    title = fm.get("title", "").strip()

    description = ""
    if not title or not description:
        # Walk paragraph-by-paragraph.  First H1 (if any) seeds the title;
        # the first non-empty, non-heading, non-code, non-fenced paragraph
        # seeds the description.
        in_fence = False
        first_h1: str | None = None
        first_para_lines: list[str] = []
        first_para_done = False
        for raw in body.splitlines():
            stripped = raw.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                if first_para_lines:
                    first_para_done = True
                continue
            if in_fence:
                continue
            if not stripped:
                if first_para_lines:
                    first_para_done = True
                continue
            if stripped.startswith("#"):
                if first_h1 is None and stripped.startswith("# "):
                    first_h1 = stripped.lstrip("#").strip()
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                # [TOC] placeholder and friends
                continue
            if not first_para_done:
                first_para_lines.append(stripped)
            else:
                break
        if not title and first_h1:
            title = first_h1
        if first_para_lines:
            description = _clean_inline(" ".join(first_para_lines))

    if not title:
        # Strip the leading "NN_" numeric prefix used by the smoke-test
        # examples so the gallery shows "Hello", not "01 hello".
        pretty = re.sub(r"^\d+[_-]", "", basename).replace("_", " ").strip()
        title = pretty[:1].upper() + pretty[1:] if pretty else basename
    if not description or len(description) < 40:
        description = FALLBACK_DESCRIPTIONS.get(basename, description)

    # Trim absurdly long descriptions to a sentence-ish length for the card.
    if len(description) > 220:
        cut = description[:220]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        description = cut + "..."

    return _clean_inline(title), description


# ---------------------------------------------------------------------------
# Thumbnail generation
# ---------------------------------------------------------------------------


def generate_thumbnail(pdf_path: Path, out_png: Path) -> bool:
    """Render page 1 of ``pdf_path`` to a ~200px-wide PNG at ``out_png``.

    Returns True on success, False on any subprocess failure (so the caller
    can keep going and emit a card without a thumbnail).
    """
    with tempfile.TemporaryDirectory(prefix="mdlout_thumb_") as tmp:
        stem = Path(tmp) / "page"
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-r",
                    "30",
                    "-f",
                    "1",
                    "-l",
                    "1",
                    str(pdf_path),
                    str(stem),
                    "-png",
                ],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"  pdftoppm failed for {pdf_path.name}: {exc}", file=sys.stderr)
            return False

        # pdftoppm names the output ``page-1.png`` (or ``page-01.png`` if
        # the document has 10+ pages and we'd asked for more than one).
        candidates = sorted(Path(tmp).glob("page-*.png"))
        if not candidates:
            print(f"  pdftoppm produced no PNG for {pdf_path.name}", file=sys.stderr)
            return False
        raw_png = candidates[0]

        try:
            subprocess.run(
                ["convert", str(raw_png), "-resize", "200x", str(out_png)],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"  convert failed for {pdf_path.name}: {exc}", file=sys.stderr)
            return False

    return True


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>mdlout - rendered examples</title>
<style>
  :root {{
    --fg: #1a1a1a;
    --muted: #555;
    --bg: #fafafa;
    --card-bg: #ffffff;
    --border: #d8d8d8;
    --accent: #2c5aa0;
    --warn-bg: #fff4d6;
    --warn-border: #e0b94a;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.45; }}
  header, footer {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 0.5rem; }}
  header h1 {{ margin: 0 0 0.4rem 0; font-size: 1.9rem; }}
  header p  {{ margin: 0.3rem 0; color: var(--muted); }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 1.2rem 1.5rem 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1.2rem; }}
  .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.9rem; display: flex; flex-direction: column; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
  .card .thumb-wrap {{ display: flex; align-items: center; justify-content: center;
    background: #eee; border: 1px solid var(--border); border-radius: 4px;
    min-height: 230px; margin-bottom: 0.7rem; overflow: hidden; }}
  .card img.thumb {{ display: block; max-width: 100%; height: auto; }}
  .card .no-thumb {{ color: var(--muted); font-size: 0.9rem; padding: 1rem; text-align: center; }}
  .card h2 {{ font-size: 1.05rem; margin: 0 0 0.3rem 0; }}
  .card h2 a {{ color: var(--fg); text-decoration: none; }}
  .card h2 a:hover {{ color: var(--accent); text-decoration: underline; }}
  .card p.desc {{ margin: 0 0 0.7rem 0; color: var(--muted); font-size: 0.92rem; flex: 1 1 auto; }}
  .card .links {{ font-size: 0.88rem; }}
  .card .links a {{ color: var(--accent); text-decoration: none; margin-right: 0.6rem; }}
  .card .links a:hover {{ text-decoration: underline; }}
  .banner {{ background: var(--warn-bg); border: 1px solid var(--warn-border);
    padding: 0.4rem 0.6rem; border-radius: 4px; font-size: 0.85rem;
    color: #6b4f10; margin-bottom: 0.6rem; }}
  .meta {{ font-size: 0.78rem; color: var(--muted); margin-top: 0.4rem; }}
  footer {{ border-top: 1px solid var(--border); margin-top: 2rem; padding-top: 1rem;
    color: var(--muted); font-size: 0.88rem; }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}
  code {{ background: #f0f0f0; padding: 0.05rem 0.25rem; border-radius: 3px;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.88em; }}
</style>
</head>
<body>
<header>
  <h1>mdlout - rendered examples</h1>
  <p>A visual gallery of the committed reference renderings under
     <code>examples/out/</code>. Each thumbnail shows page 1 of the PDF
     build; the links go to the full HTML render, the PDF, and the
     Markdown source.</p>
  <p>Regenerate with <code>python3 examples/generate_gallery.py</code>.
     Thumbnails are extracted from the committed PDFs with
     <code>pdftoppm</code> + ImageMagick <code>convert</code>.</p>
</header>
<main>
  <section class="grid">
{cards}
  </section>
</main>
<footer>
  <p><a href="../README.md">examples/README.md</a> &middot;
     <a href="../../README.md">project README</a> &middot;
     <a href="../../TODO.md">TODO</a></p>
  <p>{count} example{plural} indexed{broken_note}.</p>
</footer>
</body>
</html>
"""


CARD_TEMPLATE = """    <article class="card">
      <a class="thumb-wrap" href="{html_or_pdf_href}">
{thumb_html}
      </a>
{banner_html}      <h2><a href="{html_or_pdf_href}">{title}</a></h2>
      <p class="desc">{description}</p>
      <div class="links">
{link_list}
      </div>
      <div class="meta"><code>{basename}.md</code></div>
    </article>
"""


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_card(ex: Example) -> str:
    if ex.thumb_path is not None:
        thumb_html = (
            f'        <img class="thumb" src="{_esc(ex.thumb_path.name)}" '
            f'alt="Page 1 thumbnail of {_esc(ex.title)}" loading="lazy">'
        )
    else:
        thumb_html = '        <div class="no-thumb">(no thumbnail available)</div>'

    # Prefer the HTML render as the primary link target; fall back to the PDF
    # if the HTML version isn't committed.
    if ex.html_path is not None:
        primary = ex.html_path.name
    else:
        primary = ex.pdf_path.name

    links: list[str] = []
    if ex.html_path is not None:
        links.append(f'<a href="{_esc(ex.html_path.name)}">HTML</a>')
    links.append(f'<a href="{_esc(ex.pdf_path.name)}">PDF</a>')
    if ex.md_path is not None:
        # Source lives one directory up from examples/out/.
        src_href = f"../{ex.md_path.name}"
        links.append(f'<a href="{_esc(src_href)}">source</a>')
    link_list = "        " + "\n        ".join(links)

    banner_html = ""
    if ex.broken:
        banner_html = (
            '      <div class="banner">Known issue: this example currently '
            "does not render to PDF; the card is shown for completeness.</div>\n"
        )

    return CARD_TEMPLATE.format(
        html_or_pdf_href=_esc(primary),
        thumb_html=thumb_html,
        banner_html=banner_html,
        title=_esc(ex.title),
        description=_esc(ex.description) or "&nbsp;",
        link_list=link_list,
        basename=_esc(ex.basename),
    )


def render_page(examples: list[Example]) -> str:
    cards = "\n".join(render_card(ex) for ex in examples)
    broken_count = sum(1 for ex in examples if ex.broken)
    broken_note = (
        f", {broken_count} flagged as known-broken" if broken_count else ""
    )
    return PAGE_TEMPLATE.format(
        cards=cards,
        count=len(examples),
        plural="" if len(examples) == 1 else "s",
        broken_note=broken_note,
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def collect_examples() -> list[Example]:
    pdfs = sorted(p for p in OUT_DIR.glob("*.pdf"))
    # Pick up any known-broken examples that lack a PDF, so the gallery
    # still surfaces them with the appropriate banner.
    seen_basenames = {p.stem for p in pdfs}
    extra_basenames = sorted(b for b in KNOWN_BROKEN if b not in seen_basenames)

    examples: list[Example] = []
    for pdf in pdfs:
        basename = pdf.stem
        md_path = EXAMPLES_DIR / f"{basename}.md"
        md_arg = md_path if md_path.exists() else None
        html_path = OUT_DIR / f"{basename}.html"
        html_arg = html_path if html_path.exists() else None

        if md_arg is not None:
            title, description = extract_title_and_description(md_arg, basename)
        else:
            title = basename.replace("_", " ")
            description = FALLBACK_DESCRIPTIONS.get(basename, "")

        examples.append(
            Example(
                basename=basename,
                md_path=md_arg,
                pdf_path=pdf,
                html_path=html_arg,
                thumb_path=None,  # filled in below if generation succeeds
                title=title,
                description=description,
                broken=basename in KNOWN_BROKEN,
            )
        )

    for basename in extra_basenames:
        md_path = EXAMPLES_DIR / f"{basename}.md"
        md_arg = md_path if md_path.exists() else None
        if md_arg is not None:
            title, description = extract_title_and_description(md_arg, basename)
        else:
            title = basename.replace("_", " ")
            description = FALLBACK_DESCRIPTIONS.get(basename, "")
        examples.append(
            Example(
                basename=basename,
                md_path=md_arg,
                pdf_path=OUT_DIR / f"{basename}.pdf",  # missing on disk
                html_path=None,
                thumb_path=None,
                title=title,
                description=description,
                broken=True,
            )
        )

    return examples


def main() -> int:
    if not OUT_DIR.is_dir():
        print(f"error: {OUT_DIR} does not exist", file=sys.stderr)
        return 1

    for tool in ("pdftoppm", "convert"):
        if shutil.which(tool) is None:
            print(
                f"warning: '{tool}' not found on PATH; thumbnails will be skipped",
                file=sys.stderr,
            )

    examples = collect_examples()
    if not examples:
        print(f"warning: no PDFs found under {OUT_DIR}", file=sys.stderr)

    print(f"Generating gallery for {len(examples)} example(s)...")
    thumb_count = 0
    for ex in examples:
        if not ex.pdf_path.exists():
            print(f"  {ex.basename}: pdf missing, skipping thumbnail")
            continue
        target = OUT_DIR / f"thumb-{ex.basename}.png"
        ok = generate_thumbnail(ex.pdf_path, target)
        if ok:
            ex.thumb_path = target
            thumb_count += 1
            print(f"  {ex.basename}: thumbnail -> {target.name}")
        else:
            print(f"  {ex.basename}: thumbnail generation failed")

    index_path = OUT_DIR / "index.html"
    index_path.write_text(render_page(examples), encoding="utf-8")
    print(f"Wrote {index_path} ({thumb_count}/{len(examples)} thumbnails).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
