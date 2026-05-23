# mdlout v0.2.2 — TrueType outlines, sub-30s UG build, dark mode

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.2`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit f1fdd77).

Post-v0.2.1 release. Lands TrueType (`.ttf`) outline parsing in
`z53_glyph.c` (the third format leg behind `svg_glyph_emit_outline`
alongside Type 1 `.pfb` and CFF / OTF); a layered `z53.c` perf round
that drops the User's Guide single-pass build from ~32 s to
~26-29 s wall (beats the original v0.4 < 30 s ROADMAP target); opt-in
dark-mode CSS for the HTML wrapper (`--dark` / `theme: dark`);
opt-in font subsetting (`--subset-fonts` / `subset-fonts: true`,
~50% HTML size reduction); end-to-end SVG + PDF renders of all four
documents that ship with the Lout source tree (`doc/design`,
`doc/expert`, `doc/slides`, `doc/user`); hashed dispatch for the
`bsf` family (`LoutPageDict` / `LoutPageSet` / `LoutMargSet` /
`LoutMargShift`) so `@Place` / `@MargPut` no longer drift the
operand stack in SVG mode; HTML-escape of `@ABC` and `@Mermaid`
bodies; five new examples; eight new cookbook recipes (16-23);
publish workflow for GH Pages; and a `tests/browser_test.py`
mermaid structural check.

`z49.c` (PostScript) and the legacy PDF path remain frozen and
bit-identical to v0.2.0.

## Headlines

- **TrueType (`.ttf`) outlines via the `glyf` table.** `z53_glyph.c`
  gains a third loader behind `svg_glyph_emit_outline`. Detection
  branches on the sfnt magic `0x00010000` (also `true` / `typ1`);
  the OT table directory walker is reused. Loader parses `head`
  (UnitsPerEm + loca format), `maxp` (numGlyphs), `cmap` (format 4
  BMP + optional format 12 with Unicode-platform > Windows-Unicode
  tiebreak), `loca`, and `glyf`. Outline emit decodes simple glyphs
  (flag-stream repeat expansion, signed-short / signed-byte x/y
  deltas, implicit on-curve midpoints between two consecutive
  off-curves) and converts quadratic Beziers to cubics via the
  standard `P0 + 2/3(Q-P0), P2 + 2/3(Q-P2)` formula. Composite
  glyphs recurse with a 2x2 affine, `ARGS_ARE_XY_VALUES`
  translation, depth cap 8. DejaVu / Liberation / Noto and similar
  system fonts now resolve real outlines through `charpath` instead
  of falling back to the bbox rectangle. Verification: "Hello" at
  DejaVu Sans 36 pt emits 32 cubic-Bezier segments + 23 line
  segments across 7 contours; "Quagmire" at 48 pt emits 110 curves
  + 46 lines. `LOUT_TTF_FONT_DIR` (and `LOUT_T1_FONT_DIR` as a
  shared shortcut) prepend a search directory;
  `/usr/share/fonts/truetype/` and `/usr/share/fonts/TTF/` are
  walked one level deep.

- **Sub-30 s User's Guide build.** Perf round 2 in `z53.c` lands
  three layered optimisations: (1) `svg_glyph_to_unicode` replaces
  the linear scan over the ~380-entry `svg_glyph_table` with the
  same FNV-1a + open-addressed-linear-probing hash used by
  `svg_dict_lookup` / `svg_op_lookup`, lazily built on first call
  (the largest remaining hot spot, called once per character ~250 k
  times on the User's Guide); (2) a per-font face-flag cache
  (`svg_face_cache`, 64-entry open-addressed) keyed by `FONT_NUM`,
  so `SVG_PrintWord`'s four `strstr` probes per call become a
  single dictionary lookup (~99 k word emits avoided); (3)
  `SVG_PrintWord` stdio consolidation collapses five separate
  `fprintf` / `fputs` / `fputc` calls into one `fprintf` with
  conditional format specifiers. Attribute order preserved -- the
  SVG is byte-for-byte identical to baseline (modulo the embedded
  `@CurrentTimeAndDate` timestamp). Single-pass wall ~26-29 s on
  the reference host, user ~20 s. Beats the original v0.4 ROADMAP
  < 30 s target.

- **Opt-in dark mode** via `--dark[=force|auto]` and `theme: dark` /
  `dark-mode` frontmatter keys. Emits a CSS block that paints the
  page chrome dark and inverts each `.lout-page` via
  `filter: invert(1) hue-rotate(180deg)`. Caveat: embedded raster
  `<image>`s invert too (photos render with reversed luminance).
  A proper CSS-variable scheme will land once `z53.c` emits
  `fill=currentColor` for SVG text. PostScript output unchanged.

- **`--subset-fonts` font subsetting.** New optional pass that
  trims each of the 12 inlined URW++ Nimbus base-35 faces down to
  the codepoints the SVG actually references. Scans `<text>` /
  `<tspan>` for family + inner text, builds a per-family codepoint
  set with a printable-ASCII baseline for KaTeX / abcjs runtime
  needs, then runs each face through `fontTools.subset.Subsetter`
  before the existing base64 embed. fontTools is an optional
  dependency; import is lazy and warns once to stderr when missing.
  Measured savings:
  - scientific_paper.md: 2,328,726 -> 1,178,063 bytes (49.4%)
  - 06_report.md:        2,069,366 ->   877,110 bytes (57.6%)
  - magazine_layout.md:  2,255,289 -> 1,063,053 bytes (52.9%)
  Font payload itself shrinks ~81% in each case. Default off.

- **All four Lout docs rendered through z53.c**
  (`tests/lout_doc_renders/`). Previously only `doc/user` had been
  rendered; the new `build.sh` + `diff.sh` + `aggregate.py` drives
  a 7-pass cross-reference loop per back-end, wraps each SVG in a
  minimal HTML scaffold (CDN KaTeX, mdlout-style print stylesheet),
  and emits per-doc 10-sample PS-vs-SVG galleries with scikit-image
  SSIM + ImageMagick AE %. Surfaces three z53.c-adjacent issues
  tracked separately for v0.3: missing `@Case` SVG branches in
  `lout/include/`, untranslated raw PostScript in `@Graphic` blocks
  (design's algorithm-flow diagrams), per-pass output alternation.

- **`bsf` family hashed in `z53.c`.** `LoutPageDict` /
  `LoutPageSet` / `LoutMargSet` / `LoutMargShift` (plus the `matr`
  alias for `matrix`) now have explicit entries in `svg_op_seed[]`,
  so `bsf.lpg`'s `LoutPageDict begin matr setmatrix x y translate
  end gsave … grestore` idiom no longer takes the unknown-op
  fallthrough. `@Place`'d boxes are no longer pinned to the page
  origin in SVG mode. The `translate(x, y)` for `LoutMargShift` is
  still missing -- margin notes still render at the origin --
  tracked as a v0.3 follow-on.

- **`@ABC` and `@Mermaid` body HTML-escape.** Pre-HTML-escapes both
  block bodies before the existing `_lout_string_encode` pass.
  svgmacros wraps `@ABC`'s body inside `data-abc="..."` and
  `@Mermaid`'s body as text inside `<div class="mermaid">…</div>`;
  a literal `&`, `<`, `>`, or `"` in the source previously
  corrupted the surrounding markup before the JS engines could
  read it. abcjs / mermaid DOM-decode the attribute / textContent
  at render time, so HTML-encoded entities round-trip back to the
  originals. Companion `docs/best_practices.md` subsection
  documents the three failure modes raw-`.lt` authors hit.

- **CFF / TrueType outline parser follow-ups in `z53_glyph.c`**:
  Type 2 escape op 26 (sqrt) now performs a 16-step Newton-Raphson
  (no libm dependency); op 33 (setcurrentpoint) re-documented as a
  Type 1 leftover; composite-glyph flag handling clarified
  (`WE_HAVE_INSTRUCTIONS` naturally skipped via early return on
  last component; `OVERLAP_COMPOUND` is a fill-rule hint that
  SVG's non-zero default already honours); empty TTF glyph cases
  documented; CFF predefined charsets 1 (Expert) and 2
  (ExpertSubset) tracked as a known gap in `NEXT_OPTIMIZATIONS.md`.

- **Five new examples**: `book_with_epigraphs.md`,
  `math_with_diagrams.md`, `marginalia.md`, `multilingual.md`, and
  `mermaid.md`. All build clean in `--format=html` and
  `--format=pdf`; outputs under `examples/out/` plus regenerated
  gallery thumbs and preview SVGs.

- **Eight new cookbook recipes** (`docs/cookbook.md` 16-23):
  Mermaid flowchart; marginalia / sidenotes via `@RightNote` /
  `@OuterNote`; multilingual via `@Char` / `@Sym` / `@Language`;
  footnoted poetry with `@LeftDisplay`; `@PageOf` / `@NumberOf` /
  `@TitleOf` + `[TOC]`; book chapter with epigraph + footnotes;
  two-sided letter with date / signature / postscript; inline
  diagrams via `@Mermaid` in a math-heavy doc.

- **Docs**: `examples/PUBLISHING.md` (GH Pages deploy guide:
  single-file output, `/docs`-on-main vs `gh-pages` layouts,
  CI-driven publish via `publish.yml`, custom-domain DNS
  cheat-sheet, accessibility checklist),
  `examples/CONTRIBUTING.md` (per-example contribution guide).

- **CI**: `.github/workflows/publish.yml` ships alongside the
  pre-existing `ci.yml` + `user-guide-diff.yml`. Builds
  `examples/` to HTML and pushes the rendered tree to the
  `gh-pages` branch. Requires the `workflow` OAuth scope to push
  (`gh auth refresh -s workflow`).

- **`tests/browser_test.py --with-mermaid-strict`** structural
  check. Default-OFF flag verifies each `<div class="mermaid">`
  contains a child `<svg>` whose `aria-roledescription` is a
  recognised mermaid diagram type (or whose class list contains a
  structural class like `.node`, `.edgePath`, `.actor`,
  `.classGroup`, `.flowchart`, `.cluster`). Parse-error markers and
  missing-SVG cases fail the page. Default flag-set output
  unchanged. Companion: a non-strict `mermaid=ok(N/M)` check now
  joins `katex` and `abcjs` in the default report.

## Regression status

- 65-snippet single-feature suite: 0 Fail, 100% Pass-Excellent
  under the post-v0.2 tightened thresholds (5% AE for text, 2% AE /
  SSIM 0.95 for graphics-heavy). Unchanged from v0.2.1.
- 327-page User's Guide PS-vs-SVG diff: 38 OK / 289 DIFF / 0 BAD /
  0 MISSING; mean SSIM 0.9234. Output byte-identical to baseline
  modulo the embedded `@CurrentTimeAndDate` timestamp.
- All four Lout docs render through z53.c with per-doc 10-sample
  PS-vs-SVG galleries (`tests/lout_doc_renders/`).
- Headless-Chrome browser-test runner: gains `mermaid=ok(N/M)`
  alongside `katex` and `abcjs`; `--with-mermaid-strict` opt-in
  structural check.

## Compatibility / migration

- No CLI flag deprecations. `--dark`, `--subset-fonts`, and
  `--with-mermaid-strict` are additive and default-off.
- TrueType outline resolution is automatic in SVG mode on hosts
  with the relevant `.ttf` files installed; hosts without them
  fall back to the v0.2.1 behaviour (CFF / Type 1 / bbox).
- The `@ABC` / `@Mermaid` HTML-escape is transparent to
  Markdown-driven users (mdlout does the escape); raw-`.lt`
  authors should pre-escape `&` / `<` / `>` / `"` in their bodies
  (see `docs/best_practices.md`).
- PostScript / PDF output is bit-identical to v0.2.1.

## How to publish the GitHub release (manual instructions)

The release is being published from the v0.2.2 tag on `main`. If
`gh release create v0.2.2 --notes-file docs/RELEASE_NOTES_v0.2.2.md
--latest` succeeds in this run, no further action is required.

If `gh` rejects the create call for OAuth-scope reasons (this
cycle's `.github/workflows/publish.yml` does touch
`.github/workflows/`, so the `workflow` scope is required):

1. Push tags and commits:

       git push origin main
       git push origin v0.2.2

2. Publish the release:

       gh release create v0.2.2 \
         --title "v0.2.2 — TrueType outlines, sub-30s UG build, dark mode" \
         --notes-file docs/RELEASE_NOTES_v0.2.2.md \
         --latest

3. The companion submodule tag `svg-backend-v0.2.2` should already
   be on the `fork` remote (jclements3/lout) and point at commit
   `f1fdd77` on branch `svg-backend`. If not, from inside the
   submodule:

       cd lout
       git push fork svg-backend-v0.2.2

Full per-entry details: see
[CHANGELOG.md](../CHANGELOG.md#022---2026-05-23).
