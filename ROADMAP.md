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
User's Guide PS-vs-SVG diff sits at mean SSIM 0.9278 (47 OK / 279
DIFF / 1 BAD / 0 MISSING after v0.2.4); the 65-snippet single-feature suite is
100% Pass-Excellent under the post-v0.2 tightened thresholds (5% AE
for text, 2% AE / SSIM 0.95 for graphics-heavy). Build size: ~848 KB
lout binary, 150 KB single-file mdlout.py. User's Guide SVG build:
~22.6 s real / ~19.8 s user on the reference host after v0.2.4
perf round 4 (was ~26-29 s in v0.2.2 round 2, ~32 s in v0.2.1,
~7 min mid-v0.2 cycle; the original v0.4 < 30 s stretch target
is now cleared by ~7 s).

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
- **More cookbook recipes.** Recipe count is 30 after v0.2.3;
  the next batch targets bibliography / citation idioms,
  multi-language documents at the Lout-language level (not just
  `@Char` / `@Sym`), and longer-form `@Diag` walkthroughs.

## Mid-term (v0.4 target)

Harder, longer-tail items that haven't started yet.

- **Text shaping: ligatures and combining marks.** Today
  `svg_emit_word_text` walks character-by-character with optional
  AFM kern deltas (v0.2.1). It does not consult the font's GSUB
  table for ligature substitution (`fi`, `fl`, `ffi`) or apply
  combining-mark positioning (combining acute / grave / cedilla
  on Latin Extended-A). Both are visible on the multilingual.md
  example and on math-heavy User's Guide pages. Pulling in a
  minimal harfbuzz-shape-style stage (or a hand-rolled GSUB-lookup
  + GPOS-anchor walker against the existing AFM / OT tables)
  closes the gap.
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

Last updated: 2026-05-23. See [CHANGELOG.md](CHANGELOG.md) for
the release history this roadmap projects from, and
[TODO.md](TODO.md) for the working-engineer task list.
