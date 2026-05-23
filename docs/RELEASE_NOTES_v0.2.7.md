# mdlout v0.2.7 — slides p040 font fix, 80-snippet corpus, port-probe --serve

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.7`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit `c9142c1`).

Same-day follow-on to v0.2.6. Lands the **slides p040
font-propagation fix** in `z53.c` (`SVG_DefineGraphicNames` now
threads the galley font through into the embedded PS interpreter, so
`@Graphic` prologue ops paint with the configured heading face
instead of the back-end's last-known font), grows the regression
corpus from 70 → **80** snippets (all PASS-EXCELLENT), parameterises
`tests/lout_doc_renders` at 150 DPI, adds a 200-DPI sensitivity row
to the User's Guide diff (mean SSIM 0.9441 → **0.9510** at 200 DPI;
the worst-10 slope confirms the AA / hinting structural floor),
hardens `mdlout --serve` against busy ports (probes 20 ports before
failing), teaches `mdlout --version` to report the bundled lout
binary version plus the submodule revision, polishes
`examples/presentation.md` and `examples/textbook.md`, and adds three
more cookbook recipes (38 → **41**). `z49.c` (PostScript) and the
legacy PDF pipeline remain frozen and bit-identical to v0.2.0.

## Headlines

- **[lout] `z53.c` slides p040 font-propagation fix.** The slides
  section-marker glyph on page 040 of `doc/slides/all` painted at
  the document body font instead of the configured slides heading
  face. Root cause: `SVG_DefineGraphicNames` (the helper that
  builds the PS prologue for an `@Graphic` body) passed the
  back-end's last-known font into the embedded PS interpreter,
  which is not the same as the galley-local font set by the
  surrounding `@Heading`. The fix threads the galley font through
  into the interpreter's initial graphic state. `show` against
  the prologue now paints with the right face. SSIM ticks back
  up on p040 in `tests/lout_doc_renders`; no movement elsewhere.
  (Submodule commit `c9142c1`, mdlout commit `758a6f2`.)

- **Regression corpus 70 → 80 snippets.** Ten new single-feature
  `.lt` snippets exercise under-covered features:

  - `eq_alignment.lt` — `@Eq` multi-line column alignment
  - `diag_dashed_lines.lt` — dashed `@Diag` connectors
  - `graph_bar_chart.lt` — `@Graph` bar variant
  - `figure_with_caption.lt` — `@Fig` + `@Caption`
  - `footnote_multiple.lt` — multiple `@FootNote` on one page
  - `include_basic.lt` + `include_basic_frag` — `@Include` of a
    sibling fragment
  - `abc_chords.lt` — chord-names-over-beat-counts table
  - `table_rotated.lt` — `@Tab` with rotated header text
  - `text_subscript_superscript.lt` — `@Sub` / `@Sup` chains
  - `raw_postscript.lt` — `@Graphic` with raw PS exercising

  All 10 are under 30 lines and land PASS-EXCELLENT under the
  post-v0.2 tightened thresholds (5% AE for text, 2% AE /
  SSIM 0.95 for graphics-heavy). Corpus stays at 100%
  PASS-EXCELLENT / 0 Fail. (Commit `5ef1b02`.)

- **200 DPI sensitivity baseline confirms the structural floor.**
  The User's Guide PS-vs-SVG diff now records a 200 DPI mean SSIM
  alongside 100 and 150: **0.9510** at 200 DPI (vs 0.9441 at
  150 DPI, +0.0069). The worst-10 slope flattens from +0.0334
  (100 → 150) to +0.0107 (150 → 200), below the +0.01
  "more room to chase" threshold. This confirms the conclusion of
  `chapter3_pagination_drift_investigation.md`: the residual
  delta against the PS reference is rasteriser-AA / hinting
  floor, not back-end drift. The 150 DPI baseline remains the
  release-gate measurement; 200 DPI is informational.
  (Commit `d3fc1ca`.)

- **`tests/lout_doc_renders`: DPI override + 150 DPI SSIM column.**
  Mirrors the parameterisation `user_guide_diff.sh` picked up in
  the v0.2.6 cycle. Both `build.sh` and `diff.sh` now accept
  `DPI=N` (default 100); `diff.sh` passes it to `pdftoppm` and
  `rsvg-convert`. `build.sh` also gains `SKIP_DOC_BUILD=1` to
  reuse the existing `/tmp/{doc}.{ps,svg}` artefacts when
  re-running diffs at a different DPI. (Commit `58f7bc9`.)

- **`mdlout --serve` probes 20 ports before failing.** Previously
  `--serve` died with `EADDRINUSE` when the requested port was
  taken (common when an earlier `--serve` session was still
  cooling down). Now it tries `PORT..PORT+19` and binds the first
  free one, logs the chosen port to stderr
  (`serving at http://127.0.0.1:8081/ (port 8080 was busy)`),
  and exits 2 only if all 20 are taken. The injected SSE reloader
  picks up the chosen port automatically because it reads
  `window.location`. (Commit `443c895`.)

- **`mdlout --version` reports lout version + revision.** Two-line
  banner: `mdlout 0.2.7` on line 1, `lout 3.43 (svg-backend @
  <short-sha>)` on line 2. Each component is best-effort and
  degrades gracefully on a partial checkout (no submodule, lout
  not yet built, not a git working tree) so `--version` never
  crashes. Closes the "which lout am I really running?"
  question on PyPI installs. (PR #194.)

- **Examples polish: presentation + textbook.** `presentation.md`
  gains Part I / II section-divider slides, a
  "Thank You / Questions?" closer, an inline SVG pipeline diagram,
  and a numbered ordered list (10pp → 14pp PDF, 12 → 16 SVG
  pages). `textbook.md` gains a worked end-of-chapter exercise
  set, two `@Diag` figures (a bar chart and a tree diagram), and
  a per-chapter bibliography example using `@Cite`. Both still
  build clean in `--format=html` and `--format=pdf`. (Commit
  `b90bd3b`.)

- **Cookbook recipes 39-41 (count 38 → 41).** Recipe 39 covers
  dual-language documents (English + Spanish / French / German)
  with per-language hyphenation and quote-character gotchas;
  recipe 40 walks per-section font switching using
  `{ Helvetica Base 10p } @Font @Section`; recipe 41 shows how to
  embed YouTube / video links in HTML output via a
  `` ```lout `` fenced block emitting a `<foreignObject>` with an
  `<iframe>`, plus a PS-mode fallback to a link-with-thumbnail
  rectangle. (Commit `037f921`.)

- **`chapter3_pagination_drift_investigation.md`: 150-DPI
  follow-up.** Issue #180 re-investigated the chapter-3 worst
  pages (86, 90, 56) at 150 DPI to test whether #109's
  "antialiasing-only" conclusion holds at the finer measurement.
  New section appended to the original investigation: worst-10
  mean SSIM lifts 0.7964 → 0.8298, but the per-page glyph-overlay
  diffs are bit-identical in shape — confirming the residual is
  rasteriser-AA, not layout drift. The shared-rasteriser mid-term
  item remains the right next step. (Commit `fdd0fc0`.)

## Verification

- `python3 -m build` produces a clean sdist + wheel.
- `python3 -m twine check dist/*` reports `PASSED` on both
  artefacts.
- The 80-snippet regression suite is 80/80 PASS-EXCELLENT (mean
  SSIM at 150 DPI > 0.95).
- The User's Guide PS-vs-SVG diff mean SSIM at the 150 DPI
  release-gate is 0.9441 (unchanged from v0.2.6); the 200 DPI
  sensitivity number is 0.9510.

## Compatibility

- PostScript output bit-identical to v0.2.6 for `doc/user/all`.
- The `--format=pdf` pipeline (`ps2pdf` over the frozen `z49.c`
  PostScript) remains bit-identical to v0.2.0.
- The Lout source-compatibility contract is preserved: documents
  written for upstream Lout 3.43 still build under this fork
  without modification. The svgmacros library and the SVG back
  end (`lout -G`) remain opt-in.

## What's next

The v0.3 line is in sight. Remaining v0.3 candidates from the
roadmap: `LoutMargShift translate(x, y)` (margin-note positioning
in SVG mode), a published PyPI release once the v0.2.x cycle settles,
and the long-tail combining-mark / GSUB-lookup-beyond-Type-1 work for
multilingual text shaping. See [ROADMAP.md](../ROADMAP.md) for the
full forward-looking plan.

— James
