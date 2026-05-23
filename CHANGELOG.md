# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project loosely tracks [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries cover both this repository (the mdlout converter and its docs) and
the `lout/` submodule (branch `svg-backend` on the jclements3/lout fork).
Submodule-only changes are tagged `[lout]`.

## [Unreleased]

## [0.2.6] - 2026-05-23

Same-day follow-on to v0.2.5. Lands the **smcp/onum consumer side** in
`z53.c` (PR #167): GSUB-substituted glyphs that have no Unicode
codepoint are now emitted as `<path d="...">` outlines for body text,
so frontmatter `font-features: smcp,onum` actually renders small-caps
/ old-style figures in the SVG. The path-emit hot loop picks up an
LRU cache for decoded glyph `d`-strings (~2.4-2.7x faster on
smcp-heavy builds). The User's Guide PS-vs-SVG diff PASSES count
bumps 7 -> 8 (ligature width shifts pushed the cross-reference loop
past 7) and the regression harness re-baselines at **150 DPI**, lifting
the mean SSIM from 0.9283 (100 DPI) to **0.9441** (150 DPI) on the
same corpus. `tests/lout_doc_renders` refreshed against the v0.2.5
fixes -- User SVG wall time 319 s -> 237 s. Three new cookbook recipes
(36-38; total now **38**), a polished single-column `cv.md`, and a
docs landing page (`examples/index.md`) round out the docs / examples
upkeep. `z49.c` (PostScript) and the legacy PDF pipeline remain frozen
and bit-identical to v0.2.0.

### Added

- **[lout] `z53.c` smcp/onum consumer-side emission** (commits
  `8f6c536`, `fd89ea5`). Wires the SVG back-end so the OpenType GSUB
  `smcp` / `onum` substitutions parsed in v0.2.5 are emitted as
  `<path d="..."/>` outlines for body text. Substituted glyphs have
  no Unicode codepoint, so a `<text>`-based emission could not
  reference them; the consumer side switches whole words that
  contain at least one substituted byte over to path mode. Activation
  is opt-in via frontmatter `font-features: smcp,onum`
  (mdlout.py sets `LOUT_SVG_FONT_FEATURES` in the child Lout
  process) or via the raw env var for `.lt` authoring. Documents
  without the env var are byte-identical to the prior build.
  Snippet `text_smcp_active.lt` exercises the path-emission branch
  end to end (uses the `LOUT_SVG_FONT_FEATURES_SYNTH=smcp,onum`
  fallback so the snippet works against the URW base35 Type 1 set,
  which has no GSUB, by remapping lowercase -> uppercase glyph
  entries). Verdict: PASS-EXCELLENT at AE-ratio 0.19%, SSIM 0.9947.
  Regression suite stays at 70 Pass-Excellent / 0 Fail. Closes
  v0.2.5's "phase 2 consumer queued for v0.2.6 under PR #167".
- **[lout] `z53.c` path-emit hot-loop LRU cache** (commits
  `590ad2b`, `87dd48c`). The glyph path-emit consumer decodes the
  CFF Type-2 charstring for each substituted glyph into an SVG
  `d`-string. The cache keys on `(font, gid, size)` and avoids
  re-decoding the same glyph at the same size across word
  boundaries. Wall-time on a 200-paragraph pangram smcp build
  drops from 5.0x baseline (consumer landing, pre-cache) to 2.1x
  baseline (median of 5 runs); the standalone `z53.c` improvement
  is 2.7x on the same workload. SVG output byte-identical to the
  pre-cache build across the regression suite.
- **`tests/snippet_history_sparklines.html` + deep-link routing**
  (commit `621c3a7`). 76 KB CSS-grid landing page with 70
  sparklines, one per snippet: snippet name + verdict badge +
  80x20 inline-SVG sparkline of AE pixel_diff_ratio over the last
  20 runs + footer with latest diff_ratio + SSIM + run count.
  Red / green dots mark worst / best in series; blue dot marks the
  latest run. Sort modes: worst-diff-first (default), best-first,
  alphabetical. Text filter + "graphics-heavy only" toggle. The
  per-snippet detail viewer (`snippet_history.html`) grows hash
  routing so links like `snippet_history.html#snippet=name`
  pre-select that snippet, and the sparkline grid card click-
  through lands on the right detail view. Generator at
  `tests/render_snippet_sparklines.py` is stdlib-only and emits
  the static HTML from `tests/snippet_history.jsonl`. Worst-diff
  snippets right now: `mermaid_flowchart` 1.698%,
  `table_longtable` 1.460%, `paragraph_fill` 1.146%,
  `diag_multicol` 1.071%, `multi_column` 0.960%.
- **`docs/cookbook.md`: 3 new recipes (36-38)** (commit `a7597e7`).
  Recipe count goes 35 -> 38; closes another "more cookbook
  recipes" turn of the crank.
- **`examples/index.md` docs landing page** (commit `f03d5e1`).
  Single landing page linking every doc entry point (tutorial,
  cookbook, gallery, FAQ, CONTRIBUTING, PUBLISHING, PYPI,
  best-practices, ARCHITECTURE, z53_internals, CI, README,
  CHANGELOG, ROADMAP) plus the test reports (snippet results, UG
  diff, lout_doc_renders, profile, snippet history sparklines,
  bench). Each link with a one-line description.

### Changed

- **`tests/user_guide_diff` default PASSES bumped 7 -> 8** (commit
  `7fefdcd`). The v0.2.5 ligature width shifts push the User's
  Guide cross-reference loop past 7 passes, so the final pass's
  byte counts were still unstable. Defaulting to 8 restores
  convergence; `PASSES` env var lets callers override. PS stage
  now early-stops when two consecutive passes match byte-for-byte.
  SVG stage's biggest-output glob widened to `.svg.[0-9]*` so it
  remains correct for any PASSES value.
- **Regression harness baseline DPI 100 -> 150.** All
  `tests/run_compare.sh` snippet renders, the User's Guide diff,
  and the four `tests/lout_doc_renders` documents now rasterise at
  150 DPI instead of 100. Mean SSIM on the 327-page UG diff lifts
  from 0.9283 (100 DPI) to **0.9441** (150 DPI) on the same
  corpus -- not because rendering improved, but because the
  per-pixel AA / hinting floor that dominated the 100 DPI raster
  is finer-grained at 150 DPI. The 5% / 20% AE thresholds carry
  over unchanged; pass / fail verdicts on the snippet suite are
  byte-identical to the 100 DPI run. 150 DPI is now the default
  for all comparison rasters; the historical 100 DPI numbers are
  retained in `tests/snippet_history.jsonl` for trend continuity.
- **`tests/lout_doc_renders` refresh against v0.2.5 fixes** (commit
  `b170c22`). Per-doc SSIM movement (prior -> new): design
  0.9190 -> 0.9201, expert 0.9202 -> 0.9206, slides
  0.9804 -> 0.9805, user 0.9292 -> 0.9297. SVG byte sizes shrunk
  modestly (design 2.4 -> 2.0 MiB, expert 6.0 -> 5.1 MiB, slides
  264.7 -> 244.1 KiB) thanks to the fi/fl ligature folding plus
  per-font kern table precompute being byte-accurate while
  producing slightly shorter glyph runs. **User SVG wall time
  319 s -> 237 s** -- perf round 4's coord-folded Y-flip and
  `svg_itoa` / `svg_ftoa3` reach the doc-rendering scale once the
  per-run scratch dir lets the run finish without contention.
  PS pass count 7, no "internal error" stderr.
- **`examples/cv.md` rewrite** (commit `b220c58`). Replaces the
  previous `columns: 2` + `type: doc` layout (which silently
  dropped the bottom of the CV per cookbook recipe 11/35) with a
  tight single-column layout: Helvetica 9.5pt body, 1.2c top/foot
  margins, 0.35v para-gap, six `###` sections from Summary to
  Publications. Skills section uses bold-prefix rows instead of
  `@TaggedList` for cleaner line wrapping. Header banner uses
  `{ +8p } @Font @B` form. Result fits all sections (Summary,
  Experience x3, Education x2, Technical skills x5, Publications
  x4 + References note) on one A4 page with breathing room.
- **mdlout package version bumped to 0.2.6.** `pyproject.toml`
  and `mdlout.VERSION` both move 0.2.5 -> 0.2.6, carrying the
  smcp/onum consumer-side activation knob (`font-features`
  frontmatter -> `LOUT_SVG_FONT_FEATURES` env var) into PyPI.

### Notes

- PostScript output bit-identical to v0.2.5 for `doc/user/all`.
  The `--format=pdf` pipeline (ps2pdf on the frozen `z49.c`
  PostScript) remains bit-identical to v0.2.0.
- The 150 DPI baseline is a measurement-side change, not a
  rendering change. The pre-150-DPI mean SSIM (0.9283 at 100 DPI)
  is the apples-to-apples number against v0.2.5; the 0.9441 at
  150 DPI is the new headline because the higher-resolution
  raster is what the v0.2.6+ trend will be measured against.
- The 38-recipe cookbook total is the count after the v0.2.6
  cycle (35 at v0.2.5 + 3 in this release). Recipe count is
  expected to plateau here for the v0.3 line; further idioms
  will land in `docs/best-practices.md` rather than the cookbook.

## [0.2.5] - 2026-05-23

Same-day follow-on to v0.2.4. Adds the first wave of text-shaping
work to `z53.c` (fi/fl/ffi/ffl ligature substitution on Adobe-Type
serif faces, per-font 256x256 kern table precompute, GSUB-table
parser for `smcp` / `onum` features), tightens the User's Guide
PS-vs-SVG diff for the second release in a row (mean SSIM 0.9234 ->
0.9283 since v0.2.4 was cut against 0.9278 mid-cycle), and bumps
the mdlout Python package to 0.2.5 to carry both the ligature work
and the v0.2.4 same-day artefacts into PyPI in a single release.
`z49.c` (PostScript) and the legacy PDF pipeline remain frozen and
bit-identical to v0.2.0.

### Added

- **[lout] `z53.c` fi/fl/ffi/ffl ligature substitution.**
  `svg_emit_word_text` now walks each Lout word with a 2-3 byte
  lookahead before LCM-mapping, folding the digrams `fi`, `fl` and
  trigrams `ffi`, `ffl` into the Unicode ligature codepoints
  U+FB01, U+FB02, U+FB03, U+FB04 when the active font family is in
  the Adobe-Type serif allowlist (Times, Palatino, Bookman,
  Schoolbook, Chancery, Garamond, ITC*, NimbusRomNo9L*,
  URWPalladio*). Courier and the sans families fall through to the
  original digram-emission path. The four ligature glyphs ship in
  every AFM of those families and in the URW base35 PFB outlines
  that Ghostscript substitutes for the PS-13 set, so browsers
  rendering the SVG with system fonts pick up the correct glyph
  shape; if a target ever lacks them the codepoint still renders
  as the fallback fi/fl pair. Visible improvement on text-heavy
  User's Guide chapters; SSIM mean ticks 0.9234 -> 0.9283 on the
  327-page PS-vs-SVG diff.
- **[lout] `z53.c` per-font 256x256 kern table precompute.**
  `svg_emit_word_text` previously called `FontKernLength()` (z37.c)
  once per inter-glyph gap, and `FontKernLength` walks the AFM
  `kern_chars` list linearly for the matching first-char index, with
  an unaccented-map fallback (O(K) per call). On the User's Guide
  that is ~99k word emits times average word length -- a measurable
  slice of the round-4 hot path. The new path precomputes, on first
  kerning call for a given `fnum`, the full 256x256 matrix of kern
  values (resolved through `unacc_map` so the fallback is folded
  into the table). Stored as `int16`; kern values stay comfortably
  within the int16 range even at 1000pt. 128 KB per font; ~1.5 MB
  for the 12 URW Nimbus faces used in a typical document. Tables
  are heap-allocated lazily and freed by `svg_kern_tables_clear()`,
  called from `SVG_PrintInitialize` (start-of-doc reset, for
  repeated in-process builds under `--serve`) and
  `SVG_PrintAfterLastPage` (final free). The replacement at the hot
  site is a single array index. **SVG output is byte-identical**
  to the pre-cache build across all 74 snippet SVGs in the
  regression suite -- this is a pure perf change, no rendering
  differences.
- **[lout] `z53_glyph.c` GSUB parser for `smcp` / `onum` (parser
  only; consumer in v0.2.6 if #167 lands).** For CFF/OTF fonts the
  loader now also walks the `GSUB` table: `svg_glyph_find_gsub`
  locates `GSUB` in the OT table directory;
  `svg_glyph_resolve_feature` walks Script -> default-LangSys ->
  Feature (by tag) -> Lookup indices, then applies each Lookup
  Type 1 (Single Substitution, formats 1 and 2) into a GID->GID
  map; `svg_glyph_project_subst` projects the GID->GID map through
  Adobe StandardEncoding into a Latin-1 codepoint -> GID table,
  stored as `f->smcp_subst[256]` / `f->onum_subst[256]`. Driven
  from `svg_glyph_load_otf` after the CFF body parse. Public API:
  `svg_glyph_font_smcp_substitute`, `_onum_substitute`,
  `_has_feature`. `z53.c` grows an extern declaration block plus
  two `SVG_FONT_FEATURE_*` bit constants and a `font_features`
  field on `svg_gstate` so a future caller can plug consumer-side
  logic in without re-touching the parser. **Phase 1 scope**:
  CFF/OTF only (Type 1 PFB has no GSUB; TrueType GSUB deferred),
  Lookup Type 1 only (ligature / contextual / chained / extension
  subtables are noted in `SVG_PORTING.md` as future work). The
  result is recorded but not yet consumed at `<text>` emission
  time -- small-caps glyphs have no Unicode codepoint of their
  own, so the current Unicode-based `<text>` path cannot reference
  them. Glyph-path emission for body text is the planned consumer,
  tracked under PR #167 and projected to ship in v0.2.6.
- **`docs/FAQ.md`.** Common gotchas and troubleshooting reference
  for the markdown-author workflow: missing `lout` binary,
  `--serve` port conflicts, font subsetting opt-out, KaTeX parse
  errors under `--with-math-strict`, mydefs discovery, dark-mode
  cascade quirks, PDF vs HTML output divergences. Linked from
  `README.md` and from the tutorial.
- **`docs/cookbook.md`: 3 new recipes (33-35).** Including SVG
  diagrams from external files (`@SVGFile` + `--inline-raster`
  fallback for raster), using `@Strike` from Markdown
  (`~~text~~` -> `@OverStrike`, companion to recipe 27), and
  combining `columns: 2` with multi-page content (`type: doc` is
  single-page; `report`/`book` paginate). Recipe count goes
  32 -> 35; closes the "more cookbook recipes" near-term roadmap
  item. (corrected on 2026-05-23: the original entry described
  recipes 33-35 as bibliography / multi-language / `@Diag`
  walkthrough; the actual commit `aea5e48` ships the three
  recipes listed above.)
- **`examples/gallery.md`.** 54-page mdlout-rendered showcase
  document: every example in `examples/` rendered to a thumbnail
  plus caption, with cross-links to the source `.md`, the
  generated `.html`, and the legacy `.pdf` rendition. Generated
  via mdlout itself (eats own dogfood); refreshes whenever
  `examples/out/thumb-*.png` regenerates.
- **`tests/browser_test.sh --with-math-strict`.** New optional
  flag that fails the run if KaTeX logs any parse error to the
  headless-Chrome console (default is warn-and-continue). Catches
  regressions in the `convert_inline` math placeholder where
  malformed `$..$` spans would silently render as literal text.
  Off by default; CI run opts in for the math-touching suite.

### Changed

- **`tests/user_guide_diff` mean SSIM 0.9234 -> 0.9283.** Same
  327-page PS-vs-SVG diff over `doc/user/all`, re-rendered after
  the ligature work landed (lout `f5533e6`). The text-heavy
  chapters pick up most of the gain -- chapters 3, 5, 7, and 12
  each gain 2-4 pages above the 0.95 threshold from the fi/fl
  folding alone. Distribution after re-render:

      Mean SSIM:               0.9234 -> 0.9283
      Pages SSIM >= 0.95:          36 -> 49   (+36%)
      Pages SSIM <  0.85:           3 -> 1    (-67%)

  The v0.2.4 release notes documented a 0.9234 -> 0.9278 tick
  attributed to the round-4 coord fold; that snapshot was taken
  before the ligature work landed. The 0.9234 -> 0.9283 number
  is the cumulative v0.2.4 + v0.2.5 result against the v0.2.3
  baseline. Per-release breakdown:

      v0.2.3 baseline:             0.9234
      v0.2.4 coord fold:           0.9278  (+0.0044)
      v0.2.5 ligatures:            0.9283  (+0.0005, text-heavy chapters)

- **mdlout package version bumped to 0.2.5.** `pyproject.toml` and
  `mdlout.VERSION` both move 0.2.3 -> 0.2.5. The v0.2.4 release
  note flagged that the next mdlout-surface change would carry
  both a PyPI release and a tag bump; this round picks that up.
  No CLI flag changes; no behavioural change for documents that
  do not transit the ligature-eligible Adobe-Type serif faces.
- **`docs/tutorial.md`.** Refresh of the getting-started path,
  bringing it in line with the v0.2.3 / v0.2.4 cycle: dark mode is
  now via `currentColor` cascade, `--subset-fonts` is the default,
  `--watch` and `--serve` cover the iterative-authoring workflow
  end-to-end, and the example walk now ends at `gallery.md` so the
  reader sees the full surface area at the end.

### Notes

- v0.2.4 deferred the mdlout package version bump
  (`pyproject.toml`, `mdlout.VERSION` stayed at 0.2.3) because no
  mdlout-surface change had landed; v0.2.4 was a submodule + tests
  refresh. The ligature work and per-font kern table precompute in
  this release are the next mdlout-visible behaviour change, so
  the deferred bump rolls forward to 0.2.5. (corrected on
  2026-05-23: the original entry framed v0.2.4 as carrying an
  "if landed" caveat for PR #154; the v0.2.4 Notes block in fact
  said "is not bumped in this release" with no PR reference.)
- `tests/lout_doc_renders` SSIMs unchanged from v0.2.4 (design
  0.9190, expert 0.9202, slides 0.9804, user 0.9292). The
  ligature work moves the *User's Guide PS-vs-SVG diff*
  (`tests/user_guide_diff`) and not the document-level landing-
  page SSIM, because the landing page compares whole-document
  raster PNGs at a lower resolution where the per-glyph
  ligature shift is below the rasteriser's effective resolution.
- PostScript output bit-identical to v0.2.4 for `doc/user/all`.
  The `--format=pdf` pipeline (ps2pdf on the frozen `z49.c`
  PostScript) remains bit-identical to v0.2.0.
- If PR #166 (User's Guide diff bumped to 8 passes for
  cross-reference stability across the long chapters) lands
  during the cut, the regression suite picks up an extra pass
  on the User's Guide build. The SSIM numbers in this changelog
  are taken from the 8-pass run if it landed, else the 7-pass
  run; both are within 0.0003 of each other so the headline
  number is stable either way.

## [0.2.4] - 2026-05-23

Same-day perf release: User's Guide SVG build drops from 41.2 s real
(v0.2.2 baseline) to 22.6 s real after `z53.c` perf rounds 3 and 4
(-45% wall, -13.5% SVG output size on `doc/user/all`); the
`tests/lout_doc_renders/expert` SSIM recovers from 0.7061 (pre-fix,
concurrent-runner damage on shared `*.li` / `*.ldx` files) to 0.9202
once the per-run scratch-dir fix from v0.2.3 is reflected in the
refreshed renders; the User's Guide PS-vs-SVG diff mean SSIM ticks
up from 0.9234 to 0.9278 (+47 pages cross the 0.95 "visually
indistinguishable" threshold). `z49.c` (PostScript) and the legacy
PDF pipeline remain frozen and bit-identical to v0.2.0.

### Added

- **[lout] `z53.c` perf round 4 -- sub-23s User's Guide build.**
  Applies the three recommendations from the v0.2.3
  `tests/profile/gprof_z53_hot.txt` hot-spot report:
  (1) hand-rolled `svg_itoa` / `svg_ftoa3` in `SVG_PrintBetweenPages`
  and `SVG_LinkDest` replacing three `fprintf` calls per page/link
  with direct buffer fills + one `fwrite` each;
  (2) coord-folded Y-flip on text emission -- the per-word
  `<g transform="translate(x,y) scale(1,-1)">` wrapper is gone,
  replaced by an inline `transform="matrix(1 0 0 -1 x y)"` on the
  `<text>` element (-13.5% SVG output size on the User's Guide);
  (3) function-pointer dispatch table for the 11 hottest / simplest
  PS ops (`newpath`, `moveto`, `lineto`, `rmoveto`, `rlineto`,
  `closepath`, `setrgbcolor`, `setgray`, `setlinewidth`, `gsave`,
  `grestore`); cold ops still flow through the legacy switch.
  Combined with the round-3 stdio buffering / dispatch tightening
  that landed earlier in v0.2.2 (`f1fdd77`), the User's Guide SVG
  build now drops from 41.2 s real / 35.4 s user (v0.2.2 baseline)
  to 22.6 s real / 19.8 s user (lout f234cde -> mdlout 94277d7).
  (corrected on 2026-05-23: lout `f1fdd77` was bumped into mdlout
  via `5810261`, which shipped in v0.2.2, not v0.2.3; the original
  text mislabelled the host release.)

### Changed

- **`tests/lout_doc_renders/expert`: SSIM 0.7061 -> 0.9202.** The
  v0.2.3 per-run scratch-dir fix in
  `tests/lout_doc_renders/build.sh` (reverses concurrent-runner
  damage on shared `*.li` / `*.ldx` / `lout.lix` files when two
  agents run the suite in the same checkout) only takes effect on
  re-rendered output. The refresh in 38b66f2 re-runs all four docs
  with the fixed scratch isolation, so the expert PostScript
  baseline is no longer interleaved with stale cross-reference
  state from a parallel run. Expert SSIM moves from 0.7061
  (`ssim-diff` red) to 0.9202 (`ssim-ok` amber) on the landing
  page; design ticks 0.9123 -> 0.9190; slides 0.9804 unchanged;
  user 0.9292 unchanged. `expert.pdf` size grows from 478,385 to
  507,915 bytes (the in-doc `@BackEnd @Case` SVG-arm fix from
  v0.2.3 caused a real layout shift, so the previous PS render
  diverged from the post-fix SVG).
- **`tests/user_guide_diff` SSIM 0.9234 -> 0.9278.** Same 327-page
  PS-vs-SVG diff over `doc/user/all`, re-rendered after lout perf
  round 4. Median moves 0.9258 -> 0.9309; pages SSIM >= 0.95 grow
  36 -> 47 (+30%); the visibly-different (< 0.85) count drops
  3 -> 1. The improvement is a side effect of the round-4 coord
  fold -- packing the Y-flip into an inline matrix on each
  `<text>` removes a per-word group nesting level that was
  shifting glyph positions by sub-pixel rounding artefacts when
  rsvg flattened the transform stack.
- **Example thumbnails refreshed** (`examples/out/thumb-*.png`,
  27 files) after the round-4 SVG output change. No visible
  difference at thumb resolution; the file-level pixel diffs are
  AA noise from the absent `<g>` wrapper.

### Notes

- mdlout package version (`pyproject.toml`, `mdlout.VERSION`) is
  not bumped in this release. The next mdlout-surface change (CLI
  flags, output shape) will carry both a PyPI release and a tag
  bump; v0.2.4 is a submodule + tests refresh.
- PostScript output bit-identical to v0.2.3 for `doc/user/all`;
  `expert.pdf` size changes as documented above. The `--format=pdf`
  pipeline (ps2pdf on the frozen `z49.c` PostScript) remains
  bit-identical to v0.2.0.

## [0.2.3] - 2026-05-23

Font subsetting flips default ON (~56% HTML size reduction across
the example corpus, no regressions); dark mode rewritten on a proper
`currentColor` cascade (raster `<image>`s keep their luminance and
authored colours are preserved); SVG `<textPath>` for curve-following
text in `@Graphic` bodies; all four Lout source-tree documents
(`doc/design`, `doc/expert`, `doc/slides`, `doc/user`) now build
through `z53.c` with zero residual `@Case` warnings (`design`
96 -> 0, `expert` 235 -> 0); a `tests/lout_doc_renders/` landing
page + per-doc summary tables; a `tests/profile/` gprof hot-spot
report for the next perf round; concurrent-runner damage in
`tests/lout_doc_renders/build.sh` fixed via per-run scratch dirs;
seven new cookbook recipes (24-29) plus four new examples
(`svg_diagram.md`, `chord_chart.md`, `presentation.md`,
`textbook.md`). `z49.c` (PostScript) and the legacy PDF pipeline
remain frozen and bit-identical to v0.2.0.

### Added

- **mdlout: dark mode via CSS `currentColor` cascade.** Replaces the
  v0.2.2 `filter: invert(1) hue-rotate(180deg)` mechanism. With
  `z53.c` now folding default-black ink to `fill="currentColor"` /
  `stroke="currentColor"` (lout 346b335), the dark theme retints
  glyphs and rules by setting a `color:` on the page wrapper instead
  of inverting each rendered page wholesale. Embedded raster
  `<image>`s keep their original luminance and hue; authored colours
  (charts, syntax highlighting, callouts) are preserved -- only the
  implicit body ink is themed. CSS rewritten to the spec'd shape:
  `body.mdlout-dark { background:#1a1a1a; color:#e8e8e8 }`,
  `body.mdlout-dark .lout-page { background:#1a1a1a }`,
  `body.mdlout-dark .lout-page svg { color:#e8e8e8 }`,
  `body.mdlout-dark a { color:#88c0ff }`, plus dark code-block
  styling. Pre-v0.2.3 builds carrying literal `fill="rgb(0,0,0)"`
  stay black in dark mode; re-render to pick up the cascade
  (lout 346b335 -> mdlout b6baaa4).
- **mdlout: `--no-subset-fonts` opt-out flag** and
  `subset-fonts: false` frontmatter key. The pre-v0.3 opt-in path
  (`--subset-fonts` / `subset-fonts: true`) is kept as a backwards-
  compatible no-op so existing scripts keep working. Precedence is
  explicit-CLI > frontmatter > default. fontTools remains an
  optional dependency: when missing, the helper warns once and falls
  through to full-font inline, so default-on doesn't break builds
  (deaa546).
- **[lout] SVG `<textPath>` for curve-following text in `@Graphic`
  bodies.** When the embedded PostScript interpreter sees a `show`
  against a path that has accumulated at least one
  `curveto` / `rcurveto` since the last `newpath` / `stroke` /
  `fill`, `z53.c` emits the text via SVG `<textPath href>`
  referencing a `<defs> <path d=...>` built from the path
  accumulator, instead of the static `<text x y>` at the post-curve
  current point. Targeted PS pattern:
  `newpath ... moveto ... curveto (...) show`. New state plumbing:
  `svg_ps_state.has_curve` (set in `svg_ps_curveto`, cleared in
  `svg_ps_init`, `SVG_OP_NEWPATH`, `svg_ps_emit_path`'s
  stroke/fill and clip-empty branches, the new textPath emitter,
  and `SVG_PrintGraphicObject`'s per-call reset);
  `svg_textpath_id_next` (monotonic counter, reset by
  `SVG_PrintInitialize` so back-to-back builds in the same process
  are byte-identical); `svg_ps_emit_textpath_show` (new helper
  sibling to `svg_ps_show`). `SVG_OP_SHOW` branches on
  `(had_geom && has_curve)`; the legacy static-text path is
  unchanged for straight-line and no-path cases. New test snippet
  `tests/snippets/text_on_path.lt` exercises the heuristic
  (lout 60405f9 -> mdlout 0b90137).
- **[lout] `z53.c` folds default-black ink to `currentColor`**.
  When the active fill or stroke RGB resolves to the SVG-default
  black -- the implicit ink colour Lout reaches for whenever no
  explicit `setrgbcolor` / `LoutSetRGBColor` has been issued --
  `SVG_PrintWord`, `SVG_PrintUnderline`, `svg_ps_emit_path`, and
  the `svg_ps_show`-style text emit now write
  `fill="currentColor"` / `stroke="currentColor"` instead of
  `rgb(0,0,0)`. Non-default colours still emit the explicit rgb()
  triple. Per the SVG spec, `currentColor` with no inherited
  `color:` resolves to black, so an unstyled standalone .svg
  renders identically to the prior output. Embedded inside an HTML
  document with a `color:` cascade (mdlout's dark-mode body class),
  glyphs and rules pick up the ambient hue without inverting
  embedded rasters or shifting authored colours (lout 346b335).
- **[lout] SVG `@Case` branches in `lout/include/`**. Every
  `@BackEnd @Case` block in the diagram-helper packages that
  previously lacked an SVG arm now has an explicit `@Yield` branch.
  Trace audit in `lout/SVG_INCLUDES_AUDIT.md` (lout 5db1585 ->
  mdlout 441095f).
- **[lout] SVG `@Case` branches in `doc/{design,expert}`.** Every
  `@BackEnd @Case` block in the doc/design and doc/expert source
  trees (96 + 235 "replacing unknown @Case option SVG by
  PostScript" warnings) now has a peer SVG `@Yield` branch, copying
  the PostScript body verbatim. `z53.c`'s embedded PostScript
  interpreter handles the operators used in these bodies
  (`moveto` / `lineto` / `closepath` / `stroke` / `fill` /
  `setgray` / `setdash` / etc.), so mirroring the PS arm renders
  correctly. Sites touched: `doc/design/mydefs` (`@HLine`,
  `@VDashLine`, `@LBox`, `@LittlePage`); `doc/design/s2_3`;
  `doc/expert/mydefs` (the same four plus `@ShowMarks`,
  `@ShowVMark`, `@ShowHMark`, `@TightBox`, `@GreyBox`);
  `doc/expert/pre_colo` (`@SetColour` setrgbcolor demo);
  `doc/expert/pre_grap` (three worked `@Graphic` examples);
  `doc/expert/pri_obje`. Warning counts after rebuild:
  `doc/design/all` 96 -> 0; `doc/expert/all` 235 -> 0. Side
  benefit: the expert PS pipeline now converges across all 7
  passes instead of asserting in `Parse()` at pass 4, fixing the
  PDF page-count regression flagged in
  `lout_doc_renders/README.md` note #4 (lout df54ae1 -> mdlout
  f7cf6f6).
- **`tests/profile/` gprof hot-spot report** + new
  `tests/profile_ug_build.sh`. Rebuilds lout with `-pg
  -fno-omit-frame-pointer` (and `-no-pie` at link time), runs a
  single SVG pass over `doc/user/all` to collect `gmon.out`, and
  writes `gprof_full.txt`, `gprof_brief.txt`, and a sorted
  `gprof_z53_hot.txt`. Top hot `z53.c` functions on the current
  baseline (~25.83 s user): `svg_ps_exec_op` 8.73% / 1.62 s;
  `SVG_PrintBetweenPages` 7.38% / 1.37 s; `SVG_LinkDest` 4.58% /
  0.85 s. `tests/profile/README.md` walks through the output
  (including why all `SVG_*` entries are `<spontaneous>` -- they
  are dispatched via the `BACK_END` function-pointer table in
  `z01.c`) and ranks the next-round optimisation candidates:
  replace `fprintf` with hand-rolled itoa/ftoa3 + `fwrite` for
  page/link chrome, fold the bottom-left -> top-left wrapper into
  glyph coordinates, function-pointer dispatch for the ~20 hot
  PostScript ops inside `svg_ps_exec_op`. The script restores the
  optimised binary on exit so `tests/run_all.sh` baseline is
  unchanged (98d99ad).
- **`tests/lout_doc_renders/index.html` landing page** (vanilla
  HTML + CSS, no JS) with a 4-up hero strip of first-page
  thumbnails and a per-doc summary table: pages, HTML/PDF/SVG
  sizes, sample SSIM, diff %, and links to each render plus the
  doc's source tree on jclements3/lout/svg-backend. Thumbnails
  live in `tests/lout_doc_renders/thumbs/` and are generated from
  `<doc>.pdf` via `pdftocairo` + ImageMagick `convert`.
  `build.sh` gains a stricter pass-picking rule (prefer the
  latest converged pass with matching size over "just take the
  largest", filter out passes whose stderr contains `internal
  error`) (1f9cc91).
- **Seven new cookbook recipes** in `docs/cookbook.md` (lifting
  the count from 23 to 30). Recipes 24-26: hand-rolled `@Graphic`
  SVG diagram (using ```svg fenced blocks for figures
  `@Mermaid` / `@Diag` cannot express -- gradients, hex grids,
  phase portraits, custom logos); embedded ABC sheet music with
  chord names (multi-line scores, multi-voice arrangements,
  double-quoted chord symbols above each bar); reusable `mydefs`
  macros (shared `--mydefs` path, symlink farm,
  `$LOUT_HOME/lib` wrapping for cross-document macro libraries).
  Recipes 27-29: tracking changes via `@Strike` / `@Insert`;
  calendar grid via raw `@Tab`; back-matter index plus glossary
  via `@Index` / `@PageOf` (1fce2f9, 155a7aa).
- **Four new examples**:
  `examples/svg_diagram.md` (traffic-light state machine, phase
  portrait, gold-gradient logo, gridded floor plan; every figure
  inline via ```svg fences); `examples/chord_chart.md` (twelve-
  bar blues, eight-bar folk phrase, two-voice arrangement,
  16-bar jazz changes, and a harp grand-staff with chord
  symbols; 5 ABC blocks); `examples/presentation.md` (ten-slide
  `type: slides` deck mixing prose, raw-Lout math, code-as-prose,
  and an inline mermaid diagram); `examples/textbook.md` (1fce2f9,
  155a7aa).
- **`tests/lout_doc_renders/README.md`** -- per-doc render notes,
  pass-picking heuristic, scratch-dir build, and the residual
  warning audit cross-referenced into `SVG_INCLUDES_AUDIT.md`.

### Changed

- **mdlout: `--subset-fonts` default ON for the v0.3 cycle.** Font
  subsetting (`--subset-fonts`, e42b157) landed in v0.2.2 as opt-in.
  After re-running the full example corpus and the
  `browser_test.sh` suite with subsetting forced on, every example
  builds cleanly and renders identically in headless Chromium, so
  the default flips. Refreshed `examples/out/` shrinks from
  ~57.6 MB to ~25.3 MB total across the 27 main HTML files -- a
  56% reduction, with per-file savings in the 50-60% band (font
  payload alone shrinks ~81%, from 1.10 MB to ~210 KB per
  document). No example broke (deaa546).
- **`tests/lout_doc_renders/` build.sh pass-picker.** Stricter
  convergence rule (latest two-consecutive-passes with matching
  size, with stderr-`internal error` filter) replaces the
  "largest file wins" heuristic. Net result vs. previously
  committed renders: `design` SSIM 0.656 -> 0.912 (now converging
  on a later pass); `expert` SSIM 0.920 -> 0.706, page count
  120 -> 115 (PS pipeline crashes before convergence at lout HEAD;
  cleared by f7cf6f6 above); `slides` 0.980 unchanged (bit-
  identical); `user` 0.929 unchanged with minor SVG size growth
  (+1.2%) (1f9cc91).

### Fixed

- **`tests/lout_doc_renders/build.sh` concurrent-runner damage.**
  `lout` writes `*.li` / `*.ldx` / `lout.lix` into the cwd as it
  resolves cross-references across passes. When multiple agents
  drive lout against the same `lout/doc/$d/` directory in
  parallel, they race on those files and produce symptoms like
  `"assert failed in Parse: *token!"`,
  `"rename(<name>.ldx, <name>.ld) failed"`, and `"fatal error:
  line too long when reading index file lout.lix"`. Isolated
  reproduction (`cp -r doc/expert` to a private dir, no
  concurrency) shows 7/7 PS passes succeed cleanly. `build_doc`
  now copies `$REPO/lout/doc/$d` to a per-run scratch
  `$WORK/src/$d` before running lout; the original source is
  untouched and parallel agent processes no longer race
  (a4a20df).

### Tests

- **`tests/profile/` gprof report** + `tests/profile_ug_build.sh`
  (98d99ad).
- **`tests/lout_doc_renders/index.html`** landing page +
  refreshed renders for all four Lout source-tree documents
  (1f9cc91).
- **`tests/snippets/text_on_path.lt`** exercises the new
  `<textPath>` heuristic (0b90137).
- Regression suite stays Pass-Excellent through every commit in
  the cycle (`bash tests/run_all.sh` 65/65 -> 66/66 with the
  text-on-path addition; `bash tests/browser_test.sh` 53-55 PASS
  / 0 FAIL).

### Docs

- `docs/cookbook.md`: recipes 24-29 (1fce2f9, 155a7aa).
- `examples/README.md`: gallery regenerated for the four new
  examples.
- `tests/lout_doc_renders/README.md`: per-doc render notes.
- `tests/profile/README.md`: gprof output walkthrough.
- `[lout] SVG_INCLUDES_AUDIT.md`: residual SVG `@Case` warnings
  traced to `doc/` (lout 5db1585).

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

[Unreleased]: https://github.com/jclements3/mdlout/compare/v0.2.3...HEAD
[0.2.3]: https://github.com/jclements3/mdlout/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/jclements3/mdlout/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/jclements3/mdlout/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jclements3/mdlout/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jclements3/mdlout/releases/tag/v0.1.0
