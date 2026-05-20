# mdlout tutorial

A hands-on walkthrough that takes you from a fresh `git clone` to building
HTML and PDF documents with mathematics, music, diagrams, tables, and live
preview. Every command in this guide has been run against the current
working tree; if something fails for you, you have hit either an
environment difference or a regression, not a typo.

The walkthrough assumes you are on Linux or WSL, have a working C
toolchain (`gcc`, `make`), Python 3.10 or newer, and Ghostscript
(`ps2pdf`) installed. For the HTML path a modern browser is enough.

---

## 1. Install

Clone the repo, initialise the Lout submodule, switch the submodule to
its working branch, and build the `lout` binary. From a directory of
your choice:

```bash
git clone https://github.com/jclements3/mdlout.git
cd mdlout
git submodule update --init             # populates lout/
cd lout
git checkout svg-backend                # the SVG back-end lives here
make lout                               # builds ./lout/lout
cd ..
```

The `make lout` step takes about 20 seconds on a modern laptop and
produces `lout/lout`. There is no separate install step --- `mdlout.py`
discovers the binary at that path automatically.

Verify the toolchain:

```bash
./mdlout.py --help
ls lout/lout
```

`./mdlout.py --help` prints the full CLI reference; `lout/lout`
should be an executable. If you ever want the PDF path you also need
Ghostscript:

```bash
which ps2pdf
```

If `ps2pdf` is missing, `apt install ghostscript` (Debian/Ubuntu) or
your distro equivalent. The HTML path does not need Ghostscript at all.

---

## 2. Hello world

Create a one-paragraph Markdown file and render it:

```bash
cat > hello.md << 'EOF'
Hello from mdlout! If you see this paragraph in your browser, the
Markdown to Lout to SVG to HTML pipeline is working.
EOF
./mdlout.py hello.md
```

`mdlout.py` prints a list of inlined assets and then the output filename
to stderr. The result is `hello.html` in the current directory --- open
it with `xdg-open hello.html`, `firefox hello.html`, or just point a
browser at the file directly.

For reference, the project ships a slightly fancier version of this
example as
[`examples/01_hello.md`](../examples/01_hello.md)
with a pre-built render at
[`examples/out/01_hello.html`](../examples/out/01_hello.html) and
[`examples/out/01_hello.pdf`](../examples/out/01_hello.pdf).

Naming notes:

- `./mdlout.py hello.md` writes to `hello.html` in your current working
  directory --- not next to the input file. Use `-o` to choose the
  output path explicitly:

  ```bash
  ./mdlout.py /tmp/notes/hello.md -o /tmp/notes/hello.html
  ```

- Lout caches a per-document index in `lout.li` and `lout.lix` in your
  cwd. They are safe to delete; mdlout will recreate them on the next
  build.

---

## 3. Frontmatter

Add a YAML frontmatter block at the top of the file to control document
type, page geometry, fonts, columns, and headings. With frontmatter,
mdlout generates a custom Lout setup instead of falling back to the
plain `doc` package.

```markdown
---
title: My first report
author: Your Name
type: report
page: Letter
columns: 2
font: Helvetica Base 10p
para-gap: 1.0v
contents: Yes
---

# Introduction

This is the body of a two-column Helvetica report. Because `type` is
`report`, the `#` heading above becomes an `@Section` with automatic
numbering.

# Methods

A second section. The cover page and table of contents (`contents: Yes`)
are generated automatically by the Lout `report` package.
```

Save that as `report.md` and run:

```bash
./mdlout.py report.md
```

A handful of keys you will reach for most often:

| Key            | Example value           | Effect                                  |
| -------------- | ----------------------- | --------------------------------------- |
| `type`         | `report`                | Switch to `@Section` headings, cover    |
| `title`        | `My report`             | Cover page title                        |
| `author`       | `Jane Doe`              | Cover page author                       |
| `page`         | `Letter` / `A4`         | Page size                               |
| `orientation`  | `Portrait` / `Landscape`| Page orientation                        |
| `columns`      | `2`                     | Multi-column body                       |
| `font`         | `Times Base 11p`        | Body font and size                      |
| `para-gap`     | `1.0v`                  | Vertical gap between paragraphs         |
| `contents`     | `Yes`                   | Generate a table of contents            |
| `page-headers` | `Titles`                | Running header style                    |

See the [README](../README.md) for the full key list (it documents the
`book`-specific `chapter-font`, the `report`-specific `cover`, and a
dozen others).

---

## 4. Math

mdlout routes LaTeX-style math through the `@Math` macro, which the
HTML scaffold renders client-side with KaTeX. Inline math uses
`$...$` or `\(...\)`; display math uses `$$...$$` or a fenced
```` ```math ```` block.

Save this as `math.md`:

````markdown
# Math sampler

Inline: the golden ratio is $\varphi = \tfrac{1 + \sqrt{5}}{2}$.

A definite integral:

$$
\int_{-\infty}^{\infty} e^{-x^{2}} \, dx = \sqrt{\pi}
$$

A two-by-two matrix:

$$
\det\begin{pmatrix} a & b \\ c & d \end{pmatrix} = ad - bc
$$

A fenced display block with a fraction:

```math
\frac{a}{b} + \frac{c}{d} = \frac{ad + bc}{bd}
```
````

Build with:

```bash
./mdlout.py math.md
```

KaTeX is inlined into the HTML if it is installed at any of the paths
mdlout probes (`/usr/lib/node_modules/katex`, `/usr/share/javascript/katex`,
and a few others); otherwise it is loaded from a CDN at view time, or
forced to the CDN with `--external-assets`. To omit the math engine
entirely (smaller HTML, raw LaTeX visible in the page), pass
`--no-math-engine`.

In `--format=pdf` mode math is still routed through `@Math`, but
KaTeX is not available --- the PDF path is intended for prose-heavy
documents where the SVG/HTML output is the canonical render.

See [`examples/04_math.md`](../examples/04_math.md) for a fuller
sampler, including aligned equations and binomial coefficients.

---

## 5. Music

Fenced ```` ```abc ```` blocks render as engraved music. The HTML
scaffold inlines `abcjs` (the user's
[abcjsharp fork](https://github.com/jclements3/abcjsharp) at
`~/projects/abcjsharp`, if present; otherwise the CDN copy) and
renders ABC notation in the browser at view time.

```markdown
# A tune

```abc
X:1
T:Frere Jacques
M:4/4
L:1/4
K:G
G A B G | G A B G | B c d2 | B c d2 |
```
```

Save as `music.md` and build:

```bash
./mdlout.py music.md
```

mdlout looks for the abcjsharp build at `~/projects/abcjsharp/dist/`
before falling back to the CDN. If you have the fork checked out, the
HTML you ship is fully self-contained --- no network needed at view
time. To skip embedding the music engine, pass `--no-music-engine`.

The abcjsharp fork adds harp grand-staff features (a brace-coupled
treble-plus-bass `%%score` layout) used in
[`examples/05_music.md`](../examples/05_music.md). Stock `abcjs` works
too but does not engrave that variant.

---

## 6. Diagrams

mdlout has no Markdown-level diagram syntax; instead, use a raw
```` ```lout ```` fenced block to inject Lout's `@Diag` package
directly. When mdlout sees `@Diag`, `@Node`, `@Link`, `@Tree`, or
any of the diag shape macros (`@Ellipse`, `@Circle`, `@Diamond`,
`@Triangle`, `@SyntaxDiag`), it automatically adds
`@SysInclude { diag }` to the preamble.

A minimal two-node-and-a-link diagram:

````markdown
# Pipeline

```lout
@CentredDisplay @Diag {
A:: @Node { Markdown } ||1.5c B:: @Node { Lout } ||1.5c C:: @Node { HTML }
// @Link from { A } to { B } arrow { yes } arrowstyle { solid }
// @Link from { B } to { C } arrow { yes } arrowstyle { solid }
}
```
````

Save as `pipeline.md` and build:

```bash
./mdlout.py pipeline.md
```

The Lout User's Guide chapter 9 covers `@Diag` in full. For a
laid-out reference covering every documented feature, see
[`examples/diag_gallery.md`](../examples/diag_gallery.md): all ten
arrowstyles, every shape macro, and `@Tree`. The follow-up
[`examples/complex_diag.md`](../examples/complex_diag.md) shows
syntax diagrams, a binary search tree, and a five-arrow flowchart.

---

## 7. Tables

Both **pipe tables** and **grid tables** work. Pipe tables are concise;
grid tables let cells wrap across multiple lines.

A pipe table:

```markdown
| Feature   | Status      | Notes              |
|-----------|-------------|--------------------|
| Text      | working     | full font support  |
| Math      | working     | via KaTeX          |
| Music     | working     | via abcjsharp      |
| Diagrams  | partial     | @Diag passthrough  |
```

A grid table (cells can wrap, paragraphs allowed inside cells):

```markdown
+---------------+-----------------------------+-------------+
| Feature       | Status                      | Owner       |
+===============+=============================+=============+
| Text          | Working                     | core        |
+---------------+-----------------------------+-------------+
| Fonts         | Working (URW++ embedded)    | core        |
+---------------+-----------------------------+-------------+
| Colour        | In progress                 | macros      |
+---------------+-----------------------------+-------------+
```

Both compile to Lout's `tbl` package, which mdlout auto-includes when
it sees a table block. See
[`examples/03_lists_and_tables.md`](../examples/03_lists_and_tables.md)
for a side-by-side comparison.

---

## 8. Code blocks

Fenced code blocks are preferred --- they survive cleanly through the
inline-formatting pipeline because their contents are protected before
any Lout escaping happens.

````markdown
Some prose first, then a Python snippet:

```python
def hello(name: str) -> None:
    print(f"hello, {name}")
```

And a shell snippet:

```bash
./mdlout.py input.md --format=pdf
```
````

The language tag after the opening fence is currently informational
only (no syntax highlighting yet). Three fence languages are special:

- ```` ```lout ```` --- raw Lout passthrough (see Diagrams above).
- ```` ```math ```` --- routed through `@Math` (see Math above).
- ```` ```abc ```` --- routed through `@ABC` (see Music above).
- ```` ```svg ```` --- routed through `@SVG` (raw inline SVG).

CommonMark **indented code blocks** (four-space indent) also work:

```markdown
A paragraph.

    indented code: not yet fenced,
    but still a code block.
```

Fenced is the preferred form; indented exists for CommonMark
compatibility.

---

## 9. Two output formats

mdlout produces two outputs from the same source:

```bash
./mdlout.py input.md                    # input.html  (default, HTML/SVG)
./mdlout.py input.md --format=pdf       # input.pdf   (legacy PostScript)
./mdlout.py input.md --ps               # input.ps    (stops before ps2pdf)
./mdlout.py input.md --lout-only        # raw Lout source to stdout
```

**HTML/SVG (default)** runs `lout -G`, captures the SVG output, and
wraps it in a self-contained HTML page that inlines KaTeX, abcjsharp,
and URW++ Nimbus fonts. Choose this when:

- You want a single file you can mail, host, or version-control.
- The document contains math (rendered client-side, sharp at any zoom).
- The document contains engraved music (`abcjs` renders in browser).
- You want live preview during editing (see next section).

**PDF (legacy)** runs `lout` with the PostScript back-end, then pipes
through Ghostscript's `ps2pdf`. Choose this when:

- You need a print-ready PDF (the PostScript back-end is
  bit-stable across builds).
- The document is prose-heavy with no math/music passthrough.
- Downstream tooling consumes PDF (DOI archival, journal submission).

The PostScript back-end (`lout/z49.c`) is frozen; the SVG back-end
(`lout/z53.c`) is the one under active development. Both share the
same Lout galley engine, so line breaks and page counts agree even
when individual glyphs differ slightly between the rasterisers.

---

## 10. Live preview

For interactive editing, mdlout has two preview modes built on the
Python standard library --- no extra dependencies.

`--watch` polls the input file every 500 ms and rebuilds on every save:

```bash
./mdlout.py report.md --watch
```

You will see a `[rebuilt HH:MM:SS] report.html` line on stderr after
each successful build; transient errors are logged and the watcher
keeps running. Ctrl-C to exit.

`--serve [PORT]` is `--watch` plus a minimal single-threaded HTTP
server with Server-Sent Events live reload:

```bash
./mdlout.py report.md --serve                 # port 8080
./mdlout.py report.md --serve 9000            # custom port
```

Open the printed URL (default `http://127.0.0.1:8080/`) in a browser.
A tiny `<script>` injected into the served HTML opens an
`EventSource` to `/events`; every successful rebuild fires a
`reload` event, the script calls `location.reload()`, and the page
refreshes automatically. Edit the Markdown in your editor of choice,
save, and watch the browser update --- no manual reload, no
build-step IDE plugin.

Only `--format=html` is supported by `--serve` (it overrides `--pdf`
if you pass both).

---

## 11. Where to go next

- [`examples/`](../examples/) --- ten worked example documents with
  pre-built HTML and PDF renders in
  [`examples/out/`](../examples/out/). Read
  [`examples/README.md`](../examples/README.md) for the index.
- [`CLAUDE.md`](../CLAUDE.md) --- engineering context: source
  architecture, the four phases of the converter, frontmatter
  mapping, and Lout build variables.
- [`TODO.md`](../TODO.md) --- current roadmap, what works, what is
  partial, and what is on the horizon. Read this before opening an
  issue --- the answer is often already there.
- [`tests/README.md`](../tests/README.md) --- the 49+ regression
  snippets that gate every change. `bash tests/run_all.sh` from the
  repo root runs them in 30 seconds and confirms your build works.
- [`tests/user_guide_diff/`](../tests/user_guide_diff/) --- per-page
  visual-diff report comparing the SVG back-end's render of the full
  Lout User's Guide against the reference PostScript build.
- [`lout/doc/`](../lout/doc/) --- the upstream Lout documentation
  (`user/`, `expert/`, `tr/`). The User's Guide is the canonical
  reference for `@Diag`, `@Eq`, `@Tab`, `@Graphic`, and the
  galley-based layout model that powers everything mdlout does.
