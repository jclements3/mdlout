# mdlout v0.2.3 — font subsetting default ON, all Lout docs rendered, textPath

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.3`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit df54ae1).

Post-v0.2.2 release. Flips `--subset-fonts` to default-ON (~56% HTML
size reduction across the example corpus, no regressions); rewrites
dark mode on a proper CSS `currentColor` cascade so embedded raster
`<image>`s keep their luminance and authored colours are preserved;
lands SVG `<textPath>` for curve-following text in `@Graphic` bodies;
zeroes out the residual `@Case` SVG-arm warnings in
`doc/{design,expert}` (96 + 235 -> 0) so all four Lout source-tree
documents now build cleanly through `z53.c`; adds a
`tests/lout_doc_renders/` landing page and a `tests/profile/` gprof
hot-spot report for the next perf round; fixes concurrent-runner
damage in `tests/lout_doc_renders/build.sh` via per-run scratch
dirs; and ships seven new cookbook recipes (24-30) plus four new
examples.

`z49.c` (PostScript) and the legacy PDF path remain frozen and
bit-identical to v0.2.0.

## Headlines

- **`--subset-fonts` default ON.** Font subsetting landed in v0.2.2
  as opt-in. After re-running the full example corpus and the
  `browser_test.sh` suite with subsetting forced on, every example
  builds cleanly and renders identically in headless Chromium.
  `examples/out/` shrinks from ~57.6 MB to ~25.3 MB total across
  the 27 main HTML files (56% reduction; font payload alone
  shrinks ~81%, from ~1.10 MB to ~210 KB per document). New
  opt-out: `--no-subset-fonts` and `subset-fonts: false`
  frontmatter. The pre-v0.3 `--subset-fonts` / `subset-fonts: true`
  is kept as a backwards-compatible no-op. Precedence is
  explicit-CLI > frontmatter > default. fontTools remains an
  optional dependency; when missing, the helper warns once and
  falls through to full-font inline.

- **Dark mode via CSS `currentColor` cascade.** Replaces the v0.2.2
  `filter: invert(1) hue-rotate(180deg)` mechanism. `z53.c` now
  folds default-black ink to `fill="currentColor"` /
  `stroke="currentColor"` (see next bullet), so the dark theme
  retints by setting a `color:` on the page wrapper instead of
  inverting each rendered page wholesale. Benefits over the old
  filter: embedded raster `<image>`s keep their original luminance
  and hue; authored colours (charts, syntax highlighting,
  callouts) are preserved -- only implicit body ink is themed; no
  browser-side filter cost on large multi-page documents. CSS:

      body.mdlout-dark               { background:#1a1a1a; color:#e8e8e8 }
      body.mdlout-dark .lout-page    { background:#1a1a1a }
      body.mdlout-dark .lout-page svg { color:#e8e8e8 }
      body.mdlout-dark a             { color:#88c0ff }
      body.mdlout-dark code, body.mdlout-dark pre
                                     { background:#222; color:#ccc }

  Pre-v0.2.3 builds carrying literal `fill="rgb(0,0,0)"` stay
  black in dark mode; re-render to pick up the cascade.

- **[lout] `currentColor` for default-black ink.** `SVG_PrintWord`,
  `SVG_PrintUnderline`, `svg_ps_emit_path`, and the
  `svg_ps_show`-style text emit now write `fill="currentColor"` /
  `stroke="currentColor"` whenever the active fill or stroke RGB
  resolves to the SVG-default black. Non-default colours still
  emit the explicit `rgb()` triple. Per the SVG spec,
  `currentColor` with no inherited `color:` resolves to black, so
  unstyled standalone SVGs render identically to the prior
  output.

- **[lout] SVG `<textPath>` for curve-following text.** When the
  embedded PostScript interpreter in `z53.c` sees a `show` against
  a path that has accumulated at least one `curveto` / `rcurveto`
  since the last `newpath` / `stroke` / `fill`, it emits the text
  via SVG `<textPath href>` referencing a `<defs> <path d=...>`
  built from the path accumulator, instead of the static
  `<text x y>` at the post-curve current point. Targeted PS
  pattern: `newpath ... moveto ... curveto (...) show`. New
  test snippet `tests/snippets/text_on_path.lt` exercises the
  heuristic. The legacy static-text path is unchanged for
  straight-line and no-path cases.

- **All four Lout source-tree docs build clean through `z53.c`.**
  Every `@BackEnd @Case` block in `doc/design` and `doc/expert`
  that previously fired "replacing unknown @Case option SVG by
  PostScript" (96 warnings on `doc/design/all`, 235 on
  `doc/expert/all`) now has a peer SVG `@Yield` arm copying the
  PostScript body verbatim. `z53.c`'s embedded PS interpreter
  handles the operators in these bodies, so mirroring the PS arm
  renders correctly. Sites touched include `@HLine`, `@VDashLine`,
  `@LBox`, `@LittlePage`, `@ShowMarks`, `@ShowVMark`, `@ShowHMark`,
  `@TightBox`, `@GreyBox`, the `@SetColour setrgbcolor` demo, and
  three `@Graphic` worked examples. Side benefit: the `expert` PS
  pipeline now converges across all 7 passes instead of asserting
  in `Parse()` at pass 4. `lout/include/*` SVG `@Case` arms also
  audited and rounded out.

- **`tests/lout_doc_renders/` landing page + refreshed renders.**
  Vanilla HTML + CSS landing at `index.html` with a 4-up hero
  strip of first-page thumbnails and a per-doc summary table:
  pages, HTML/PDF/SVG sizes, sample SSIM, diff %, and links to
  each render. `build.sh` gains a stricter pass-picker (latest
  converged pass with matching size, filter out `internal
  error` stderr) and a per-run scratch dir to avoid concurrent-
  runner damage to `*.li` / `*.ldx` / `lout.lix` files.

- **`tests/profile/` gprof hot-spot report.** New
  `tests/profile_ug_build.sh` rebuilds lout with `-pg
  -fno-omit-frame-pointer` (and `-no-pie` at link time), runs a
  single SVG pass over `doc/user/all`, and emits
  `gprof_full.txt`, `gprof_brief.txt`, and a sorted
  `gprof_z53_hot.txt`. Top hot `z53.c` functions on the current
  ~25.83 s user baseline: `svg_ps_exec_op` 8.73% / 1.62 s;
  `SVG_PrintBetweenPages` 7.38% / 1.37 s; `SVG_LinkDest` 4.58% /
  0.85 s. `tests/profile/README.md` ranks the next-round
  optimisation candidates: hand-rolled itoa/ftoa3 + `fwrite` for
  page/link chrome, fold the bottom-left -> top-left wrapper into
  glyph coordinates, function-pointer dispatch for the ~20 hot
  PostScript ops. The script restores the optimised binary on
  exit so the regression baseline is unchanged.

- **Seven new cookbook recipes** (`docs/cookbook.md` 24-30):
  hand-rolled `@Graphic` SVG diagram via ```svg fences; embedded
  ABC sheet music with chord names; reusable `mydefs` macros;
  tracking changes via `@Strike` / `@Insert`; calendar grid via
  raw `@Tab`; back-matter index + glossary via `@Index` /
  `@PageOf`.

- **Four new examples**: `svg_diagram.md` (traffic-light state
  machine, phase portrait, gold-gradient logo, gridded floor
  plan), `chord_chart.md` (5 ABC blocks including a harp grand-
  staff with chord symbols), `presentation.md` (ten-slide
  `type: slides` deck with prose, math, code, and an inline
  mermaid diagram), and `textbook.md`. All build cleanly in
  `--format=html` and `--format=pdf`.

## Regression status

- 65-snippet single-feature suite plus the new `text_on_path.lt`:
  0 Fail, 100% Pass-Excellent under the post-v0.2 tightened
  thresholds (5% AE for text, 2% AE / SSIM 0.95 for graphics-
  heavy).
- All four Lout docs (`doc/design`, `doc/expert`, `doc/slides`,
  `doc/user`) render cleanly through `z53.c` with zero residual
  SVG `@Case` warnings. `expert` PS pipeline now converges across
  all 7 passes (was asserting in `Parse()` at pass 4 in v0.2.2).
- `bash tests/browser_test.sh`: 53-55 PASS / 0 FAIL across the
  cycle.
- PostScript / PDF output bit-identical to v0.2.2.

## Compatibility / migration

- **`--subset-fonts` default flip.** Existing HTML output will
  shrink ~50-60% on next build. If a downstream consumer relies
  on every base-35 codepoint being available at runtime (e.g.
  client-side JS that mutates text content into glyphs the source
  document does not reference), pass `--no-subset-fonts` or set
  `subset-fonts: false` in YAML frontmatter.
- **Dark-mode behaviour change.** Pre-v0.2.3 builds carrying
  literal `fill="rgb(0,0,0)"` SVG output will stay black under
  `--dark`. Re-render to pick up the `currentColor` cascade. The
  CLI surface (`--dark[=force|auto]`, `theme: dark`,
  `dark-mode: true`) is unchanged.
- No CLI flag deprecations. `--no-subset-fonts` is additive;
  `--subset-fonts` kept as a backwards-compatible no-op.

## How to publish the GitHub release (manual instructions)

The release is being published from the v0.2.3 tag on `main`. If
`gh release create v0.2.3 --notes-file docs/RELEASE_NOTES_v0.2.3.md
--latest` succeeds in this run, no further action is required.

If `gh` rejects the create call for OAuth-scope reasons:

1. Push tags and commits:

       git push origin main
       git push origin v0.2.3

2. Publish the release:

       gh release create v0.2.3 \
         --title "v0.2.3 — font subsetting default ON, all Lout docs rendered, textPath" \
         --notes-file docs/RELEASE_NOTES_v0.2.3.md \
         --latest

3. The companion submodule tag `svg-backend-v0.2.3` should already
   be on the `fork` remote (jclements3/lout) and point at commit
   `df54ae1` on branch `svg-backend`. If not, from inside the
   submodule:

       cd lout
       git push fork svg-backend-v0.2.3

Full per-entry details: see
[CHANGELOG.md](../CHANGELOG.md#023---2026-05-23).
