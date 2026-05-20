# mdlout

[![CI](https://github.com/jclements3/mdlout/actions/workflows/ci.yml/badge.svg)](https://github.com/jclements3/mdlout/actions/workflows/ci.yml)

**mdlout** is a Markdown to {HTML/SVG, PDF} converter built on top of a forked
copy of the [Lout](https://github.com/jclements3/lout) typesetting system (an
ANSI C document formatter by Jeffrey H. Kingston). It pairs Lout's
professional-grade typesetting (galley-based line breaking, hyphenation,
high-quality tables, equations, and the `@Graphic` / `@Diag` / `@Fig` / `@Tab`
drawing primitives that browser-native typesetters cannot match) with two
delivery formats: the **default HTML/SVG path** (a new SVG back-end inside
Lout emits SVG drawing commands that mdlout wraps in an HTML scaffold for the
browser), and the **legacy PDF path** (Markdown to Lout to PostScript to PDF),
preserved bit-identically.

## Status

- HTML/SVG path: **default**. SVG back-end (`lout/z53.c`) plus three
  passthrough macros (`@Math`, `@ABC`, `@SVG`). Text content, page chrome,
  simple shapes, and the arrowstyle gallery render correctly. `@Math` via
  KaTeX, `@ABC` via abcjsharp, and `@SVG` raw passthrough all work. The
  long tail of complex `@Diag` / `@Fig` / `@Eq` rendering is partial — see
  [TODO.md](TODO.md).
- PDF path: working, frozen. PostScript back-end (`z49.c`) untouched.

49+ regression snippets pass via `bash tests/run_all.sh`; see
[tests/README.md](tests/README.md).

See [CLAUDE.md](CLAUDE.md) for engineering details and [TODO.md](TODO.md) for
the current roadmap.

## Quick start

```bash
git clone <repo-url> mdlout
cd mdlout
git submodule update --init             # populate lout/
cd lout && git checkout svg-backend     # the fork's working branch
make lout && cd ..                      # build the lout binary
./mdlout.py input.md                    # produces input.html (default)
./mdlout.py input.md --format=pdf       # legacy PDF pipeline
```

The submodule lives at https://github.com/jclements3/lout (the maintainer's
fork). Its default working branch is `svg-backend`, which contains the new
`z53.c` SVG back-end and the `svgmacros` library file. You must check out
that branch after `git submodule update --init`.

## Requirements

- Python 3.10+ (no third-party Python packages).
- A built `lout` binary from the vendored submodule (`cd lout && make lout`).
- `ps2pdf` (from Ghostscript) for the PDF path.
- For the HTML path: a modern browser. KaTeX and abcjsharp are inlined from a
  local copy if found at `/usr/lib/node_modules/katex/`,
  `/usr/share/javascript/katex/`, or `~/projects/abcjsharp/dist/`; otherwise
  loaded from CDN, or pass `--external-assets` to force CDN.

## The two output paths

### HTML/SVG (default)

```
input.md ──[mdlout.py]──> input.lt ──[lout -G, SVG back-end z53.c]──> input.svg ──[mdlout.py wrap]──> input.html
```

`z53.c` mirrors `z49.c` capability-for-capability, emitting SVG instead of
PostScript. mdlout wraps the SVG in a single-file HTML page that inlines (or
links) KaTeX and abcjsharp so the browser renders math and music client-side.

### PDF (legacy)

```
input.md ──[mdlout.py]──> input.lt ──[lout, PS back-end z49.c]──> input.ps ──[ps2pdf]──> input.pdf
```

The PostScript back-end (`lout/z49.c`) is frozen. The pipeline runs `lout` up
to three times for cross-reference resolution, then Ghostscript's `ps2pdf`.

## CLI

```text
./mdlout.py input.md                    # produces input.html (default)
./mdlout.py input.md --format=pdf       # produces input.pdf (legacy path)
./mdlout.py input.md -o out.html        # custom output path
./mdlout.py input.md --ps               # stop at PostScript (input.ps)
./mdlout.py input.md --lout-only        # emit Lout source to stdout
./mdlout.py input.md --lout-only -o out.lt
./mdlout.py input.md --external-assets  # CDN for KaTeX/abcjsharp instead of inlining
./mdlout.py input.md --no-math-engine   # omit KaTeX (smaller HTML)
./mdlout.py input.md --no-music-engine  # omit abcjsharp (smaller HTML)
./mdlout.py input.md --mydefs path/to/mydefs
./mdlout.py input.md --lout-bin /path/to/lout
./mdlout.py input.md --lout-args "..."
```

### Live preview: `--watch` and `--serve`

```text
./mdlout.py input.md --watch                 # rebuild on every save (Ctrl-C to exit)
./mdlout.py input.md --serve                 # serve at http://127.0.0.1:8080/
./mdlout.py input.md --serve 9000            # custom port
```

`--watch` polls the input file's mtime (every 500 ms) and re-runs the full
pipeline whenever it changes. Each rebuild prints `[rebuilt HH:MM:SS] PATH`
to stderr. Transient build errors are caught and logged; the watcher keeps
running.

`--serve [PORT]` (default port `8080`) is `--watch` plus a minimal
single-threaded HTTP server:

- `GET /` returns the rendered HTML (always fresh on disk).
- `GET /events` is a Server-Sent Events stream; a `reload` event is sent
  on every successful rebuild. A tiny `<script>` injected into the served
  HTML opens an `EventSource` to `/events` and calls `location.reload()`,
  so a browser tab refreshes automatically after each save.

Only `--format=html` is supported by `--serve` (it overrides PDF). Both
modes are stdlib-only (no extra dependencies).

## Frontmatter reference

YAML frontmatter at the top of the markdown file maps to Lout setup clauses.
When frontmatter is present, mdlout generates a custom setup instead of using
`@SysInclude { doc }`.

```yaml
---
type: report           # doc (default), report, book, slides
title: My Report
author: Jane Doe
font: Helvetica Base 11p
page: Letter
orientation: Portrait
para-indent: 0f
para-gap: 1.0v
page-headers: None     # None, Simple, Titles
columns: 2
---
```

Common keys:

| Key                          | Purpose                                              |
| ---------------------------- | ---------------------------------------------------- |
| `type`                       | `doc` (default), `report`, `book`, `slides`          |
| `title`, `author`, `date`    | Document metadata                                    |
| `font`                       | Base font, e.g. `Times Base 10p`                     |
| `page`                       | Page size: `A4`, `Letter`, etc.                      |
| `orientation`                | `Portrait` or `Landscape`                            |
| `top-margin`, `foot-margin`, `left-margin`, `right-margin` | Margins (Lout units)   |
| `para-indent`, `para-gap`    | Paragraph indent and spacing                         |
| `language`                   | Hyphenation/locale, e.g. `English`                   |
| `colour`                     | Default text colour                                  |
| `heading-font`, `fixed-font` | Override fonts for headings and code                 |
| `columns`                    | Number of columns                                    |
| `page-headers`               | `None`, `Simple`, `Titles`                           |
| `contents`                   | Generate table of contents                           |
| `optimize-pages`             | Lout's page-breaking optimizer                       |

`report` adds `cover`, `date`, `section-numbers`. `book` adds `title-font`,
`chapter-font`, `chapter-start`, `chapter-numbers`.

For `type: report` and `type: book`, Markdown `#` headings become Lout
`@Section` / `@Chapter` with automatic numbering. For `type: doc` (default),
headings render as styled `@Display` blocks.

## Markdown extensions supported

- Headings: H1-H6, ATX (`#`) and setext (`===`, `---`) forms
- Emphasis: `**bold**`, `*italic*`, `` `inline code` ``, `~~strikethrough~~`,
  `^superscript^`
- `[links](url)`
- Images
- Lists: bullet, numbered, task, and definition
- Blockquotes
- Fenced code blocks
- Pipe tables and grid tables
- Horizontal rules
- Math blocks (`$$ ... $$` and ```` ```math ```` fences), inline math
  (`$..$` and `\(..\)`)
- Admonitions: `!!! type "title"`
- `\newpage` page breaks
- `[TOC]` placeholders
- HTML entities and backslash escapes
- Raw Lout passthrough via ```` ```lout ```` fenced code blocks

In HTML mode, additional fence and inline routings produce the new macros:

- `$$ ... $$` / ```` ```math ```` / `$ ... $` / `\(..\)` → `@Math { ... }`
- ```` ```abc ```` → `@ABC { ... }`
- ```` ```svg ```` → `@SVG { ... }`
- Markdown image of a `.svg` file → `@SVGFile { path }`

## Raw Lout passthrough

Use a `lout` fenced code block to inject Lout source directly:

````markdown
```lout
@CentredDisplay @Eq { a sup 2 + b sup 2 = c sup 2 }
```
````

## The new macros (HTML/SVG path)

| Macro       | Argument               | SVG back-end behaviour                                      | PostScript back-end behaviour                  |
| ----------- | ---------------------- | ----------------------------------------------------------- | ---------------------------------------------- |
| `@Math`     | LaTeX math source      | Emits `<foreignObject>` with `<span class="math">...</span>`; KaTeX renders client-side. | Stub / fallback (uses Lout `@Eq` where possible). |
| `@ABC`      | ABC music notation     | Emits `<foreignObject>` with `<div class="abc-music" data-abc="...">`; abcjsharp renders client-side. | Stub / fallback. |
| `@SVG`      | Raw SVG fragment       | Emits the argument verbatim as nested SVG.                  | Not supported; emits a placeholder.            |
| `@SVGFile`  | Path to `.svg` file    | Inlines the file's `<svg>` root as a `<g>`.                 | Converted via `rsvg-convert`/`inkscape` to EPS if available. |

Math and music are *passthrough* in HTML mode: Lout does not render them;
the browser does. SVG geometry of those constructs is finalized client-side.

## mydefs convention

A file named `mydefs` next to the input `.md` is automatically copied into the
build directory, where Lout picks it up via `@Include { mydefs }`. Use it for
raw Lout macro definitions specific to a document. The location can also be
set explicitly with `--mydefs path/to/mydefs`.

## Project layout

```
mdlout/
  mdlout.py        # the converter (single-file Python 3.10+)
  lout/            # git submodule: jclements3/lout, branch svg-backend
  examples/        # sample documents (see examples/README.md)
  tests/           # regression tests (see tests/README.md)
  CLAUDE.md        # engineering details
  TODO.md          # roadmap and current status
  README.md        # this file
```

## Further reading

- [CLAUDE.md](CLAUDE.md) — engineering context: source architecture, build
  variables, mdlout phases, frontmatter mapping.
- [TODO.md](TODO.md) — current roadmap, what works, what's still in flight.
- [tests/README.md](tests/README.md) — regression test framework.
- [examples/README.md](examples/README.md) — sample documents.
- [lout/README](lout/README) — upstream Lout README (Jeffrey H. Kingston's
  original).

## License

Lout (in `lout/`) is GPLv3, copyright 1994-2023 Jeffrey H. Kingston.
The `mdlout.py` converter follows the same license unless otherwise noted.
