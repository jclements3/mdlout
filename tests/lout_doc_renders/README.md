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
| [design](./design.html) | 40 | 431.9 KiB | [173.5 KiB](./design.pdf) | 2.3 MiB | [2.3 MiB](./design.html) | 3s | 6s | 0.9123 | 9.16% |
| [expert](./expert.html) | 115 | 894.4 KiB | [467.2 KiB](./expert.pdf) | 5.9 MiB | [5.9 MiB](./expert.html) | 20s | 22s | 0.7061 | 11.11% |
| [slides](./slides.html) | 42 | 150.3 KiB | [73.0 KiB](./slides.pdf) | 262.7 KiB | [264.6 KiB](./slides.html) | 3s | 2s | 0.9804 | 1.68% |
| [user](./user.html) | 327 | 4.5 MiB | [1.6 MiB](./user.pdf) | 18.4 MiB | [18.4 MiB](./user.html) | 201s | 224s | 0.9292 | 7.73% |

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

Building the three previously-unrendered docs through z53.c highlighted three issue classes:

1. **`@Case { PostScript ... PDF ... }` lacks an `SVG` branch.** Many Lout include files (most loudly `s2_3` in `design`) ship with explicit `PostScript` and `PDF` cases for back-end-specific instructions. Under `lout -G` these fall through to the PostScript branch — the message `replacing unknown @Case option SVG by PostScript` accounts for most of the stderr volume. Functionally harmless (the PostScript branch is usually fine) but it should grow an `SVG` case in `lout/include/`.

2. **Raw PostScript inside `@Graphic { ... }`.** The `design` document embeds hand-written PostScript snippets in its algorithm-flow diagrams (`lightgrey`, `lfig` operators in `s2_3`). z53.c flags these as `unknown PostScript operator`. This is the long tail tracked by `lout/SVG_PORTING.md` — translating PostScript drawing primitives to SVG `<path>` operations is future work. Page-level effect is the diagram appears as an XML comment with surrounding text intact.

3. **Per-pass output alternation continues.** With 7 passes, every doc's SVG run alternates between the full multi-page output and a smaller partial output on each pass — the same phenomenon `tests/user_guide_diff.sh` already documents. `build.sh` picks the latest *converged* pass (the one where two consecutive passes agree on file size) as the canonical output, falling back to the largest non-crashed pass if no two passes agree.

4. **`expert` doc asserts in `Parse()` at lout HEAD from PS pass 4 onward.** A regression somewhere in the current submodule pointer makes `lout` (PostScript back-end) fail with `internal error: assert failed in Parse: *token!` on the fourth and later passes of `lout/doc/expert/all`. The SVG back-end is unaffected; only the PostScript pipeline crashes. `build.sh` therefore picks PS pass 2 as the best available PostScript output for `expert`, which leaves cross-references unresolved (rendered as `??`) and drops the expert sample SSIM from ~0.92 to ~0.71 relative to the previously committed renders. PDF page count goes from 120 to 115. The SVG (`lout -G`) pipeline converges normally and is unchanged.

Each per-doc gallery (`*_diff.html`) shows 10 evenly-spaced sample pages with PS / SVG / pixel-diff panels side by side.

## How the HTML scaffold differs from `mdlout.py`

`mdlout.py:_build_html_scaffold` is wired into the Markdown front end and assumes the caller has parsed YAML frontmatter. These docs are raw Lout source, so we use a much smaller scaffold (`wrap_html.py`) — same `.lout-page` styling, same print stylesheet shape, but CDN-loaded KaTeX (no font embedding, no abcjsharp, no dark-mode toggle). That's enough for the docs since they don't use `@Math`/`@ABC`/`@Mermaid`.

