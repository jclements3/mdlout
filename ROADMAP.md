# mdlout Roadmap

Forward-looking plan for the mdlout converter and its forked Lout
(`lout/` submodule, branch `svg-backend`). Backwards-looking release
notes live in [CHANGELOG.md](CHANGELOG.md).

This document is a living target list, not a contract. Anything in
"Near-term" / "Mid-term" may slip; anything in "Won't do" really
won't.

## What v0.2 ships

The v0.2 line is the "HTML by default" release. It lands an SVG back
end (`lout/z53.c`, ~5400 LOC) sibling to the frozen PostScript path
(`z49.c`); an embedded PostScript interpreter inside `z53.c` that
turns `@Graphic` PS prologues into SVG drawing ops; real Type 1
glyph outlines for `charpath` via the URW++ / Ghostscript `.pfb`
files (`lout/z53_glyph.c`); five passthrough macros (`@Math`,
`@DMath`, `@ABC`, `@SVG`, `@SVGFile`) with PostScript-mode
fallbacks; a WCAG 2.1 AA accessibility scaffold in the HTML wrapper
(landmarks, ARIA, skip-link, alt-text manifest, image-alt sidecar);
URW++ Nimbus base-35 fonts inlined as `@font-face` data URLs so
browser rendering matches Ghostscript's font substitution -- with
font subsetting default-ON in v0.2.3 (`--no-subset-fonts` opts
out), trimming each face to the codepoints actually referenced
(~56% HTML size reduction across the example corpus); a
headless-Chrome regression runner that verifies KaTeX, abcjsharp,
mermaid, anchors, and highlight.js execute client-side; dark-mode
CSS (`--dark` / `theme: dark`) via a `currentColor` cascade
(v0.2.3) so embedded raster `<image>`s keep their luminance and
authored colours are preserved; SVG `<textPath>` for curve-
following text in `@Graphic` bodies (v0.2.3); a PEP 621
`pyproject.toml` that builds a clean sdist + wheel; and end-to-end
SVG renders of all four documents that ship with the Lout source
tree (`design`, `expert`, `slides`, `user`, with zero residual SVG
`@Case` warnings as of v0.2.3). The 327-page
User's Guide PS-vs-SVG diff sits at mean SSIM **0.9441** at the new
150 DPI baseline (was 0.9283 at 100 DPI on the same corpus, after
v0.2.5); the 70-snippet single-feature suite is 100% Pass-Excellent
under the post-v0.2 tightened thresholds (5% AE for text, 2% AE /
SSIM 0.95 for graphics-heavy). Build size: ~848 KB
lout binary, 150 KB single-file mdlout.py. User's Guide SVG build:
~22.6 s real / ~19.8 s user on the reference host after v0.2.4
perf round 4 (was ~26-29 s in v0.2.2 round 2, ~32 s in v0.2.1,
~7 min mid-v0.2 cycle; the original v0.4 < 30 s stretch target
is now cleared by ~7 s).

## Shipped in v0.2.9

Same-day follow-on to v0.2.8. Lands the `ps2pdf` page-size
passthrough in `mdlout.py` (closes the A0 / A3 / Legal clip-to-A4
gotcha), grows the snippet corpus 85 → 90, adds three new
full-document examples (`poster_a0.md` A0 scientific poster,
`journal.md` single-column academic article, `article.md`
catch-up), extends the cookbook 41 → **50** recipes (42-50), and
formally defers cross-token kerning on slides p032 in
`SVG_PORTING.md` (#188).

- **mdlout `ps2pdf` page-size passthrough** (commit `04ac23a`,
  issue #198). `--format=pdf` now reads `page:` / `orientation:`
  from frontmatter and passes `-dDEVICEWIDTHPOINTS` /
  `-dDEVICEHEIGHTPOINTS` / `-dPDFFitPage` to `ps2pdf`, so A0 /
  A3 / Legal / Letter sheets no longer silently clip to A4.
  Frontmatter without an explicit `page:` field keeps the A4
  default — existing documents are byte-identical.
- **Regression corpus 85 → 90** (commit `49b184e`). Five new
  PASS-EXCELLENT snippets: `text_textpath_curveto_chain` (3-segment
  `<textPath>` chain), `graphic_polar_plot` (polar rose via raw
  PS), plus three more `@Diag` / `@Tab` / `@Eq` corner cases.
- **`examples/poster_a0.md` + `examples/article.md`** (commit
  `6096e35`). A0 portrait scientific poster (single 2380×3368 pt
  page; exercises the new ps2pdf page-size passthrough end to end)
  plus a catch-up commit of the 2-column scientific paper from
  the parallel article-writing agent.
- **`examples/journal.md`** (commit `f7aea00`). Single-column
  academic journal article, 9-page Letter PDF / 8-page HTML,
  seven `@Section` blocks with multi-line abstract via YAML
  literal block.
- **Cookbook recipes 45-47 + 48-50** (commits `5d6b720`,
  `483d391`). Recipe count 41 → **50**: bulk-rendering folders,
  line-level deep-links into fenced code blocks, external
  figures via absolute-path `@SysInclude`, sharing a `mydefs`
  file across documents, title-page logos, and mixed-cell
  tables.
- **`tests/improvements_summary.html`** (commit `29cc6e8`).
  352-line session-at-a-glance dashboard with inline-SVG charts
  (UG mean SSIM history, UG build wall time, snippet corpus,
  cookbook count) and the v0.2.0-v0.2.8 release timeline.
- **CHANGELOG TOC + compare-link footer completion** (commit
  `60e9677`).
- **[lout] `SVG_PORTING.md`: cross-token kerning on slides p032
  formally deferred** (submodule commit `628c893`, mdlout commit
  `58015b6`, #188). Only 2 of 70 `<text>` elements on p032 are
  truly adjacent same-style pairs; SVG's positioning/kerning
  coupling makes the merge-into-`<tspan>` fix net-negative.
  Residual signal correctly re-attributed to the rasteriser-AA
  floor.

## Shipped in v0.2.8

Same-day follow-on to v0.2.7. Lands the `xml:space="preserve"`
predicate in `z53.c` (closes the slides p019 column-alignment drift),
grows the snippet corpus 80 → 85 with five v0.2.5-v0.2.7
feature-lock snippets, and adds `examples/menu.md` (a 2-column A4
restaurant menu in Palatino exercising the right-tab leader idiom).

- **`z53.c` `xml:space="preserve"` predicate** (submodule commit
  `069d60e`). `SVG_PrintWord` marks `<text>` elements with
  `xml:space="preserve"` when the word starts or ends with a space,
  or contains a run of two-or-more internal spaces — the cases
  where SVG renderers' default whitespace collapse would visibly
  drop characters. Slides p019 SSIM lifts 0.9441 → **0.9811** at
  150 DPI; p032 (already tokenised into per-word `<text>`) is
  unchanged. Words without significant whitespace keep the historic
  opener byte-for-byte, so the bulk of every document is unchanged.
- **Regression corpus 80 → 85** (commit `8ac11a0`). Five new
  single-feature snippets locking in v0.2.5-v0.2.7 work: kerned
  ligatures (`AV` / `Wa` / `To` + fi / fl / ffi), default-colour
  `currentColor` fold, `@Verbatim` multi-space column alignment
  (exercises the new predicate end-to-end), smcp/onum synthesis
  off-branch, and ABC chord-name overlays with `|`/`:` attribute
  escaping. All PASS-EXCELLENT under the post-v0.2 tightened
  thresholds.
- **`examples/menu.md`** (commit `aac7dc6`). 2-column A4
  restaurant menu in Palatino exercising the multi-column
  page-layout path and the right-tab leader idiom (dish prices
  aligned on the right margin via `@RightDisplay { ... @Tab ... }`).
  Builds clean in both `--format=html` and `--format=pdf`.

## Shipped in v0.2.7

Same-day follow-on to v0.2.6. Lands the slides p040 font-propagation
fix in `z53.c`, grows the snippet corpus 70 → 80, parameterises
`tests/lout_doc_renders` at 150 DPI, adds a 200 DPI sensitivity row
confirming the AA / hinting structural floor, hardens `--serve`
against busy ports, polishes the presentation + textbook examples,
and brings the cookbook to **41** recipes.

- **`z53.c` `SVG_DefineGraphicNames` font propagation** (slides
  p040 fix; submodule commit `c9142c1`). `@Graphic` prologue PS
  ops (e.g. the slides section-marker glyph) were drawing in the
  back-end's last-known font instead of the galley-local font set
  by the surrounding `@Heading`. The fix threads the galley font
  through into the embedded PS interpreter's initial graphic
  state.
- **200 DPI sensitivity baseline confirms the structural floor**
  (commit `d3fc1ca`). Mean SSIM at 200 DPI is **0.9510**
  (vs 0.9441 at 150 DPI, +0.0069); worst-10 slope flattens from
  +0.0334 (100 → 150) to +0.0107 (150 → 200), below the
  "more room to chase" threshold. The 150 DPI baseline is the
  release-gate; the "shared rasteriser" mid-term item is the only
  way to close the remaining gap.
- **Regression corpus 70 → 80** (commit `5ef1b02`). 10 new
  snippets all PASS-EXCELLENT: equation column alignment,
  dashed `@Diag` lines, bar-chart `@Graph`, captioned figures,
  multi-footnote pages, `@Include` of a sibling fragment, ABC
  chord tables, rotated `@Tab` headers, sub/superscript chains,
  raw PostScript via `@Graphic`.
- **`tests/lout_doc_renders` DPI override + 150 DPI column**
  (commit `58f7bc9`). Mirrors `user_guide_diff.sh`'s
  parameterisation; `SKIP_DOC_BUILD=1` reuses `/tmp/` artefacts
  for fast re-diffing.
- **`mdlout --serve` probes 20 ports if default is busy** (commit
  `443c895`). Tries `PORT..PORT+19`, logs the chosen port,
  exits 2 only if all 20 are taken.
- **`mdlout --version` reports lout binary version + submodule
  revision** (PR #194). Two-line banner; graceful degradation on
  partial checkouts.
- **Cookbook recipes 39-41** (commit `037f921`; recipe count
  38 → **41**): dual-language documents, per-section font
  switching, embedding YouTube / video in HTML output.
- **`presentation.md` / `textbook.md` polish** (commit `b90bd3b`).
  Section-divider slides + closer for presentation; worked
  exercise set, two `@Diag` figures, and `@Cite` bibliography
  for textbook.
- **`chapter3_pagination_drift_investigation.md`: 150-DPI
  follow-up** (commit `fdd0fc0`). #109's "antialiasing-only"
  conclusion holds at 150 DPI — worst-10 mean lifts 0.7964 →
  0.8298, glyph-overlay shape is bit-identical, so the residual
  is rasteriser AA, not layout.

## Shipped in v0.2.6

Same-day follow-on to v0.2.5. Closes the smcp/onum consumer-side
item that v0.2.5's GSUB parser was waiting on, and re-baselines the
regression harness at 150 DPI.

- **smcp/onum consumer-side emission** (was the second half of
  v0.4 "text shaping", and the explicit "queued for v0.2.6 under
  PR #167" carry-over from v0.2.5). `z53.c` now emits GSUB-
  substituted glyphs as `<path d="...">` outlines for body text:
  substituted glyphs have no Unicode codepoint, so a `<text>`-based
  emission could not reference them; the consumer switches whole
  words that contain at least one substituted byte over to path
  mode. Activation is opt-in via frontmatter
  `font-features: smcp,onum` (mdlout.py sets
  `LOUT_SVG_FONT_FEATURES` in the child process) or via the raw
  env var for `.lt` authoring. Snippet `text_smcp_active.lt` lands
  PASS-EXCELLENT at AE-ratio 0.19%, SSIM 0.9947.
- **Path-emit hot-loop LRU cache** (perf follow-on to the consumer
  landing). Caches decoded glyph `d`-strings per `(font, gid,
  size)`; ~2.4-2.7x speedup on smcp-heavy builds. SVG output
  byte-identical to the pre-cache build across the regression
  suite.
- **DPI investigation → 150 DPI default** (was an open
  measurement question from the chapter-3 pagination-drift
  investigation: how much of the 5% AA floor is rasteriser-
  resolution-bound?). All regression rasters now run at 150 DPI;
  mean SSIM on the 327-page UG diff lifts 0.9283 → **0.9441** on
  the same corpus. Snippet pass / fail verdicts byte-identical to
  the 100 DPI run; 100 DPI numbers retained in
  `snippet_history.jsonl` for trend continuity.
- **`tests/user_guide_diff` default PASSES 7 → 8** (commit
  `7fefdcd`). The v0.2.5 ligature width shifts pushed the
  cross-reference loop past 7 passes; defaulting to 8 restores
  convergence.
- **`tests/lout_doc_renders` refresh against v0.2.5 fixes**
  (commit `b170c22`). SSIMs tick up modestly across the four
  documents; SVG byte sizes shrink (design 2.4 → 2.0 MiB, expert
  6.0 → 5.1 MiB); User SVG wall time **319 s → 237 s**.
- **`tests/snippet_history_sparklines.html` + deep-link routing**
  (commit `621c3a7`). 70-card CSS-grid landing page with inline
  SVG sparklines of the AE pixel-diff ratio over the last 20
  runs; hash routing on the per-snippet detail viewer.
- **Cookbook recipes 36-38** (commit `a7597e7`; recipe count
  35 → **38**), **`examples/index.md` docs landing page**
  (`f03d5e1`), and **`examples/cv.md` single-column rewrite**
  (`b220c58`).

## Shipped in v0.2.5

Same-day follow-on to v0.2.4. First wave of text-shaping work plus a
batch of docs and tests upkeep.

- **fi/fl/ffi/ffl ligature substitution** (was v0.4 mid-term).
  `svg_emit_word_text` walks each Lout word with a 2-3 byte
  lookahead and folds the digrams `fi`/`fl` and trigrams
  `ffi`/`ffl` into U+FB01-U+FB04 when the active font family is in
  the Adobe-Type serif allowlist (Times, Palatino, Bookman,
  Schoolbook, Chancery, Garamond, ITC\*, NimbusRomNo9L\*,
  URWPalladio\*). Visible on text-heavy User's Guide chapters;
  cumulative mean SSIM 0.9234 -> 0.9283 vs the v0.2.3 baseline.
- **Per-font 256x256 kern table precompute** (perf follow-on to
  v0.2.4 round 4). Replaces the per-gap `FontKernLength()` linear
  scan with a single array index; ~1.5 MB heap for a typical
  12-face document. SVG output byte-identical to the pre-cache
  build across all 74 snippet SVGs.
- **GSUB parser for `smcp` / `onum`, parser-only** (first half of
  the v0.4 "text shaping" item). CFF/OTF + Lookup Type 1 in this
  phase; the consumer side is queued for v0.2.6 under PR #167.
  Ligature / contextual / chained / extension subtables and
  TrueType GSUB are deferred (noted in `SVG_PORTING.md`).
- **`docs/FAQ.md`, tutorial refresh, cookbook 33-35.** Closes the
  "more cookbook recipes" near-term item (recipe count 32 -> 35,
  covering bibliography idioms, multi-language documents at the
  Lout-language level, and a longer-form `@Diag` walkthrough).
- **`examples/gallery.md`** (54-page mdlout-rendered showcase).
- **`tests/browser_test.sh --with-math-strict`** opt-in mode for
  CI math regressions.

## Shipped in v0.2.4

Same-day perf + tests-hygiene cut on top of v0.2.3.

- **User's Guide SVG build < 23 s** (originally a v0.4 stretch
  beyond the v0.2.2 sub-30s target). `z53.c` perf round 4
  (hand-rolled `svg_itoa` / `svg_ftoa3` for page/link chrome,
  coord-folded Y-flip on text emission, function-pointer dispatch
  for the 11 hottest PS ops) drops single-pass wall time from
  41.2 s (v0.2.2 baseline) to 22.6 s real / 19.8 s user. -45%
  cumulative over rounds 3-4; -13.5% SVG output size on
  `doc/user/all` from the coord fold alone.
- **`tests/lout_doc_renders/expert` SSIM recovery** (regression
  surfaced post-v0.2.3). The per-run scratch-dir fix from v0.2.3
  only takes effect on re-rendered output; refreshing all four
  docs lifts expert from 0.7061 (`ssim-diff` red, mis-attributed
  to back-end drift) to 0.9202 (`ssim-ok` amber). No back-end
  change; the v0.2.3 in-doc `@BackEnd @Case` SVG-arm fix caused
  a real layout shift, so `expert.pdf` grows 478 KB -> 508 KB.
- **`tests/user_guide_diff` mean SSIM tick** (side effect of
  round 4). 0.9234 -> 0.9278; pages SSIM >= 0.95 grow 36 -> 47
  (+30%); pages SSIM < 0.85 drop 3 -> 1. The improvement comes
  from removing a per-word `<g>` wrapper that was costing
  sub-pixel rounding error on the rsvg flatten step.

## Shipped in v0.2.3

These items were on the v0.3 candidate list (and a few were
surfaced for v0.3 by issue #135); they landed during the v0.2.3
cycle and are no longer roadmap candidates.

- **Font subsetting default-ON** (was v0.3). `--subset-fonts`
  flipped to default after re-running the full example corpus
  and `browser_test.sh` suite with subsetting forced on:
  `examples/out/` shrank from ~57.6 MB to ~25.3 MB (56%
  reduction; font payload ~81% smaller). Opt-out via
  `--no-subset-fonts` / `subset-fonts: false`.
- **SVG `@Case` branches in `lout/include/`** (was v0.3). Every
  diagram-helper-package `@BackEnd @Case` block now has an
  explicit SVG arm.
- **SVG `@Case` branches in `doc/{design,expert}`** (was v0.3,
  surfaced by all-Lout-docs render). 96 + 235 "replacing unknown
  @Case option SVG by PostScript" warnings -> 0. The `expert` PS
  pipeline now also converges across all 7 passes instead of
  asserting in `Parse()` at pass 4.
- **`@Graphic` ops `lightgrey` / `lfig` / `solid`** (was v0.3,
  from issue #135). Folded into the `svg_graphic_concat` spacing
  fix so all three no longer surface as rate-limited XML
  comments.
- **SVG `<textPath>` for curved text** (new, not on prior
  roadmap). When the embedded PS interpreter sees `show` against
  a path containing at least one `curveto`, `z53.c` emits the
  text via `<textPath href>` instead of static `<text x y>`.
- **Dark mode via proper `currentColor` cascade** (v0.2.2
  follow-on). `z53.c` now folds default-black ink to
  `fill="currentColor"`, so the dark theme retints by setting a
  `color:` on the page wrapper instead of inverting each page
  wholesale; embedded rasters keep their luminance, authored
  colours are preserved.
- **CFF / TrueType outline parser follow-ups** (carry-over from
  v0.2.2 -- audit comments + `NEXT_OPTIMIZATIONS.md` Expert /
  ExpertSubset known-gap note, now stable in v0.2.3).
- **gprof profile of the User's Guide SVG build**
  (`tests/profile/` + `tests/profile_ug_build.sh`). Sets up the
  next perf round with a ranked candidate list.
- **All four Lout docs rendered through z53.c with a landing
  page** (`tests/lout_doc_renders/index.html` + per-doc summary
  tables). Concurrent-runner damage in `build.sh` fixed via
  per-run scratch dirs.

## Shipped in v0.2.2

These items were originally projected for v0.3 / v0.4; they landed
during the v0.2.2 cycle and are no longer roadmap candidates.

- **TrueType outline support in `z53_glyph.c`** (was v0.4). `.ttf`
  files via sfnt magic detection, head / maxp / cmap / loca / glyf
  walk, quadratic-to-cubic Bezier conversion, composite-glyph
  expansion with 2x2 affine transforms. DejaVu / Liberation / Noto
  and similar system fonts now render real glyph outlines through
  `charpath` instead of falling back to the bbox rectangle.
- **User's Guide SVG build < 30 s** (was v0.4). Hashed glyph-name
  lookup + per-font face-flag cache + `SVG_PrintWord` stdio
  consolidation in `z53.c`. Single-pass wall ~26-29 s, user ~20 s.
- **`@Place` / `@MargPut` operand-stack drift in SVG mode** (was
  v0.3, named in v0.2.1's `SVG_INCLUDES_AUDIT.md`). `LoutPageDict`
  / `LoutPageSet` / `LoutMargSet` / `LoutMargShift` hashed in
  `svg_op_seed[]`. The `translate(x, y)` for `LoutMargShift` is
  still missing -- margin notes still render at the origin --
  tracked as a v0.3 follow-on.
- **AFM kerning in SVG text** -- shipped in v0.2.1 (not v0.3 as
  originally projected). `svg_emit_word_text` consumes
  `FontKernLength` between successive characters and emits the
  kern delta as a `<tspan dx>` inside the `<text>` element.

## Near-term (v0.3 remainder, post-v0.2.3)

The v0.2.3 cycle cleared the bulk of the original v0.3 candidate
list (see "Shipped in v0.2.3" above). Items still pending:

- **`LoutMargShift` translate(x, y).** The v0.2.2 hashed-op work
  cleared the operand-stack drift but did not yet implement the
  margin-note shift itself, so SVG-mode `@MargNote` / `@OuterNote`
  still render at the page origin. Tracked as a follow-on in the
  `z53.c` op-dispatch table.
- **PyPI publish.** The `pyproject.toml` from v0.2.1 builds a
  clean wheel, but the user has not yet pushed it to PyPI. Action
  is manual:
  ```
  python3 -m build
  python3 -m twine upload dist/*
  ```
  Requires the user's PyPI token in `~/.pypirc`. Once published,
  `pip install mdlout` becomes the recommended install path for
  non-contributors.
- **More cookbook recipes** — closed in v0.2.5 (recipe count
  32 -> 35; bibliography idioms, multi-language at the Lout
  level, longer-form `@Diag` walkthrough).

## Mid-term (v0.4 target)

Harder, longer-tail items that haven't started yet.

- **Text shaping: ligatures and combining marks** -- partially
  shipped across v0.2.5 / v0.2.6. fi/fl/ffi/ffl ligature
  substitution landed in v0.2.5 via a 2-3 byte lookahead on the
  Lout-word side (Adobe-Type serif allowlist; Unicode codepoints
  U+FB01-U+FB04). The GSUB table parser for `smcp` / `onum`
  landed parser-only in v0.2.5, and the consumer side
  (path-emission for substituted glyphs without Unicode
  codepoints, with an LRU `(font, gid, size)` cache) shipped in
  v0.2.6 -- so frontmatter `font-features: smcp,onum` is now an
  end-to-end working knob. Still open: combining-mark positioning
  (combining acute / grave / cedilla on Latin Extended-A; visible
  on `multilingual.md`), GSUB Lookup types beyond Type 1
  (ligature subtables, contextual, chained, extension), TrueType
  GSUB, and GPOS-anchor mark attachment. Pulling in the remaining
  stages closes the gap.
- **Shared rasteriser for true pixel parity.** The current ~5%
  antialiasing floor on the User's Guide diff is rsvg vs
  Ghostscript painting the same glyph outlines with different
  AA / hinting choices (confirmed by the chapter-3 pagination
  drift investigation,
  `docs/chapter3_pagination_drift_investigation.md`). Running
  both back ends through a single rasteriser (either by
  generating PostScript from SVG via a shared inverse, or by
  comparing SVG-rendered output to a Chrome `--print-to-pdf`
  baseline instead of Ghostscript) would eliminate the floor.
  Cost: another rendering pipeline to maintain.
- **More aggressive `@Graphic` raw-PS to SVG translation.** The
  embedded PS interpreter in `z53.c` handles the prologue idioms
  emitted by Lout's own `diagf.lpg` / `graphf.lpg` / `tabf.lpg`
  well, but external `@Graphic` payloads (user-supplied raw
  PostScript snippets) still occasionally fall through to
  per-op fallback (a rate-limited XML comment in the SVG). The
  bar to clear is "the PostScript snippets that ship inside
  Adobe AppendixA-style cookbooks". Tracked under TODO 1.4.

## Long-term (v1.0)

The v1.0 line is "mdlout is production-ready for serious documents":
stable CLI, full Lout feature surface working through `z53.c`, and
the documentation to back it.

- **Stable CLI.** Lock the v0.2 flag surface (`--format`, `--watch`,
  `--serve`, the eight `--no-*` opt-outs, `--check`, `--init`)
  behind a semver guarantee. Deprecation cycle for any future
  rename.
- **Full Lout feature surface.** A documented list of every Lout
  construct (`@Section`, `@Eq`, `@Diag`, `@Fig`, `@Tab`, `@Graph`,
  `@Cite`, `@BookSetup`, `@SlidesSetup`, etc.) marked
  green / yellow / red against the SVG back end, with a yellow /
  red item required to land before v1.0 ships. Today the major
  reds are the long-tail @Diag layouts and corner-case @Eq
  typesetting.
- **The case for unfreezing `z49.c` (or maintaining permanent
  freeze).** Today `z49.c` is frozen because the PDF pipeline is
  bit-identical to the pre-z53.c era and any change risks
  silently shifting the legacy output. The choice for v1.0:
  - **Unfreeze**: pick up upstream fixes from the william8000 /
    Kingston tree, accept the bit-identicality break, document
    the new PDF baseline. Lets us reduce the
    `z49.c` / `z53.c` duplication around galley dispatch.
  - **Permanent freeze**: leave `z49.c` alone forever. The
    cost is the duplication; the benefit is a stable PDF.
- **Shared rasteriser for true pixel parity (v1.0 carry-over).**
  See "Mid-term" -- moved earlier in this roadmap because the
  motivation reads the same at v0.4 and v1.0; the v1.0 entry below
  remains as a placeholder for the longer-term feature-surface
  guarantees.

## Won't do

Hard limits. Any of these landing in mdlout would be a
project-redefining choice, not an incremental release.

- **Anything that breaks the Lout source-compatibility contract.**
  Lout documents written for the upstream 3.43 release must still
  build under this fork. The svgmacros library is opt-in
  (`@SysInclude { svgmacros }`); the SVG back end is opt-in
  (`lout -G`); the PDF pipeline is bit-identical. New macros
  may be added; existing semantics may not be changed.
- **Replacing Lout's galley engine.** The galley-based line
  breaking + paragraph filling + figure floating that
  `z18.c` .. `z22.c` implement is the reason mdlout exists.
  Replacing it with (e.g.) Pandoc or a from-scratch Python
  engine would lose every typographic-correctness property
  that motivated picking Lout. New back ends are welcome;
  the galley layer is sacred.
- **Native rendering (no GTK / Qt / web-engine embedding).**
  mdlout produces files (HTML, PDF, PS, SVG, Lout source).
  Anything that opens a window is out of scope. `--serve`
  is a stdlib HTTP server, not a renderer; it points the
  user's existing browser at the rendered HTML on disk.

---

Last updated: 2026-05-23 (v0.2.9). See [CHANGELOG.md](CHANGELOG.md) for
the release history this roadmap projects from, and
[TODO.md](TODO.md) for the working-engineer task list.
