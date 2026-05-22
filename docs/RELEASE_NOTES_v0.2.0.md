# mdlout v0.2.0 — SVG/HTML output, accessibility, PS-vs-SVG parity

Released: 2026-05-22
Companion submodule tag: `lout/svg-backend-v0.2`
   (https://github.com/jclements3/lout, branch `svg-backend`,
    commit a3e9d04).

The "HTML by default" release. Lands the SVG back end (`lout/z53.c`,
~5400 LOC), an embedded PostScript interpreter inside it, five new
passthrough macros (`@Math`, `@DMath`, `@ABC`, `@SVG`, `@SVGFile`),
an HTML output path with WCAG 2.1 AA accessibility scaffolding,
print-mode CSS, a 62-snippet regression corpus, a 327-page per-page
User's Guide PS-vs-SVG diff with SSIM scoring, and a headless-Chrome
runner that verifies the HTML renders client-side.

The legacy PostScript-to-PDF path (`--format=pdf`) is preserved
bit-identically; `z49.c` is frozen.

## Headlines

- HTML/SVG as the default `mdlout input.md` output (was PDF).
- SVG back end in the C Lout fork: full `BACK_END` interface,
  embedded PostScript interpreter (mark-and-sweep dict GC, FNV-1a
  hashed op dispatch), Adobe Symbol glyph table (~150 names ->
  Unicode), all 8 texture patterns, `setlinecap` / `setlinejoin` /
  `setmiterlimit` emission, `@Graph` plot-symbol fix.
- HTML wrapper: URW++ Nimbus base-35 `@font-face` data-URLs for
  PS-metric parity; KaTeX + abcjsharp inlined (CDN fallback);
  highlight.js syntax highlighting; WCAG 2.1 AA landmarks / ARIA /
  alt-text manifest / skip link / hidden `<h1>`; print-mode CSS.
- CLI ergonomics: `--check` (parse-only validation), `--init [DIR]`
  (project scaffold), `--version`, plus the build flags
  `--inline-raster`, `--text-as-paths`, `--no-math-engine`,
  `--no-music-engine`, `--no-font-embedding`, `--no-highlight`,
  `--no-a11y`, `--external-assets`. Live preview: `--watch` and
  `--serve [PORT]` with SSE reload + an error overlay on rebuild
  failure.
- Markdown surface: Pandoc-style citations, auto figure/table
  numbering, `abstract:` frontmatter, CommonMark indented code,
  finalised TOC + footnote + math-newline + table-alignment +
  hljs hooks.
- Regression status: 62 snippets / 0 Fail; 327-page User's Guide
  diff at mean SSIM 0.9230, 324 / 327 pages at SSIM >= 0.85;
  headless-Chrome browser-test 37 / 37 PASS on default checks and
  with `--with-all` (axe-core / print / dark).
- Performance: User's Guide SVG build dropped from ~7 min to ~32 s
  wall time across the cycle (setvbuf, dict-hash, op-hash dispatch,
  `@Graphic` token memo, filledsquare first-char hoist).
- Docs: ARCHITECTURE.md, CONTRIBUTING.md, build_notes.md,
  tutorial.md, best_practices.md, z53_internals.md; submodule
  SVG_PORTING.md / SVG_PERFORMANCE.md / NEXT_OPTIMIZATIONS.md.

Full details: see [CHANGELOG.md](../CHANGELOG.md#020---2026-05-22).

## How to create the GitHub release (manual instructions)

The automated `gh release create` step was deferred for v0.2.0
because the same commit that carries the updated CHANGELOG also
adds `.github/workflows/ci.yml` + `user-guide-diff.yml`, and the
current `gh` token is missing the `workflow` OAuth scope.

To finish the release:

1. Refresh the `gh` OAuth token interactively (this CLI step
   cannot run inside non-interactive automation):

       gh auth refresh -s workflow

2. Push the v0.2.0 commit and tag (the tag is already created
   locally and points at `HEAD`):

       git push origin main
       git push origin v0.2.0

3. Publish the GitHub release. The body can be the contents of
   this file (everything above the "How to create" section), or
   the v0.2.0 section of `CHANGELOG.md`:

       gh release create v0.2.0 \
         --title "v0.2.0 — SVG/HTML output, accessibility, PS-vs-SVG parity" \
         --notes-file docs/RELEASE_NOTES_v0.2.0.md \
         --latest

The submodule tag `svg-backend-v0.2` has already been pushed to
`https://github.com/jclements3/lout` (the `fork` remote) and points
at commit `a3e9d04` on branch `svg-backend`.
