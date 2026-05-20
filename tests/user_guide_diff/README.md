# Lout User's Guide: PostScript vs SVG visual diff

This directory captures a per-page visual comparison of the entire
**Lout 3.43 User's Guide** rendered through two of Lout's backends:

- the long-stable PostScript backend (`z49.c`), and
- the newer SVG backend (`z53.c`).

It exists so anyone tracking SVG-backend parity work has a concrete,
inspectable artefact showing how close the two outputs currently are
and which pages still diverge most.

> **Note on freshness (2026-05-20).** The numbers and worst-page table
> below were captured against `svg-backend` SHA `611dcb2`, when the
> SVG output was 306 pages because non-final cross-reference passes
> were running heavy emission callbacks instead of true no-ops. SHA
> `c618ce3` rewired `SVG_NullBackEnd` to dedicated stubs and the SVG
> output now converges to **327 pages**, matching PS. The bibliography
> / references / index back-matter that was reported as "missing in
> SVG (21 pages)" is now present. Re-running `tests/user_guide_diff.sh`
> will regenerate the manifest against the current converged output —
> we have intentionally not refreshed the committed artefacts because
> they document the state at the time of the worst-page analysis.

## Methodology

1. **Build both renders.** From `lout/doc/user/`, delete every `.li`
   cross-reference index and run `lout` seven times for each backend
   (`-G` selects the SVG backend). Seven passes is the typical Lout
   convergence budget for a document that mixes a table of contents,
   index, bibliography and forward cross-references.

   In practice the SVG backend's seven passes were unstable: some
   passes regenerated the full multi-page SVG (~16 MB) while others
   crashed with `database index file seems to be out of date` and
   produced a partial file. The largest converged pass (pass 5) was
   used as the canonical SVG output. The PostScript build converged
   normally.

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

## Aggregate stats

Total PS pages: **327**.

| bucket                           | pages |
|----------------------------------|-------|
| `OK` (diff < 5%)                 | 3     |
| `DIFF` (5% <= diff < 20%)        | 298   |
| `BAD` (diff >= 20%)              | 5     |
| `MISSING` (no SVG page at all)   | 21    |

The 21 `MISSING` pages are the tail of the document: PS produces
pages 307-327 (back-matter: bibliography continuation and the index),
while the SVG run only emitted 306 pages. They are not "broken" pages;
the SVG backend's cross-reference passes never converged far enough
to lay out the index.

The dominant pattern in the `DIFF` bucket is **page-boundary drift**.
The two backends do not paginate identically (the SVG backend places
content in a slightly different region of the page), so by mid-document
the same body text lands on different page numbers in PS vs SVG. A
side-by-side at page N often shows the same paragraphs but offset by
half a page or one full page, which the AE metric scores as a large
diff even though both pages are well-formed individually.

## Top 10 worst-matching pages

Ranked by `diff_ratio` among pages that exist in both renders. Side-by-side
(`PS | SVG | DIFF`) images are checked in as `worst-01.png` ... `worst-10.png`.

| rank | page | diff   | observation                                                                                   |
|-----:|-----:|-------:|-----------------------------------------------------------------------------------------------|
| 01   | 015  | 0.2813 | Page-boundary drift: PS shows section 1.5 prose, SVG shows the entity table (PS page 16).     |
| 02   | 019  | 0.2715 | Page-boundary drift: PS continues the entity table, SVG shows the "Hello World" example.      |
| 03   | 303  | 0.2493 | SVG fills the page with a color-name swatch grid; PS shows section text on document setup.    |
| 04   | 304  | 0.2325 | Same color swatch grid in SVG continues; PS is one page further into Appendix.                |
| 05   | 244  | 0.2252 | SVG page is nearly empty (small figure/diagram); PS page contains a multi-column code listing.|
| 06   | 056  | 0.1943 | Page-boundary drift around the `@Display` / `@Figure` discussion in Chapter 2.                |
| 07   | 082  | 0.1939 | Page-boundary drift inside the section on document structure.                                 |
| 08   | 057  | 0.1903 | Page-boundary drift; both pages discuss figures and tables but with different text on screen. |
| 09   | 086  | 0.1902 | Page-boundary drift on a dense prose page describing display options.                         |
| 10   | 302  | 0.1861 | Color swatch grid in SVG vs Appendix prose in PS - same content-shift cluster as 303-304.     |

The recurring theme: most of the high-diff pages are not bugs in the
SVG output per se, they are pagination drift. The genuinely SVG-specific
issues we did spot are:

- The color-name swatch tables (appendix, PS pages ~302-304) lay out
  much more densely in SVG than PS, which is itself a real layout-fidelity
  gap worth tracking.
- Page 244 SVG renders a near-empty page; the PS version has a code listing.
  This is the only outright "content missing" case in the worst 10.

## Reproducing this report

Run `tests/user_guide_diff.sh` from the repo root. The script rebuilds the
User's Guide in both modes (~15 min wall time including the 100 dpi raster
pass and the per-page compare), regenerates the manifests, and rebuilds the
ten side-by-side PNGs. It is idempotent and does not modify the C source or
any file under `lout/include/`.

## Build provenance

- Date built: 2026-05-20 (UTC).
- `lout/` submodule SHA: `611dcb290e1b542e5ce61b9a357e6a86026eb96a`
  (william8000/lout fork, Lout 3.43 base).
- Tools: `lout`, `ps2pdf` (Ghostscript), `pdftoppm` (poppler),
  `rsvg-convert` (librsvg), `compare`/`convert` (ImageMagick 6).
- Render DPI: 100. Compare fuzz: 5%. Compare metric: `AE` (absolute
  count of differing pixels).
