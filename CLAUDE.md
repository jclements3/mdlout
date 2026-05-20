# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repo is **mdlout**: a Markdown → Lout → PDF converter (`mdlout.py`) plus a vendored copy of **Lout** (version 3.43), a document formatting system in ANSI C that reads high-level descriptions and emits PostScript/PDF/plain text. Lout was created by Jeffrey H. Kingston at the University of Sydney (GPLv3).

## Repo Layout & Submodule

- `mdlout.py` (repo root) — the only first-party source; the Markdown-to-Lout converter.
- `lout/` — **git submodule** pointing at `https://github.com/william8000/lout.git` (a Lout fork). Treat it as third-party: don't make local edits unless deliberately patching upstream.
- After cloning, initialize the submodule before building:

  ```bash
  git submodule update --init
  ```

  Without this, `lout/` is empty and every `make` command fails.

## Build Commands

All commands run from the `lout/` directory:

```bash
cd lout
make all          # Build both lout and prg2lout binaries
make lout         # Build just the lout binary
make prg2lout     # Build just the prg2lout auxiliary program
make clean        # Remove compiled objects and binaries
make test         # Regression test: compares doc/user output against an older lout version
make testclean    # Remove test artifacts from doc/user/
```

The compiler is gcc with `-ansi -std=c99 -pedantic -Wall -O3`. C sources, object files, and `externs.h` all live directly in `lout/` — this fork (william8000) has a flat layout, *not* the `lout/src/` arrangement of upstream Lout. All `.c` files include `externs.h` as their sole header.

For installation: `make install` copies binaries to `$(PREFIX)/bin` (default `/usr/local`) and libraries to `$(PREFIX)/share/lout-3.43/lib`. The install step also runs `lout -x` to initialize hyphenation and database index files.

## Source Architecture

All C source lives directly in `lout/` (flat layout — no `src/` subdir in this fork). The codebase is 53 modules (`z01.c`–`z53.c`) plus `prg2lout.c` and a single shared header `externs.h`.

Key module groups:

- **Supervisor & main**: `z01.c` — contains `main()`, entry point; back-end dispatch lives at z01.c:689–705
- **Lexer/Parser pipeline**: `z02.c` (lexical analyser), `z03.c` (file service), `z04.c` (token service), `z05.c` (definition reader), `z06.c` (parser)
- **Object system**: `z07.c` (object service), `z08.c` (object manifest), `z09.c` (closure expansion)
- **Galley system** (Lout's core layout engine): `z18.c`–`z22.c` — galley transfer, attaching, flushing, sizing, and service
- **Output backends**: `z48.c`/`z50.c` (PDF), `z49.c` (PostScript — **frozen**), `z51.c` (plain text), **`z53.c` (SVG)**
- **Typography**: `z11.c` (style), `z13.c` (object breaking), `z14.c` (fill/paragraph breaking), `z36.c` (hyphenation), `z37.c` (font service)
- **Cross-references & databases**: `z10.c`, `z33.c`
- **Symbol table**: `z29.c`, `z30.c`
- **Support**: `z28.c` (errors), `z31.c` (memory allocator), `z39.c` (string handler), `z42.c` (colour), `z43.c` (language), `z52.c` (texture)

### SVG back-end (z53.c)

New in this fork. Sibling to `z49.c` (PostScript), selected by `lout -G`. Uses Lout's existing galley engine, font metrics, and colour service — only the emission layer differs (SVG drawing primitives instead of PostScript). Implements the full `BACK_END` interface defined in `externs.h:2073–2116`:

- `<svg>` per page with viewBox in points; coordinate flip from Lout's bottom-left to SVG top-left handled per-emission.
- Text emission via `<text>` elements with font-family (from `FontFamily`), font-size (from `FontSize`), font-weight/font-style derived from `FontFace` ("Bold"/"Italic"/"Slope"/"Oblique" substring detection), and fill from `ColourCommand` (parses `setrgbcolor` / `setgray`).
- Graphics state stack: `SaveGraphicState` opens a `<g>` level; each `CoordTranslate`/`CoordRotate`/`CoordScale`/`CoordHMirror`/`CoordVMirror` opens a nested `<g transform="…">`; `RestoreGraphicState` closes all groups opened in that level. Lout's positive-angle CCW rotation is negated for SVG's CW convention.
- `@IncludeGraphic` dispatches by file extension: `.svg`/`.png`/`.jpg`/`.gif` → `<image href>`; `.eps` → unsupported in SVG mode.
- `@Graphic` content: joined into one buffer, then leading character determines route — `<` means raw HTML/SVG markup, pass through verbatim; anything else is treated as PostScript and emitted as an XML comment (translation to SVG drawing ops is future work, see `lout/SVG_PORTING.md`).
- Cross-references: `LinkSource`/`LinkDest`/`LinkURL` emit clickable `<a xlink:href>` overlays sized to the bbox.

`z49.c` (PostScript) is frozen — every change to the SVG path is additive. PDF mode (`mdlout --format=pdf`) goes through `z49.c → ps2pdf` and is bit-identical to the pre-z53.c era.

### Three new passthrough macros (`lout/include/svgmacros`)

`@Math { ... }` — wraps body in `<foreignObject><span class="math">…</span></foreignObject>` (rendered client-side by KaTeX).
`@ABC { ... }` — wraps body in `<foreignObject><div class="abc-music" data-abc="…"></div></foreignObject>` (rendered client-side by abcjsharp).
`@SVG { ... }` — passes body through verbatim as nested SVG.
`@SVGFile { path }` — uses `@IncludeGraphic` to inline the file (SVG/PNG/JPG accepted in SVG mode).

All four are opt-in: source files must `@SysInclude { svgmacros }`. mdlout adds this automatically when any of the routed Markdown blocks is present. PostScript mode has fallback definitions that emit a placeholder so the macros don't break legacy documents.

`externs.h` defines all shared types, macros, and function prototypes. Build-time configuration (OS, library paths, character sets, locale, debug flags) is set via `-D` flags in the makefile.

## Library Files

- `lout/include/` — Lout package definitions (the standard library): `doc`, `book`, `slides`, `eq` (equations), `fig` (figures), `diag` (diagrams), `graph`, `tab`/`tbl` (tables), language-specific formatting, etc.
- `lout/data/` — database files (`.ld`) and their indexes (`.li`)
- `lout/font/` — Adobe AFM font metrics
- `lout/maps/` — LCM character mapping files
- `lout/hyph/` — hyphenation pattern files (`.lh` source, `.lp` packed)
- `lout/doc/` — documentation source (in Lout format) and pre-built PDFs

## Key Makefile Variables

- `DEBUGGING=1` + `TRACING=-g` enables debug/tracing mode (slower, larger binary)
- `PDF_COMPRESSION=1` + `ZLIB`/`ZLIBPATH` enables compressed PDF output (requires zlib)
- `CHARIN=1` (ISO-LATIN-1 input), `CHAROUT=0` (7-bit ASCII PostScript output) — recommended defaults
- `DESTDIR` support for staged installs

## Testing

`make test` compares PostScript output of `doc/user/all` between the current build and a reference older version (`lout-3.40-18sep20`). The older binary must be installed at `/usr/local/bin/lout-3.40-18sep20`. Output is diffed with `diff --text`.

## mdlout — Markdown to Lout Converter

`mdlout.py` (in repo root) converts Markdown files to Lout source. It's a single-file Python 3.10+ script with no external Python dependencies. The default output is **HTML** wrapping a Lout-emitted SVG (using the new `z53.c` back-end); `--format=pdf` selects the legacy PostScript pipeline. There is a regression test suite at `tests/` — `bash tests/run_all.sh` runs the snippet corpus through both back-ends and produces a side-by-side diff gallery at `tests/report.html`.

```bash
./mdlout.py input.md                    # produces input.html (default)
./mdlout.py input.md --format=pdf       # produces input.pdf (legacy path)
./mdlout.py input.md -o out.html        # custom output path
./mdlout.py input.md --lout-only        # print Lout source to stdout
./mdlout.py input.md --ps               # stop at PostScript (input.ps)
./mdlout.py input.md --external-assets  # use CDN for KaTeX/abcjsharp instead of inlining
./mdlout.py input.md --no-math-engine   # omit KaTeX (smaller HTML)
./mdlout.py input.md --no-music-engine  # omit abcjsharp (smaller HTML)
./mdlout.py input.md --watch            # rebuild on every save (Ctrl-C to exit)
./mdlout.py input.md --serve            # http://127.0.0.1:8080/ with SSE live-reload
./mdlout.py input.md --serve 9000       # custom port
```

### `--watch` and `--serve` (live preview)

Both are stdlib-only and meant for the markdown author's edit loop.

- `--watch` polls `args.input`'s mtime every 500 ms via `os.path.getmtime`
  and re-runs `_build_once()` whenever it advances. The initial build
  runs immediately. `[rebuilt HH:MM:SS]` lines go to stderr. Transient
  exceptions (parse errors, lout failures, file races) are caught and
  logged so the loop keeps going; only SIGINT exits.
- `--serve [PORT]` (default 8080) is `--watch` plus a
  `http.server.ThreadingHTTPServer` bound to `127.0.0.1:PORT`. Two routes:
  `GET /` reads the freshly-built HTML off disk and streams it back; `GET
  /events` is an SSE long-poll that sends `event: reload` on every
  rebuild (with a 15 s heartbeat in between). A 5-line `<script>` injected
  before `</body>` opens an `EventSource("/events")` and calls
  `location.reload()` on the reload event. Only `--format=html` is
  supported (server overrides to HTML if asked otherwise).
- Inter-thread signalling uses a `threading.Condition` and a monotonic
  `_serve_version` counter; the watch loop runs in the main thread and
  the HTTP server in a daemon thread, so Ctrl-C cleanly tears both down.

### Supported Markdown extensions

Headings (H1-H6, ATX and setext), **bold**, *italic*, `inline code`, ~~strikethrough~~, ^superscript^, [links](url), images, bullet/numbered/task/definition lists, blockquotes, fenced code blocks, pipe and grid tables, horizontal rules, math blocks (`$$` or ````math`), inline math (`$..$` and `\(..\)`), admonitions (`!!! type "title"`), page breaks (`\newpage`), `[TOC]` placeholders, HTML entities, and backslash escapes.

### Math, music, raw SVG (HTML mode)

In HTML mode these route through the new passthrough macros:

- `$..$` / `\(..\)` / `$$..$$` / ` ```math ` fences → `@Math { ... }` → KaTeX in the browser
- ` ```abc ` fences → `@ABC { ... }` → abcjsharp in the browser
- ` ```svg ` fences → `@SVG { ... }` → raw inline SVG
- `![alt](file.svg)` → `@SVGFile { file.svg }` → inline `<image>`

In PDF mode the same documents still build (svgmacros has fallback definitions); math goes through the placeholder, ABC blocks render as an `[ABC music notation: ...]` literal, and SVG is omitted with a note.

### Raw Lout passthrough

Use a ````lout` fenced code block to inject raw Lout source directly into the output:

    ```lout
    @CentredDisplay @Eq { a sup 2 + b sup 2 = c sup 2 }
    ```

### YAML frontmatter → Lout styling

YAML frontmatter maps to Lout `@Use { @BasicSetup }`, `@Use { @DocumentSetup }`, and type-specific setup clauses. When frontmatter is present, mdlout generates a custom setup instead of using `@SysInclude { doc }`.

```yaml
---
type: report           # doc (default), report, book, slides
title: My Report
author: Jane Doe
font: Helvetica Base 11p
page: Letter           # A4, Letter, etc.
para-indent: 0f
para-gap: 1.0v
page-headers: None     # None, Simple, Titles
columns: 2
---
```

Key frontmatter fields: `font`, `page`, `orientation`, `top-margin`, `foot-margin`, `left-margin`, `right-margin`, `para-gap`, `para-indent`, `language`, `colour`, `heading-font`, `fixed-font`, `columns`, `page-headers`, `contents`, `optimize-pages`. Report adds: `cover`, `date`, `section-numbers`. Book adds: `title-font`, `chapter-font`, `chapter-start`, `chapter-numbers`.

For `type: report`/`book`, markdown `#` headings become Lout `@Section`/`@Chapter` with automatic numbering. For `type: doc` (default), headings render as styled `@Display` blocks.

### mydefs

A `mydefs` file next to the input `.md` is automatically copied into the build directory for Lout to pick up via `@Include { mydefs }`. Use it for raw Lout macro definitions. Alternatively pass `--mydefs path/to/mydefs`.

### Architecture

The converter has four phases: (1) `parse_frontmatter()` extracts YAML config, (2) block-level parser splits markdown into `Block` objects (including `BlockType.ABC` / `BlockType.SVG_RAW` / `BlockType.MATH_BLOCK`), (3) `convert_inline()` handles inline formatting using a placeholder system that protects code/links/math from double-escaping, (4) `generate_lout()` produces the preamble (setup clauses from frontmatter) and maps blocks to Lout constructs. For `report`/`book` types, `_generate_sectioned_body()` wraps headings in `@Section @Begin`/`@End` nesting. When any math/music/SVG block is present, the preamble auto-emits `@SysInclude { svgmacros }`.

Two output pipelines:

- **HTML mode** (default): md → .lt → .svg (`lout -G`) → .html (wraps the SVG with KaTeX + abcjsharp script tags via `_build_html_scaffold`). KaTeX is loaded from a local copy if present at `/usr/lib/node_modules/katex/` or `/usr/share/javascript/katex/`, else CDN. abcjsharp is inlined from `~/projects/abcjsharp/dist/abcjs-basic-min.js` (the user's fork — see project memory).
- **PDF mode** (`--format=pdf`): md → .lt → .ps (`lout`) → .pdf (`ps2pdf`). Bit-identical to the pre-z53.c era. The lout binary is auto-discovered, lout runs up to 3 times for cross-reference resolution.

### Directory layout (additions)

- `examples/` — 8 sample Markdown files covering hello, typography, lists+tables, math, music, report, raw Lout/SVG, kitchen-sink. Each builds in both `--format=html` and `--format=pdf`.
- `tests/` — regression framework. `snippets/*.lt` (20 single-feature snippets), `run_compare.sh` (PS+SVG → 150dpi PNG → ImageMagick AE diff), `compare.py` (per-snippet pass/fail + JSON), `run_all.sh` orchestrator, `report.html` (side-by-side gallery).
- `lout/SVG_PORTING.md` — function-by-function port plan from `z49.c` to `z53.c`. Living document; consult before adding to `z53.c`.
- `lout/include/svgmacros` — the three passthrough macros.

### Constraints on C code in `lout/`

All new C must be **ANSI C, tcc-compilable**. No mid-block declarations, no `//` comments, no designated initializers, no GCC extensions. Match the dialect already used in z01.c–z52.c. The existing makefile builds with `-ansi -std=c99 -pedantic -Wall -O3`; tcc compatibility is the hard floor.
