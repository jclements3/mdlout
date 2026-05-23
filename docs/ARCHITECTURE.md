# mdlout Architecture

A reading guide for the codebase as of mdlout **0.2.7**, intended for two
audiences: someone considering mdlout for a real document, and someone
considering contributing. Numbers and file references are taken directly
from the source; where a claim is not verifiable from the tree, it is
omitted or qualified. Companion documents:

- [`docs/z53_internals.md`](z53_internals.md) — deep dive on the SVG
  back end's data structures and PostScript interpreter.
- [`docs/PERFORMANCE.md`](PERFORMANCE.md) — current build-time numbers,
  bottlenecks, and the `tests/bench.py` workflow.
- [`docs/best_practices.md`](best_practices.md) — recommended frontmatter,
  CLI flags, and authoring conventions.

## 1. What this is

mdlout is a converter from Markdown to two output formats: an HTML
scaffold containing per-page SVG (the default), and a PDF (the legacy
path). Both paths run through the same intermediate language — Lout
source (`.lt`) — and through the same C typesetting engine (a forked
copy of Jeffrey Kingston's Lout, vendored as a submodule at `lout/`).
The only difference between the two paths is which Lout back end runs:
the original PostScript back end (`lout/z49.c`, frozen) for PDF, or the
new SVG back end (`lout/z53.c` + `lout/z53_glyph.c`) for HTML. Lout's
galley layout, line breaking, hyphenation, table and equation engines
are the same in both paths; only the drawing emitter differs. The
submodule URL is `https://github.com/jclements3/lout` and its working
branch is `svg-backend`.

## 2. Top-level layout

```
mdlout/
  mdlout.py            single-file Python markdown -> Lout -> {HTML, PDF}
  pyproject.toml       version 0.2.7, no runtime deps
  dist/                wheels + sdists (0.2.5, 0.2.6, 0.2.7)
  lout/                git submodule, branch svg-backend (the C typesetter)
  examples/            ~12 markdown samples (kitchen sink, scientific paper, ...)
  tests/               regression framework (snippets, browser, user-guide diff)
  docs/                this file + tutorial, cookbook, perf, internals, ...
  .github/workflows/   ci.yml, user-guide-diff.yml, publish.yml
  README.md, CLAUDE.md, TODO.md, ROADMAP.md, CHANGELOG.md
```

## 3. The pipelines

```
                            mdlout.py
                          (parse + emit)
                                |
                                v
                           input.lt  (Lout source)
                                |
            +-------------------+--------------------+
            |                                        |
            v                                        v
       lout -G                                  lout (default)
   (SVG back end, z53.c)                  (PS back end, z49.c)
            |                                        |
            v                                        v
       input.svg                                input.ps
            |                                        |
            v                                        v
   mdlout.py HTML scaffold                       ps2pdf
   (KaTeX, abcjs, mermaid,                          |
    fonts, a11y, dark mode)                         v
            |                                   input.pdf
            v
       input.html
```

Both branches run Lout up to three passes for cross-reference
convergence (`mdlout.py:_run_lout`); only the back end's `-G` flag
differs. The PDF branch hands off to Ghostscript's `ps2pdf` at the end.
The HTML branch reads the SVG back, optionally rewrites `<text>` runs
as `<path>` outlines (`--text-as-paths`), optionally inlines raster
images as base64 (`--inline-raster`), and wraps the result in an HTML
page that inlines (or links to) the KaTeX, abcjs, and mermaid runtimes
plus, by default, **subsetted** URW++ Nimbus `@font-face` web fonts.

## 4. mdlout.py — the four-phase pipeline

A single ~4400-line Python 3.10+ script with no third-party runtime
dependencies (fontTools is optional, only for `--text-as-paths` and
font subsetting). The architecture is a strict four-phase pipeline:

### Phase (a) — `parse_frontmatter`

Reads the optional `---`-delimited YAML block at the head of the input.
Performs a permissive YAML parse (only the subset Markdown frontmatter
needs: scalars, mappings, simple sequences) and runs **key
normalisation**: aliases (`page-size` / `pagesize` / `page_size`), kebab
vs snake case, and value coercion for fonts, page sizes, margins,
columns, and a growing list of feature toggles (`inline-raster`,
`font-subset`, `text-as-paths`, `accessibility`, `dark-mode`, ...). The
normalised dictionary becomes the input to the preamble generator.

### Phase (b) — `parse_markdown`

A block-level lexer that walks the source line-by-line and emits a list
of typed `Block` objects. The `BlockType` enum (`mdlout.py:675+`)
covers: `PARAGRAPH`, `HEADING`, `CODE_BLOCK`, `MATH_BLOCK`, `ABC`,
`MERMAID_BLOCK`, `SVG_RAW`, `LOUT_RAW`, `BULLET_LIST`, `NUMBERED_LIST`,
`TASK_LIST`, `DEFINITION_LIST`, `TABLE`, `BLOCKQUOTE`, `ADMONITION`,
`HORIZONTAL_RULE`, `PAGE_BREAK`, `TOC`, `FOOTNOTE_DEF`, `IMAGE`, and
the inline image manifest entries. Fenced code blocks dispatch by
language tag (` ```math `, ` ```abc `, ` ```svg `, ` ```mermaid `,
` ```lout `, anything else → highlighted code).

### Phase (c) — `convert_inline`

Inline formatting (bold / italic / code / strikethrough / superscript /
subscript / links / images / inline math / autolinks / HTML entities /
backslash escapes) is applied using a **placeholder system**: every
"protected" span (code, math, link, image) is first replaced with an
opaque sentinel, the rest of the line is then escaped and re-formatted,
and finally the sentinels are replaced with their fully-rendered Lout
output. This prevents double-escaping (e.g. a `&` inside an URL) and
prevents inline parsers from recursing into protected spans.

### Phase (d) — `generate_lout`

Walks the block list and emits the Lout source. The preamble is
generated from the normalised frontmatter (chooses `@SysInclude { doc
}`, `report`, `book`, or `slides`; emits `@BasicSetup`,
`@DocumentSetup`, and type-specific setup overrides). For
`type: report` / `type: book`, `_generate_sectioned_body` rewires the
heading tree as nested `@Section` / `@Chapter` blocks with automatic
numbering. The body emits one Lout construct per block. **svgmacros is
gated on usage**: `@SysInclude { svgmacros }` is added only when the
document actually uses `@Math`, `@ABC`, `@SVG`, `@SVGFile`, or mermaid
— small documents stay svgmacros-free.

After phase (d) the script orchestrates the external build: locates the
`lout` binary (auto-discovered relative to the script, or via
`$LOUT_BIN`), copies any `mydefs` into the build dir, runs Lout (up to
three passes), and either pipes through `ps2pdf` (PDF) or assembles the
HTML scaffold (HTML).

## 5. HTML scaffold features

The HTML produced for `--format html` is assembled by
`_build_html_scaffold` (`mdlout.py:~3000+`). Features layered on the raw
SVG:

- **KaTeX** for `@Math` foreignObjects — auto-detected from
  `/usr/lib/node_modules/katex/` or `/usr/share/javascript/katex/`,
  otherwise CDN. `--no-math-engine` strips it out entirely.
- **abcjs** for `@ABC` foreignObjects — inlined from
  `~/projects/abcjsharp/dist/` (the user's harp-grandstaff fork), CDN
  fallback, suppressed by `--no-music-engine`.
- **mermaid.js** for ` ```mermaid ` fences — inlined from a local
  install when present, CDN fallback. Mermaid runs after page load and
  replaces each `<div class="mermaid">` text body with a child `<svg>`.
- **Accessibility scaffolding** (WCAG 2.1 conformant by default;
  disable with `--no-accessibility`):
  - Skip-link as the first focusable element (WCAG 2.4.1).
  - Visible focus ring on every focusable element (WCAG 2.4.7).
  - Visually-hidden `<h1>` derived from the document title — every
    page needs exactly one `<h1>` for AT rotor lists.
  - `<header role="banner">`, `<main id="main" role="main">`,
    `<article>`, `<aside class="footnotes">`, `<nav class="toc">` —
    full landmark set with `aria-label`s.
  - Image alt manifest: one `<figure role="img" aria-label="...">` per
    referenced image so screen readers can list them.
  - Anchor list (`<div class="mdlout-anchors" aria-hidden="true">`)
    for skip-to-section navigation.
- **Dark mode** via `currentColor`. When the document doesn't paint
  pure black, the SVG's text/strokes are rewritten to
  `fill="currentColor"` / `stroke="currentColor"` and the page picks
  up `color-scheme: light dark` so the OS theme drives ink colour.
- **Font subsetting (ON by default).** The default URW Nimbus
  `@font-face` payloads are subsetted to the glyphs actually used in
  the SVG via fontTools (when installed); this shrinks a 200-page
  document's HTML by a factor of 5–10. `--no-font-embedding` skips
  fonts entirely; `--no-font-subset` (or frontmatter
  `font-subset: false`) inlines the full font.
- **`--inline-raster`** rewrites every `<image href="..."/>` whose
  href is a relative PNG/JPG/GIF to a base64 `data:` URL. Useful for
  self-contained HTML.

## 6. lout submodule — the typesetting engine

A git submodule pointing at the maintainer's Lout fork
(`jclements3/lout`, branch `svg-backend`). After cloning mdlout, run
`git submodule update --init` and `cd lout && git checkout svg-backend
&& make lout`. The build is a single `make lout` (or `make all` for
`lout` + `prg2lout`); the compiler invocation is gcc with `-ansi
-std=c99 -pedantic -Wall -O3`. C sources live flat in `lout/` (no
`src/`); all `.c` files share the single header `externs.h`.

The fork relative to upstream (william8000/lout):

- **`lout/z49.c` — PostScript back end. FROZEN.** Not modified by this
  fork; PDF output is therefore identical to upstream Lout fed the
  same `.lt` source. All new work is purely additive.
- **`lout/z53.c` — SVG back end.** ~5000+ LOC (7681 lines including
  the embedded PS interpreter). Mirrors `z49.c` function-for-function:
  same `back_end_rec` struct shape, same callbacks (Save, Restore,
  Translate, Rotate, Scale, Word, Graphic, Texture, ...). Defines
  `SVG_BackEnd` and `SVG_NullBackEnd`; `code = SVG`. Dispatched from
  `z01.c` when the `-G` flag (`CH_FLAG_SVG`, `externs.h:490`) is seen.
- **`lout/z53_glyph.c` — glyph outline reader.** 4528 lines. Parses
  Type 1 PFB fonts (the Lout default for URW Nimbus), CFF / OTF
  CharStrings, and TrueType `glyf` tables, then converts the outlines
  to SVG `<path d="...">` strings on demand. Also contains a GSUB
  parser used for ligature substitution (`fi`, `fl`, `ffi`, `ffl`)
  and stylistic alternates. Outlines are cached per-font, per-glyph
  in a hash table sized to the document's working set.
- **`lout/include/svgmacros` and 51 other shared library files** —
  `diagf`, `figf`, `graphf`, `tabf`, `eqf`, etc. — gain `@BackEnd
  @Case { PostScript @Yield ... SVG @Yield ... }` branches for the
  handful of constructs that differ. Grep `SVG @Yield` for the touch
  points.

The remaining 51 `z??.c` modules (lexer, parser, galley engine,
hyphenation, font service, symbol table, cross-references, ...) are
shared between both back ends and effectively untouched by this fork.

## 7. z53.c — the embedded PostScript interpreter

The central design choice in `z53.c`: rather than fork every drawing
macro in `lout/include/` to emit SVG primitives directly, the SVG back
end carries a small PostScript interpreter that **executes** the same
PS fragments Lout's standard libraries already emit, translating
drawing ops to SVG `<path>` / `<line>` / `<rect>` / `<g transform=...>`
on the fly. New drawing macros require no back-end work as long as they
stick to PS operators the interpreter already implements.

Implementation details (all in `z53.c`, see `docs/z53_internals.md` for
the full tour):

- **Hashed dictionary stack with op_id dispatch.** Operator names are
  interned at startup; `svg_ps_exec_op` dispatches on a small integer
  op_id rather than running `strcmp` against every operator. The dict
  uses open-addressing hashing.
- **Mark-and-sweep dict GC.** PS programs allocate dictionaries
  liberally (`dict`, `begin`, `end`); the interpreter walks the
  reachable set from the gstate stack on each page boundary and
  compacts the dict pool. This caps per-document memory and keeps the
  user-guide build under fixed RSS regardless of page count.
- **Arena allocator for glyph paths.** All `<path d=...>` strings for
  a single page share an arena that is freed wholesale at end-of-page.
  Avoids per-glyph `malloc/free` churn — the dominant hotspot in early
  profiles.
- **Per-font kern table precompute.** On first use of a font, the kern
  table is read once and converted to a sorted array keyed on the
  `(left_glyph << 16) | right_glyph` digram; lookups are then
  branch-prediction-friendly binary searches.
- **Ligature digram folding.** During text emission the interpreter
  scans the glyph stream for adjacent pairs (`f`,`i`), (`f`,`l`),
  (`f`,`f`,`i`), (`f`,`f`,`l`) and substitutes the corresponding
  ligature glyph if the active font's GSUB table provides one. The
  precomputed digram table makes this an O(n) pass.

`SVG_WARN_MAX` (`z53.c:4285+`) caps the per-build count of "unknown
PostScript operator" warnings so the stderr stream stays usable.

## 8. Test infrastructure

`tests/` is a regression-comparison framework rather than a unit-test
suite for `mdlout.py`. Components:

- **`tests/snippets/*.lt` — 85 snippets** covering text/typography,
  lists, tables, equations, diagrams (the full `@Diag` arrowstyle
  gallery), figures, graphs, footnotes, cross-references, mermaid
  flowcharts, raw PostScript, ligatures, small caps, oldstyle figures,
  page rules, multi-column, and so on. Each snippet is a single
  feature, single page.
- **`tests/run_all.sh`** runs every snippet through both back ends
  (Lout → PS → PNG via Ghostscript at 150 dpi; Lout → SVG → PNG via
  Chromium headless at the same dpi) and diffs the rendered PNGs with
  ImageMagick `compare -metric AE` plus a `scikit-image` SSIM pass
  (`tests/compare.py`). Produces `tests/report.html`, a side-by-side
  gallery with pass/fail per snippet.
- **`tests/user_guide_diff.sh`** exercises the full 327-page Lout user
  guide through both back ends at **100, 150, and 200 dpi**, producing
  per-page SSIM scores and a HTML gallery
  (`tests/user_guide_diff/README.md`). The current measured agreement
  is mean SSIM 0.9218, median 0.9254, 322/327 pages at >= 0.85.
- **`tests/lout_doc_renders/`** mirrors that comparison against the
  **four built-in Lout documents**: `user.pdf`, `expert.pdf`,
  `design.pdf`, `slides.pdf`. These are larger and exercise corner
  cases the user guide alone does not.
- **`tests/browser_test.py` — headless Chrome runner.** Loads each
  built HTML page in Chromium and verifies: mermaid diagrams rendered
  to SVG; KaTeX rendered all math spans; abcjs rendered every
  `.abc-music` div; in-page anchors resolve; highlight.js coloured
  every fenced code block. Optional flags: `--with-a11y` (runs
  axe-core or pa11y, with a structural fallback), `--with-print`
  (renders the print stylesheet), `--with-dark` (forces
  `prefers-color-scheme: dark`).
- **`tests/bench.py` + `tests/bench.html`** — wall-clock benchmark
  harness. Runs a fixed corpus through the full pipeline, records
  per-stage timings to `tests/bench.jsonl`, and renders an HTML
  dashboard with sparklines so regressions show up as a visible
  bend in the curve. Companion `tests/history.py` archives across
  commits.

## 9. Releases + packaging

- **`pyproject.toml`** declares `mdlout` at version **0.2.7**, GPLv3,
  Python >= 3.10, no runtime dependencies. Optional extra
  `[font-subset]` pulls fontTools for path/subset features.
- **`dist/`** contains the built wheels and sdists for 0.2.5, 0.2.6,
  and 0.2.7 (`mdlout-0.2.7-py3-none-any.whl`,
  `mdlout-0.2.7.tar.gz`).
- **`.github/workflows/`** stages three pipelines, all gated on a
  manual or tag-driven trigger until the user-guide diff stabilises:
  - `ci.yml` — push/PR: lint + snippet diffs + browser tests on
    Ubuntu, Python 3.10/3.11/3.12.
  - `user-guide-diff.yml` — nightly: full 327-page user-guide diff at
    150 dpi, posts SSIM aggregate stats and the gallery as a PR
    comment when run on a PR branch.
  - `publish.yml` — tag-driven: builds the wheel + sdist, runs
    `twine check`, uploads to PyPI on `v*` tags. Currently staged
    (not yet enabled in production).

See [`docs/PERFORMANCE.md`](PERFORMANCE.md) for current build-time
numbers and [`docs/best_practices.md`](best_practices.md) for
authoring guidance.

## 10. Key design decisions (recap)

**The PostScript back end is frozen.** `lout/z49.c` is not modified.
PDF output is identical to upstream Lout fed the same `.lt` source.
All new work is purely additive: `z53.c`, `z53_glyph.c`, `svgmacros`,
and `@BackEnd @Case` branches in library files.

**The SVG back end embeds a PostScript interpreter.** ~4500 LOC of
`z53.c` is the interpreter itself. The alternative — forking every
drawing macro to emit SVG directly — would have meant a per-macro
divergence with no upper bound. Instead, the back end executes the
same PS fragments Lout's libraries already emit and converts them in
flight.

**Math, music, and mermaid are rendered client-side.** Lout has no
built-in handler for LaTeX-syntax math, ABC music, or mermaid
diagrams. The HTML path emits `<foreignObject>` containers with the
source text; KaTeX / abcjs / mermaid render them in the browser. The
PDF path falls back to a plain rendering (`@Eq` where possible for
math; placeholders for music and mermaid).

**Font embedding matches Ghostscript's substitutes.** When Ghostscript
rasterises one of Lout's base-14 PostScript fonts to PDF, it actually
draws URW++ Nimbus outlines. The HTML scaffold inlines the same Nimbus
fonts as **subsetted** base64 `@font-face` web fonts, mapped to the
family names the SVG actually references. Without this, the browser
picks an arbitrary fallback face and line layout drifts.

**`--text-as-paths` is opt-in.** The most pixel-faithful HTML output
rewrites every `<text>` element as a `<path>` outline using fontTools,
eliminating the browser's text rasteriser entirely. Off by default
because files are substantially larger and fontTools is not required
for normal use.

## 11. Known limits

- **Pixel-identical agreement between PostScript and SVG is not
  reachable.** Anti-aliasing across two different rasterisers
  (Ghostscript vs. a browser's SVG engine) produces irreducible
  noise. The metric that matters is perceptual similarity; the
  user-guide-wide mean is SSIM 0.92.
- **Some `@Graphic` content uses uncommon PS operators not yet
  implemented in `z53.c`.** When this happens the interpreter logs
  `lout (SVG): unknown PostScript operator '<name>'` to stderr (capped
  at `SVG_WARN_MAX`) and skips the op. The visible effect is that one
  drawing element is omitted; the rest of the page still renders.
- **`@Math`, `@ABC`, and mermaid are browser-only in HTML mode.** With
  JavaScript disabled, the page shows the raw source text inside the
  `<foreignObject>`.
- **`--serve` does not support PDF.** It overrides to HTML and warns.
- **mdlout has no unit-test suite for the Python converter itself.**
  Verification is by running it on the example markdown files (and
  the snippet / user-guide diffs in `tests/`) and inspecting the
  output.

## 12. How to extend

- **Add a Markdown feature.** Edit `mdlout.py` only. Add a `BlockType`
  if needed, extend `parse_markdown` (phase b) or `convert_inline`
  (phase c), and map it in `generate_lout` (phase d). Add an example
  under `examples/` and a snippet under `tests/snippets/`.
- **Add a missing PostScript operator to the SVG back end.** Edit
  `lout/z53.c`, specifically `svg_ps_exec_op` for built-in ops; the
  function dispatches on op_id. Rebuild with `cd lout && make lout`.
- **Add or tweak a Lout-side construct.** Edit files under
  `lout/include/`. Gate per-back-end output with `@BackEnd @Case {
  PostScript @Yield ... SVG @Yield ... }`.
- **Add a frontmatter key.** Edit `parse_frontmatter` (phase a) and
  the preamble generator (phase d) in `mdlout.py`.

When in doubt, run the change through `examples/08_kitchen_sink.md`
in both `--format html` and `--format pdf` modes and compare.

## 13. Where things live

- `README.md` — quickstart, CLI summary, frontmatter reference.
- `CLAUDE.md` — engineering notes (this repository's working memory
  for Claude Code sessions; also useful as a developer crib sheet).
- `TODO.md`, `ROADMAP.md`, `CHANGELOG.md` — current work, future
  plans, release history.
- `docs/tutorial.md` — first-time-user walkthrough.
- `docs/cookbook.md` — recipe-style examples.
- `docs/best_practices.md` — recommended authoring conventions.
- `docs/PERFORMANCE.md` — build-time numbers and bench workflow.
- `docs/z53_internals.md` — SVG back-end internals deep dive.
- `docs/CI.md`, `docs/PYPI.md` — pipeline and publishing notes.
- `docs/RELEASE_NOTES_v0.2.*.md` — per-release notes.
- `lout/SVG_PORTING.md` — the porting plan from `z49.c` to `z53.c`.
- `lout/SVG_PERFORMANCE.md` — read-only profiling audit of `z53.c`.
- `lout/NEXT_OPTIMIZATIONS.md` — ranked list of remaining SVG
  back-end performance wins.
- `tests/README.md` — how the regression framework works.
- `tests/user_guide_diff/README.md` — SSIM aggregate stats on the
  327-page Lout user guide.
- `examples/README.md` — what each example file demonstrates.
- `lout/README` — upstream Lout README (Kingston's original).
