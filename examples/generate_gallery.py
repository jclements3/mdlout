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
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
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
    # New metadata for the filter / sort UI.
    doc_type: str = "doc"           # one of doc/report/book/slides/poster/magazine
    features: list[str] = field(default_factory=list)
    page_count: int = 0
    md_source: str = ""             # raw .md text (for the copy-to-clipboard button)


# ---------------------------------------------------------------------------
# Feature detection
# ---------------------------------------------------------------------------


# Each entry: (chip-id, regex against the Markdown source). Patterns are
# intentionally generous; the chips are advisory, not contractual.
FEATURE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("math",
     re.compile(r"(\$\$[^$]+\$\$|```math|(?<![\$\\])\$(?!\$)[^$\n]+?\$)", re.M)),
    ("music",
     re.compile(r"```abc", re.M)),
    ("code",
     re.compile(r"```(?:python|c|cpp|c\+\+|shell|bash|sh|js|javascript|"
                r"ts|typescript|rust|go|java|yaml|json|xml|html|css|sql|"
                r"haskell|markdown|text)\b", re.I | re.M)),
    ("diagrams",
     re.compile(r"@(?:Diag|DiagTree|SyntaxDiag|Node|Link|Tree)\b", re.M)),
    ("tables",
     re.compile(r"^\s*\|[^\n]+\|\s*$", re.M)),
    ("multi-col",
     re.compile(r"^columns:\s*[2-9]\b", re.M | re.I)),
    ("bibliography",
     re.compile(r"\[@[A-Za-z0-9_][A-Za-z0-9_-]*\]", re.M)),
    ("footnotes",
     re.compile(r"\[\^[A-Za-z0-9_-]+\]", re.M)),
    ("raw-lout",
     re.compile(r"```lout\b", re.M)),
    ("svg",
     re.compile(r"```svg\b|\]\([^)]+\.svg\b", re.M)),
    ("admonitions",
     re.compile(r"^!!!\s+\w+", re.M)),
]

# Special-case override map: some example basenames belong to a "presentation"
# document type beyond what frontmatter announces. The mapping is keyed by
# basename and overrides the value extracted from ``type:``.
DOCTYPE_OVERRIDES: dict[str, str] = {
    "academic_poster": "poster",
    "magazine_layout": "magazine",
}

# Canonical chip ordering, used for both the top filter bar and the per-card
# tag chips. Each entry is (chip-id, human-readable-label).
DOCTYPE_CHIPS: list[tuple[str, str]] = [
    ("doc", "Doc"),
    ("report", "Report"),
    ("book", "Book"),
    ("slides", "Slides"),
    ("poster", "Poster"),
    ("magazine", "Magazine"),
]
FEATURE_CHIPS: list[tuple[str, str]] = [
    ("math", "Math"),
    ("music", "Music"),
    ("code", "Code"),
    ("diagrams", "Diagrams"),
    ("tables", "Tables"),
    ("multi-col", "Multi-col"),
    ("bibliography", "Bibliography"),
    ("footnotes", "Footnotes"),
    ("raw-lout", "Raw Lout"),
    ("svg", "SVG"),
    ("admonitions", "Admonitions"),
]


def detect_features(md_text: str) -> list[str]:
    """Return the list of feature chip-ids that fire on ``md_text``.

    Matches are stable in canonical chip order so the per-card chips
    render in a predictable sequence.
    """
    hits: list[str] = []
    for chip_id, pat in FEATURE_PATTERNS:
        if pat.search(md_text):
            hits.append(chip_id)
    return hits


def detect_doc_type(basename: str, frontmatter: dict[str, str]) -> str:
    """Pick the doc-type chip for an example.

    The basename override map wins over the YAML ``type:`` so the
    poster and magazine examples land on their dedicated chips even
    though their underlying Lout package is ``doc``.
    """
    if basename in DOCTYPE_OVERRIDES:
        return DOCTYPE_OVERRIDES[basename]
    raw = (frontmatter.get("type") or "doc").strip().lower()
    if raw not in {c[0] for c in DOCTYPE_CHIPS}:
        raw = "doc"
    return raw


# ---------------------------------------------------------------------------
# Page-count extraction
# ---------------------------------------------------------------------------


# The SVG back end emits ``<svg class="lout-page" ...>`` per page; count those
# occurrences to derive a page count from the HTML file without parsing it.
# Falls back to a PDF-based count via ``pdfinfo`` if no HTML is present.
_LOUT_PAGE_RE = re.compile(r'<svg\b[^>]*\bclass\s*=\s*"[^"]*\blout-page\b', re.I)


def count_pages_html(html_path: Path) -> int:
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return len(_LOUT_PAGE_RE.findall(text))


def count_pages_pdf(pdf_path: Path) -> int:
    if not pdf_path.exists():
        return 0
    try:
        proc = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    for line in proc.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return 0
    return 0


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


def generate_preview_svg(pdf_path: Path, out_svg: Path) -> bool:
    """Render page 1 of ``pdf_path`` to an SVG at ``out_svg``.

    Used by the per-example preview landing page so the page-1 hero scales
    cleanly. Falls back to False if ``pdftocairo`` is missing or fails -
    the preview page then renders without the SVG hero.
    """
    try:
        subprocess.run(
            [
                "pdftocairo",
                "-svg",
                "-f", "1",
                "-l", "1",
                str(pdf_path),
                str(out_svg),
            ],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"  pdftocairo failed for {pdf_path.name}: {exc}", file=sys.stderr)
        return False
    return out_svg.exists()


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
    --accent-bg: #eaf1fb;
    --warn-bg: #fff4d6;
    --warn-border: #e0b94a;
    --chip-bg: #eef0f3;
    --chip-fg: #333;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    line-height: 1.45; }}
  header, footer {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 0.5rem; }}
  header h1 {{ margin: 0 0 0.4rem 0; font-size: 1.9rem; }}
  header p  {{ margin: 0.3rem 0; color: var(--muted); }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 1.2rem 1.5rem 2rem; }}
  nav.gallery-filters {{ max-width: 1100px; margin: 0 auto 1rem auto; padding: 0.6rem 1.5rem;
    background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
  nav.gallery-filters .row {{ display: flex; flex-wrap: wrap; align-items: center;
    gap: 0.5rem; margin: 0.4rem 0; }}
  nav.gallery-filters .row-label {{ font-size: 0.85rem; color: var(--muted);
    margin-right: 0.4rem; min-width: 4.5rem; }}
  nav.gallery-filters button.chip {{ border: 1px solid var(--border); background: var(--chip-bg);
    color: var(--chip-fg); border-radius: 999px; padding: 0.25rem 0.7rem; font-size: 0.82rem;
    cursor: pointer; font-family: inherit; }}
  nav.gallery-filters button.chip:hover {{ background: #dfe3ea; }}
  nav.gallery-filters button.chip.active {{ background: var(--accent); color: white;
    border-color: var(--accent); }}
  nav.gallery-filters select.sort {{ border: 1px solid var(--border); background: white;
    border-radius: 4px; padding: 0.25rem 0.5rem; font-size: 0.85rem; font-family: inherit; }}
  nav.gallery-filters .count {{ font-size: 0.82rem; color: var(--muted); margin-left: auto; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1.2rem; }}
  .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px;
    padding: 0.9rem; display: flex; flex-direction: column; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
  .card.hidden {{ display: none; }}
  .card .thumb-wrap {{ display: flex; align-items: center; justify-content: center;
    background: #eee; border: 1px solid var(--border); border-radius: 4px;
    min-height: 230px; margin-bottom: 0.7rem; overflow: hidden; }}
  .card img.thumb {{ display: block; max-width: 100%; height: auto; }}
  .card .no-thumb {{ color: var(--muted); font-size: 0.9rem; padding: 1rem; text-align: center; }}
  .card h2 {{ font-size: 1.05rem; margin: 0 0 0.3rem 0; }}
  .card h2 a {{ color: var(--fg); text-decoration: none; }}
  .card h2 a:hover {{ color: var(--accent); text-decoration: underline; }}
  .card p.desc {{ margin: 0 0 0.7rem 0; color: var(--muted); font-size: 0.92rem; flex: 1 1 auto; }}
  .card .tags {{ display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.6rem; }}
  .card .tag {{ font-size: 0.72rem; padding: 0.1rem 0.5rem; border-radius: 999px;
    background: var(--chip-bg); color: var(--chip-fg); border: 1px solid var(--border); }}
  .card .tag.type {{ background: var(--accent-bg); color: var(--accent); border-color: #c9d6ec; }}
  .card .links {{ font-size: 0.88rem; }}
  .card .links a {{ color: var(--accent); text-decoration: none; margin-right: 0.6rem; }}
  .card .links a:hover {{ text-decoration: underline; }}
  .card button.copy-md {{ font-size: 0.82rem; padding: 0.25rem 0.6rem; margin-top: 0.5rem;
    border: 1px solid var(--border); background: var(--chip-bg); border-radius: 4px;
    color: var(--chip-fg); cursor: pointer; font-family: inherit; align-self: flex-start; }}
  .card button.copy-md:hover {{ background: var(--accent-bg); color: var(--accent);
    border-color: #c9d6ec; }}
  .card button.copy-md.copied {{ background: #d8eed8; color: #225522; border-color: #b6d8b6; }}
  .banner {{ background: var(--warn-bg); border: 1px solid var(--warn-border);
    padding: 0.4rem 0.6rem; border-radius: 4px; font-size: 0.85rem;
    color: #6b4f10; margin-bottom: 0.6rem; }}
  .meta {{ font-size: 0.78rem; color: var(--muted); margin-top: 0.4rem; }}
  .page-badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
    background: var(--chip-bg); color: var(--chip-fg); font-size: 0.72rem;
    border: 1px solid var(--border); margin-left: 0.4rem; }}
  .empty-message {{ color: var(--muted); font-style: italic; padding: 2rem;
    text-align: center; grid-column: 1 / -1; }}
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
<nav class="gallery-filters" aria-label="Filter and sort gallery examples">
  <div class="row" data-row="type">
    <span class="row-label">Type:</span>
{type_chips}
  </div>
  <div class="row" data-row="feature">
    <span class="row-label">Feature:</span>
{feature_chips}
  </div>
  <div class="row" data-row="sort">
    <span class="row-label">Sort:</span>
    <select class="sort" id="sort-select" aria-label="Sort order">
      <option value="title">Title (A-Z)</option>
      <option value="title-desc">Title (Z-A)</option>
      <option value="pages">Page count (low-high)</option>
      <option value="pages-desc">Page count (high-low)</option>
    </select>
    <span class="count" id="visible-count" aria-live="polite"></span>
  </div>
</nav>
<main>
  <section class="grid" id="gallery-grid">
{cards}
    <div class="empty-message" id="empty-message" hidden>
      No examples match the current filter combination.
    </div>
  </section>
</main>
<footer>
  <p><a href="../README.md">examples/README.md</a> &middot;
     <a href="../../README.md">project README</a> &middot;
     <a href="../../TODO.md">TODO</a></p>
  <p>{count} example{plural} indexed{broken_note}.</p>
</footer>
<script>
(function() {{
  "use strict";
  var grid = document.getElementById("gallery-grid");
  if (!grid) return;
  var cards = Array.prototype.slice.call(grid.querySelectorAll(".card"));
  var emptyMsg = document.getElementById("empty-message");
  var visibleCount = document.getElementById("visible-count");
  var sortSelect = document.getElementById("sort-select");

  // Active-filter state. ``typeActive`` is a single string ("" means all
  // types). ``featuresActive`` is a Set of feature ids (empty = all).
  var typeActive = "";
  var featuresActive = new Set();

  function cardMatches(card) {{
    if (typeActive && card.getAttribute("data-type") !== typeActive) {{
      return false;
    }}
    if (featuresActive.size > 0) {{
      var raw = card.getAttribute("data-features") || "";
      var have = new Set(raw.split(",").filter(Boolean));
      var iter = featuresActive.values();
      var step;
      while (!(step = iter.next()).done) {{
        if (!have.has(step.value)) return false;
      }}
    }}
    return true;
  }}

  function applyFilters() {{
    var nVisible = 0;
    for (var i = 0; i < cards.length; i++) {{
      var card = cards[i];
      if (cardMatches(card)) {{
        card.classList.remove("hidden");
        nVisible++;
      }} else {{
        card.classList.add("hidden");
      }}
    }}
    if (emptyMsg) emptyMsg.hidden = nVisible > 0;
    if (visibleCount) {{
      visibleCount.textContent = nVisible + " of " + cards.length + " visible";
    }}
  }}

  function applySort(key) {{
    var rev = key.indexOf("-desc") >= 0;
    var base = key.replace("-desc", "");
    var sorted = cards.slice().sort(function(a, b) {{
      var av, bv;
      if (base === "pages") {{
        av = parseInt(a.getAttribute("data-pages") || "0", 10);
        bv = parseInt(b.getAttribute("data-pages") || "0", 10);
      }} else {{
        av = (a.getAttribute("data-title") || "").toLowerCase();
        bv = (b.getAttribute("data-title") || "").toLowerCase();
      }}
      if (av < bv) return rev ? 1 : -1;
      if (av > bv) return rev ? -1 : 1;
      return 0;
    }});
    // Re-attach in sorted order. ``emptyMsg`` stays at the end.
    for (var i = 0; i < sorted.length; i++) grid.appendChild(sorted[i]);
    if (emptyMsg) grid.appendChild(emptyMsg);
  }}

  // Wire up chip clicks.
  var chips = document.querySelectorAll("nav.gallery-filters button.chip");
  chips.forEach(function(chip) {{
    chip.addEventListener("click", function() {{
      var row = chip.closest(".row").getAttribute("data-row");
      var value = chip.getAttribute("data-value");
      if (row === "type") {{
        // Single-select within the Type row.
        if (typeActive === value) {{
          typeActive = "";
          chip.classList.remove("active");
        }} else {{
          typeActive = value;
          var typeChips = document.querySelectorAll(
            'nav.gallery-filters .row[data-row="type"] button.chip');
          typeChips.forEach(function(c) {{ c.classList.remove("active"); }});
          chip.classList.add("active");
        }}
      }} else if (row === "feature") {{
        // Multi-select; every active chip must be present on the card.
        if (featuresActive.has(value)) {{
          featuresActive.delete(value);
          chip.classList.remove("active");
        }} else {{
          featuresActive.add(value);
          chip.classList.add("active");
        }}
      }}
      applyFilters();
    }});
  }});

  // Sort dropdown.
  if (sortSelect) {{
    sortSelect.addEventListener("change", function() {{
      applySort(sortSelect.value);
    }});
  }}

  // Copy-markdown buttons. Each card holds the raw .md in a hidden
  // <script type="application/json"> sibling under the card root; we
  // JSON.parse the textContent (which is the .md text encoded as a JSON
  // string literal) and hand the result to navigator.clipboard.
  cards.forEach(function(card) {{
    var btn = card.querySelector("button.copy-md");
    if (!btn) return;
    btn.addEventListener("click", function() {{
      var src = card.querySelector('script.md-source');
      var decoded = "";
      if (src) {{
        try {{ decoded = JSON.parse(src.textContent); }}
        catch (e) {{ decoded = src.textContent; }}
      }}
      var done = function() {{
        var orig = btn.textContent;
        btn.textContent = "Copied!";
        btn.classList.add("copied");
        setTimeout(function() {{
          btn.textContent = orig;
          btn.classList.remove("copied");
        }}, 1400);
      }};
      if (navigator.clipboard && navigator.clipboard.writeText) {{
        navigator.clipboard.writeText(decoded).then(done, function() {{
          /* Permission denied or insecure context. Fall back to selection. */
          var ta = document.createElement("textarea");
          ta.value = decoded;
          document.body.appendChild(ta);
          ta.select();
          try {{ document.execCommand("copy"); done(); }} catch (e) {{}}
          document.body.removeChild(ta);
        }});
      }} else {{
        var ta = document.createElement("textarea");
        ta.value = decoded;
        document.body.appendChild(ta);
        ta.select();
        try {{ document.execCommand("copy"); done(); }} catch (e) {{}}
        document.body.removeChild(ta);
      }}
    }});
  }});

  // Initial sort + count.
  applySort(sortSelect ? sortSelect.value : "title");
  applyFilters();
}})();
</script>
</body>
</html>
"""


CARD_TEMPLATE = """    <article class="card" data-type="{data_type}" \
data-features="{data_features}" data-pages="{data_pages}" \
data-title="{data_title}">
      <a class="thumb-wrap" href="{preview_href}">
{thumb_html}
      </a>
{banner_html}      <h2><a href="{preview_href}">{title}</a>\
<span class="page-badge" title="Pages in rendered output">{data_pages} pp</span></h2>
      <p class="desc">{description}</p>
      <div class="tags">
{tag_chips}
      </div>
      <div class="links">
{link_list}
      </div>
      {copy_button}
      <div class="meta"><code>{basename}.md</code></div>
      {md_template}
    </article>
"""


PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} - mdlout preview</title>
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
    line-height: 1.5; }}
  header, main, footer {{ max-width: 1000px; margin: 0 auto; padding: 1.4rem 1.5rem; }}
  header {{ padding-bottom: 0.4rem; }}
  header .back a {{ color: var(--accent); text-decoration: none; font-size: 0.92rem; }}
  header .back a:hover {{ text-decoration: underline; }}
  header h1 {{ margin: 0.5rem 0 0.3rem 0; font-size: 1.8rem; }}
  header p.desc {{ margin: 0.3rem 0 0.6rem 0; color: var(--muted); font-size: 1.02rem; }}
  header .meta {{ font-size: 0.85rem; color: var(--muted); }}
  main {{ padding-top: 0.6rem; }}
  .actions {{ margin-bottom: 1.0rem; }}
  .actions a {{ display: inline-block; background: var(--card-bg); border: 1px solid var(--border);
    border-radius: 4px; padding: 0.45rem 0.9rem; margin-right: 0.5rem; margin-bottom: 0.4rem;
    color: var(--accent); text-decoration: none; font-size: 0.94rem; }}
  .actions a:hover {{ border-color: var(--accent); background: #f0f5ff; }}
  .hero {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 6px;
    padding: 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
  .hero .frame {{ display: flex; align-items: flex-start; justify-content: center;
    background: #f4f4f4; border: 1px solid var(--border); border-radius: 4px;
    overflow: hidden; padding: 0.6rem; }}
  .hero .frame svg, .hero .frame img {{ display: block; max-width: 100%; height: auto;
    background: white; box-shadow: 0 0 4px rgba(0,0,0,0.08); }}
  .hero .caption {{ color: var(--muted); font-size: 0.85rem; margin-top: 0.6rem; text-align: center; }}
  .no-svg {{ color: var(--muted); padding: 2rem; text-align: center; }}
  .banner {{ background: var(--warn-bg); border: 1px solid var(--warn-border);
    padding: 0.5rem 0.7rem; border-radius: 4px; font-size: 0.9rem; color: #6b4f10;
    margin-bottom: 1rem; }}
  footer {{ border-top: 1px solid var(--border); margin-top: 1.5rem; padding-top: 1rem;
    color: var(--muted); font-size: 0.88rem; }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}
  code {{ background: #f0f0f0; padding: 0.05rem 0.25rem; border-radius: 3px;
    font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.88em; }}
</style>
</head>
<body>
<header>
  <p class="back"><a href="index.html">&larr; Back to gallery</a></p>
  <h1>{title}</h1>
  <p class="desc">{description}</p>
  <p class="meta">Source: <code>{basename}.md</code></p>
</header>
<main>
{banner_html}  <div class="actions">
{action_links}
  </div>
  <div class="hero">
    <div class="frame">
{hero_html}
    </div>
    <p class="caption">Page 1 of the rendered PDF (rasterised to SVG by <code>pdftocairo</code>).</p>
  </div>
</main>
<footer>
  <p><a href="index.html">Back to gallery</a> &middot;
     <a href="../README.md">examples/README.md</a> &middot;
     <a href="../../README.md">project README</a></p>
</footer>
</body>
</html>
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

    # Preview landing page is the primary link target. We always generate one
    # (named ``<basename>_preview.html``); even broken examples get a card
    # whose preview surfaces the warning banner.
    preview_href = f"{ex.basename}_preview.html"

    links: list[str] = [f'<a href="{_esc(preview_href)}">Preview</a>']
    if ex.html_path is not None:
        links.append(f'<a href="{_esc(ex.html_path.name)}">HTML</a>')
    if ex.pdf_path.exists():
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

    # Build the tag chip list. The first chip is always the doc-type
    # (rendered with the ``.tag.type`` accent); subsequent chips are the
    # feature flags in canonical order.
    type_label = dict(DOCTYPE_CHIPS).get(ex.doc_type, ex.doc_type.title())
    chip_lines = [
        f'        <span class="tag type">{_esc(type_label)}</span>'
    ]
    feature_label = dict(FEATURE_CHIPS)
    for feat in ex.features:
        if feat in feature_label:
            chip_lines.append(
                f'        <span class="tag">{_esc(feature_label[feat])}</span>'
            )
    tag_chips = "\n".join(chip_lines)

    # Copy-markdown button (and the hidden JSON payload that carries the .md
    # text) only emitted when there's actual source to copy.
    if ex.md_source:
        copy_button = (
            '<button type="button" class="copy-md" '
            'aria-label="Copy Markdown source to clipboard">'
            'Copy markdown</button>'
        )
        # JSON-encode the .md text so it can survive embedding in a
        # ``<script type="application/json">`` element without colliding with
        # the browser-test anchor regex (which matches ``href="#..."`` even
        # inside <template> nodes). The JSON-encoded form has no ``href=``
        # substring and is robust to all the metacharacters mdlout examples
        # carry.
        encoded = json.dumps(ex.md_source)
        md_template = (
            '<script type="application/json" class="md-source">'
            + encoded
            + '</script>'
        )
    else:
        copy_button = ""
        md_template = ""

    return CARD_TEMPLATE.format(
        preview_href=_esc(preview_href),
        thumb_html=thumb_html,
        banner_html=banner_html,
        title=_esc(ex.title),
        description=_esc(ex.description) or "&nbsp;",
        link_list=link_list,
        basename=_esc(ex.basename),
        data_type=_esc(ex.doc_type),
        data_features=_esc(",".join(ex.features)),
        data_pages=ex.page_count,
        data_title=_esc(ex.title),
        tag_chips=tag_chips,
        copy_button=copy_button,
        md_template=md_template,
    )


def render_preview(ex: Example, preview_svg_name: str | None) -> str:
    """Render a per-example landing page.

    ``preview_svg_name`` is the basename of the page-1 SVG (relative to
    ``examples/out/``), or None if SVG generation failed. We fall back to
    inlining the PNG thumbnail in that case so the page is never empty.
    """
    action_items: list[str] = []
    if ex.html_path is not None:
        action_items.append(f'    <a href="{_esc(ex.html_path.name)}">View full HTML</a>')
    if ex.pdf_path.exists():
        action_items.append(f'    <a href="{_esc(ex.pdf_path.name)}">Download PDF</a>')
    if ex.md_path is not None:
        src_href = f"../{ex.md_path.name}"
        action_items.append(f'    <a href="{_esc(src_href)}">Source .md</a>')
    action_links = "\n".join(action_items) if action_items else "    <span>&nbsp;</span>"

    if preview_svg_name is not None:
        hero_html = (
            f'      <object type="image/svg+xml" data="{_esc(preview_svg_name)}" '
            f'aria-label="Page 1 of {_esc(ex.title)}"></object>'
        )
    elif ex.thumb_path is not None:
        hero_html = (
            f'      <img src="{_esc(ex.thumb_path.name)}" '
            f'alt="Page 1 thumbnail of {_esc(ex.title)}">'
        )
    else:
        hero_html = '      <div class="no-svg">(no preview available)</div>'

    banner_html = ""
    if ex.broken:
        banner_html = (
            '  <div class="banner">Known issue: this example currently '
            "does not render to PDF. The preview below may be unavailable.</div>\n"
        )

    return PREVIEW_TEMPLATE.format(
        title=_esc(ex.title),
        description=_esc(ex.description) or "&nbsp;",
        basename=_esc(ex.basename),
        banner_html=banner_html,
        action_links=action_links,
        hero_html=hero_html,
    )


def _render_chip_row(chip_defs: list[tuple[str, str]],
                     present_ids: set[str]) -> str:
    """Render a row of filter-chip buttons.

    Only chips that some example actually carries make it into the bar -- a
    chip nobody can match would be confusing. Chips are emitted in the
    canonical order defined in ``DOCTYPE_CHIPS`` / ``FEATURE_CHIPS``.
    """
    out: list[str] = []
    for chip_id, label in chip_defs:
        if chip_id not in present_ids:
            continue
        out.append(
            f'    <button type="button" class="chip" '
            f'data-value="{_esc(chip_id)}">{_esc(label)}</button>'
        )
    if not out:
        # Keep the row non-empty so the layout doesn't collapse.
        out.append('    <span style="color: var(--muted); '
                   'font-size: 0.82rem;">(none)</span>')
    return "\n".join(out)


def render_page(examples: list[Example]) -> str:
    cards = "\n".join(render_card(ex) for ex in examples)
    broken_count = sum(1 for ex in examples if ex.broken)
    broken_note = (
        f", {broken_count} flagged as known-broken" if broken_count else ""
    )
    # Build the chip rows from the union of doc-types and features actually
    # present in the example set.
    present_types = {ex.doc_type for ex in examples}
    present_features: set[str] = set()
    for ex in examples:
        present_features.update(ex.features)
    type_chips = _render_chip_row(DOCTYPE_CHIPS, present_types)
    feature_chips = _render_chip_row(FEATURE_CHIPS, present_features)
    return PAGE_TEMPLATE.format(
        cards=cards,
        count=len(examples),
        plural="" if len(examples) == 1 else "s",
        broken_note=broken_note,
        type_chips=type_chips,
        feature_chips=feature_chips,
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _populate_metadata(ex: Example) -> None:
    """Fill in the doc_type / features / page_count / md_source fields on ``ex``.

    Best-effort: a missing .md or HTML file simply leaves the corresponding
    field empty. The function never raises.
    """
    if ex.md_path is not None:
        try:
            ex.md_source = ex.md_path.read_text(encoding="utf-8")
        except OSError:
            ex.md_source = ""
    fm, _ = parse_frontmatter(ex.md_source) if ex.md_source else ({}, "")
    ex.doc_type = detect_doc_type(ex.basename, fm)
    ex.features = detect_features(ex.md_source) if ex.md_source else []
    if ex.html_path is not None:
        ex.page_count = count_pages_html(ex.html_path)
    if ex.page_count == 0:
        # PDF fallback - matches the rendered page count even when no HTML.
        ex.page_count = count_pages_pdf(ex.pdf_path)


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

        ex = Example(
            basename=basename,
            md_path=md_arg,
            pdf_path=pdf,
            html_path=html_arg,
            thumb_path=None,  # filled in below if generation succeeds
            title=title,
            description=description,
            broken=basename in KNOWN_BROKEN,
        )
        _populate_metadata(ex)
        examples.append(ex)

    for basename in extra_basenames:
        md_path = EXAMPLES_DIR / f"{basename}.md"
        md_arg = md_path if md_path.exists() else None
        if md_arg is not None:
            title, description = extract_title_and_description(md_arg, basename)
        else:
            title = basename.replace("_", " ")
            description = FALLBACK_DESCRIPTIONS.get(basename, "")
        ex = Example(
            basename=basename,
            md_path=md_arg,
            pdf_path=OUT_DIR / f"{basename}.pdf",  # missing on disk
            html_path=None,
            thumb_path=None,
            title=title,
            description=description,
            broken=True,
        )
        _populate_metadata(ex)
        examples.append(ex)

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
    if shutil.which("pdftocairo") is None:
        print(
            "warning: 'pdftocairo' not found on PATH; preview SVGs will be skipped",
            file=sys.stderr,
        )

    examples = collect_examples()
    if not examples:
        print(f"warning: no PDFs found under {OUT_DIR}", file=sys.stderr)

    print(f"Generating gallery for {len(examples)} example(s)...")
    thumb_count = 0
    preview_count = 0
    for ex in examples:
        if not ex.pdf_path.exists():
            print(f"  {ex.basename}: pdf missing, skipping thumbnail")
            preview_svg_name: str | None = None
        else:
            target = OUT_DIR / f"thumb-{ex.basename}.png"
            ok = generate_thumbnail(ex.pdf_path, target)
            if ok:
                ex.thumb_path = target
                thumb_count += 1
                print(f"  {ex.basename}: thumbnail -> {target.name}")
            else:
                print(f"  {ex.basename}: thumbnail generation failed")

            preview_svg_path = OUT_DIR / f"preview-{ex.basename}.svg"
            if generate_preview_svg(ex.pdf_path, preview_svg_path):
                preview_svg_name = preview_svg_path.name
                preview_count += 1
                print(f"  {ex.basename}: preview SVG -> {preview_svg_path.name}")
            else:
                preview_svg_name = None

        preview_path = OUT_DIR / f"{ex.basename}_preview.html"
        preview_path.write_text(render_preview(ex, preview_svg_name), encoding="utf-8")

    index_path = OUT_DIR / "index.html"
    index_path.write_text(render_page(examples), encoding="utf-8")
    print(
        f"Wrote {index_path} ({thumb_count}/{len(examples)} thumbnails, "
        f"{preview_count}/{len(examples)} preview SVGs, {len(examples)} preview pages)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
