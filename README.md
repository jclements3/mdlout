# mdlout

**mdlout** is a Markdown to {PDF, HTML/SVG} converter built on top of a forked
copy of the [Lout](https://github.com/william8000/lout) typesetting system (an
ANSI C document formatter by Jeffrey H. Kingston). It pairs Lout's
professional-grade typesetting (galley-based line breaking, hyphenation,
high-quality tables, equations, and the `@Graphic` / `@Diag` / `@Fig` / `@Tab`
drawing primitives that browser-native typesetters cannot match) with two
delivery formats: a legacy PDF path (Markdown to Lout to PostScript to PDF) and
a new HTML/SVG path in which a new SVG back-end inside Lout itself emits SVG
drawing commands, which mdlout then wraps in an HTML scaffold for the browser.

## Status

- PDF path: working today.
- HTML/SVG path: **in progress**. A new SVG back-end (`lout/z53.c`) and three
  passthrough macros (`@Math`, `@ABC`, `@SVG`) are being added. The HTML path
  will become the default once it lands. The PostScript back-end is **frozen**
  during this work; the PDF pipeline is preserved bit-identically.

See [TODO.md](TODO.md) for the full roadmap and [CLAUDE.md](CLAUDE.md) for
engineering details.

## Quick start

```bash
git clone <repo-url> mdlout
cd mdlout
git submodule update --init        # populate lout/
cd lout && make lout && cd ..      # build the lout binary
./mdlout.py input.md               # produces input.pdf today
```

Once the HTML path lands, the default output flips to HTML:

```bash
./mdlout.py input.md               # produces input.html (planned default)
./mdlout.py input.md --format=pdf  # legacy PDF pipeline
```

## Requirements

- Python 3.10+ (no third-party Python packages).
- A built `lout` binary from the vendored submodule (`cd lout && make lout`).
- `ps2pdf` (from Ghostscript) for the PDF path.
- Optional, for richer PDF output of music/diagrams: `rsvg-convert` or
  `inkscape`, and `node` for ABC music rendering.
- The HTML/SVG path (planned) will pull `KaTeX` and `abcjsharp` from
  `/home/clementsj/projects/abcjsharp/dist/` (a personal abcjs fork with
  grand-staff support for harp music) for self-contained mode, or from CDN
  with `--external-assets`.

## The two output paths

### PDF (legacy, available today)

```
input.md ──[mdlout.py]──> input.lt ──[lout, PS back-end]──> input.ps ──[ps2pdf]──> input.pdf
```

The PostScript back-end is `lout/z49.c`. The pipeline runs `lout` up to three
times for cross-reference resolution, then Ghostscript's `ps2pdf` for the PDF.

### HTML/SVG (new default, in progress)

```
input.md ──[mdlout.py]──> input.lt ──[lout, SVG back-end z53.c]──> input.svg ──[mdlout.py wrap]──> input.html
```

`z53.c` mirrors `z49.c` capability-for-capability, emitting SVG instead of
PostScript. mdlout wraps the SVG in a single-file HTML page that inlines (or
links) KaTeX and abcjsharp so the browser renders math and music client-side.

## CLI

Current flags (PDF pipeline):

```text
./mdlout.py input.md                  # produces input.pdf
./mdlout.py input.md -o out.pdf       # custom output path
./mdlout.py input.md --ps             # stop at PostScript (input.ps)
./mdlout.py input.md --lout-only      # emit Lout source to stdout
./mdlout.py input.md --lout-only -o out.lt
./mdlout.py input.md --mydefs path/to/mydefs
./mdlout.py input.md --lout-bin /path/to/lout
./mdlout.py input.md --lout-args "..."
```

Planned (HTML pipeline):

```text
./mdlout.py input.md --format=html    # default once z53.c lands
./mdlout.py input.md --format=pdf     # legacy path, preserved bit-identically
./mdlout.py input.md --external-assets   # link KaTeX/abcjsharp from CDN
```

### Live preview: `--watch` and `--serve`

```text
./mdlout.py input.md --watch                 # rebuild on every save (Ctrl-C to exit)
./mdlout.py input.md --serve                 # serve at http://127.0.0.1:8080/
./mdlout.py input.md --serve 9000            # custom port
```

`--watch` polls the input file's mtime (every 500 ms) and re-runs the
full pipeline whenever it changes. Each rebuild prints `[rebuilt HH:MM:SS]
PATH` to stderr. Transient build errors are caught and logged; the watcher
keeps running.

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
- `[links](url)` (rendered as footnotes in the PDF path)
- Images
- Lists: bullet, numbered, task, and definition
- Blockquotes
- Fenced code blocks
- Pipe tables and grid tables
- Horizontal rules
- Math blocks (`$$ ... $$` and ```` ```math ```` fences)
- Admonitions: `!!! type "title"`
- `\newpage` page breaks
- `[TOC]` placeholders
- HTML entities and backslash escapes
- Raw Lout passthrough via ```` ```lout ```` fenced code blocks

In HTML mode (planned), additional fence and inline routings produce the new
macros:

- `$$ ... $$` and ```` ```math ```` → `@Math { ... }`
- `$ ... $` inline → inline `@Math { ... }`
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

## The new macros (HTML/SVG path, planned)

| Macro       | Argument               | SVG back-end behaviour                                      | PostScript back-end behaviour                  |
| ----------- | ---------------------- | ----------------------------------------------------------- | ---------------------------------------------- |
| `@Math`     | LaTeX math source      | Emits `<foreignObject>` with `<span class="math">...</span>`; KaTeX renders client-side. | Stub / fallback (uses Lout `@Eq` where possible). |
| `@ABC`      | ABC music notation     | Emits `<foreignObject>` with `<div class="abc-music" data-abc="...">`; abcjsharp renders client-side. | Stub / fallback (planned via abcjsharp + rsvg-convert when present). |
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
  lout/            # git submodule: forked C Lout (with new z53.c SVG back-end)
  examples/        # sample documents                  [planned]
  tests/           # regression tests                  [planned]
  CLAUDE.md        # engineering details
  TODO.md          # roadmap
  README.md        # this file
```

`examples/` and `tests/` are on the roadmap, not yet present.

## Further reading

- [CLAUDE.md](CLAUDE.md) — engineering context: source architecture, build
  variables, mdlout phases, frontmatter mapping.
- [TODO.md](TODO.md) — current roadmap: SVG back-end design, new macros, HTML
  wrapper, examples and tests.
- [lout/README](lout/README) — upstream Lout README (Jeffrey H. Kingston's
  original).

## License

Lout (in `lout/`) is GPLv3, copyright 1994-2023 Jeffrey H. Kingston.
The `mdlout.py` converter follows the same license unless otherwise noted.
