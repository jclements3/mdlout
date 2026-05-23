# mdlout v0.2.6 — smcp/onum consumer, glyph-path LRU cache, 150 DPI baseline

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.6`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit `87dd48c`).

Same-day follow-on to v0.2.5. Lands the **smcp/onum consumer side**
that v0.2.5's GSUB parser was waiting on (PR #167):
GSUB-substituted glyphs that have no Unicode codepoint are now
emitted as `<path d="...">` outlines for body text, so frontmatter
`font-features: smcp,onum` actually renders small-caps and old-style
figures in the SVG. The path-emit hot loop picks up an LRU cache for
decoded glyph `d`-strings (~2.4-2.7x faster on smcp-heavy builds).
The User's Guide PS-vs-SVG diff PASSES count bumps 7 → 8 (ligature
width shifts pushed the cross-reference loop past 7), and the
regression harness re-baselines at **150 DPI**, lifting the mean
SSIM from 0.9283 (100 DPI) to **0.9441** (150 DPI) on the same
corpus. The `tests/lout_doc_renders` refresh against the v0.2.5
fixes drops User SVG wall time 319 s → 237 s. Three new cookbook
recipes (36-38; total now **38**), a polished single-column
`cv.md`, and a docs landing page (`examples/index.md`) round out
the docs / examples upkeep. `z49.c` (PostScript) and the legacy
PDF pipeline remain frozen and bit-identical to v0.2.0.

## Headlines

- **[lout] smcp/onum consumer-side emission.** The OpenType GSUB
  `smcp` / `onum` substitutions parsed in v0.2.5 are now emitted
  as `<path d="..."/>` outlines for body text. Substituted glyphs
  have no Unicode codepoint, so a `<text>`-based emission could
  not reference them; the consumer switches whole words that
  contain at least one substituted byte over to path mode.
  Activation is opt-in via frontmatter `font-features: smcp,onum`
  (mdlout.py sets `LOUT_SVG_FONT_FEATURES` in the child Lout
  process) or via the raw env var for `.lt` authoring. Documents
  without the env var are byte-identical to the prior build.
  Snippet `text_smcp_active.lt` exercises the path-emission branch
  end to end and lands PASS-EXCELLENT at AE-ratio 0.19%,
  SSIM 0.9947. Regression suite stays at 70 Pass-Excellent / 0
  Fail. Closes v0.2.5's "phase 2 consumer queued for v0.2.6 under
  PR #167". (lout commits `8f6c536`, `fd89ea5`.)

- **[lout] Path-emit hot-loop LRU cache.** The glyph path-emit
  consumer decodes the CFF Type-2 charstring for each substituted
  glyph into an SVG `d`-string; this decode is the dominant cost
  in the new path. The cache keys on `(font, gid, size)` and
  avoids re-decoding the same glyph at the same size across word
  boundaries. Wall time on a 200-paragraph pangram smcp build
  drops from 5.0x baseline (consumer landing, pre-cache) to 2.1x
  baseline (median of 5 runs); the standalone `z53.c` improvement
  measured against the consumer-only build is **2.7x** on the
  same workload. SVG output byte-identical to the pre-cache
  build across the regression suite. (lout commits `87dd48c`,
  `590ad2b`.)

- **Regression harness baseline DPI 100 → 150.** All
  `tests/run_compare.sh` snippet renders, the User's Guide diff,
  and the four `tests/lout_doc_renders` documents now rasterise
  at 150 DPI. Mean SSIM on the 327-page UG diff lifts from
  0.9283 (100 DPI) to **0.9441** (150 DPI) on the same corpus —
  the higher-resolution raster reduces the per-pixel AA / hinting
  floor that dominated the 100 DPI numbers. The 5% / 20% AE
  thresholds carry over unchanged; pass / fail verdicts on the
  snippet suite are byte-identical to the 100 DPI run.
  Historical 100 DPI numbers retained in
  `tests/snippet_history.jsonl` for trend continuity.

- **`tests/user_guide_diff` default PASSES 7 → 8.** The v0.2.5
  ligature width shifts push the User's Guide cross-reference
  loop past 7 passes, so the final pass's byte counts were
  unstable. Defaulting to 8 restores convergence; `PASSES` env
  var lets callers override. PS stage now early-stops when two
  consecutive passes match byte-for-byte. (Commit `7fefdcd`.)

- **`tests/lout_doc_renders` refresh.** Per-doc SSIM movement
  (prior → new): design 0.9190 → 0.9201, expert 0.9202 → 0.9206,
  slides 0.9804 → 0.9805, user 0.9292 → 0.9297. SVG byte sizes
  shrunk modestly (design 2.4 → 2.0 MiB, expert 6.0 → 5.1 MiB,
  slides 264.7 → 244.1 KiB) thanks to the v0.2.5 fi/fl ligature
  folding plus per-font kern table precompute being byte-accurate
  while producing slightly shorter glyph runs. **User SVG wall
  time 319 s → 237 s** — perf round 4's coord-folded Y-flip and
  `svg_itoa` / `svg_ftoa3` reach the doc-rendering scale.
  (Commit `b170c22`.)

- **`tests/snippet_history_sparklines.html` + deep-link routing.**
  76 KB CSS-grid landing page with 70 sparklines, one per snippet:
  verdict badge + 80x20 inline-SVG sparkline of AE
  `pixel_diff_ratio` over the last 20 runs. Sort modes:
  worst-diff-first (default), best-first, alphabetical. Text
  filter + "graphics-heavy only" toggle. The per-snippet detail
  viewer (`snippet_history.html`) grows hash routing so
  `snippet_history.html#snippet=name` pre-selects that snippet.
  Worst-diff snippets right now: `mermaid_flowchart` 1.698%,
  `table_longtable` 1.460%, `paragraph_fill` 1.146%,
  `diag_multicol` 1.071%, `multi_column` 0.960%. Generator at
  `tests/render_snippet_sparklines.py` is stdlib-only.
  (Commit `621c3a7`.)

- **Docs / examples upkeep.** Three new cookbook recipes (36-38;
  recipe count 35 → 38) at commit `a7597e7`. `examples/index.md`
  docs landing page links every doc entry point (tutorial,
  cookbook, gallery, FAQ, CONTRIBUTING, PUBLISHING, PYPI,
  best-practices, ARCHITECTURE, z53_internals, CI, README,
  CHANGELOG, ROADMAP) plus the test reports
  (`f03d5e1`). `examples/cv.md` rewritten as a tight
  single-column Helvetica 9.5pt one-page resume — replaces the
  previous `columns: 2` + `type: doc` layout that silently
  dropped the bottom of the CV (`b220c58`).

- **mdlout package version 0.2.5 → 0.2.6.** `pyproject.toml`
  and `mdlout.VERSION` both bump, carrying the smcp/onum
  consumer-side activation knob (`font-features` frontmatter →
  `LOUT_SVG_FONT_FEATURES` env var) into PyPI.

## Regression status

- 70-snippet single-feature suite: 0 Fail, 100% Pass-Excellent
  at 150 DPI. `text_smcp_active.lt` lands PASS-EXCELLENT at
  AE-ratio 0.19%, SSIM 0.9947.
- `tests/lout_doc_renders/` landing page: design 0.9201, expert
  0.9206, slides 0.9805, user 0.9297. User SVG wall 319 s → 237 s.
- `tests/user_guide_diff/` at 150 DPI: mean SSIM **0.9441** (was
  0.9283 at 100 DPI on the same corpus); 8-pass cross-reference
  loop.
- `bash tests/browser_test.sh`: 53-55 PASS / 0 FAIL across the
  cycle. Unchanged from v0.2.5.
- PostScript / `--format=pdf` output bit-identical to v0.2.5 for
  the example corpus and `doc/user/all`.

## Compatibility / migration

- mdlout package version 0.2.5 → 0.2.6. `pip install --upgrade
  mdlout` (once the PyPI publish lands) picks up the new wheel.
- No CLI flag changes. To activate small-caps / old-style figures,
  add `font-features: smcp,onum` to the markdown frontmatter; the
  child Lout process will pick up `LOUT_SVG_FONT_FEATURES` and
  switch eligible words to path-emit mode. Documents without the
  knob are byte-identical to the v0.2.5 output.
- The 150 DPI baseline is a measurement-side change. The
  pre-150-DPI mean SSIM (0.9283 at 100 DPI) is the apples-to-apples
  number against v0.2.5; 0.9441 at 150 DPI is the new headline
  because v0.2.6+ trend numbers are taken at 150 DPI.
- For `font-features: smcp,onum` to actually substitute, the
  resolved font must be CFF/OTF with a populated GSUB table.
  Type 1 PFB (URW base35 default) has no GSUB — the snippet
  `text_smcp_active.lt` uses the `LOUT_SVG_FONT_FEATURES_SYNTH`
  fallback to exercise the path-emission branch against
  base35 by remapping lowercase → uppercase glyph entries.

## How to publish the GitHub release

The release is being published from the v0.2.6 tag on `main`. If
`gh release create v0.2.6 --notes-file docs/RELEASE_NOTES_v0.2.6.md
--latest` succeeds in this run, no further action is required.

If `gh` rejects the create call for OAuth-scope reasons:

1. Push tags and commits:

       git push origin main
       git push origin v0.2.6

2. Publish the release:

       gh release create v0.2.6 \
         --title "v0.2.6 — smcp/onum consumer, glyph-path LRU cache, 150 DPI baseline" \
         --notes-file docs/RELEASE_NOTES_v0.2.6.md \
         --latest

3. The companion submodule tag `svg-backend-v0.2.6` should be on
   the `fork` remote (jclements3/lout) and point at commit
   `87dd48c` on branch `svg-backend`. If not, from inside the
   submodule:

       cd lout
       git push fork svg-backend-v0.2.6

Full per-entry details: see
[CHANGELOG.md](../CHANGELOG.md#026---2026-05-23).
