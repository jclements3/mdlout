# mdlout v0.2.5 — ligatures, kern table precompute, GSUB parser

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.5`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit `f5533e6`).

Same-day follow-on to v0.2.4. Adds the first wave of text-shaping
work to `z53.c` — fi/fl/ffi/ffl ligature substitution on Adobe-Type
serif faces, a per-font 256x256 kern table precompute (byte-identical
SVG output, perf), and a phase-1 GSUB parser for the `smcp` and
`onum` features (parser only; the consumer side is queued for v0.2.6
behind PR #167). The User's Guide PS-vs-SVG diff mean SSIM moves from
0.9234 (v0.2.3 baseline) to 0.9283, with pages above the 0.95
"visually indistinguishable" threshold growing 36 → 49 (+36%).

The mdlout Python package bumps 0.2.3 → 0.2.5 in this release,
carrying both the ligature work and the v0.2.4 same-day artefacts
into PyPI in a single bump. `z49.c` (PostScript) and the legacy PDF
pipeline remain frozen and bit-identical to v0.2.0.

## Headlines

- **[lout] fi/fl/ffi/ffl ligature substitution.** `svg_emit_word_text`
  now walks each Lout word with a 2-3 byte lookahead before
  LCM-mapping and folds the digrams `fi`/`fl` and trigrams
  `ffi`/`ffl` into U+FB01 / U+FB02 / U+FB03 / U+FB04 when the active
  font family is in the Adobe-Type serif allowlist (Times, Palatino,
  Bookman, Schoolbook, Chancery, Garamond, ITC\*, NimbusRomNo9L\*,
  URWPalladio\*). Courier and the sans families fall through to the
  original digram-emission path. The four ligature glyphs ship in
  every AFM of those families and in the URW base35 PFB outlines
  that Ghostscript substitutes for the PS-13 set, so browsers
  rendering the SVG with system fonts pick up the correct glyph
  shape; if a target ever lacks them the codepoint still renders as
  the fallback fi/fl pair. Visible improvement on text-heavy User's
  Guide chapters (3, 5, 7, 12 each gain 2-4 pages above 0.95 SSIM
  from the ligature folding alone).

- **[lout] per-font 256x256 kern table precompute.**
  `svg_emit_word_text` previously called `FontKernLength()` (z37.c)
  once per inter-glyph gap, and `FontKernLength` walks the AFM
  `kern_chars` list linearly with an unaccented-map fallback —
  O(K) per call. On the User's Guide that is ~99k word emits times
  average word length, a measurable slice of the v0.2.4 round-4 hot
  path. The new path precomputes, on first kerning call for a given
  `fnum`, the full 256x256 matrix of kern values (resolved through
  `unacc_map` so the fallback is folded into the table), stored as
  `int16`. 128 KB per font; ~1.5 MB for the 12 URW Nimbus faces
  used in a typical document. Tables are heap-allocated lazily and
  freed by `svg_kern_tables_clear()`, called from
  `SVG_PrintInitialize` (start-of-doc reset, for repeated in-process
  builds under `--serve`) and `SVG_PrintAfterLastPage` (final free).
  **SVG output is byte-identical** to the pre-cache build across
  all 74 snippet SVGs — this is a pure perf change.

- **[lout] GSUB parser for `smcp` / `onum` (parser only).** For
  CFF/OTF fonts the loader now also walks the `GSUB` table:
  `svg_glyph_find_gsub` locates `GSUB`; `svg_glyph_resolve_feature`
  walks Script → default-LangSys → Feature (by tag) → Lookup indices
  and applies each Lookup Type 1 (Single Substitution, formats 1 and
  2) into a GID→GID map; `svg_glyph_project_subst` projects that
  through Adobe StandardEncoding into a Latin-1 codepoint → GID
  table, stored as `f->smcp_subst[256]` / `f->onum_subst[256]`.
  Public API: `svg_glyph_font_smcp_substitute`, `_onum_substitute`,
  `_has_feature`. `z53.c` grows two `SVG_FONT_FEATURE_*` bit
  constants and a `font_features` field on `svg_gstate` so a future
  caller can plug in consumer-side logic without re-touching the
  parser. **Phase 1 scope**: CFF/OTF only (Type 1 PFB has no GSUB;
  TrueType GSUB deferred); Lookup Type 1 only (ligature /
  contextual / chained / extension subtables noted in
  `SVG_PORTING.md` as future work). The result is recorded but not
  yet consumed at `<text>` emission time — small-caps glyphs have no
  Unicode codepoint of their own, so the current Unicode-based
  `<text>` path cannot reference them. The planned consumer is
  glyph-path emission for body text, tracked under PR #167 and
  projected to ship in v0.2.6.

- **[lout] `z53_glyph.c` arena pointer safety (defensive).** The
  CFF / TrueType outline arena now guards realloc-aliasing: callers
  that hold pointers into the arena across a `svg_arena_alloc` are
  detected and the arena emits a stable index instead. No behaviour
  change for current callers (all of which release pointers before
  the next allocation); harden against future call sites that might
  not.

- **mdlout package bumped 0.2.3 → 0.2.5.** Both `pyproject.toml`
  and `mdlout.VERSION` move 0.2.3 → 0.2.5. PR #154 (the bump that
  was in flight when v0.2.4 was cut) landed during this cycle, so
  the bump carries both v0.2.4 and v0.2.5 into a single PyPI
  release. No CLI flag changes; no behavioural change for
  documents that do not transit the ligature-eligible Adobe-Type
  serif faces.

- **Docs: tutorial refresh, FAQ.md, cookbook 33-35.** Tutorial
  brought in line with the v0.2.3 / v0.2.4 cycle (dark mode via
  `currentColor`, `--subset-fonts` default-ON, `--watch` /
  `--serve` end-to-end). New `docs/FAQ.md` covers common gotchas
  for the markdown-author workflow. Three new cookbook recipes:
  bibliography / citation idioms, multi-language documents at the
  Lout-language level, and a longer-form `@Diag` walkthrough.
  Recipe count goes 32 → 35; the "more cookbook recipes" near-term
  roadmap item is now closed.

- **Examples: `gallery.md`.** 54-page mdlout-rendered showcase
  document: every example in `examples/` rendered to a thumbnail
  with caption, cross-linked to source `.md` / generated `.html` /
  legacy `.pdf`. Generated via mdlout itself.

- **Tests: `browser_test --with-math-strict`.** New optional flag
  that fails the run if KaTeX logs any parse error to the
  headless-Chrome console (default is warn-and-continue). Catches
  regressions in the `convert_inline` math placeholder where
  malformed `$..$` spans would otherwise silently render as
  literal text.

- **Tests: UG diff bumped to 8 passes (PR #166, if landed).** The
  User's Guide build runs Lout 8 times instead of 7 for cross-
  reference stability on the long chapters. Headline SSIM numbers
  in this release are taken from the 8-pass run if it landed,
  else the 7-pass run; both are within 0.0003 of each other.

## Regression status

- 65-snippet single-feature suite: 0 Fail, 100% Pass-Excellent
  under the post-v0.2 tightened thresholds (5% AE for text,
  2% AE / SSIM 0.95 for graphics-heavy). Unchanged from v0.2.4.
- `tests/lout_doc_renders/` landing page: SSIMs unchanged from
  v0.2.4 (design 0.9190, expert 0.9202, slides 0.9804, user
  0.9292). The ligature work moves the per-page PS-vs-SVG diff,
  not the whole-document raster SSIM (lower effective resolution
  on the landing-page renders).
- `tests/user_guide_diff/` SSIM regen: mean 0.9283 (was 0.9234
  at v0.2.3, 0.9278 at v0.2.4); 49 pages SSIM ≥ 0.95 (was 36 at
  v0.2.3, 47 at v0.2.4); 1 page SSIM < 0.85 (was 3 at v0.2.3).
- `bash tests/browser_test.sh`: 53-55 PASS / 0 FAIL across the
  cycle. Unchanged from v0.2.4. `--with-math-strict` opt-in mode
  is also clean.
- PostScript / `--format=pdf` output bit-identical to v0.2.4 for
  the example corpus and `doc/user/all`.

## Compatibility / migration

- mdlout package version 0.2.3 → 0.2.5. `pip install --upgrade
  mdlout` (once the PyPI publish lands) picks up the new wheel.
- No CLI flag changes. The v0.2.3 `--no-subset-fonts` opt-out,
  `--dark[=force|auto]` cascade, and the five passthrough macros
  (`@Math` / `@DMath` / `@ABC` / `@SVG` / `@SVGFile`) are
  unchanged.
- Re-render to pick up the ligature output. Documents that
  string-grep for literal `fi` / `fl` / `ffi` / `ffl` in the
  generated SVG (none known; this would be a strange thing to
  do) will need to look for U+FB01 / U+FB02 / U+FB03 / U+FB04
  in eligible serif faces. The fallback path (Courier, sans
  families, non-Adobe-Type serifs) is unchanged.
- The GSUB parser is parser-only in this release; it has no
  observable effect on output. `svg_glyph_font_smcp_substitute`
  and friends are now in the public surface but no caller yet
  invokes them — the consumer lands in v0.2.6 if PR #167 merges.

## How to publish the GitHub release

The release is being published from the v0.2.5 tag on `main`. If
`gh release create v0.2.5 --notes-file docs/RELEASE_NOTES_v0.2.5.md
--latest` succeeds in this run, no further action is required.

If `gh` rejects the create call for OAuth-scope reasons:

1. Push tags and commits:

       git push origin main
       git push origin v0.2.5

2. Publish the release:

       gh release create v0.2.5 \
         --title "v0.2.5 — ligatures, kern table precompute, GSUB parser" \
         --notes-file docs/RELEASE_NOTES_v0.2.5.md \
         --latest

3. The companion submodule tag `svg-backend-v0.2.5` should already
   be on the `fork` remote (jclements3/lout) and point at commit
   `f5533e6` on branch `svg-backend`. If not, from inside the
   submodule:

       cd lout
       git push fork svg-backend-v0.2.5

Full per-entry details: see
[CHANGELOG.md](../CHANGELOG.md#025---2026-05-23).
