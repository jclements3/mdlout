# mdlout v0.2.1 — real font outlines, kerning, Mermaid

Released: 2026-05-22
Companion submodule tag: `lout/svg-backend-v0.2.1`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit b021b71).

Post-v0.2.0 maintenance release. Lands real font-outline support
for `charpath` across both Type 1 (`.pfb`) and CFF / OTF (`.otf`,
`.otc`) containers via the new `lout/z53_glyph.c` module; AFM
kern-pair emission in SVG text via `<tspan dx>`; a fourth client-
side passthrough macro (`@Mermaid`) alongside `@Math` / `@ABC` /
`@SVG`; 10 new cookbook recipes (lifting the count from 10 to 20);
three new examples (`exam.md`, `marginalia.md`, `multilingual.md`);
a submodule-wide `include/` audit (`SVG_INCLUDES_AUDIT.md`); a
CI scaffold, packaging via `pyproject.toml`, a microbenchmark
suite, a per-snippet history viewer, and a per-snippet
`compare.py --bisect` mode; plus a follow-on round of SVG
back-end fixes (rotated-show inside `@Graphic`, default stroke
attribute suppression, Lout tag-name leak suppression).

`z49.c` (PostScript) and the legacy PDF path remain frozen and
bit-identical to v0.2.0.

## Headlines

- **Real font outlines for `charpath`.** `z53_glyph.c` now parses
  Type 1 `.pfb` files (eexec-decrypted charstring interpreter with
  hsbw / sbw, the rmoveto / rlineto / hlineto / vlineto family,
  rrcurveto, vhcurveto / hvcurveto, closepath, callsubr / return,
  endchar, seac, div, callothersubr / pop, and the flex group)
  AND CFF Top DICT / Private DICT / CharStrings / GlobalSubrs /
  LocalSubrs inside OTF / OTC containers (Type 2 charstrings with
  the hh/vv/hv/vh/rcurveline/rlinecurve variants, hint ops as
  no-ops, callsubr / callgsubr with the standard subr biases,
  endchar, return, flex). One shared arena / cache. Lets `charpath`
  resolve outlines for the Adobe base-35 PS names regardless of
  whether the system ships Type 1 or OpenType (most modern URW++
  packages are `.otf`). Missing glyphs fall back to the 0.5 em x
  1.0 em bbox rectangle so `coltex`'s `charpath flattenpath
  pathbbox` callers still see a plausible bbox.

- **AFM kerning in SVG text.** `svg_emit_word_text` consumes
  `FontKernLength` between successive characters and emits the
  kern delta as a `<tspan dx>` inside the `<text>` element,
  bringing SVG word spacing into line with the PostScript back-
  end's glyph metrics. Most visible on proper-noun heavy paragraphs
  where AV / To / Wa / Ya pairs were noticeably loose.

- **`@Mermaid` passthrough macro.** Fourth client-side passthrough
  alongside `@Math` (KaTeX), `@ABC` (abcjsharp), and `@SVG` (raw).
  ` ```mermaid ` fenced blocks route through
  `BlockType.MERMAID_BLOCK` -> `@Mermaid { "..." }` -> the svgmacros
  entry that wraps the body in `<foreignObject><div class="mermaid">…
  </div>`. The HTML wrapper lazy-loads mermaid.js (local copy
  preferred, mermaid@10 CDN otherwise, `MDLOUT_MERMAID_URL`
  overrides the CDN). Engine ships only when at least one mermaid
  block is present; `--no-mermaid-engine` suppresses the injection.
  PDF mode falls back to a placeholder note. `examples/mermaid.md`
  showcases flowchart / sequence / class diagrams.

- **10 new cookbook recipes** (`docs/cookbook.md`, count 10 -> 20).
  First batch: CV, conference handout, exam paper, scientific
  report with bibliography, recipe page. Second batch: Mermaid
  flowcharts, marginalia / sidenotes via `@RightNote` / `@OuterNote`,
  multilingual documents (Latin via `@Char` / Greek via `@Sym` /
  Russian via `@Language`), footnoted poetry with `@LeftDisplay`
  vlists, and the `@PageOf` / `@NumberOf` / `@TitleOf` cross-
  reference idiom alongside `[TOC]`.

- **Three new examples**: `exam.md` (five-question calculus midterm
  with blank workspace via the `//Nc` vlist-separator idiom plus a
  separate Answer Key section), `marginalia.md` (`@RightNote` and
  `@OuterNote` against a widened right margin), `multilingual.md`
  (exercises the Adobe Symbol glyph table plus `@Char "eacute"` for
  accented Latin and `@Language { Russian }` for Cyrillic). All
  three build clean in HTML and PDF.

- **`@Diag` chapter gallery** (User's Guide pages 190-229):
  `tests/user_guide_diff/diag_gallery.html` with 40 per-page
  thumbnails + 10 worst-NN panels. Mean AE 6.93%, mean SSIM 0.9248;
  worst page p221 at SSIM 0.8820.

- **SVG back-end fixes.** Rotated-show inside `@Graphic` now
  propagates the path-delta rotation into a SVG `rotate()`
  transform on the emitted text wrapper, restoring correct
  orientation for the `translate N rotate moveto show` PS idiom
  (drives `ldiagshowtags` and any `@Diag` link-label using
  `linklabelangle`). Default stroke attributes
  (`stroke-linecap` / `stroke-linejoin` / `stroke-miterlimit`)
  are now suppressed when the gstate value matches the SVG default,
  unblocking rsvg edge-antialiasing on the User's Guide page 308
  swatch grid. Lout tag-name leaks (uppercase ASCII + digits) that
  arrive through `@Diag` / `@Fig` macro expansion are now silently
  dropped instead of surfacing as `<!-- z53.c: unimplemented
  PostScript op 'A1' -->` comments.

- **`SVG_INCLUDES_AUDIT.md`** in the submodule: 427-line walk of
  every `@BackEnd @Case` block in `lout/include/*`. Findings: zero
  PostScript-only blocks without an SVG or else fallback; the PS-
  side `bsf` helpers (`LoutPageSet` / `LoutMargShift` / `LoutPageDict`)
  are not yet hashed by `z53.c`, so `@Place` and `@MargPut` silently
  drop in SVG mode (deferred to v0.3).

- **CI scaffold.** `.github/workflows/ci.yml` (per-PR snippet
  regression) + `.github/workflows/user-guide-diff.yml` (weekly
  327-page PS-vs-SVG diff with artefact upload). Both pinned to
  current action majors (checkout@v4, setup-python@v5, cache@v4,
  upload-artifact@v4). Committed locally; pushing to `origin`
  requires the `workflow` OAuth scope
  (`gh auth refresh -s workflow`). Local reproduction + the OAuth-
  scope dance documented in `docs/CI.md`.

- **Packaging.** `pyproject.toml` (PEP 621, setuptools backend,
  single-module layout) exposes `mdlout` as a console_script entry
  point. `python -m build` produces a clean sdist + wheel; pip
  install registers the `mdlout` command. The packaged `version`
  string still reads `0.2.0` and `mdlout.VERSION` is unchanged from
  v0.2.0; bumping both to `0.2.1` is deferred to a follow-on commit.
  PyPI publish remains deferred to v0.3 per `ROADMAP.md`.

- **Perf instrumentation.** `tests/bench.py` records per-stage
  timings (PS build, SVG build, ps2pdf, rsvg-convert) at median-of-3
  to `tests/bench.jsonl`; `tests/bench.html` is a dependency-free
  30-run dashboard. Regression detection compares against median of
  last 5 runs, prints `WARNING` at >1.5x baseline, exits non-zero
  with `--strict`. Baseline (63 snippets): PS+SVG total ~21 s,
  ps2pdf ~33 s, rsvg ~45 s.

- **Snippet thresholds tightened.** Graphics-heavy tier moves from
  20% AE / SSIM 0.75 to 2% AE / SSIM 0.95. Suite stays 100%
  Pass-Excellent (65 snippets after the two Mermaid additions).

## Regression status

- 65-snippet single-feature suite: 0 Fail, 100% Pass-Excellent
  under the post-v0.2 tightened thresholds (5% AE for text, 2% AE /
  SSIM 0.95 for graphics-heavy).
- 327-page User's Guide PS-vs-SVG diff: 38 OK / 289 DIFF / 0 BAD /
  0 MISSING; mean SSIM 0.9234, median 0.9258, 324 / 327 pages at
  SSIM >= 0.85. Aggregate moved from mean 0.9230 / 36 OK in v0.2.0.
- Headless-Chrome browser-test runner: 41 / 41 examples PASS on
  the default checks (loaded, katex, abcjs, anchors, hljs).
- @Diag chapter gallery: mean SSIM 0.9248 over 40 pages; worst
  p221 SSIM 0.8820.

## Compatibility / migration

- No CLI flag deprecations; `--no-mermaid-engine` is additive.
- `@Mermaid` is opt-in: source files must contain a ` ```mermaid `
  block (mdlout auto-adds `@SysInclude { svgmacros }` whenever any
  of the routed Markdown blocks is present). PostScript-mode
  fallback emits a literal text block, matching the `@ABC`
  precedent.
- AFM kerning is applied automatically in SVG mode; PostScript
  output is unchanged.
- `charpath` outlines now render against real Type 1 / CFF data on
  hosts with URW++ / gsfonts installed; on hosts without those
  files, behaviour is identical to v0.2.0 (bbox-rectangle fallback).

## How to publish the GitHub release (manual instructions)

The release is being published from the v0.2.1 tag on `main`. If
`gh release create v0.2.1 --notes-file docs/RELEASE_NOTES_v0.2.1.md
--latest` succeeds in this run, no further action is required.

If `gh` rejects the create call for OAuth-scope reasons (the v0.2.1
commit chain does not touch `.github/workflows/`, so the `workflow`
scope is not strictly required; but if a prior session refreshed
the token without that scope, the `gh` client may still demand it
on repos that already carry workflow files), the manual path is:

1. Push the v0.2.1 tag and the underlying commits to `origin`:

       git push origin main
       git push origin v0.2.1

2. Publish the release with this file as the body:

       gh release create v0.2.1 \
         --title "v0.2.1 — real font outlines, kerning, Mermaid" \
         --notes-file docs/RELEASE_NOTES_v0.2.1.md \
         --latest

3. The companion submodule tag `svg-backend-v0.2.1` should already
   be on the `fork` remote (jclements3/lout) and point at commit
   `b021b71` on branch `svg-backend`. If not, from inside the
   submodule:

       cd lout
       git push fork svg-backend-v0.2.1

Full per-entry details: see
[CHANGELOG.md](../CHANGELOG.md#021---2026-05-22).
