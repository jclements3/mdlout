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
opt-in `--subset-fonts` (v0.2.2) trimming each face to the
codepoints actually referenced (~50% HTML size reduction); a
headless-Chrome regression runner that verifies KaTeX, abcjsharp,
mermaid, anchors, and highlight.js execute client-side; opt-in
dark-mode CSS (`--dark` / `theme: dark`, v0.2.2); a PEP 621
`pyproject.toml` that builds a clean sdist + wheel; and end-to-end
SVG renders of all four documents that ship with the Lout source
tree (`design`, `expert`, `slides`, `user`, v0.2.2). The 327-page
User's Guide PS-vs-SVG diff sits at mean SSIM 0.9234 (38 OK / 289
DIFF / 0 BAD / 0 MISSING); the 65-snippet single-feature suite is
100% Pass-Excellent under the post-v0.2 tightened thresholds (5% AE
for text, 2% AE / SSIM 0.95 for graphics-heavy). Build size: ~848 KB
lout binary, 150 KB single-file mdlout.py. User's Guide SVG build:
~26-29 s wall time on the reference host (v0.2.2 perf round 2,
beats the original v0.4 < 30 s target; was ~32 s in v0.2.1 and
~7 min mid-v0.2 cycle).

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

## Near-term (v0.3 target)

Items surfaced by the v0.2.2 all-Lout-docs render
(`tests/lout_doc_renders/`) plus the still-pending packaging item.

- **SVG `@Case` branches in `lout/include/`.** The all-Lout-docs
  render flagged a small set of `@BackEnd @Case` blocks under
  `lout/include/*` that still lack an explicit SVG arm (today they
  fall through to PostScript or to a generic else). The audit at
  `lout/SVG_INCLUDES_AUDIT.md` enumerates them; the v0.2.2 cycle
  cleared the `bsf` `LoutPageDict` family but the remaining
  arms (mostly diagram-helper packages used by `doc/design`) are
  still pending.
- **More `@Graphic` ops in `z53.c`.** The all-Lout-docs render
  surfaced three under-implemented ops the User's Guide had not
  exercised at the same density: `lightgrey` (used as a fill
  shorthand by several `@Diag` callers), `lfig` (the
  let-fig label-placement helper in `figf.lpg`), and the bare
  `solid` keyword (vs the parameterised `solid 1` already
  implemented). All three are currently rate-limited XML comments
  in the SVG; each is a 5-15 LOC `svg_op_seed[]` entry.
- **Font subsetting default-ON.** v0.2.2 shipped `--subset-fonts`
  as opt-in; the measured savings (~50% HTML size, ~81% font
  payload) and the absence of regressions across the example
  corpus make the default flip a v0.3 candidate. Gate: confirm the
  subset pass survives a full `tests/lout_doc_renders/` build
  (`design` / `expert` / `slides` / `user`) with no glyph
  drop-outs.
- **`LoutMargShift` translate(x, y).** The v0.2.2 hashed-op work
  cleared the operand-stack drift but did not yet implement the
  margin-note shift itself, so SVG-mode `@MargNote` / `@OuterNote`
  still render at the page origin. Tracked as a v0.3 follow-on in
  the `z53.c` op-dispatch table.
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
