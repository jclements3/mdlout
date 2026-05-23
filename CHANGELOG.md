# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project loosely tracks [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries cover both this repository (the mdlout converter and its docs) and
the `lout/` submodule (branch `svg-backend` on the jclements3/lout fork).
Submodule-only changes are tagged `[lout]`.

## [Unreleased]

Post-v0.2.0 maintenance: CI, packaging, perf instrumentation, more
examples, and a follow-on round of SVG back-end fixes. User's Guide
diff aggregate ticked from mean SSIM 0.9230 to 0.9234 (36 -> 38 pages
in the OK bucket); snippet corpus expanded to 63 with strictly tighter
graphics-heavy thresholds (now 2% AE / SSIM 0.95, was 20% / 0.75).

### Added

- **CI: GitHub Actions workflows.** `.github/workflows/ci.yml` builds
  lout and runs the snippet regression suite on every push / PR.
  `.github/workflows/user-guide-diff.yml` runs the 327-page PS-vs-SVG
  diff weekly (Mondays 06:00 UTC) and uploads the per-page manifest +
  worst-NN PNGs as artefacts. Actions pinned to current majors
  (checkout@v4, setup-python@v5, cache@v4, upload-artifact@v4)
  (1aabc68, 213d112, 53164c7, dc1be74).
- **`docs/CI.md`**: covers what each workflow does, the
  `gh auth refresh -s workflow` OAuth-scope dance required to push
  workflow files, local reproduction (act, plain bash), and the
  submodule init dependency (3f4d8af).
- **Packaging: `pyproject.toml`** (PEP 621, setuptools backend, single-
  module layout) exposing `mdlout` as a console_script entry point.
  Builds a clean sdist + wheel via `python -m build`; pip install
  registers the `mdlout` command and resolves `--version` to `0.2.0`.
  `.gitignore` picks up `dist/`, `build/`, `*.egg-info/` artefacts
  (1c63a39, 06bff7e).
- **`tests/bench.py` microbenchmark suite.** Per-snippet timing of
  four pipeline stages (PS build, SVG build, ps2pdf, rsvg-convert) at
  median-of-3; one JSON record per run appended to `tests/bench.jsonl`.
  Regression detection compares against median of last 5 runs, prints
  `WARNING` at >1.5x baseline, exits non-zero with `--strict`.
  `tests/run_all.sh` gains an optional `--bench` flag (default off).
  `tests/bench.html` is a dependency-free 30-run stacked-bar +
  sortable per-snippet line chart. Baseline (63 snippets): PS+SVG
  total ~21 s, ps2pdf ~33 s, rsvg ~45 s; full run ~5 min on the
  reference host (6444b6b).
- **`tests/compare.py --bisect <snippet>`**: binary-search over a
  failing snippet's body lines to localize the smallest contiguous
  range that still reproduces the FAIL verdict, rendering each
  candidate through the same PS+SVG pipeline as `run_compare.sh`
  (1dd327d).
- **`tests/snippet_history.html` + history viewer.** `history.py`
  now appends one JSON record per snippet to
  `tests/snippet_history.jsonl` (63 records per clean run); the new
  vanilla-JS viewer has a sidebar list of all snippets and inline-SVG
  charts of AE diff_ratio and SSIM over time (1dd327d).
- **`examples/exam.md`**: a five-question calculus midterm with
  blank workspace via the `//Nc` vlist-separator idiom and a separate
  Answer Key section. Builds clean to PDF (3 pages) and HTML
  (6 pages); uses prose math throughout so both back-ends stay in
  sync (38b66f8).
- **Five new cookbook recipes in `docs/cookbook.md`**: CV, conference
  handout, exam paper, scientific report with bibliography, and
  recipe page. Each carries motivation, source skeleton, rendered-
  result note, and a real-build gotcha (38b66f8, 3c50271).
- **`docs/RELEASE_NOTES_v0.2.0.md`**: manual release-create
  instructions plus the publish-after-rollback path for the v0.2.0
  tag (f86faca, b6a42f9).
- **`tests/user_guide_diff/diag_gallery.html`** + 40 per-page
  thumbnails + 10 worst-NN panels for the @Diag chapter
  (User's Guide pages 190-229). Mean AE 6.93%, mean SSIM 0.9248;
  worst page p221 at SSIM 0.8820 (e9664ff).
- **Snippet `tests/snippets/graphic_rotated_show.lt`**: 12 rotated
  `(label)` strings around a circle perimeter via the PS-prologue
  rotated-show path; SSIM 0.9927, Pass-Excellent (61471c6).
- **[lout] Real Type 1 glyph outlines for `charpath`** via the new
  `z53_glyph.c` module. Lazily loads URW++ / gsfonts `.pfb` files
  for the Adobe base-35 PS names, unwraps PFB segments, decrypts the
  eexec body (key 55665, lenIV 4) and per-charstring blobs (key 4330,
  lenIV from `/lenIV`), and runs a Type 1 charstring interpreter
  covering hsbw / sbw, the rmoveto family, rlineto / hlineto /
  vlineto, rrcurveto, vhcurveto / hvcurveto, closepath, callsubr /
  return, endchar, seac, div, callothersubr / pop, and the flex
  group. Subrs cap 4096; glyphs cap 1024; Adobe StandardEncoding
  honoured by `seac`. Per-glyph outlines cached in a per-font arena.
  Search path: `$LOUT_T1_FONT_DIR`, then
  `/usr/share/fonts/type1/{gsfonts,urw-fonts}/`, then the Ghostscript
  `Resource/Font/` tree. Missing fonts / glyphs fall back to the
  original 0.5 em x 1.0 em bbox rectangle so `coltex`'s
  `charpath flattenpath pathbbox` callers still see a plausible
  bbox (lout 78244cc -> mdlout 6d2a529).
- **[lout] Rotated-show fix in `svg_ps_show`** (~22 LOC):
  propagates the path-delta rotation into a SVG `rotate()`
  transform on the emitted text wrapper, restoring correct
  orientation for the `translate N rotate moveto show` PS idiom.
  Drives `ldiagshowtags` in `diagf.lpg` (User's Guide page 207
  compass-point label demo) and any `@Diag` link-label using
  `linklabelangle`. Document audit lives in `SVG_PORTING.md`
  (lout 78244cc / a0a5c28 -> mdlout 61471c6).

### Changed

- **Snippet thresholds tightened.** The graphics-heavy tier moves
  from 20% AE / SSIM 0.75 to 2% AE / SSIM 0.95. With the embedded PS
  interpreter and Symbol-font glyph table both in tree, the worst
  graphics-heavy snippet (`colour_mixed`) clears 0.49% AE / SSIM
  0.9926. New bar leaves ~1.5% / ~0.04 of margin to absorb CI
  jitter; suite stays 63/63 Pass-Excellent (9384168).
- **User's Guide diff baseline rebuilt** for lout a0a5c28
  (real Type 1 charpath + rotated-show fix). Aggregate moves from
  36 OK / 291 DIFF / mean SSIM 0.9230 to 38 OK / 289 DIFF / mean
  SSIM 0.9234 (e9664ff).
- **`examples/out/index.html` + `examples/README.md`** regenerated
  to include the new exam example and the regrouped recipe sections
  in `docs/cookbook.md` (38b66f8, 3c50271).

### Fixed

- **`tests/user_guide_diff.sh` no longer silently dies under
  `set -euo pipefail`.** Two compounding hazards: `compare -metric
  AE` exits non-zero on any visual difference (i.e. every page),
  and `identify -format "%w %h"` emits no trailing newline so
  `read w h` returns 1 even though both variables are populated.
  The per-page loop used to abort after writing only the header
  line of `manifest.txt`; now `compare` is wrapped with `|| true`
  and the `read` is also guarded. A clean run produces a fully
  populated 328-line manifest (header + 327 pages) without manual
  intervention (ff27bc3, 1e9900d).
- **[lout] Always-on `stroke-linecap` / `stroke-linejoin` /
  `stroke-miterlimit` emission** introduced by the a3e9d04
  line-style port was perturbing rsvg's edge antialiasing on
  the User's Guide page 308 swatch grid. `svg_ps_emit_path` now
  emits these attributes only when the gstate value differs from
  the SVG default (butt / miter / 4), restoring the pre-a3e9d04
  shape of the output for paths that never touched
  `setlinecap` / `setlinejoin` (lout 999168f -> mdlout f33d25a).
- **[lout] Lout tag-name leaks** surfacing as
  `<!-- z53.c: unimplemented PostScript op 'A1' -->` XML comments
  in `diag_arrowstyle_gallery.svg`. `svg_ps_exec_value` now
  silently drops unknown names matching Lout's tag-identifier
  shape (uppercase ASCII + digits, starts with a letter); these
  arrive through `@Diag` / `@Fig` macro expansion, not from any
  `@Graphic` prologue, so the PS interpreter has nothing to bind
  them to. Output goes from 7 visible XML comments + a "suppressed"
  tail to 0; the per-snippet `.svg.err` is now empty
  (lout 999168f -> mdlout f33d25a).

### Tests

- Snippet corpus expanded 62 -> 63 (adds
  `graphic_rotated_show.lt`).
- Snippet history viewer (`tests/snippet_history.html`) +
  per-snippet bisect (`compare.py --bisect`).
- Microbenchmark suite (`tests/bench.py` +
  `tests/bench.jsonl` + `tests/bench.html`) with a 1.5x baseline
  regression alert.
- @Diag chapter gallery (`tests/user_guide_diff/diag_gallery.html`,
  40 thumbnails + 10 worst panels).
- User's Guide PS-vs-SVG diff now reproducible end-to-end under
  `set -euo pipefail` after the two shell-loop fixes.

### Docs

- `docs/CI.md`: GitHub Actions workflow overview + OAuth-scope dance.
- `docs/cookbook.md`: 5 new task-oriented recipes
  (CV / conference handout / exam paper / scientific report with
  bibliography / recipe page); `examples/README.md` regrouped by
  category to match.
- `docs/RELEASE_NOTES_v0.2.0.md`: manual release-create instructions,
  publish-after-rollback path for the v0.2.0 tag.
- `docs/chapter3_pagination_drift_investigation.md`: walks
  PS-vs-SVG at the Lout-coordinate level (not the rasterised pixel
  level) and finds every line and word emitted on identical
  `(x, y)`. The apparent 2.25 pt body offset traces to comparing
  a stale May-20 PS snapshot against the fresh May-22 SVG; after
  a fresh PS rebuild the coordinates match bit-for-bit. Conclusion:
  the chapter-3 worst-10 panels are antialiasing-only artefacts
  of the rsvg vs Ghostscript font pipeline (685fb95).
- `[lout] SVG_PORTING.md` updated with the "Rotated show inside
  @Graphic (fixed 2026-05-22)" subsection and the broader
  @Fig / @Diag audit, plus the SVG-tracker refresh for hash-op-
  dispatch + glyph-gap audit (lout a0a5c28, 2ff1b24).

### Packaging

- `pyproject.toml` for pip-installable mdlout (PyPI publish is
  manual via `python3 -m twine upload`, deferred until v0.3 per
  `ROADMAP.md`).

## [0.2.0] - 2026-05-22

The "HTML by default" release. Lands the SVG back end, the embedded
PostScript interpreter inside it, the new passthrough macros, an HTML
output path with accessibility scaffolding, a 62-snippet regression
corpus, a 327-page per-page User's Guide diff, and a headless-Chrome
runner that verifies the HTML actually renders client-side.

### Added

- **[lout] SVG back end (`lout/z53.c`, ~5400 LOC).** Sibling to `z49.c`
  (PostScript, now FROZEN), peer implementation of the full `BACK_END`
  interface from `externs.h`, selected by `lout -G`. Reuses Lout's
  galley engine, font metrics, and colour service; only the emission
  layer differs (53b9a9a).
- **[lout] Embedded PostScript interpreter inside `z53.c`** for the PS
  fragments Lout's `@Graphic` emits. Operand stack, dict stack,
  mark-and-sweep dict GC, hashed dictionary lookup, op_id dispatch by
  hash, control-flow operators (611dcb2, 24d76b4, 2a33e3d).
- **[lout] svgmacros library (`lout/include/svgmacros`)**: the
  `@Math`, `@DMath`, `@ABC`, `@SVG`, and `@SVGFile` passthrough macros,
  with PostScript-mode fallbacks so legacy documents still build
  (53b9a9a, 2a33e3d).
- **[lout] All 8 Lout texture patterns** implemented as SVG
  `<pattern>` defs (f423e35).
- **[lout] SVG-friendly `graphf` markers and `tabf` rules** inlined
  where the PS-interpreter route loses fidelity (52441b9).
- **HTML output as mdlout's default format.** `--format=html` is
  implicit; the legacy PostScript-to-PDF path moves behind
  `--format=pdf` (bdb260a, 0872f62).
- **URW++ Nimbus base-35 fonts** embedded as `@font-face` data-URLs in
  the HTML wrapper so the browser matches Ghostscript's font
  substitution on screen (0ddad2b).
- **WCAG 2.1 AA accessibility scaffold** in the HTML output: semantic
  landmarks (`<header>`, `<main>`, `<nav>`, `<aside>`), ARIA roles,
  image-alt manifest projected as a hidden `<figure role="img">`
  sidecar, skip-link, focus rings, and `<html lang>`. Opt-out via
  `--no-a11y` for diff tooling (2918706).
- **KaTeX + abcjsharp inline integration** in the HTML wrapper, with
  CDN fallback and `--external-assets` to force CDN; abcjsharp is
  sourced from the user's `~/projects/abcjsharp` fork when present
  (bdb260a).
- **highlight.js syntax highlighting** for fenced code blocks (via
  CDN), with `--no-highlight` to disable (4ef5182).
- **mdlout CLI surface** (final shape for v0.2.0): `--format`,
  `--watch`, `--serve [PORT]`, `--inline-raster`, `--text-as-paths`,
  `--no-math-engine`, `--no-music-engine`, `--no-font-embedding`,
  `--no-highlight`, `--no-a11y`, `--external-assets`, `--lout-only`,
  `--ps`, `--mydefs`, `--lout-bin`, `--lout-args`, plus the new
  ergonomic flags `--check` (parse-only validation, exits non-zero on
  failure with a `path:line:col` diagnostic), `--init [DIR]` (scaffold
  a fresh project with `index.md`, `mydefs`, `.gitignore`, and
  `README.md`), and `--version` (476e7b6).
- **Print-mode CSS in the HTML scaffold**: `@media print` rules map
  each `<svg class="lout-page">` onto its own physical sheet via
  `@page size` + margin and `page-break-before: always`, hide non-
  content chrome (skip link, TOC nav, footnote aside, banner), so
  Chrome `--print-to-pdf` matches the legacy PDF route page-for-page
  (3c98006).
- **`--inline-raster`** (also `inline-raster: true` in frontmatter):
  base64-inlines local `<image href>` raster files
  (png/jpg/jpeg/gif/webp) into the lout-emitted SVG so the served
  HTML is fully self-contained (3c98006).
- **`--serve` error overlay**: rebuild failures now drape a red
  panel over the last-known-good render with a Retry button (POST
  `/rebuild`) and Dismiss control; captured lout/python stderr lives
  in the overlay body (3c98006).
- **[lout] Adobe Symbol glyph table** (~150 names → Unicode) in
  `z53.c`'s `svg_glyph_table`, covering Greek upper/lower case + Symbol-
  font variants, mathematical operators at U+2200..U+22FF, set/logic,
  arrows at U+2190..U+21FF, multi-piece fences at U+239B..U+23AE,
  card suits, and miscellaneous trademark / copyright glyphs
  (ec987be).
- **[lout] `setlinecap` / `setlinejoin` / `setmiterlimit`** in the SVG-
  mode PS interpreter: per-attribute setters flow through to `<path
  stroke-linecap/-linejoin/-miterlimit>` instead of the previous
  hard-coded butt+miter on every stroke. Adds `currentlinewidth` plus
  the `linewidth` / `save` / `restore` aliases used by `@Graph` and
  the PS VM save/restore convention. Unknown ops surface as rate-
  limited XML comments in the SVG so the gap is visible in the file,
  not just stderr (a3e9d04, e57a92b).
- **`tests/snippets` corpus expanded 53 → 62 snippets**: Greek-letter
  gallery (`sym_greek_full.lt`), `@Eq` continued fraction / matrices
  (3x3, 4x4) / braced systems / integral+summation,
  `@Diag arrowstyle` gallery, `@Graph` with negative + log axes,
  spanned-column `@Tab`, and `@PageOf` forward cross-reference, plus
  a `tests/snippets/README.md` chapter index mapping each `.lt` to
  the User's Guide section it exercises (91d039b).
- **Three new examples**: `technical_manual.md` (1255-line software
  manual with `@Section` chapters, Python/C/shell listings, pipe
  tables, footnotes, cross-refs, and admonitions), `academic_poster.md`
  (single landscape A0 page with 3-column layout, equations, and a
  small bibliography), and `magazine_layout.md` (two-column article
  with mixed images, pull quotes, and sidebar admonitions); each
  builds in both `--format=html` and `--format=pdf` (0395896).
- **Gallery sort/filter** in `examples/generate_gallery.py`: per-card
  `data-type` / `data-features` / `data-pages` attributes, a
  `<nav class="gallery-filters">` block with type + feature chips, a
  sort selector (by title / page count), and a per-card "Copy
  markdown" button using `navigator.clipboard.writeText()` (0395896).
- **Live preview**: `--watch` polls mtime every 500 ms and rebuilds;
  `--serve [PORT]` (default 8080) is `--watch` plus a stdlib
  `ThreadingHTTPServer` with a Server-Sent-Events `/events` stream
  and an injected reload script (bdb260a).
- **Pandoc-style citations, auto figure/table numbering, and an
  `abstract:` frontmatter field** (0988285).
- **CommonMark indented code blocks** in the markdown parser (90c6b99).
- **TOC and footnote support** finalised, plus math-newline
  normalisation, table-alignment markers, and the highlight.js hook
  (4ef5182).
- **`examples/` corpus**: the eight numbered `01_*..08_*` tour files
  plus `scientific_paper.md`, `complex_diag.md`, `slides_basic.md`,
  `letter.md`, `cv.md`, `book_chapter.md`, `diag_gallery.md`,
  `academic_poster.md`, `technical_manual.md`, and a sortable /
  filterable gallery (`examples/generate_gallery.py`) plus per-example
  preview landing pages.
- **`tests/snippets/`**: 53-snippet single-feature regression corpus
  (started in bdb260a, expanded in 7425f1c).
- **`tests/user_guide_diff/`**: 327-page per-page PS-vs-SVG diff with
  SSIM scoring and a worst-pages report (bfbc1e1, 6ed661d, a6accc8).
- **`tests/browser_test.{py,sh}`**: headless-Chrome runner that loads
  each example HTML and verifies KaTeX, abcjs, anchors, and
  highlight.js execute client-side. `--with-a11y` adds an axe-core
  audit; `--with-print` exercises print CSS; `--with-dark` checks
  prefers-color-scheme: dark (cf40b28, 49ecdc2).
- **`tests/chromium_diff.sh`**: Chromium-headless variant of the
  user-guide diff for the worst-case and evenly-spread page subsets
  (e61148e).
- **`tests/history.py` + `tests/history.html`**: regression-history
  tracker, now a 5-panel dashboard (7425f1c, a901eff).
- **Docs**: `docs/ARCHITECTURE.md` (e626b0b), `docs/CONTRIBUTING.md`
  + `docs/build_notes.md` + the first cut of this `CHANGELOG.md`
  (a7ebae2), `docs/tutorial.md` (34514fb),
  `docs/best_practices.md` (939f8b6), `docs/z53_internals.md`
  contributor-facing PS-interpreter deep-dive (2da8c93).

### Changed

- **Default output format from PDF to HTML.** `mdlout input.md` now
  produces `input.html`; PDF requires `--format=pdf` (bdb260a).
- **`@Math` rendering**: uses direct `katex.render()` per node
  instead of the auto-render delimiter scan, fixing math bodies that
  carry no delimiters (7f14a50).
- **Display math** (`MATH_BLOCK`) now emits `@DMath`, which carries
  the `math-display` class so KaTeX picks `displayMode: true`
  (2a33e3d).
- **`@DocInfo` in SVG mode** now emits nothing instead of a stray
  pdfmark fragment (63c247a).
- **HTML scaffold banner**: the hidden doc-title `<p class="mdlout-
  doc-title">` was promoted to `<h1>` so axe-core's `page-has-
  heading-one` rule passes for documents whose first markdown heading
  is `##` or `@Section` (`type: report` / `book`). Visually-hidden
  CSS unchanged (d1d7e2e).

### Fixed

- **[lout] `eq` / `ne` comparing NUM and BOOL as equal** in the SVG-mode
  PS interpreter (broke `@Graph` axis drawing); tightened to require
  same-kind operands (3e26007).
- **[lout] Dict-pool leak via tag-dicts** that dropped thin connector
  strokes; fixed by mark-and-sweep dict GC (611dcb2).
- **[lout] `@Graph` plot-symbol stroke width** was 5-25pt; now hairline
  (e34f24e, f3393d6).
- **21-page bibliography / references / index gap** between PS and SVG
  renders, traced to the `SVG_NullBackEnd` non-final-pass stubs
  borrowing side-effects from `SVG_BackEnd`; fixed with dedicated
  no-ops (49398d3).
- **[lout] `LoutSetTexture` / `LoutMakeTexture` stack drift**: now
  consume their operands per PS semantics (e7a4735).
- **[lout] `filledsquare` and other 20-strcmp op-dispatch chains**
  hoisted via a first-character switch (95e16de).
- **[lout] Arc emission spurious lineto** affecting tangent
  decorations inside circles (covered under 53b9a9a / later patches).
- **[lout] `svg_tex_identify` hardened against custom paintprocs**
  (7c58caf).
- **[lout] `@DocInfo` pdfmark leak in SVG mode** (455c485 / 63c247a).
- **mdlout placeholder leak** in the inline conversion pipeline that
  could surface raw ` P0 ` tokens (90c6b99).
- **KaTeX rendering of delimiter-less `<span class="math">` bodies**,
  surfaced by the new headless-Chrome runner (7f14a50).
- **[lout] `filledsquare` / `filledcircle` / etc. dispatch** in
  `svg_ps_exec_symbol`: previously the routine stripped the `do`
  prefix but not the optional `filled` prefix, so plot symbols
  vanished from User's Guide pages 248 and 262 (SSIM 0.7485 → 0.9280
  and 0.8214 → 0.9027 after the fix) (ec987be, c60ed3f).
- **`tests/browser_test.py` anchor + hljs heuristics**: the anchor
  regex now requires a leading letter (HTML4/5) and scrubs
  `<script>` bodies and HTML entities before scanning, so
  `&#x27;` and JSON-escaped `href="\"#x\""` strings no longer leak
  phantom anchor names; the hljs check restricts the denominator to
  languages highlight.js ships by default and treats `class="hljs"`
  / `data-highlighted="yes"` as "ran" even when there's nothing to
  tokenise. Suite goes 36/37 → 37/37 (2ae2d39).

### Performance

- **User's Guide SVG build**: roughly 7 min -> 36 s -> 32 s wall time
  across the cycle. Contributing factors: `setvbuf` on output streams,
  hash-table dict lookup (~2.3x on its own at the dict-lookup site;
  dd42ff5), `@Graphic` token memoisation, `filledsquare` first-char
  hoist (95e16de / 9ddc198), and hashed `svg_ps_exec_op` dispatch
  giving ~58% on the last step (2a33e3d).
- **User's Guide page count**: SVG converges to 327 pages, matching
  PS exactly (1d927fe, 6ed661d). After the Symbol glyph table and
  filledsquare dispatch fix, mean SSIM 0.9230, median 0.9255, min
  SSIM 0.8354 (was 0.7485 on p248); 324 / 327 pages at SSIM >= 0.85,
  no remaining SVG-specific page bugs in the worst-10 (c60ed3f).

### Tests

- 62-snippet regression suite: 0 Fail, 100% Pass-Excellent on the
  agreed thresholds (5% pixel diff for text snippets, 20% for
  graphics-heavy).
- Per-page User's Guide diff: 36 OK / 291 DIFF / 0 BAD / 0 MISSING
  out of 327 pages; mean SSIM 0.9230, 324 / 327 at SSIM >= 0.85.
- Headless Chrome browser-test runner: 37 / 37 examples pass on the
  default checks (loaded, katex, abcjs, anchors, hljs) after the
  anchor + hljs heuristic hardening; `--with-all` (axe-core, print
  CSS, dark mode) likewise green.

### Docs

- `README.md` rewritten around the HTML-first default, with a
  Quickstart that points at `docs/tutorial.md`.
- `docs/best_practices.md` (484 lines, 11 sections): copy-pasteable
  recipes for research papers, books, slides, letters, and CVs, plus
  math / music / diagram / citation embedding and debugging tips.
- `docs/tutorial.md`: clone-to-built-document walkthrough.
- `docs/ARCHITECTURE.md`: project architecture and design overview.
- `docs/CONTRIBUTING.md` and `docs/build_notes.md`.
- `docs/z53_internals.md`: contributor-facing PS-interpreter deep
  dive.
- `[lout] SVG_PERFORMANCE.md` (gprof hotspot report) and
  `NEXT_OPTIMIZATIONS.md` (ranked quick wins after dict-hash) inside
  the submodule.
- TODO.md restructured with per-session status blocks; `.gitignore`
  refreshed for new build artefacts.

## [0.1.0] - 2026-03-16

### Added

- Initial commit: `mdlout.py` Markdown-to-Lout-to-PDF converter, plus
  a vendored copy of Lout 3.43 (the william8000 fork) as a submodule.
- Supported Markdown: H1-H6 (ATX and setext), bold / italic / inline
  code / strikethrough / superscript, links (as footnotes), images,
  bullet / numbered / task / definition lists, blockquotes, fenced
  code, pipe and grid tables, horizontal rules, math blocks (`$$` or
  ```` ```math ````), admonitions, page breaks, `[TOC]` placeholders,
  HTML entities, and backslash escapes.
- YAML frontmatter mapped to Lout `@BasicSetup` / `@DocumentSetup`
  clauses; `type: doc | report | book | slides`.
- `mydefs` convention: a file next to the input is copied into the
  build directory and picked up by `@Include { mydefs }`.
- Raw Lout passthrough via ```` ```lout ```` fenced code blocks.

## Upstream Lout history (for context)

The submodule's pre-fork history (Lout 2.03 through 3.43) is not
reproduced here; see `lout/whatsnew` inside the submodule for
upstream release notes by Jeffrey H. Kingston and the william8000
fork contributors. Selected upstream changes pulled in via the
submodule:

- 2025-09-22: clang 20 prototype-form fixes (`void` argument lists in
  `z28.c`, `z29.c`, `z38.c`, `z48.c`).
- 2025-05-20: `SOURCE_DATE_EPOCH` support in the makefile tests.
- 2025-04-09: `SOURCE_DATE_EPOCH` support for build dates; webp image
  support; `magick` over `convert` on Linux.
- 2025-03-10: gcc 14 / clang 19 warning fixes; `make test` /
  `make testclean` added.
- 2024-01-26: lout 3.43 (the version vendored at the time of initial
  commit).

[Unreleased]: https://github.com/jclements3/mdlout/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/jclements3/mdlout/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jclements3/mdlout/releases/tag/v0.1.0
