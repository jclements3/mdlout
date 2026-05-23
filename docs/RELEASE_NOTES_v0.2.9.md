# mdlout v0.2.9 — ps2pdf page-size, 90-snippet corpus, 50-recipe cookbook

Released: 2026-05-23
Companion submodule tag: `lout/svg-backend-v0.2.9`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit `628c893`).

Same-day follow-on to v0.2.8. Lands the **`ps2pdf` page-size
passthrough** in `mdlout.py` (#198): the `--format=pdf` pipeline now
reads `page:` / `orientation:` from frontmatter and passes
`-dDEVICEWIDTHPOINTS` / `-dDEVICEHEIGHTPOINTS` / `-dPDFFitPage` to
`ps2pdf`, so A0 / A3 / Legal / Letter sheets no longer silently
clip to A4. Grows the regression corpus 85 → **90** with five more
single-feature snippets, adds three new full-document examples
(`poster_a0.md` A0 scientific poster, `journal.md` single-column
academic article, `article.md` catch-up), extends `docs/cookbook.md`
41 → **50** (recipes 42-50 over the v0.2.8 + v0.2.9 cycle), adds
`tests/improvements_summary.html` (session-at-a-glance dashboard),
and completes the CHANGELOG TOC + compare-link footer. On the
submodule side, `lout/SVG_PORTING.md` gains a written-up
investigation of the cross-token kerning question (issue #188) on
slides p032 — the residual signal is per-glyph rasteriser metric
drift, not lost kerning, so the merge-into-`<tspan>` fix is
formally deferred. `z49.c` (PostScript) and the legacy PDF
pipeline remain frozen and bit-identical to v0.2.0.

## Headlines

- **mdlout: ps2pdf page-size passthrough from frontmatter** (#198).
  `--format=pdf` previously called `ps2pdf` with no page-size
  hints, so Ghostscript defaulted to A4 and any sheet larger than
  A4 (notably A0 posters, A3 spreads, Legal, Tabloid) was silently
  clipped to the A4 media box even though the underlying
  PostScript carried the correct `%%BoundingBox`. The fix adds a
  `_page_size_pt(page, orientation)` lookup (A0-A5, Letter, Legal,
  Tabloid, Executive — plus an explicit `<w>x<h>pt` / `mm` parser
  for arbitrary sizes) and passes `-dDEVICEWIDTHPOINTS=<w>` /
  `-dDEVICEHEIGHTPOINTS=<h>` / `-dPDFFitPage` on the `ps2pdf`
  command line. Frontmatter without an explicit `page:` field
  keeps the prior A4 default, so existing documents are
  byte-identical. Closes the workaround documented in
  `examples/poster_a0.md`; the A0 poster (2380×3368 pt) now
  produces a single uncropped PDF page. (Commit `04ac23a`.)

- **Three new full-document examples.** `poster_a0.md` —
  A0 portrait, 3-column scientific poster on "Sparse MoE Routing
  for Long-Context Transformers" (60pt centred title,
  lightgrey-shaded abstract box via raw-Lout `@Box`, five body
  sections, two inline ` ```svg ` figures, two display equations,
  results table, four references). Single 2380×3368 pt page;
  browser-test PASS (KaTeX 14/14); exercises the new ps2pdf
  page-size passthrough end to end. `journal.md` — single-column
  academic article (Letter, Times Base 11p, `type: report` /
  `columns: 1`), 9-page PDF / 8-page HTML, seven `@Section`
  blocks (Introduction; Background w/ sub-sections; Method;
  Results w/ two theorems + proof sketches, figure, table;
  Related Work; Conclusions; References). `article.md` —
  2-column scientific paper, the `examples/index.md` catch-up
  commit. (Commits `6096e35`, `f7aea00`.)

- **Regression corpus 85 → 90 snippets.** Five more
  single-feature `.lt` snippets, all PASS-EXCELLENT (SSIM ≥
  0.9923):

  - `text_textpath_curveto_chain.lt` — text along a 3-segment
    cubic `curveto` chain (companion to the existing
    `text_on_path` snippet, which uses one `curveto`). Exercises
    `z53.c`'s `<textPath>` emitter on multi-segment paths.
  - `graphic_polar_plot.lt` — polar rose `r = cos(3·θ)` traced
    via a raw-PS `for` / `sin` / `cos` loop. Hits the embedded
    PS interpreter's transcendental ops.
  - Three further single-feature snippets (`@Diag` / `@Tab` /
    `@Eq` corner cases) locking in v0.2.7-v0.2.8 work.

  All five are under 30 lines and land PASS-EXCELLENT under the
  post-v0.2 tightened thresholds (5% AE for text, 2% AE / SSIM
  0.95 for graphics-heavy). Corpus stays at 100% PASS-EXCELLENT /
  0 Fail. (Commit `49b184e`.)

- **`docs/cookbook.md`: 41 → 50 recipes.** Recipes 42-44 +
  45-47 + 48-50 over the v0.2.8 + v0.2.9 cycle. The v0.2.9
  additions: 45 (bulk-rendering a folder of Markdown sources),
  46 (line-level deep-links into fenced code blocks via the
  anchor-id work), 47 (pulling figures from outside the source
  tree via `@SysInclude` / `@SVGFile` with absolute paths), 48
  (sharing a `mydefs` file across many documents), 49
  (title-page logo via `@IncludeGraphic`), 50 (mixed-cell
  tables with `@Graphic` / `@Eq` / prose side by side). The
  cookbook is the practical-idiom companion to the tutorial;
  the v0.3 line will likely freeze the count here and route
  further idioms into `docs/best_practices.md`. (Commits
  `5d6b720`, `483d391`.)

- **[lout] `SVG_PORTING.md`: cross-token kerning formally
  deferred** (#188). 67-line investigation appended to
  `SVG_PORTING.md` explaining why merging adjacent same-style
  `<text>` elements into `<tspan>` children on `doc/slides/all`
  p032 isn't a viable fix for the residual SSIM signal. Only 2
  of the 70 `<text>` elements on p032 are truly adjacent
  same-style pairs (`"nil"`/`"then"` and `"then"`/`"begin"` in
  the Pascal listing); the rest of the inter-token gaps are
  whitespace-sized. Furthermore SVG couples explicit positioning
  and automatic kerning — any glyph or `<tspan>` with an
  explicit `x` resets position and disables kerning across that
  boundary — so the proposed merge either drops Lout's
  pre-computed gap (introducing new drift) or keeps explicit
  `x` and loses the kerning it set out to gain. The residual
  signal on p032 is now correctly attributed to the
  rasteriser-AA floor that the "shared rasteriser" mid-term
  item tracks. (Submodule commit `628c893`, mdlout commit
  `58015b6`.)

## Verification

- `python3 -m build` produces a clean sdist + wheel.
- `python3 -m twine check dist/*` reports `PASSED` on both
  artefacts.
- The 90-snippet regression suite is 90/90 PASS-EXCELLENT (mean
  SSIM at 150 DPI > 0.95).
- The A0 poster (`examples/poster_a0.md`) builds to a single
  uncropped 2380×3368 pt PDF page, verifying the ps2pdf
  page-size passthrough end to end.
- The User's Guide PS-vs-SVG diff mean SSIM at the 150 DPI
  release-gate is unchanged from v0.2.8 (0.9441 / 0.9811 on
  slides p019); no z53.c output changes shipped in this cycle.

## Compatibility

- PostScript output bit-identical to v0.2.8 for `doc/user/all`.
- The legacy `--format=pdf` pipeline is bit-identical to v0.2.0
  *for documents that don't set `page:` in frontmatter*.
  Documents with an explicit `page:` field now produce a PDF
  media box matching the requested sheet (rather than the
  silent A4 clip). The underlying PostScript is unchanged, so
  `pdftops` round-trips back to the v0.2.0 bytes.
- The Lout source-compatibility contract is preserved:
  documents written for upstream Lout 3.43 still build under
  this fork without modification. The svgmacros library and
  the SVG back end (`lout -G`) remain opt-in.

## What's next

The v0.3 line is in sight. Remaining v0.3 candidates from the
roadmap: `LoutMargShift translate(x, y)` (margin-note positioning
in SVG mode) and a published PyPI release once the v0.2.x cycle
settles. The long-tail combining-mark / GSUB-lookup-beyond-Type-1
work for multilingual text shaping plus the "shared rasteriser
for true pixel parity" item carry forward into v0.4. See
[ROADMAP.md](../ROADMAP.md) for the full forward-looking plan.

— James
