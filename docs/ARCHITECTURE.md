# mdlout Architecture

A reading guide for the codebase, intended for two audiences: someone considering
mdlout for a real document, and someone considering contributing. The tone here
is technical and honest. Numbers and file references are taken directly from the
source; where a claim isn't verifiable from the tree, it is omitted or qualified.

## 1. What this is

mdlout is a converter from Markdown to two output formats: an HTML scaffold
containing per-page SVG (the default), and a PDF (the legacy path). Both paths
run through the same intermediate language — Lout source (`.lt`) — and through
the same C typesetting engine (a forked copy of Jeffrey Kingston's Lout,
vendored as a submodule at `lout/`). The only difference between the two paths
is which Lout back end runs: the original PostScript back end (`lout/z49.c`,
unchanged) for PDF, or the new SVG back end (`lout/z53.c`) for HTML. Lout's
galley layout, line breaking, hyphenation, table and equation engines are the
same in both paths; only the drawing emitter differs. The submodule URL is
`https://github.com/jclements3/lout` and its working branch is `svg-backend`.

## 2. Why

Lout is a mature batch typesetter (~50 C modules, decades of engineering) with
a feature set most browser-native tooling cannot reproduce: high-quality
paragraph filling, real hyphenation, the `@Eq` math syntax, the `@Tab` table
model, `@Diag` and `@Fig` drawing primitives, `@Graph` for plots, and named
texture patterns (striped / brickwork / honeycomb / chessboard / etc.). The
goal of mdlout is to keep that typesetting engine in place and add a second
rendering target — HTML+SVG — so the same source can ship as a print-quality
PDF and as a browser-readable document.

The deliberate non-goal is reinventing the typesetting algorithms in JavaScript.
mdlout never tries to lay out a page in the browser; Lout has already done
that. The browser only needs to render the resulting SVG and run two
client-side helpers (KaTeX for math, abcjs for music) for the constructs Lout
itself does not handle.

## 3. The pipelines

```
                            mdlout.py
                          (parse + emit)
                                |
                                v
                           input.lt  (Lout source)
                                |
            +-------------------+--------------------+
            |                                        |
            v                                        v
       lout -G                                  lout (default)
   (SVG back end, z53.c)                  (PS back end, z49.c)
            |                                        |
            v                                        v
       input.svg                                input.ps
            |                                        |
            v                                        v
   mdlout.py HTML scaffold                       ps2pdf
   (KaTeX, abcjs, fonts)                            |
            |                                        v
            v                                   input.pdf
       input.html
```

Both branches run Lout up to three passes for cross-reference convergence
(`mdlout.py:_run_lout`); only the back end's `-G` flag differs. The PDF branch
hands off to Ghostscript's `ps2pdf` at the end. The HTML branch reads the SVG
back, optionally rewrites `<text>` elements as `<path>` outlines
(`--text-as-paths`), and wraps the result in an HTML page that inlines (or
links to) the KaTeX and abcjs runtimes plus, by default, URW++ Nimbus
`@font-face` web fonts to match what Ghostscript itself rasterises with.

## 4. The pieces

### `/home/clementsj/projects/mdlout/mdlout.py`

A single ~2700-line Python 3.10+ script with no third-party dependencies. It
does four things:

1. Parses YAML frontmatter (`parse_frontmatter`) and maps it to a Lout setup
   block — `@BasicSetup` / `@DocumentSetup` / etc.
2. Walks the markdown line-by-line into typed `Block` objects, then emits
   their inline content (`convert_inline` and a placeholder system that
   protects code/links/images from being double-escaped or re-parsed).
3. Generates the Lout source. For `type: report` / `type: book` it also wraps
   the heading tree as `@Section` / `@Chapter` nests
   (`_generate_sectioned_body`). For HTML output, three new macros are
   produced — `@Math { … }`, `@ABC { … }`, `@SVG { … }` — defined in
   `lout/include/svgmacros`.
4. Orchestrates the build: locates the `lout` binary (auto-discovers relative
   to the script), copies in any `mydefs`, runs Lout, then either pipes
   through `ps2pdf` (PDF) or assembles an HTML scaffold (HTML). The HTML
   scaffold inlines KaTeX and abcjs from `/usr/lib/node_modules/katex/`,
   `/usr/share/javascript/katex/`, or `~/projects/abcjsharp/dist/` when
   present; otherwise it links to a CDN, or `--external-assets` forces CDN.

The CLI is defined at `mdlout.py:2585+`. The most relevant flags:

- `--format html|pdf` (default `html`); `--pdf` and `--ps` are legacy aliases
- `--lout-only` emits Lout source to stdout or `-o`
- `--text-as-paths` rewrites `<text>` to `<path>` outlines (requires
  `fontTools`)
- `--no-font-embedding` / `--no-math-engine` / `--no-music-engine` trim the
  HTML scaffold
- `--watch` rebuilds on input mtime change; `--serve [PORT]` adds a minimal
  HTTP server with Server-Sent-Events live reload (HTML-only)
- `--mydefs PATH` and `--lout-args "…"` are escape hatches

### `lout/` — the typesetting engine

A git submodule pointing at the maintainer's Lout fork (jclements3/lout,
branch `svg-backend`). After cloning mdlout, run `git submodule update --init`
and `cd lout && git checkout svg-backend && make lout`. The build is a single
`make lout` (or `make all` for `lout` + `prg2lout`); the compiler invocation
is gcc with `-ansi -std=c99 -pedantic -Wall -O3`. C sources live flat in
`lout/` (no `src/`), and all `.c` files share the single header `externs.h`.

Of the ~52 `z??.c` modules, only one is new in this fork:

- **`lout/z53.c` — the SVG back end.** 4907 lines (`wc -l`). Mirrors the
  PostScript back end (`z49.c`) function-for-function: same
  `back_end_rec` struct shape, same callbacks (Save, Restore, Translate,
  Rotate, Scale, Word, Graphic, Texture, …). Defines `SVG_BackEnd` and
  `SVG_NullBackEnd`; `code = SVG`. Dispatched from `lout/z01.c` when the
  `-G` flag (`CH_FLAG_SVG`, `externs.h:490`) is seen.

  The non-obvious piece is that `z53.c` contains a small embedded
  PostScript interpreter (`svg_ps_exec_op` / `svg_ps_exec_value` /
  `svg_ps_exec_proc`, lines ~2617–4250). This exists because Lout's
  drawing macros (in `lout/include/`) historically emit PostScript
  fragments via `@Graphic`. Rather than rewrite every one of those
  macros for SVG, the SVG back end executes the same PostScript on a
  small stack-and-dict interpreter and translates the resulting drawing
  ops to SVG `<path>`, `<line>`, `<rect>`, `<g transform=…>`, etc. The
  interpreter has its own CTM, gstate save/restore stack, dict stack
  with open-addressing hash (recently optimised — see
  `lout/NEXT_OPTIMIZATIONS.md`), mark-and-sweep dict GC, and the
  small subset of PS operators Lout's standard libraries actually call.

- **`lout/include/svgmacros`.** Three opt-in macros (`@Math`, `@ABC`,
  `@SVG`, `@SVGFile`) that branch on `@BackEnd @Case` to either emit raw
  `<foreignObject>` (or inline `<svg>`) under SVG, or fall back to a
  plain rendering under PostScript. Included automatically by `mdlout.py`
  when the source uses any of these features.

- **Existing Lout library files** (`lout/include/diagf`, `figf`, `graphf`,
  `tabf`, …) have been extended with `@BackEnd @Case` branches that emit
  SVG-compatible passthrough for unit suffixes, hairline rule widths, and
  similar minor differences. Grep for `SVG @Yield` in `lout/include/*` to
  see the touch points.

### `examples/`

Small markdown files exercising specific feature areas: `01_hello.md`
through `08_kitchen_sink.md`, plus a `scientific_paper.md`,
`complex_diag.md`, and `diag_gallery.md`. These double as smoke tests.

### `tests/`

Regression-comparison framework rather than a unit-test suite. The entry
point is `tests/run_all.sh` (runs `tests/snippets/*.md` through both back
ends and diffs the rendered output); `tests/compare.py` measures SSIM and
pixel ratios when `scikit-image` / `Pillow` are present;
`tests/user_guide_diff.sh` exercises the full Lout user guide through both
back ends. The current measured agreement on the 327-page user guide is
documented in `tests/user_guide_diff/README.md`: mean SSIM `0.9218`,
median `0.9254`, 36/327 pages at `>= 0.95`, 322/327 pages at `>= 0.85`.

### `docs/`

This file plus `docs/tutorial.md` (end-to-end walkthrough for first-time
users).

## 5. Key design decisions

**The PostScript back end is frozen.** `lout/z49.c` is not modified by this
fork; nothing in the SVG path edits it, nothing in mdlout depends on
back-end-specific PS behaviour beyond what unmodified upstream Lout would
emit. PDF output is therefore identical to upstream Lout fed the same `.lt`
source. New work is purely additive (`z53.c`, `svgmacros`, `@Case` branches
in library files).

**The SVG back end embeds a PostScript interpreter.** This is the central
trade-off in `z53.c`. The simpler alternative would have been to fork every
drawing macro in `lout/include/` to emit SVG primitives directly. That would
have meant a per-macro divergence with no upper bound (`diagf`, `figf`,
`graphf`, `tabf`, plus all the language-specific and document-class files),
and any future Lout-side macro change would have needed to be implemented
twice. Instead, `z53.c` accepts the cost of carrying its own PS interpreter
(~4500 LOC of the file's 4907) so that the same PS fragments Lout's libraries
already emit get executed and converted in flight. New drawing macros do not
require any back-end work as long as they stick to PS operators the
interpreter already implements.

**Math and music are rendered client-side.** Lout has no built-in handler for
LaTeX-syntax math or ABC music. Rather than try to typeset either in the C
engine, the HTML path emits `<foreignObject>` containers with the source
text, and the HTML scaffold loads KaTeX (for `@Math`) and abcjs (for `@ABC`)
to render them in the browser. The PDF path falls back to a plain rendering
(`@Eq` where possible for math; a placeholder for music).

**Font embedding matches Ghostscript's substitutes.** When Ghostscript
rasterises one of Lout's base-14 PostScript fonts to PDF, it actually draws
URW++ Nimbus outlines. So the HTML scaffold inlines those same Nimbus fonts
(`mdlout.py:1657+`) — `NimbusRoman`, `NimbusSans`, `NimbusMonoPS` from
`/usr/share/fonts/opentype/urw-base35/` — as base64 `@font-face` web fonts,
mapped to the family names the SVG actually references. Without this, the
browser picks an arbitrary fallback face and the line layout drifts.

**`--text-as-paths` is opt-in.** The most pixel-faithful HTML output rewrites
every `<text>` element as a `<path>` outline using fontTools, eliminating
the browser's text rasteriser entirely. This is off by default because the
files are substantially larger and the dependency on fontTools is not
required for normal use.

## 6. Known limits

These are real and worth knowing before committing to mdlout for a project.

- **Pixel-identical agreement between PostScript and SVG is not reachable.**
  Anti-aliasing across two different rasterisers (Ghostscript versus a
  browser's SVG engine) produces irreducible noise. The metric that matters
  is perceptual similarity; the documented user-guide-wide mean is SSIM
  `0.92` (`tests/user_guide_diff/README.md`).
- **Some `@Graphic` content uses uncommon PS operators not yet implemented
  in the `z53.c` interpreter.** When this happens, the interpreter prints
  `lout (SVG): unknown PostScript operator '<name>'` to stderr (capped at
  `SVG_WARN_MAX` to avoid log spam, `z53.c:4285+`) and skips that op.
  The visible effect is that one drawing element is omitted from the SVG;
  the rest of the page still renders. The long tail of `@Diag` / `@Fig` /
  `@Eq` constructs that still drop ops is tracked in `TODO.md`.
- **`@Math` and `@ABC` are browser-only in HTML mode.** With JavaScript
  disabled, the page shows the raw LaTeX / ABC source text inside its
  `<foreignObject>`.
- **`--serve` does not support PDF.** It overrides to HTML and warns.
- **mdlout has no unit-test suite for the converter itself.** Verification
  is by running it on the example markdown files (and the snippet/user-guide
  diffs in `tests/`) and inspecting the output.

## 7. How to extend

A few realistic extension tasks and where they land:

- **Add a Markdown feature.** Edit `mdlout.py` only. The block parser is
  the top-level loop in `generate_lout`'s neighbourhood; new inline syntax
  goes into `convert_inline`. Add an example under `examples/` and a
  snippet under `tests/snippets/` to keep regression coverage honest.

- **Add a missing PostScript operator to the SVG back end.** Edit
  `lout/z53.c`, specifically `svg_ps_exec_op` (line ~2622) for built-in
  ops; the function dispatches on operator name. Build with `cd lout &&
  make lout`. If the operator emits new geometry, mirror what `z49.c`
  would have produced and translate to the equivalent SVG element.

- **Add or tweak a Lout-side construct.** Edit files under
  `lout/include/`. If the construct produces different output per back
  end, gate it with `@BackEnd @Case { PostScript @Yield … SVG @Yield … }`
  as the existing `diagf` / `figf` files do.

- **Add a frontmatter key.** Edit `parse_frontmatter` and
  `_generate_preamble` in `mdlout.py`. The existing keys (font, page,
  margins, columns, page-headers, contents, etc.) are good models.

When in doubt, run the change through `examples/08_kitchen_sink.md` in
both `--format html` and `--format pdf` modes and compare.

## 8. Where things live

- `README.md` — quickstart, CLI summary, frontmatter reference.
- `CLAUDE.md` — engineering notes (this repository's working memory for
  Claude Code sessions; also useful as a developer crib sheet).
- `TODO.md` — current roadmap, what works, what is still partial.
- `docs/tutorial.md` — first-time-user walkthrough.
- `lout/SVG_PORTING.md` — the porting plan from `z49.c` to `z53.c`, with
  the function-pointer table and per-callback notes.
- `lout/SVG_PERFORMANCE.md` — read-only profiling audit of `z53.c`,
  including wall-clock and gprof numbers for the user-guide build.
- `lout/NEXT_OPTIMIZATIONS.md` — ranked list of remaining SVG back-end
  performance wins.
- `tests/README.md` — how the regression framework works.
- `tests/user_guide_diff/README.md` — the SSIM aggregate stats on the
  327-page Lout user guide.
- `examples/README.md` — what each example file demonstrates.
- `lout/README` — upstream Lout README (Kingston's original).
