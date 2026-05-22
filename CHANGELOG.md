# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).
This project does not yet emit versioned releases; sections are dated by the
range of underlying commit dates.

Entries below cover both this repository (the mdlout converter and its docs)
and the `lout/` submodule (the SVG back end, branch `svg-backend` on the
jclements3/lout fork). Submodule-only changes are tagged `[lout]`.

## [Unreleased]

### Features

- mdlout: pandoc-style citation syntax, auto figure/table numbering, and
  an `abstract:` frontmatter field.
- Examples: `slides_basic.md`, `letter.md`, `cv.md`, `book_chapter.md`
  added to `examples/`.
- mdlout: partial scaffolds for TOC and footnotes (still in progress).
- [lout] `@Graph` axes: type-tightening of `eq` / `ne` so axes render
  correctly with mixed-kind operands.
- [lout] `@Graphic` token memoisation and `filledsquare` fast-path, plus
  `setvbuf` on output streams. Roughly 5.3% wall-clock improvement on
  the user-guide build.

### Tests

- SSIM-based regression tests added alongside the pixel-diff metrics.

## 2026-05-20

### Features

- **HTML/SVG output path becomes default.** `--format=html` is implicit;
  the legacy PostScript-to-PDF path moves to `--format=pdf`.
- Live preview: `--watch` rebuilds on input mtime change; `--serve [PORT]`
  starts a single-threaded HTTP server with Server-Sent-Events reload.
  Both are stdlib-only.
- `--text-as-paths` SVG flag: rewrites every `<text>` element to a
  `<path>` outline via fontTools. Honest verdict: not pixel-identical to
  Ghostscript, but closer than browser text rasterisation in most pages.
- URW++ Nimbus base-35 fonts embedded as `@font-face` in the HTML wrapper
  so the browser matches Ghostscript's font substitution.
- Chromium-headless regression pipeline (`tests/chromium_diff.sh`) added
  alongside the rsvg-convert baseline.
- Pandoc-style citations and auto figure/table numbering in mdlout.
- CommonMark indented code blocks supported in mdlout.
- New examples: `scientific_paper.md` (6 pages, numerical quadrature),
  `complex_diag.md`, plus the eight numbered `examples/01..08_*.md` files.
- [lout] **SVG back end (`z53.c`) and the `svgmacros` library file**
  introduced. Sibling to the PostScript back end (`z49.c`, frozen),
  selected by `lout -G`. Implements the full `BACK_END` interface against
  SVG drawing primitives, with an embedded PostScript interpreter for
  Lout's `@Graphic`-emitted PS fragments.
- [lout] All 8 Lout texture patterns implemented as SVG `<pattern>` defs.
- [lout] SVG-friendly `graphf` markers and `tabf` rules inlined for the
  cases where the PS-interpreter route loses fidelity.
- [lout] Colour propagation through SVG output, plus recognition of the
  `errordict` family.

### Fixes

- mdlout: placeholder leak in the inline conversion pipeline fixed.
- [lout] `SVG_NullBackEnd` now uses dedicated no-op stubs for non-final
  passes (previously borrowed from `SVG_BackEnd`, which had observable
  side effects).
- [lout] `@Graph*` symbol-legend stroke widths corrected.
- [lout] `@Graph` plot-symbol sizing fixed (pages 248 and 262 of the
  user guide).
- [lout] Mark-and-sweep dict GC and a fix to a `LoutSetTexture` /
  `MakeTexture` stack-drift bug in the SVG-mode PS interpreter.
- [lout] `tex_identify` hardened against custom `paintprocs`.

### Performance

- [lout] Open-address hash for the SVG-mode PS interpreter's dict
  lookup: 2.3x speedup on SVG-mode rendering.

### Docs

- `docs/ARCHITECTURE.md` added (project architecture and design overview,
  ~280 lines).
- `docs/tutorial.md` added (end-to-end walkthrough from clone to built
  HTML and PDF).
- README quickstart rewritten around the new default HTML path.
- CI status badge added to README.
- User's Guide regression report: 327/327 pages, 0 BAD, 0 missing pages.
  Mean SSIM 0.9218, median 0.9254; 322/327 pages at SSIM >= 0.85.
- TODO.md restructured with overnight-session status blocks.
- README / CLAUDE.md / TODO.md aligned; build artefacts added to
  `.gitignore`.
- [lout] `SVG_PERFORMANCE.md` (gprof hotspot report) and
  `NEXT_OPTIMIZATIONS.md` (ranked quick wins after the dict-hash work)
  added inside the submodule.

### Tests

- Snippet corpus expanded to 39 single-feature `.lt` files under
  `tests/snippets/`, exercised by `tests/run_all.sh`.
- 327-page User's Guide regression (`tests/user_guide_diff.sh`) added
  comparing PS-rendered PNGs to SVG-rendered PNGs (rsvg-convert path).
- Chromium-headless variant of the user-guide diff for the worst-case and
  evenly-spread page subsets.

## 2026-03-16

### Features

- Initial commit: `mdlout.py` Markdown-to-Lout-to-PDF converter plus a
  vendored copy of Lout 3.43 (the william8000 fork) as a submodule.
- Supported Markdown: H1-H6 (ATX and setext), bold/italic/code/strike/
  superscript, links (as footnotes), images, bullet/numbered/task/
  definition lists, blockquotes, fenced code, pipe and grid tables,
  horizontal rules, math blocks (`$$` or ```` ```math ````), admonitions,
  page breaks, `[TOC]` placeholders, HTML entities, and backslash
  escapes.
- YAML frontmatter mapped to Lout `@BasicSetup` / `@DocumentSetup`
  clauses; `type: doc | report | book | slides`.
- `mydefs` convention: a file next to the input is copied into the build
  directory and picked up by `@Include { mydefs }`.
- Raw Lout passthrough via ```` ```lout ```` fenced code blocks.

## Upstream Lout history (for context)

The submodule's pre-fork history (versions 2.03 through 3.43) is not
reproduced here; see `lout/whatsnew` inside the submodule for upstream
release notes by Jeffrey H. Kingston and the william8000 fork
contributors. Selected upstream changes pulled in via the submodule:

- 2025-09-22: clang 20 prototype-form fixes (`void` argument lists in
  `z28.c`, `z29.c`, `z38.c`, `z48.c`).
- 2025-05-20: `SOURCE_DATE_EPOCH` support in the makefile tests.
- 2025-04-09: `SOURCE_DATE_EPOCH` support for build dates;
  webp image support and `magick` over `convert` on Linux.
- 2025-03-10: gcc 14 / clang 19 warning fixes; `make test` / `make
  testclean` added.
- 2024-01-26: lout 3.43 (the version vendored at the time of initial
  commit).
