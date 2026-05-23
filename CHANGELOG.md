# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project loosely tracks [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries cover both this repository (the mdlout converter and its docs) and
the `lout/` submodule (branch `svg-backend` on the jclements3/lout fork).
Submodule-only changes are tagged `[lout]`.

## [Unreleased]

## [0.2.2] - 2026-05-23

Sub-30 s User's Guide build, real TrueType (`.ttf`) outlines for
`charpath`, dark-mode CSS opt-in for the HTML wrapper, and end-to-end
SVG renders of all four documents that ship with the Lout source tree
(`design`, `expert`, `slides`, `user`). The perf round 2 beats the
v0.4 ROADMAP target: User's Guide single-pass wall drops ~32 s ->
~26-29 s (~31%). TrueType lifts `charpath` coverage off URW++ /
gsfonts onto DejaVu / Liberation / Noto and other system fonts.
Three deferred SVG-includes items from v0.2.1
(`LoutPageDict` / `LoutPageSet` / `LoutMargSet` / `LoutMargShift`
hashed; `@ABC` + `@Mermaid` body HTML-escaped) ship. Five new
examples and eight new cookbook recipes (lifting the count to 23).

### Added

- **mdlout: opt-in dark mode** via `--dark[=force|auto]` CLI flag and
  the `dark-mode` / `theme: dark` YAML frontmatter keys. Emits a CSS
  block that paints the page chrome dark and inverts each
  `.lout-page` via `filter: invert(1) hue-rotate(180deg)`. Embedded
  raster `<image>`s invert too (photos render with reversed
  luminance); a proper CSS-variable scheme will land once `z53.c`
  emits `fill=currentColor` for SVG text. Default off; PostScript
  output unchanged (0d3ba23).
- **mdlout: `--subset-fonts` CLI + `subset-fonts: true` frontmatter
  key.** New optional pass that subsets each of the 12 inlined URW++
  Nimbus base-35 faces down to just the codepoints the SVG actually
  references. Scans `<text>` / `<tspan>` elements for font-family
  and inner text, builds a per-family codepoint set (with a
  printable-ASCII baseline for KaTeX / abcjs runtime glyph needs),
  then runs each face through `fontTools.subset.Subsetter` before
  the existing base64 embed. fontTools is an optional dependency;
  import is lazy and warns once to stderr when missing.
  Representative example sizes: scientific_paper.md
  2,328,726 -> 1,178,063 bytes (49.4%); 06_report.md
  2,069,366 -> 877,110 bytes (57.6%); magazine_layout.md
  2,255,289 -> 1,063,053 bytes (52.9%). Font payload itself shrinks
  ~81% in each case. Default off until verified across the example
  corpus (e42b157).
- **mdlout + lout: HTML-escape `@ABC` and `@Mermaid` body text.**
  Pre-HTML-escapes both block bodies before the existing
  `_lout_string_encode` pass so a literal `&`, `<`, `>`, or `"` in
  the source no longer corrupts the surrounding `data-abc="..."`
  attribute or the `<div class="mermaid">…</div>` text node.
  abcjs / mermaid DOM-decode the attribute / textContent at render
  time, so HTML-encoded entities round-trip back to the originals
  intact. Companion `docs/best_practices.md` subsection
  "Hand-authoring @Math / @ABC / @Mermaid in raw Lout: gotchas"
  documents the three failure modes raw-`.lt` authors hit
  (HTML-active chars in @Body, Lout-active chars in @Body, literal
  LFs inside Lout `"…"` literals) (lout a9bc073 -> mdlout e2b3d26).
- **Five new examples**: `book_with_epigraphs.md` (short story with
  leading epigraphs per section + multiple footnotes),
  `math_with_diagrams.md` (math proofs interspersed with mermaid
  sequence diagrams), plus three more landing during this cycle:
  `marginalia.md`, `multilingual.md`, `mermaid.md` (all build clean
  in both `--format=html` and `--format=pdf`; outputs under
  `examples/out/`) (f98827b, 6414738).
- **Eight new cookbook recipes** in `docs/cookbook.md`, lifting the
  count from 15 to 23. Recipes 16-20 (Mermaid flowchart, marginalia
  / sidenotes via `@RightNote` / `@OuterNote`, multilingual via
  `@Char` / `@Sym` / `@Language`, footnoted poetry with
  `@LeftDisplay` vlists, `@PageOf` / `@NumberOf` / `@TitleOf` plus
  `[TOC]`) and recipes 21-23 (book chapter with epigraph +
  footnotes, two-sided letter with date / signature / postscript,
  inline diagrams via `@Mermaid` in a math-heavy doc) (f98827b).
- **`examples/PUBLISHING.md`** walkthrough for publishing
  mdlout-generated HTML to GitHub Pages: single-file output,
  `/docs`-on-main vs `gh-pages` layouts, CI-driven publish via
  `publish.yml`, custom-domain DNS cheat-sheet, accessibility
  checklist, recommended `src/` + `docs/` layout for downstream
  users (d5888a5).
- **`examples/CONTRIBUTING.md`**: per-example contribution guide
  alongside the docs-tree `CONTRIBUTING.md`; documents the example
  corpus conventions (frontmatter, builds-in-both-modes
  requirement, gallery regeneration step).
- **`.github/workflows/publish.yml`**: GH Pages deploy workflow.
  Builds `examples/` to HTML and pushes the rendered tree to the
  `gh-pages` branch. Requires the `workflow` OAuth scope to push
  (`gh auth refresh -s workflow`); local validation passes
  `yaml.safe_load` (4c39182).
- **`tests/lout_doc_renders/`**: end-to-end PS + PDF and SVG + HTML
  renders of all four documents shipping with the Lout source tree
  (`doc/design`, `doc/expert`, `doc/slides`, `doc/user`).
  `build.sh` + `diff.sh` + `aggregate.py` drives a 7-pass
  cross-reference loop per back-end, wraps each SVG in a minimal
  HTML scaffold (CDN KaTeX, mdlout-style print stylesheet), and
  emits per-doc 10-sample PS-vs-SVG galleries with scikit-image
  SSIM + ImageMagick AE %. Surfaces three z53.c-adjacent issues
  tracked separately: missing `@Case` SVG branches in
  `lout/include/`, untranslated raw PostScript in `@Graphic` blocks
  (design's algorithm-flow diagrams), per-pass output alternation
  (dc7c1fd).
- **`tests/browser_test.py --with-mermaid-strict`** structural
  check. Default-OFF flag. When enabled, each
  `<div class="mermaid">` is verified to contain a child `<svg>`
  whose `aria-roledescription` is a recognised mermaid diagram type
  (or whose class list contains a structural class like `.node`,
  `.edgePath`, `.actor`, `.classGroup`, `.flowchart`, `.cluster`).
  Parse-error markers (`aria-roledescription="error"`, "Syntax
  error" text) and missing-SVG cases fail the page. Default
  flag-set output unchanged (7721915).
- **`tests/browser_test.py` mermaid render check + tightened katex
  check.** Reports `mermaid=ok(N/M)` alongside `katex` and `abcjs`:
  counts `<div class="mermaid">` openers, counts those that contain
  a child `<svg>` (mermaid.js replaces inner source text once
  rendered), passes when at least 50% rendered. Virtual-time-budget
  bumped 20 s -> 22 s for mermaid's per-diagram render cost
  (2508ed8).
- **[lout] TrueType (`.ttf`) outline parsing via `glyf` table** in
  `z53_glyph.c`. Third format leg behind `svg_glyph_emit_outline`
  alongside Type 1 (`.pfb`) and CFF / OTF. Detection branches on
  the sfnt magic `0x00010000` (also `true`, `typ1`); the OT table
  directory walker is reused. Loader parses `head` (UnitsPerEm +
  loca format), `maxp` (numGlyphs), `cmap` (format 4 BMP +
  optional format 12 with Unicode-platform > Windows-Unicode
  tiebreak), `loca`, and `glyf`. Outline emit decodes simple
  glyphs (flag-stream repeat expansion, signed-short / signed-byte
  x/y deltas, implicit on-curve midpoints between two consecutive
  off-curves) and converts quadratic Beziers to cubics via
  `P0 + 2/3(Q-P0), P2 + 2/3(Q-P2)`. Composite glyphs recurse with a
  2x2 affine (scale / xy-scale / two-by-two-2.14-fixed),
  `ARGS_ARE_XY_VALUES` translation, depth cap 8. Aliases for
  DejaVu / Liberation / Noto live in `svg_glyph_ttf_map`;
  `LOUT_TTF_FONT_DIR` (and `LOUT_T1_FONT_DIR` as a shared
  shortcut) prepend a search directory.
  `/usr/share/fonts/truetype/` and `/usr/share/fonts/TTF/` are
  walked one level deep. Verification: "Hello" at DejaVu Sans 36 pt
  emits 32 cubic-Bezier segments + 23 line segments across 7
  contours; "Quagmire" at 48 pt emits 110 curves + 46 lines (vs
  the bbox-rectangle fallback). Type 1 PFB and CFF / OTF charpath
  paths unchanged (lout 50ebec5 -> mdlout bb146fe).
- **[lout] `z53.c` hashes `LoutPageDict` / `LoutPageSet` /
  `LoutMargSet` / `LoutMargShift`** so `bsf.lpg` / `dsf`'s
  `@Place` / `@MargPut` SVG branches no longer take the
  unknown-PostScript-operator fallthrough. Five entries added to
  `svg_op_seed[]` + `svg_ps_exec_op()`: `LoutPageDict` pushes a
  userdict stand-in (same strategy as the SYSDICT alias group) so
  `begin` / `end` balance; `LoutPageSet` is a no-op with traceability
  XML comment; `LoutMargSet` and `LoutMargShift` pop their
  parity / margin-type arguments; `matr` aliases the `matrix` op so
  `matr setmatrix` lands on a fresh identity CTM. The
  `LoutMargShift` translate(x, y) is still missing, so margin notes
  still render at the origin in SVG mode, but the stack no longer
  drifts. Companion `svgmacros` header-comment update names the
  hand-author gotchas (lout a9bc073 -> mdlout e2b3d26).
- **[lout] CFF / TrueType follow-ups in `z53_glyph.c`**: Type 2
  escape op 26 (sqrt) now performs a 16-step Newton-Raphson in
  place of the prior silent stack-clear (no libm dependency); op 33
  (setcurrentpoint) re-documented as a Type 1 leftover under the
  default branch; composite-glyph flag handling clarified
  (`WE_HAVE_INSTRUCTIONS` naturally skipped via early return on
  last component; `OVERLAP_COMPOUND` is a fill-rule hint that
  SVG's non-zero default honours); empty TTF glyph cases (zero-
  length `glyf` entry and 10-byte header with `numberOfContours ==
  0`) explicitly documented; CFF predefined charsets 1 (Expert) and
  2 (ExpertSubset) tracked as a known gap in `NEXT_OPTIMIZATIONS.md`
  (lout 6373ebb -> mdlout 2d563d9).

### Changed

- **[lout] Perf round 2 -- User's Guide single-pass wall ~32 s ->
  ~26-29 s (~31%, beats the v0.4 ROADMAP < 30 s target).** Three
  layered optimisations in `z53.c`:
  (1) `svg_glyph_to_unicode` replaces the linear scan over the
  ~380-entry `svg_glyph_table` with the same FNV-1a +
  open-addressed-linear-probing hash used by `svg_dict_lookup` and
  `svg_op_lookup`, lazily built on first call -- this was the
  largest remaining hot spot (~250 k chars on the User's Guide,
  folded into `svg_emit_word_text`'s significant share of CPU).
  Lookup drops O(N) -> ~1.2 probes/avg.
  (2) Per-font face-flag cache (`svg_face_cache`, 64-entry
  open-addressed) keyed by `FONT_NUM`: `SVG_PrintWord` fires once
  per word (~99 k times on the User's Guide); each call previously
  ran four `strstr` probes against the FontFace string to decide
  font-weight / font-style. Cache pre-renders the family attribute
  fragment.
  (3) `SVG_PrintWord` stdio consolidation: five separate
  `fprintf` / `fputs` / `fputc` calls combined into one `fprintf`
  with conditional format specifiers. Attribute order preserved so
  the SVG is byte-for-byte identical to baseline (modulo the
  embedded `@CurrentTimeAndDate` timestamp). User-time drops
  ~22 s -> ~20 s. Regression suite unchanged
  (lout f1fdd77 -> mdlout 5810261).
- **CI workflows pushed.** `.github/workflows/ci.yml` and
  `user-guide-diff.yml` (committed in v0.2.1) are now joined by
  `publish.yml` for GH Pages deploy. All three pinned to current
  action majors (e65fb09, 4c39182).

### Fixed

- **[lout] `@Place` / `@MargPut` operand-stack drift in SVG mode.**
  Without explicit ops for `LoutPageDict` / `LoutPageSet` /
  `LoutMargSet` / `LoutMargShift`, the names took the unknown-PS-op
  fallthrough, leaving the operand stack imbalanced and the
  surrounding `gsave` / `grestore` ineffective; `@Place`'d boxes
  landed at the page origin instead of (x, y). Fixed by the hashed
  op-dispatch above (lout a9bc073 -> mdlout e2b3d26).
- **mdlout + lout: HTML-active characters in `@ABC` / `@Mermaid`
  bodies** corrupting the surrounding `<foreignObject>` markup
  before the JS engines could read it. Both bodies are now
  pre-HTML-escaped (lout a9bc073 -> mdlout e2b3d26).

### Tests

- **All four Lout docs rendered through z53.c**
  (`tests/lout_doc_renders/`): `design`, `expert`, `slides`, and
  `user` now have PS + PDF + SVG + HTML outputs and per-doc
  10-sample PS-vs-SVG galleries (dc7c1fd).
- **Mermaid render check + structural `--with-mermaid-strict`**
  added to `tests/browser_test.py` (7721915, 2508ed8).
- Regression suite stays at 65 Pass-Excellent / 0 Fail through
  every commit in the cycle.

### Docs

- `examples/PUBLISHING.md`: GH Pages deploy guide (d5888a5).
- `examples/CONTRIBUTING.md`: per-example contribution guide.
- `docs/best_practices.md`: new "Hand-authoring @Math / @ABC /
  @Mermaid in raw Lout: gotchas" subsection (e2b3d26).
- `docs/cookbook.md`: recipes 16-23 (f98827b).
- `[lout] z53_glyph.c` audit comments + `NEXT_OPTIMIZATIONS.md`
  CFF Expert / ExpertSubset known-gap note (lout 6373ebb).

## [0.2.1] - 2026-05-22

Post-v0.2.0 maintenance: real font outlines (Type 1 charpath, plus
CFF/OTF Type 2 charstrings), AFM kerning in SVG text, a fourth
client-side passthrough (`@Mermaid`), 10 new cookbook recipes
(11-20), three new examples (`exam.md`, `marginalia.md`,
`multilingual.md`), an `include/` audit (`SVG_INCLUDES_AUDIT.md`),
CI, packaging, perf instrumentation, and a follow-on round of
SVG back-end fixes. User's Guide diff aggregate ticked from mean
SSIM 0.9230 to 0.9234 (36 -> 38 pages in the OK bucket); snippet
corpus expanded to 63 (then 65 with the two new Mermaid snippets)
with strictly tighter graphics-heavy thresholds (now 2% AE /
SSIM 0.95, was 20% / 0.75).

### Added

- **CI: GitHub Actions workflows.** `.github/workflows/ci.yml` builds
  lout and runs the snippet regression suite on every push / PR.
  `.github/workflows/user-guide-diff.yml` runs the 327-page PS-vs-SVG
  diff weekly (Mondays 06:00 UTC) and uploads the per-page manifest +
  worst-NN PNGs as artefacts. Actions pinned to current majors
  (checkout@v4, setup-python@v5, cache@v4, upload-artifact@v4).
  Workflows are committed but have not yet been pushed to `origin`;
  pushing requires the `workflow` OAuth scope
  (`gh auth refresh -s workflow`), tracked in `docs/CI.md`
  (1aabc68, 213d112, 53164c7, dc1be74, 1bf055c).
- **`docs/CI.md`**: covers what each workflow does, the
  `gh auth refresh -s workflow` OAuth-scope dance required to push
  workflow files, local reproduction (act, plain bash), and the
  submodule init dependency (3f4d8af).
- **Packaging: `pyproject.toml`** (PEP 621, setuptools backend, single-
  module layout) exposing `mdlout` as a console_script entry point.
  Builds a clean sdist + wheel via `python -m build`; pip install
  registers the `mdlout` command. The packaged `version` string is
  still `0.2.0` for this cycle and `mdlout.VERSION` is unchanged;
  bumping both to `0.2.1` is deferred to a follow-on commit.
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
- **`examples/marginalia.md`**: exercises `@RightNote` and
  `@OuterNote` against a widened right margin (1faa99f).
- **`examples/multilingual.md`**: exercises the post-ec987be Adobe
  Symbol glyph table plus the `@Char "eacute"` route for accented
  Latin and the `@Language { Russian }` route for Cyrillic (1faa99f).
- **Ten new cookbook recipes in `docs/cookbook.md`** (lifting the
  count from 10 to 20). First batch (11-15): CV, conference handout,
  exam paper, scientific report with bibliography, recipe page
  (38b66f8, 3c50271). Second batch (16-20): Mermaid flowcharts,
  marginalia / sidenotes via `@RightNote`/`@OuterNote`, multilingual
  documents (Latin via `@Char` / Greek via `@Sym` / Russian via
  `@Language`), footnoted poetry with `@LeftDisplay` vlists, and the
  `@PageOf`/`@NumberOf`/`@TitleOf` cross-reference idiom alongside
  `[TOC]` (1faa99f). Each recipe carries motivation, source
  skeleton, rendered-result note, and a real-build gotcha.
- **`docs/RELEASE_NOTES_v0.2.0.md`**: manual release-create
  instructions plus the publish-after-rollback path for the v0.2.0
  tag (f86faca, b6a42f9).
- **`ROADMAP.md`**: forward-looking plan for v0.3 / v0.4 / "won't
  do", split out of the existing CHANGELOG / TODO. Names the
  parallel agent items (Mermaid, CFF/OTF, AFM kerning, cookbook
  recipes 11-20) that landed during this cycle and the remaining
  manual PyPI publish step (165eeed).
- **`@Mermaid` passthrough macro for ` ```mermaid ` fenced blocks.**
  Fourth client-side passthrough alongside `@Math` (KaTeX), `@ABC`
  (abcjsharp), and `@SVG` (raw). mdlout gains `BlockType.MERMAID_BLOCK`
  + `parse_markdown` routing that Lout-escapes the body and emits
  `@Mermaid { "..." }`; `_build_html_scaffold` gains a
  `mermaid_engine` parameter that lazy-loads mermaid.js (local copy
  preferred, mermaid@10 CDN otherwise, `MDLOUT_MERMAID_URL` overrides
  the CDN). Engine only ships when at least one `mermaid` block is
  present. `--no-mermaid-engine` suppresses the injection entirely.
  PDF mode falls back to a placeholder note. Companion svgmacros
  entry wraps the body in `<foreignObject><div class="mermaid">…</div>`
  for the SVG back-end. `examples/mermaid.md` showcases flowchart /
  sequence / class diagrams; HTML + PDF outputs committed.
  `tests/snippets/mermaid_inline.lt` + `mermaid_flowchart.lt` cover
  the macro at the trivial-edge and four-node-graph scales (both
  PASS-EXCELLENT, AE-ratio < 2%, SSIM > 0.95)
  (lout d5bc449 -> mdlout 9187311).
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
- **[lout] CFF / OTF outline parsing (Type 2 charstrings) in
  `z53_glyph.c`.** Extends the Type 1 charpath path with an OTF /
  OTC container reader and a CFF Top DICT + Private DICT + CharStrings
  + GlobalSubrs / LocalSubrs decoder, then a Type 2 charstring
  interpreter sharing the same arena / cache as the Type 1 path
  (rmoveto family, rlineto / hlineto / vlineto, rrcurveto and its
  hh/vv/hv/vh/rcurveline/rlinecurve variants, hstem/vstem and hint
  ops as no-ops, callsubr / callgsubr with the standard subr biases,
  endchar, return, and the flex family). Lets `charpath` resolve
  outlines for the system's OpenType base-35 shipments (most modern
  URW++ packages are `.otf`, not `.pfb`). Missing CFF glyphs still
  fall back to the bbox rectangle (lout b021b71 -> mdlout 9ab617b).
- **[lout] AFM kern-pair emission in SVG text** via `<tspan dx>`.
  `svg_emit_word_text` now consumes `FontKernLength` between
  successive characters and emits the kern delta as a `<tspan dx>`
  inside the `<text>` element, bringing SVG word spacing into line
  with the PostScript back-end's glyph metrics. Most visible on
  proper-noun heavy paragraphs where AV / To / Wa / Ya pairs were
  noticeably loose (lout fc94e3c -> mdlout 2c4c498).
- **[lout] `SVG_INCLUDES_AUDIT.md`** in the submodule: walks every
  `@BackEnd @Case` block in `lout/include/*` and records how each
  arm treats the SVG back-end. Findings: zero PostScript-only blocks
  without an SVG or else fallback (automated brace-balanced scan);
  the PS-side helpers in `bsf` (`LoutPageSet` / `LoutMargShift` /
  `LoutPageDict`) are not yet hashed by `z53.c`, so `@Place` and
  `@MargPut` silently drop in SVG mode (deferred). Fixes the
  `svgmacros` `@SVGFile` doc-comment that named the wrong include
  primitive (lout 6a2dac2 -> mdlout 2094ada).
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
  to include the new exam / marginalia / multilingual / mermaid
  examples and the regrouped recipe sections in `docs/cookbook.md`
  (38b66f8, 3c50271, 1faa99f, 9187311).
- **`CLAUDE.md` "Math, music, raw SVG" section** updated for the
  new `@Mermaid` routing and engine-loading semantics (9187311).

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
  `graphic_rotated_show.lt`), then 63 -> 65 with
  `mermaid_inline.lt` + `mermaid_flowchart.lt`.
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
- `docs/cookbook.md`: 10 new task-oriented recipes (11-20)
  (CV / conference handout / exam paper / scientific report with
  bibliography / recipe page / Mermaid flowchart / marginalia /
  multilingual / footnoted poetry / TOC + cross-references);
  `examples/README.md` regrouped by category to match.
- `ROADMAP.md`: new forward-looking plan covering v0.3 / v0.4 /
  "won't do" with status callouts for the parallel-agent items.
- `docs/RELEASE_NOTES_v0.2.0.md`: manual release-create instructions,
  publish-after-rollback path for the v0.2.0 tag.
- `docs/RELEASE_NOTES_v0.2.1.md`: this release.
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
- `[lout] SVG_INCLUDES_AUDIT.md`: 427-line per-include audit of
  the @BackEnd Case arms, see Added (lout 6a2dac2).

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

[Unreleased]: https://github.com/jclements3/mdlout/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/jclements3/mdlout/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/jclements3/mdlout/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jclements3/mdlout/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jclements3/mdlout/releases/tag/v0.1.0
