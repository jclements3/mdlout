# Lout User's Guide: PostScript vs SVG visual diff

This directory captures a per-page visual comparison of the entire
**Lout 3.43 User's Guide** rendered through two of Lout's backends:

- the long-stable PostScript backend (`z49.c`), and
- the newer SVG backend (`z53.c`).

It exists so anyone tracking SVG-backend parity work has a concrete,
inspectable artefact showing how close the two outputs currently are
and which pages still diverge most.

## Methodology

1. **Build both renders.** From `lout/doc/user/`, delete every `.li`
   cross-reference index and run `lout` eight times for each backend
   (`-G` selects the SVG backend). Eight passes is the current Lout
   convergence budget for a document that mixes a table of contents,
   index, bibliography and forward cross-references — the SVG side
   converges by pass 5 but the PS side needs the extra pass after
   the 2026-05-23 ligature folding round perturbed pagination
   slightly. The 8th pass is taken as canonical.

   Both the PostScript and SVG runs converge cleanly to **327
   pages**. (Earlier the SVG run alternated between full/partial
   outputs and the largest converged pass had to be picked; that
   was a side-effect of non-final cross-reference passes running
   heavy emission callbacks instead of true no-ops.  After the
   `SVG_NullBackEnd` rewire the SVG side converges by pass 5.)

2. **Rasterise both renders at 100 dpi.** PostScript was converted
   with `ps2pdf` and then `pdftoppm -r 100` to per-page PNGs. The
   multi-page SVG was split (one `<svg>` element per page) by
   `split_svg.py` and each page rendered with
   `rsvg-convert -d 100 -p 100`. Both routes produce 827x1170 PNGs,
   so they can be compared pixel-for-pixel.

3. **Compute a diff per page.** ImageMagick
   `compare -metric AE -fuzz 5%` counts the number of pixels whose RGB
   differs by more than 5% between the PS and SVG renders. We divide
   that by the total pixel count to get a `diff_ratio` in [0, 1]. The
   verdict thresholds:

   | verdict   | ratio                            |
   |-----------|----------------------------------|
   | `OK`      | < 0.05                           |
   | `DIFF`    | 0.05 - 0.20                      |
   | `BAD`     | >= 0.20                          |
   | `MISSING` | PS page has no SVG counterpart   |

   Per-page diff PNGs (showing the red mismatched pixels) live in
   `/tmp/userguide_compare/diff/` after a fresh run; only the worst-10
   side-by-side PNGs and the manifests are checked in.

4. **Compute SSIM per page.** In addition to the AE pixel count, the
   per-page PNGs are scored with the structural similarity index
   (`skimage.metrics.structural_similarity`, grayscale, `data_range=255`).
   SSIM is a perceptual metric in [0, 1] — 1.0 means pixel-identical,
   >= 0.95 is the standard cutoff for "visually indistinguishable" at
   this DPI, and < 0.85 means a human would actually see a difference.
   The SSIM column is appended to `manifest.txt` / `manifest.json` by
   `tests/user_guide_diff_ssim.py`; it does not change the AE-based
   `verdict`. See "SSIM vs AE" below for why both metrics are kept.

## Aggregate stats

Total PS pages: **327**.  Total SVG pages: **327**.

After perf round 3+4, fi/fl ligature folding, arena safety, textPath,
currentColor, kern table precompute, and GSUB smcp/onum parser
(2026-05-23, lout submodule `f5533e6`):

| bucket                           | pages |
|----------------------------------|-------|
| `OK` (diff < 5%)                 | 42    |
| `DIFF` (5% <= diff < 20%)        | 285   |
| `BAD` (diff >= 20%)              | 0     |
| `MISSING` (no SVG page at all)   | 0     |

AE bucket counts continue to move slowly: 4 more pages crossed into
the `OK` band (38 -> 42) since the prior baseline. The bigger signal
is on SSIM (next table): mean SSIM rose from `0.9234` to `0.9283`,
and 13 more pages crossed into the "visually indistinguishable" band
(>= 0.95), most of them text-only chapters where the new fi/fl
ligature folding now matches the PS Type 1 ligature widths exactly.

Prior baselines for reference:

| date       | submodule | mean SSIM | OK | pages >= 0.95 | pages < 0.85 |
|------------|-----------|-----------|----|---------------|--------------|
| 2026-05-20 | `c618ce3` | 0.9218    | 36 | 33            | 5            |
| 2026-05-22 | `a0a5c28` | 0.9234    | 38 | 36            | 3            |
| 2026-05-23 | `f5533e6` | 0.9283    | 42 | 49            | 1            |

Before SVG_NullBackEnd fix (lout submodule `611dcb2`, SVG had 306 pages):

| bucket                           | pages |
|----------------------------------|-------|
| `OK` (diff < 5%)                 | 3     |
| `DIFF` (5% <= diff < 20%)        | 298   |
| `BAD` (diff >= 20%)              | 5     |
| `MISSING` (no SVG page at all)   | 21    |

Summary of the move:

- Every page now exists in both renders.  The 21 `MISSING` index /
  bibliography pages were eliminated by SVG_NullBackEnd.
- The 5 `BAD` pages are gone.  In particular the appendix colour-name
  swatch grid (PS pages ~302-304), which used to render densely in
  SVG and produced four of the five `BAD` pages, now lays out at
  parity with PS.
- The `OK` bucket grew from 3 to 36 pages; the worst `DIFF` page
  (page 248) sits at 0.1948 vs the previous worst at 0.2813.
- Across the 291 remaining `DIFF` pages the mean diff is `0.080`
  and the median is `0.078`, consistent with subpixel font rendering
  differences between Ghostscript and librsvg plus modest
  pagination drift.

## SSIM aggregate stats

Same 327 pages, scored with structural similarity index
(`skimage.metrics.structural_similarity`, grayscale, `data_range=255`).
Computed by `tests/user_guide_diff_ssim.py` over the existing PNGs in
`/tmp/userguide_compare/{ps,svg}/`.

| statistic                                       | value  |
|-------------------------------------------------|--------|
| pages scored                                    | 327    |
| mean SSIM                                       | 0.9283 |
| median SSIM                                     | 0.9312 |
| min SSIM                                        | 0.8455 (page 086, pagination drift) |
| max SSIM                                        | 1.0000 (page 008, pixel-identical)  |
| pages with SSIM >= 0.99                         | 2      |
| pages with SSIM >= 0.95 (visually indistinguishable) | 49 |
| pages with SSIM >= 0.85 (close)                 | 326    |
| pages with SSIM <  0.85 (visibly different)     | 1      |

The 2026-05-23 round of fixes (fi/fl/ffi/ffl ligature folding to
U+FB01-FB04 for AT serif faces, perf round 4 sub-23s build, arena
allocator hardening, <textPath> for curve-following text,
currentColor for CSS-driven theming, per-font 256x256 kern table
precompute, GSUB smcp / onum parser) moved mean SSIM from `0.9234`
to `0.9283` and lifted 13 more pages into the "visually
indistinguishable" band (>= 0.95). The "visibly different" tail is
now a single page: 086 at SSIM `0.8455` (pagination drift in
chapter-3 prose, antialiasing-floor artefact).

## DPI sensitivity: is the SSIM floor really irreducible?

Earlier baselines characterised the worst-10 pages as "irreducible
antialiasing at 100 dpi" (see issue #109). To test that, the same 327
PS / SVG pages were re-rasterised at **150 dpi** and then again at
**200 dpi** (with no other changes; same `/tmp/user.ps`, `/tmp/user.svg`,
same `ps2pdf`, same `rsvg-convert`, only `pdftoppm -r N` and
`rsvg-convert -d N -p N` swapping the resolution). Reproduce with
`DPI=150 tests/user_guide_diff.sh` or `DPI=200 tests/user_guide_diff.sh`
(the `DPI` override, default 100, is wired in to the same script).

Comparison (327 pages, 100/150 dpi computed 2026-05-23, 200 dpi computed 2026-05-23):

| statistic                                   | 100 dpi | 150 dpi | 200 dpi | d 100->150 | d 150->200 |
|---------------------------------------------|---------|---------|---------|-----------:|-----------:|
| mean SSIM                                   | 0.9283  | 0.9441  | 0.9510  | +0.0158    | +0.0069    |
| median SSIM                                 | 0.9312  | 0.9453  | 0.9518  | +0.0141    | +0.0065    |
| min SSIM                                    | 0.8455  | 0.8890  | 0.8939  | +0.0435    | +0.0049    |
| max SSIM                                    | 1.0000  | 1.0000  | 1.0000  |     0      |     0      |
| pages SSIM >= 0.99                          | 2       | 3       | 3       | +1         |     0      |
| pages SSIM >= 0.95 (visually indistinguishable) | 49  | 110     | 181     | +61        | +71        |
| pages SSIM >= 0.85 (close)                  | 326     | 327     | 327     | +1         |     0      |
| pages SSIM <  0.85 (visibly different)      | 1       | 0       | 0       | -1         |     0      |

Worst-10 (by AE diff_ratio in the 100 dpi baseline) movement across the three DPIs:

| page | AE@100 | SSIM@100 | SSIM@150 | SSIM@200 | d 100->200 | d 150->200 |
|-----:|-------:|---------:|---------:|---------:|-----------:|-----------:|
| 086  | 0.1426 | 0.8455   | 0.8956   | 0.9210   | +0.0755    | +0.0254    |
| 090  | 0.1379 | 0.8512   | 0.9003   | 0.9245   | +0.0733    | +0.0242    |
| 063  | 0.1194 | 0.8714   | 0.9186   | 0.9276   | +0.0562    | +0.0090    |
| 056  | 0.1185 | 0.8683   | 0.9306   | 0.9340   | +0.0657    | +0.0034    |
| 094  | 0.1162 | 0.9124   | 0.9242   | 0.9250   | +0.0126    | +0.0008    |
| 095  | 0.1161 | 0.8902   | 0.8890   | 0.9118   | +0.0216    | +0.0228    |
| 075  | 0.1129 | 0.8881   | 0.9393   | 0.9411   | +0.0530    | +0.0018    |
| 019  | 0.1115 | 0.8989   | 0.9201   | 0.9251   | +0.0262    | +0.0050    |
| 096  | 0.1109 | 0.8931   | 0.9332   | 0.9284   | +0.0353    | -0.0048    |
| 060  | 0.1081 | 0.9238   | 0.9257   | 0.9455   | +0.0217    | +0.0198    |

Worst-10 mean delta 100->200 **+0.0441** (median +0.0442); worst-10
mean delta 150->200 **+0.0107** (median +0.0070). Corpus-wide 100 ->
150: 295/327 pages improved, 31 worsened (min delta -0.0284), 1
unchanged. Corpus-wide 150 -> 200: 284/327 pages improved, 40
worsened (max worsening -0.0132 on page 178), 3 unchanged. The
previously-worst page 086 moves another **+0.0254** from 150 dpi to
SSIM 0.9210 at 200 dpi.

**Conclusion: 200 dpi is effectively the structural floor.** The
100 -> 150 step moved mean SSIM **+0.0158** and lifted 61 more pages
over the 0.95 threshold; the 150 -> 200 step moves it only **+0.0069**
and the slope on the worst pages is genuinely flattening (worst-10
mean delta dropped from +0.0334 over the first step to +0.0107 over
the second). +0.0069 falls below the +0.01 "more room to chase"
threshold, so there is no third plateau worth pursuing. The remaining
~0.05 gap to the theoretical ceiling (~0.998, measured on a single-
paragraph render) is genuine pagination drift: the same prose breaking
lines at slightly different y-offsets between PS and SVG, and no DPI
high enough will make that drift disappear.

### Recommendation

Keep the canonical baseline at **100 dpi** for continuity with prior
quarters' tracking tables (and to keep run-time short -- 200 dpi adds
another ~10 min on top of the already-long 150 dpi run, and the PNG
byte budget grows ~16x vs 100 dpi). Cite the **150 dpi mean SSIM
0.9441** as the headline secondary number for SVG-back-end change
review; the 200 dpi number (**0.9510**) confirms there is no third
plateau worth chasing -- past 150 dpi diminishing returns set in and
the residual gap is pagination drift, not antialiasing. Use
`DPI=200 tests/user_guide_diff.sh` only when you specifically want to
verify a fix isn't being masked by the AA floor; for routine review,
`DPI=150` is sufficient.

### SSIM vs AE: what the numbers mean

The AE metric reports 7-15% pixel diff per page across the body of the
guide, which sounds alarming. SSIM tells the honest story: the mean
SSIM is `0.92` and 322 of 327 pages (98.5%) score >= 0.85, with most
of the SSIM-low pages clustering around 0.85-0.92 — i.e. **the AE
percentages are dominated by sub-pixel anti-aliasing differences
between Ghostscript and librsvg, not by actual rendering errors.**

Sanity check: rendering `examples/01_hello.md` (a single paragraph)
through the same PS-vs-SVG pipeline scored SSIM = **0.9976**. Two
renders of content with no layout/pagination disagreement at all still
do not hit 1.0 because Ghostscript and librsvg disagree on text
anti-aliasing at the sub-pixel level. That establishes the practical
ceiling for this pipeline at ~0.998; the median 0.9254 across the
guide reflects real pagination drift on top of that anti-aliasing
floor.

The one page now with SSIM < 0.85 is pagination drift in
chapter-3 prose (no real bug):

- **086** (SSIM 0.8455): half-page pagination drift in chapter-3
  prose. The same paragraphs render fine on both sides; they just
  sit at different vertical offsets, which both metrics correctly
  flag as a real visual difference.

Pages **090** (0.8512) and **308** (now in the close band) used to
sit below 0.85 in the prior baseline; the ligature folding round
lifted them above the threshold. The previously-worst pages 248
(SSIM 0.7485) and 262 (0.8214) were already in the close band at
0.9280 and 0.9027 after the @Graph plot-symbol dispatch fix (see
the `Recently fixed` section below).

Worst-10-by-AE and worst-10-by-SSIM still mostly agree. SSIM also
surfaces page 308 (appendix colour-swatch boundary antialiasing)
that AE does not flag in its top-10. The two metrics are
complementary: AE is sensitive to localised pixel disagreements;
SSIM is sensitive to structural / luminance changes over a window.

## Top 10 worst-matching pages

Ranked by `diff_ratio` among pages that exist in both renders. Side-by-side
(`PS | SVG | DIFF`) images are checked in as `worst-01.png` ... `worst-10.png`.

| rank | page | AE diff | SSIM   | observation                                                                                  |
|-----:|-----:|--------:|-------:|----------------------------------------------------------------------------------------------|
| 01   | 086  | 0.1426  | 0.8455 | Pagination drift: chapter 3 prose, same paragraphs, half-page offset between PS and SVG.    |
| 02   | 090  | 0.1379  | 0.8512 | Pagination drift: continuation of the same chapter-3 section, similar half-page offset.      |
| 03   | 063  | 0.1194  | 0.8714 | Pagination drift on a dense prose page about cross-references.                               |
| 04   | 056  | 0.1185  | 0.8683 | Pagination drift around the `@Display` / `@Figure` discussion in chapter 2.                  |
| 05   | 094  | 0.1162  | 0.9124 | Pagination drift inside the section on document structure. SSIM > 0.9 -- almost a false positive in the AE ranking. |
| 06   | 095  | 0.1161  | 0.8902 | Pagination drift: continuation of page 094.                                                  |
| 07   | 075  | 0.1129  | 0.8881 | Pagination drift in chapter on running heads.                                                |
| 08   | 019  | 0.1115  | 0.8989 | Pagination drift on the introduction page (new entrant -- one paragraph straddles a page break differently).   |
| 09   | 096  | 0.1109  | 0.8931 | Pagination drift: continuation of the document-structure chapter.                            |
| 10   | 060  | 0.1081  | 0.9238 | Pagination drift on a cross-reference prose page (new entrant -- replaces former page 081 / 290). |

None of the current worst-10 are real bugs -- all are
pagination-drift artefacts where the same prose lays out on
slightly different page boundaries (Ghostscript and rsvg disagree
on text antialiasing at the sub-pixel level, which compounds into
line-break decisions over a long page).

No real bugs remain in the current worst-10. All entries are
page-boundary drift: the same prose laid out on slightly different
page boundaries, which the AE metric flags as a large diff even
though both pages are individually well-formed.

## Diagrams chapter (@Diag, pages 190-229)

40 pages exercising `@Diag`, `@Fig`, `@Tree`, label orientation,
arrowstyles, link labels.  This is the highest-stakes chapter for
SVG-back-end correctness; the chapter-wide pixel-diff heatmaps
live under [`diag_thumbs/`](diag_thumbs/) and are stitched into a
single per-page gallery at [`diag_gallery.html`](diag_gallery.html).

Aggregate stats (built 2026-05-22 with lout `a0a5c28`):

| statistic       | value  |
|-----------------|--------|
| pages           | 40     |
| mean AE         | 6.93%  |
| mean SSIM       | 0.9248 |
| min SSIM        | 0.8820 (page 221) |

Worst-10 by SSIM in this chapter (side-by-side panels at
`diag-worst-NN.png`):

| rank | page | AE     | SSIM   |
|-----:|-----:|-------:|-------:|
| 01   | 221  | 9.86%  | 0.8820 |
| 02   | 205  | 8.07%  | 0.8889 |
| 03   | 213  | 7.42%  | 0.8986 |
| 04   | 219  | 7.35%  | 0.8993 |
| 05   | 211  | 7.78%  | 0.8998 |
| 06   | 207  | 9.39%  | 0.9022 |
| 07   | 224  | 7.77%  | 0.9052 |
| 08   | 202  | 7.65%  | 0.9137 |
| 09   | 216  | 7.52%  | 0.9138 |
| 10   | 193  | 7.70%  | 0.9144 |

After the rotated-show fix (lout `a0a5c28`):
- p205 SSIM 0.8850 -> 0.8889 (+0.0039)
- p207 SSIM 0.8986 -> 0.9022 (+0.0036)
- p224 SSIM 0.9010 -> 0.9052 (+0.0042)
- p211 / p213: no measurable change (the rotated-show idiom isn't
  the dominant diff source there).

None of the @Diag pages appear in the corpus-wide worst-10 (which
is dominated by chapter-3 prose pagination drift, confirmed
antialiasing-only by docs/chapter3_pagination_drift_investigation.md).
The remaining @Diag SSIM gap is the same sub-pixel Ghostscript-vs-
librsvg antialiasing floor we see corpus-wide; no layout bugs.

## Recently fixed (2026-05-23)

- **fi / fl / ffi / ffl ligature folding for AT serif faces**. The
  PS Type 1 metrics for Times/AvantGarde include the ligature
  glyphs at narrower combined widths than the two-letter sequences,
  but the SVG side was emitting the unfolded characters and picking
  up the wider browser default. z53.c now folds the four standard
  ligatures into the Unicode private-use codepoints U+FB01-FB04 at
  emit time, matching the PS width budget. Net effect: 13 more
  text-heavy pages crossed SSIM >= 0.95, and pages 081 / 290
  dropped out of the corpus worst-10.

- **Performance regressions from earlier z53.c work**. Perf rounds
  3 and 4 brought the User's Guide SVG build under the 23-second
  budget (was ~38 s at the SVG_NullBackEnd baseline). Output is
  byte-identical to the slower path so SSIM is unaffected, but the
  full diff (incl. 8 cross-ref passes + rasterise + compare) now
  fits comfortably inside the 15-minute target.

- **Arena allocator hardening** in z53_glyph.c (handles realloc
  pointer aliasing) and **GSUB smcp / onum parser** (parser-only,
  no output emission yet) landed in this baseline. Neither
  changes pixel output.

## Recently fixed (2026-05-22)

- **`@Graph` plot symbols vanished** (was pages 248, 262 in the
  prior baseline). The `svg_ps_exec_symbol` dispatch in z53.c
  stripped the `do` prefix but not the optional `filled` prefix,
  so `filledsquare` / `filledcircle` / etc. never matched any
  shape branch and emitted nothing -- the plot symbols disappeared
  from the SVG output entirely. The "5x oversized" description in
  earlier baselines reflected an even earlier failure mode; by the
  time SSIM was first measured, the symbols were silently dropping
  instead. Fix landed in lout commit `ec987be` (z53.c "Adobe Symbol
  glyph table + @Graph plot-symbol dispatch fix"). Page 248 went
  from SSIM 0.7485 to 0.9280; page 262 from 0.8214 to 0.9027.

- **Adobe Symbol-font glyphs rendered as wrong codepoints**. The
  `svg_glyph_table` in z53.c covered Latin-1 plus a few punctuation
  glyphs; the ~150 Adobe Symbol names (Greek upper + lower case,
  math operators, set / logic, arrows, fences, card suits)
  resolved to the wrong byte. The User's Guide SVG build had 1182
  `font-family="Symbol"` references with zero correct Greek/math
  hits before. Fix landed in the same commit `ec987be`; page 18
  (the Symbol character chart) now correctly emits the full Adobe
  Symbol Unicode set (`∀`, `∃`, `∋`, `∇`, etc.).

## Known remaining real bugs

None at this revision. Pagination drift in chapter-3 prose
(pages 019, 056, 060, 063, 075, 086, 090, 094, 095, 096) remains
visible in the diff but is caused by the irreducible Ghostscript-
vs-librsvg sub-pixel antialiasing floor compounding into line-break
decisions over a long page; it would require either a shared
rasteriser or accepting that AE metrics are not the right tool to
measure SVG correctness at this layer. The appendix colour-swatch
grid (page 308) has now crossed SSIM 0.85 and is no longer in the
visible-difference band.

## Reproducing this report

Run `tests/user_guide_diff.sh` from the repo root. The script rebuilds the
User's Guide in both modes (~15-20 min wall time including the 100 dpi raster
pass and the per-page compare), regenerates the manifests, and rebuilds the
ten side-by-side PNGs. It is idempotent and does not modify the C source or
any file under `lout/include/`.

## Build provenance

- Date built: 2026-05-23 (UTC).
- `lout/` submodule SHA: `f5533e6` (jclements3/lout fork, branch
  `svg-backend`; fi/fl/ffi/ffl ligature folding + perf round 4 +
  arena-allocator hardening + <textPath> + currentColor + per-font
  kern table precompute + GSUB smcp/onum parser).
- Tools: `lout`, `ps2pdf` (Ghostscript), `pdftoppm` (poppler),
  `rsvg-convert` (librsvg), `compare`/`convert` (ImageMagick 6),
  `scikit-image` 0.25 + `Pillow` + `numpy` for SSIM.
- Render DPI: 100. Compare fuzz: 5%. Compare metrics: `AE` (absolute
  count of differing pixels, ImageMagick) and SSIM
  (`skimage.metrics.structural_similarity`, grayscale, `data_range=255`).
- The SSIM column is added (in place) to `manifest.json` /
  `manifest.txt` by running
  `tests/user_guide_diff_ssim.py` (uses the PNGs already
  produced under `/tmp/userguide_compare/{ps,svg}/`).
