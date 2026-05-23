# Lout documentation: PostScript + z53.c SVG renders

This directory holds end-to-end renders of all four documents that ship with the Lout source tree (`lout/doc/{design,expert,slides,user}`) using the SVG back-end (`z53.c`). Each document is built twice — once through the PostScript pipeline (`lout` + `ps2pdf`) and once through the SVG pipeline (`lout -G` + HTML scaffold). Both runs use 7 passes for cross-reference convergence.

Landing page: [index.html](./index.html) (thumbnails + summary table).

Reproduce with:

```bash
bash tests/lout_doc_renders/build.sh
```

## Per-document summary

| Doc | Pages | PS | PDF | SVG | HTML | PS wall | SVG wall | Sample SSIM | Diff %|
|-----|------:|---:|----:|----:|-----:|--------:|---------:|------------:|------:|
| [design](./design.html) | 40 | 431.9 KiB | [173.5 KiB](./design.pdf) | 2.0 MiB | [2.0 MiB](./design.html) | 4s | 8s | 0.9201 | 8.62% |
| [expert](./expert.html) | 120 | 937.5 KiB | [496.0 KiB](./expert.pdf) | 5.1 MiB | [5.1 MiB](./expert.html) | 12s | 15s | 0.9206 | 6.70% |
| [slides](./slides.html) | 42 | 150.3 KiB | [73.0 KiB](./slides.pdf) | 244.1 KiB | [246.0 KiB](./slides.html) | 5s | 3s | 0.9805 | 1.67% |
| [user](./user.html) | 327 | 4.5 MiB | [1.6 MiB](./user.pdf) | 15.9 MiB | [15.9 MiB](./user.html) | 298s | 237s | 0.9297 | 7.72% |

Sample SSIM is the mean of scikit-image `structural_similarity` (Wang et al. 2004) over 10 evenly-spaced sampled pages per document on luminance, data_range=255 (1.0 = pixel-identical, >0.95 = visually indistinguishable at 100 dpi, <0.85 = actually different). Diff % is the ImageMagick AE pixel-diff ratio at 5% fuzz averaged over the same samples. Side-by-side galleries:

- [design_diff.html](./design_diff.html)
- [expert_diff.html](./expert_diff.html)
- [slides_diff.html](./slides_diff.html)
- [user_diff.html](./user_diff.html)

## Per-document notes

### design

Jeffrey Kingston's 1993 design paper. Heavy on `@Eq` (display equations), `@Fig` (algorithm flow diagrams), and worked examples of Lout's galley system. The toughest of the four for the SVG back-end because the diagrams use direct PostScript via `@Graphic`.

### expert

The Expert's Guide (`@Book` style). Exercises advanced features — `@Span`, `@TagItem`, `@OneCol`/`@OneRow`, custom galleys, `@Insert`, scaled/rotated graphics. The largest in source line count.

### slides

`@OverheadTransparencies` style. Big fonts, landscape, lots of `@Code` blocks; light on graphics. The cheapest to build.

### user

The User's Guide. The reference document tracked separately by `tests/user_guide_diff.sh`; included here for completeness.

## Bugs / divergences surfaced by these renders

Building the three previously-unrendered docs through z53.c highlighted a handful of issue classes. The first two are now fixed at lout HEAD; the rest are the long-tail residue:

1. **`@Case { PostScript ... PDF ... }` lacked an `SVG` branch** *(fixed at lout HEAD)*. Many Lout include files (most loudly `s2_3` in `design`) shipped with explicit `PostScript` / `PDF` cases for back-end-specific instructions; under `lout -G` these fell through to the PostScript branch, emitting `replacing unknown @Case option SVG by PostScript` warnings (~96 for `design`, ~235 for `expert`). The fork now adds explicit `SVG` branches in `lout/include/` and in `doc/{design,expert}` (see PRs #141 and #143). Stderr volume for these docs drops from hundreds of warnings to zero, restoring the design SSIM from 0.6560 (build was picking a non-converged pass) to 0.9190.

2. **Concurrent-runner cross-reference races** *(fixed in `build.sh`, a4a20df)*. Lout writes `*.li` / `*.ldx` / `lout.lix` to the cwd as it resolves cross-references, so two agents running the same doc in parallel raced on those files — yielding `assert failed in Parse: *token!`, `rename failed`, and `line too long` errors that previously dropped `expert`'s SSIM from ~0.92 to ~0.71 and PDF page count from 120 to 115. `build.sh` now copies each doc into a per-run scratch dir (`/tmp/loutdocs/src/$doc/`) before invoking `lout`, so concurrent agents no longer collide; the expert SSIM is back to 0.9202 and the page count back to 120.

3. **Raw PostScript inside `@Graphic { ... }`.** The `design` document embeds hand-written PostScript snippets in its algorithm-flow diagrams (`lightgrey`, `lfig` operators in `s2_3`). z53.c flags these as `unknown PostScript operator`. This is the long tail tracked by `lout/SVG_PORTING.md` — translating PostScript drawing primitives to SVG `<path>` operations is future work. Page-level effect is the diagram appears as an XML comment with surrounding text intact.

4. **Per-pass output alternation continues.** With 7 passes, every doc's SVG run alternates between the full multi-page output and a smaller partial output on each pass — the same phenomenon `tests/user_guide_diff.sh` already documents. `build.sh` picks the latest *converged* pass (the one where two consecutive passes agree on file size) as the canonical output, falling back to the largest non-crashed pass if no two passes agree.

Each per-doc gallery (`*_diff.html`) shows 10 evenly-spaced sample pages with PS / SVG / pixel-diff panels side by side.

## How the HTML scaffold differs from `mdlout.py`

`mdlout.py:_build_html_scaffold` is wired into the Markdown front end and assumes the caller has parsed YAML frontmatter. These docs are raw Lout source, so we use a much smaller scaffold (`wrap_html.py`) — same `.lout-page` styling, same print stylesheet shape, but CDN-loaded KaTeX (no font embedding, no abcjsharp, no dark-mode toggle). That's enough for the docs since they don't use `@Math`/`@ABC`/`@Mermaid`.

