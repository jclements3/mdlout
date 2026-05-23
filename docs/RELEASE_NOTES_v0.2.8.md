# mdlout v0.2.8 — xml:space=preserve predicate, 85-snippet corpus, menu example

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.8`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit `069d60e`).

Same-day follow-on to v0.2.7. Lands the **`xml:space="preserve"`
predicate** in `z53.c` (`SVG_PrintWord` now marks `<text>` elements
that start or end with a space, or contain a run of two-or-more
internal spaces, with `xml:space="preserve"` — closing the
column-alignment drift that SVG renderers' default whitespace
collapse was causing in `@Code` blocks on `doc/slides/all` p019).
Slides p019 SSIM lifts **0.9441 → 0.9811** at 150 DPI. Grows the
regression corpus 80 → **85** with five more single-feature snippets
that lock in v0.2.5-v0.2.7 work (kerned ligatures, currentColor
default, verbatim whitespace, smcp/onum-off, ABC chord names). Adds
`examples/menu.md`: a 2-column A4 restaurant menu in Palatino
exercising the right-tab leader idiom. `z49.c` (PostScript) and the
legacy PDF pipeline remain frozen and bit-identical to v0.2.0.

## Headlines

- **[lout] `z53.c` `xml:space="preserve"` predicate.** SVG
  renderers (browsers, librsvg) default to `xml:space="default"`,
  which collapses leading and trailing spaces and reduces runs of
  internal spaces to a single space inside `<text>` content.
  `@Code` blocks in `lout/doc/slides` (notably page 019) rely on
  those exact spaces for column alignment, so the rendered SVG
  was visibly losing characters relative to the PostScript
  reference. `SVG_PrintWord` now scans `string(x)` before
  building the `<text>` opener and sets `xml:space="preserve"`
  exactly when:

  - the word starts with a space (`" foo"`), or
  - the word ends with a space (`"foo "`), or
  - the word has two-or-more consecutive spaces anywhere
    (`"col1  col2"`).

  Words without any of those patterns keep the historic opener
  byte-for-byte (no attribute added), so the predicate is a
  no-op on the body-text bulk of every document. Slides p019
  SSIM (PS vs SVG at 150 DPI): **0.9441 → 0.9811**. Slides p032
  SSIM (0.9726) is unchanged — its `@Code` listing is already
  tokenised into per-word `<text>` elements with no internal
  space runs in any single element, so the predicate correctly
  leaves them alone. Regression suite stays Pass-Excellent / 0
  Fail. (Submodule commit `069d60e`, mdlout commit `21600d8`.)

- **Regression corpus 80 → 85 snippets.** Five more
  single-feature `.lt` snippets lock in features that landed in
  the v0.2.5-v0.2.7 cycle:

  - `text_ligatures_kerned.lt` — kern pairs (AV / Wa / To)
    interleaved with fi / fl / ffi ligatures, exercising the
    GPOS-kern + GSUB-ligature paths together. Guards against a
    regression where kerning between two glyphs that
    individually trigger a ligature was being applied to the
    pre-ligature pair rather than the post-ligature glyph.
  - `text_currentcolor_default.lt` — default-black text
    exercising `z53.c`'s `currentColor` fold. When the active
    colour matches the page default, the `fill` attribute is
    omitted from `<text>`, which is what lets the dark-mode
    `currentColor` cascade in the HTML wrapper actually invert
    the body text.
  - `text_verbatim_whitespace.lt` — `@Verbatim` with multi-space
    column alignment, exercising the new `xml:space="preserve"`
    heuristic from this release end to end. Without the
    predicate this snippet would visibly drop columns; with it
    the column alignment is byte-aligned to the PS reference.
  - `text_smcp_synthesis_off.lt` — locks in the "feature off"
    branch of the v0.2.6 smcp/onum synthesis gate. With no
    `LOUT_SVG_FONT_FEATURES_SYNTH` env var set, the substitution
    table is empty and `<text>` output is bit-identical to a
    build without the GSUB feature compiled in.
  - `abc_chord_names.lt` — chord-symbol overlays on an `@ABC`
    block, exercising the `data-abc` attribute escaping for
    `|` (bar lines) and `:` (repeat markers) characters that
    would otherwise interfere with HTML attribute parsing.

  All five are under 30 lines and land PASS-EXCELLENT under the
  post-v0.2 tightened thresholds (5% AE for text, 2% AE /
  SSIM 0.95 for graphics-heavy). Corpus stays at 100%
  PASS-EXCELLENT / 0 Fail. (Commit `8ac11a0`.)

- **`examples/menu.md`: a 2-column A4 restaurant menu.** A new
  example: "La Maison Verte" — a single-page restaurant menu in
  Palatino exercising the multi-column page layout path. One
  `type: doc` flow with raw-Lout blocks for the typography:
  right-tab leaders to align dish prices on the right margin,
  small-cap section headers for course names, em-dashes between
  dish names and descriptions. The right-tab leader idiom
  (`@RightDisplay { ... @Tab ... }`) hadn't been covered by any
  prior example. Both `--format=html` and `--format=pdf` build
  clean. (Commit `aac7dc6`.)

## Verification

- `python3 -m build` produces a clean sdist + wheel.
- `python3 -m twine check dist/*` reports `PASSED` on both
  artefacts.
- The 85-snippet regression suite is 85/85 PASS-EXCELLENT (mean
  SSIM at 150 DPI > 0.95).
- The User's Guide PS-vs-SVG diff mean SSIM at the 150 DPI
  release-gate is unchanged from v0.2.7 (0.9441); the predicate
  fires on whitespace-significant words only, which the User's
  Guide body text doesn't have.
- Slides p019 SSIM at 150 DPI: 0.9441 → **0.9811** (the headline
  visible win of the cycle).

## Compatibility

- PostScript output bit-identical to v0.2.7 for `doc/user/all`.
- The `--format=pdf` pipeline (`ps2pdf` over the frozen `z49.c`
  PostScript) remains bit-identical to v0.2.0.
- The Lout source-compatibility contract is preserved:
  documents written for upstream Lout 3.43 still build under
  this fork without modification. The svgmacros library and the
  SVG back end (`lout -G`) remain opt-in.
- The `xml:space="preserve"` predicate is additive: words
  without significant whitespace keep their `<text>` opener
  byte-for-byte, so the bulk of every document's SVG output is
  unchanged from v0.2.7.

## What's next

The v0.3 line is in sight. Remaining v0.3 candidates from the
roadmap: `LoutMargShift translate(x, y)` (margin-note positioning
in SVG mode), a published PyPI release once the v0.2.x cycle
settles, and the long-tail combining-mark / GSUB-lookup-beyond-Type-1
work for multilingual text shaping. See [ROADMAP.md](../ROADMAP.md)
for the full forward-looking plan.

— James
