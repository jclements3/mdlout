# mdlout v0.3.0 — `gsave`/`grestore` path save/restore, 95-snippet corpus

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.3.0`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit `841874d`).

The first minor-version bump beyond the v0.2 line. The headline
change is a correctness fix in `z53.c`'s embedded PostScript
interpreter (submodule commit `6688249`, issue #208): `gsave` and
`grestore` now snapshot and restore the **current path** alongside
the existing gstate struct. The visible consequence is that every
`LoutBox` border across the entire document corpus now renders
correctly (matched fill + stroke) instead of silently dropping the
stroke half of the idiom. PostScript output and the
`--format=pdf` pipeline remain bit-identical to v0.2.9.

## Why a minor bump, not v0.2.10?

The v0.2.x line had been a tight patch-level cadence: nine
patch-level releases in two days, each landing perf / docs / tests
polish without changing the SVG output bytes for any document that
didn't opt in (e.g. by setting `font-features: smcp,onum`). The
v0.3.0 fix is different: the SVG output for **every document with
a `LoutBox` border** is materially different from v0.2.9.
Concretely, on the 327-page User's Guide build:

- `stroke=` attribute count `6912 → 7736` (+824, +11.9%).
- Page 308 (the colour-swatch grid that exercises the worst case)
  `<path>` element count `185 → 366` (+97.8%) — every swatch now
  emits both the fill and the trailing stroke pair instead of just
  the fill.
- Every framed display, every `@Tab` cell rule, and every example
  document with a boxed callout picks up the missing stroke
  half-of-pair.

The new output is correct: every `LoutBox` now matches the
PostScript reference. But downstream pipelines that byte-diff SVG
output across mdlout releases will see the change on every
affected document. Bumping the minor version signals that intent
clearly, in line with the project's "loosely tracks SemVer"
policy. A v0.2.10 release that contained this fix would have
obscured a real output-shape change under the patch / docs / tests
rubric of the rest of the v0.2.x line.

## Headlines

- **[lout] `gsave` / `grestore` save/restore the current path**
  (submodule commit `6688249`, issue #208). The embedded PS
  interpreter inside `z53.c` previously only snapshotted the
  `svg_gstate` struct (colour, line width, transform, dash
  array). PostScript's `gsave` saves the entire graphics state
  including the current path under construction, and `grestore`
  restores it. The very common idiom
  `<build path> gsave fill grestore stroke` silently dropped the
  stroke under the old behaviour — `fill` cleared the path,
  `grestore` put the gstate back but the path stayed empty, and
  the next emit saw `had_geom=FALSE`. Every `LoutBox` border
  (table cell rules, colour-swatch grids on UG pages 302-305,
  framed displays) rendered as fill-only with no stroke. The fix
  extends `svg_gstate` with `saved_path` / `plen` / `had_geom`
  plus `saved_have_cp` / `has_curve` / `last_pt_valid` /
  `cur_x` / `cur_y` / `last_xp` / `last_yp`. `svg_op_h_gsave`
  stashes the live values into the new stack top after the
  existing struct-copy; `svg_op_h_grestore` reads them back
  before decrementing. `SVG_OP_SAVE` / `SVG_OP_RESTORE` mirror
  the same dance. Static cost is 16 KB path buffer × 32 gstate
  slots ≈ 512 KB — acceptable for a one-shot doc build. No
  regressions: `tests/run_all.sh` stays at 163 Pass-Excellent /
  0 Fail.

- **Regression corpus 90 → 95 snippets** (mdlout commit
  `3f18943`). Five more single-feature `.lt` snippets, all
  PASS-EXCELLENT (worst is `text_smcp_kerned_lig` at 0.62% AE /
  SSIM 0.9933):
  - `text_smcp_kerned_lig.lt` — smcp + AFM kerning + OT
    ligatures in one paragraph; stacks all three text-shaping
    pipelines so a regression in any one would surface.
  - `graph_dual_series.lt` — two overlaid `@Data` series (solid
    + dashed) on one set of axes.
  - `diag_col_layout.lt` — 2×3 grid of `@Node` cells tiled in a
    single `@Diag` via `||` / `//` gap operators.
  - `box_save_restore.lt` — the dedicated reproducer for #208.
    `LoutBox` followed by `gsave` / `fill` / `grestore` /
    `stroke` — fails before this commit, PASS-EXCELLENT after.
  - `table_complex_borders.lt` — `@Tbl` with selective per-cell
    `rulebelow` / `ruleleft`. Exercises the same `LoutBox`-stroke
    path on table internals.

- **11 non-A4 example PDFs rebuilt at correct page sizes**
  (commit `a85abbd`). The 11 example documents whose
  frontmatter declares a non-A4 page size (A0 poster, A3
  magazine layout, A5 letter, Letter for academic article +
  journal + CV + textbook + chord chart + book chapters +
  scientific paper) were built pre-#198 and `ps2pdf` had
  silently emitted them as A4 with the rest clipped. After
  landing the v0.2.9 page-size passthrough, those binaries on
  disk were stale. This commit rebuilds all 11 against the
  post-#198 pipeline so the gallery thumbnails and downloadable
  PDFs reflect the intended page dimensions. No source changes.

- **`docs/cookbook.md`: 50 → 53 recipes** (commit `747f8e5`).
  Recipe 51 documents `--inline-raster` / frontmatter
  `inline-raster: true` for self-contained HTML distribution.
  Recipe 52 documents the `tests/run_all.sh` +
  `tests/browser_test.sh` harness as an authoring-loop
  build-verification step. Recipe 53 is a comprehensive CLI
  flag reference table, cross-referenced back into the recipes
  that demonstrate each one in context.

- **[lout] `SVG_PORTING.md`: v0.3.0 status refresh** (submodule
  commit `841874d`). Re-baselines the document as the v0.3.0
  status doc. Adds a preamble with v0.3.0 baseline numbers (UG
  mean SSIM ~0.95 at 150 DPI, 95-snippet corpus at 100% Pass-
  Excellent, 22.6 s UG SVG build). Adds a "Shipped through
  v0.3.0" section listing the work that has landed since the
  previous revision. Trims "Remaining known issues" to the
  three actual open items (cross-token `@Code` kerning, the
  long tail of `@Graphic` raw-PS ops, shared rasteriser).

## Verification

- `python3 -m build` produces a clean sdist + wheel.
- `python3 -m twine check dist/*` reports `PASSED` on both
  artefacts.
- The 95-snippet regression suite is 95 / 95 PASS-EXCELLENT
  under the post-v0.2 tightened thresholds (5% AE for text,
  2% AE / SSIM 0.95 for graphics-heavy).
- `tests/run_all.sh` reports 163 Pass-Excellent / 0 Fail across
  all back-end variants.
- User's Guide `stroke=` attribute count: `6912 → 7736` (+824),
  page 308 `<path>` count `185 → 366` — both confirm the #208
  fix is taking effect across the full corpus.

## Compatibility

- PostScript output is bit-identical to v0.2.9 for
  `doc/user/all` and the rest of the corpus. `z49.c` remains
  frozen.
- The legacy `--format=pdf` pipeline is bit-identical to v0.2.9
  (which preserved the v0.2.0 behaviour for `page:`-less
  documents and added the page-size passthrough for documents
  that set `page:` in frontmatter).
- **SVG output changes** for every document with a `LoutBox`
  border. The new output is correct (matching the PostScript
  reference); the old output silently dropped the stroke half
  of the fill+stroke idiom. See "Why a minor bump" above.
- The Lout source-compatibility contract is preserved:
  documents written for upstream Lout 3.43 still build under
  this fork without modification. The svgmacros library and
  the SVG back end (`lout -G`) remain opt-in.

## What's next

The v0.3 line is feature-locked. Forward work tracked on
[ROADMAP.md](../ROADMAP.md):

- **TTF advanced features** — combining-mark positioning
  (combining acute / grave / cedilla on Latin Extended-A;
  visible on `multilingual.md`), GSUB Lookup types beyond
  Type 1 (ligature subtables, contextual, chained,
  extension), TrueType GSUB, and GPOS-anchor mark attachment.
- **Hardening across UTF-8 input** — the C Lout core still
  reads ISO-LATIN-1; a full UTF-8 input layer (z02.c / z03.c /
  FULL_CHAR widening) is the precondition for multilingual
  documents to round-trip cleanly.
- **More cookbook recipes** — the cookbook is the primary
  forward-facing docs artefact; v0.4 will continue extending
  it past 53.
- **Shared rasteriser for true pixel parity** (carry-over from
  v0.4 target). The current ~5% antialiasing floor on the
  User's Guide diff is rsvg vs Ghostscript painting the same
  glyph outlines with different AA / hinting choices, not a
  back-end correctness gap.

— James
