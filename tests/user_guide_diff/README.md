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
   cross-reference index and run `lout` seven times for each backend
   (`-G` selects the SVG backend). Seven passes is the typical Lout
   convergence budget for a document that mixes a table of contents,
   index, bibliography and forward cross-references.

   Both the PostScript and SVG runs now converge cleanly to **327
   pages**. (Earlier the SVG run alternated between full/partial
   outputs and the largest converged pass had to be picked; that
   was a side-effect of non-final cross-reference passes running
   heavy emission callbacks instead of true no-ops.  After the
   `SVG_NullBackEnd` rewire the SVG side converges by pass 5 and
   pass 7 is taken as canonical.)

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

After SVG_NullBackEnd fix (2026-05-20, lout submodule `c618ce3`):

| bucket                           | pages |
|----------------------------------|-------|
| `OK` (diff < 5%)                 | 36    |
| `DIFF` (5% <= diff < 20%)        | 291   |
| `BAD` (diff >= 20%)              | 0     |
| `MISSING` (no SVG page at all)   | 0     |

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
| mean SSIM                                       | 0.9218 |
| median SSIM                                     | 0.9254 |
| min SSIM                                        | 0.7485 (page 248, the `@Graph` bug) |
| max SSIM                                        | 1.0000 (page 008, pixel-identical)  |
| pages with SSIM >= 0.99                         | 2      |
| pages with SSIM >= 0.95 (visually indistinguishable) | 36 |
| pages with SSIM >= 0.85 (close)                 | 322    |
| pages with SSIM <  0.85 (visibly different)     | 5      |

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

The five pages with SSIM < 0.85 are:

- **248** (SSIM 0.7485) and **262** (SSIM 0.8214): the `@Graph` plot
  symbol bug documented below. These are the only pages where AE and
  SSIM agree it is genuinely broken.
- **086** (0.8354), **090** (0.8438), **056** (0.8547): half-page
  pagination drift in chapter-3 prose. The same paragraphs render
  fine on both sides; they just sit at different vertical offsets,
  which both metrics correctly flag as a real visual difference.

Worst-10-by-AE and worst-10-by-SSIM agree on 8 of 10 pages. SSIM
additionally surfaces the appendix colour-swatch pages 307/308 (where
many small coloured rectangles are anti-aliased differently across
their boundaries) that AE does not flag in its top-10. The two
metrics are complementary: AE is sensitive to localised pixel
disagreements; SSIM is sensitive to structural / luminance changes
over a window.

## Top 10 worst-matching pages

Ranked by `diff_ratio` among pages that exist in both renders. Side-by-side
(`PS | SVG | DIFF`) images are checked in as `worst-01.png` ... `worst-10.png`.

| rank | page | AE diff | SSIM   | observation                                                                                  |
|-----:|-----:|--------:|-------:|----------------------------------------------------------------------------------------------|
| 01   | 248  | 0.1948  | 0.7485 | **Real bug:** `@Graph` plot symbols (`filledsquare`/`filledcircle`) draw at ~5x correct size, overdrawing the page; graph axes/curve also misplaced. PS interp doesn't track `symbolsize` scale through `font { -2p }`. SSIM also flags this as worst page. |
| 02   | 086  | 0.1462  | 0.8354 | Pagination drift: chapter 3 prose, same paragraphs, half-page offset between PS and SVG.    |
| 03   | 090  | 0.1404  | 0.8438 | Pagination drift: continuation of the same chapter-3 section, similar half-page offset.      |
| 04   | 262  | 0.1345  | 0.8214 | Same `@Graph` bug as page 248: oversized plot symbols draw a black blob over the axes.       |
| 05   | 056  | 0.1220  | 0.8547 | Pagination drift around the `@Display` / `@Figure` discussion in chapter 2.                  |
| 06   | 063  | 0.1213  | 0.8650 | Pagination drift on a dense prose page about cross-references.                               |
| 07   | 094  | 0.1183  | 0.9046 | Pagination drift inside the section on document structure. SSIM > 0.9 -- almost a false positive in the AE ranking. |
| 08   | 095  | 0.1182  | 0.8850 | Pagination drift: continuation of page 094.                                                  |
| 09   | 075  | 0.1165  | 0.8751 | Pagination drift in chapter on running heads.                                                |
| 10   | 019  | 0.1138  | 0.8860 | Pagination drift around the entity table early in the guide (was rank 02 before the fix).    |

Only pages 248 and 262 are genuine SVG-specific bugs.  Both stem
from the same underlying issue (graph plot-symbol sizing via the
embedded `graphf` PostScript prologue).  Everything else in the
worst-10 is page-boundary drift: the same prose laid out on
slightly different page boundaries, which the AE metric flags as
a large diff even though both pages are individually well-formed.

## Known remaining real bugs

- **`@Graph` plot symbols are oversized** (pages 248, 262, and any
  other graph rendered with `font { -2p }` or similar font scaling).
  The embedded `graphf.lpg` PostScript prologue computes
  `symbolsize` relative to the current font scale, but the SVG
  backend's embedded PS interpreter doesn't track that scaling
  through to `symbolsize`, so `filledsquare`/`filledcircle` etc.
  fill rectangles of roughly 5x the intended size.  Pages 248 and
  262 show the failure mode clearly: a single oversized fill
  covers the plot area.  Not a correctness issue with z53.c's
  emission code per se; it's a missing piece of PS state tracking
  in the interpreter.

## Reproducing this report

Run `tests/user_guide_diff.sh` from the repo root. The script rebuilds the
User's Guide in both modes (~15-20 min wall time including the 100 dpi raster
pass and the per-page compare), regenerates the manifests, and rebuilds the
ten side-by-side PNGs. It is idempotent and does not modify the C source or
any file under `lout/include/`.

## Build provenance

- Date built: 2026-05-20 (UTC).
- `lout/` submodule SHA: `c618ce34ef88cca20b1d1a6f30676bb1a32d7e26`
  (william8000/lout fork, Lout 3.43 base; SVG_NullBackEnd rewire).
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
