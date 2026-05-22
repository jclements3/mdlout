# mdlout best practices

Practical advice for getting good output from `mdlout.py`. This page is a
recipe book; for the full CLI and frontmatter reference see the
[README](../README.md), and for the end-to-end walkthrough see
[docs/tutorial.md](tutorial.md).

All commands assume you are at the repo root with `mdlout.py` on disk and
the Lout binary built at `lout/lout` (see the tutorial for setup).

## 1. When to choose HTML vs PDF

mdlout supports two output formats. They share the same Markdown front end
and the same Lout intermediate; only the back end differs.

Pick **HTML** (the default, `./mdlout.py input.md`) when:

- You want browser delivery (publish on a website, share over Slack, view
  on a phone).
- You want live preview while editing. `--watch` rebuilds on every save,
  `--serve` adds a tiny SSE server and a one-line `<script>` injection so
  the open tab reloads automatically:

      ./mdlout.py input.md --serve

- You want KaTeX-rendered math. In HTML mode `$...$` and `$$...$$` route
  through `@Math` and KaTeX paints them client-side, so the full KaTeX
  feature set is available.
- You want abcjsharp-engraved music. ` ```abc ` fences route through
  `@ABC` and abcjsharp renders them in the browser.
- You want raw SVG passthrough (` ```svg ` fences, `@SVG` macro) or
  Markdown images of `.svg` files inlined directly into the page.

Pick **PDF** (`./mdlout.py input.md --format=pdf`) when:

- You need exact print fidelity — the PostScript back-end (`z49.c`) is
  the frozen reference renderer and what every paginated layout in
  `examples/out/*.pdf` was built with.
- The output has to be archival, signable, or fed to a PDF-only tool
  (a journal upload form, a print shop, a long-term repository).
- You want Lout's own equation typesetting via raw `@Eq` (the `eq`
  package), not browser-rendered LaTeX.
- You depend on Lout's diagrams (`@Diag`, `@Tree`), which currently
  render best to the PostScript path; the SVG back-end's `@Diag`
  support is partial (see `TODO.md`).

You can switch formats per build — the Markdown source rarely needs to
change. The exception is fenced `abc` / `svg` / `math` blocks: in PDF
mode `@Math` and `@ABC` are stubs (mdlout falls back to Lout's `@Eq`
where possible), and `@SVG` emits a placeholder. If you need engraved
music or LaTeX math in PDF output today, embed a pre-rendered image
with `![](score.svg)`.

## 2. Frontmatter recipes for common doc types

Drop one of these YAML blocks at the very top of your `.md` file. All
keys are documented in the README; this section just bundles them into
working templates. Each recipe is the YAML you'd type in your file, not
a shell command.

### Research / scientific paper

Two-column report with cover sheet, abstract, table of contents, and
numeric citations. Verified against `examples/scientific_paper.md`.

```yaml
---
type: report
title: A Comparative Study of the Trapezoidal and Simpson's Rules
author: J. L. Clements
institution: mdlout project, Sydney
date: 2026-05-20
cover: Yes
contents: Yes
page: A4
columns: 2
column-gap: 0.5c
section-numbers: Arabic
para-indent: 0f
para-gap: 1.0v
language: English
font: Times Base 11p
abstract: |
  Two short paragraphs of abstract here. YAML's `|` literal-block
  syntax keeps line breaks; mdlout splits the result into Lout
  `@PP` paragraphs.
references_format: numeric    # or 'alpha' for [a], [b], ...
---
```

Use `#` for top-level sections, `##` for subsections; mdlout maps them
to `@Section` / `@SubSection` with automatic numbering. Put a `[TOC]`
line wherever you want the contents block.

### Book chapter

Single-column, generous margins, Roman chapter numbers, no section
numbers, running heads. Verified against `examples/book_chapter.md`.

```yaml
---
type: book
title: The Cartographers of Veil
author: James Clements III
font: Times Base 11p
page: A5
top-margin: 2.0c
foot-margin: 2.0c
left-margin: 2.0c
right-margin: 2.0c
para-gap: 0b
para-indent: 2f
chapter-start: Any
chapter-numbers: Roman
section-numbers: None
page-headers: Titles
---
```

For `type: book`, `#` is a chapter, `##` is a section, `###` is a
subsection. Multiple chapters in one file work; one chapter per file
is more conventional.

### Letter

There is **no `type: letter`** in mdlout. Use `type: doc` with raw-Lout
fenced blocks for the address, date, salutation, and signature. The
verified template is `examples/letter.md`:

```yaml
---
type: doc
font: Times Base 11p
page: Letter
top-margin: 2.5c
foot-margin: 2.5c
left-margin: 2.5c
right-margin: 2.5c
para-gap: 1.2v
para-indent: 0f
page-headers: None
---
```

Then in the body, use ` ```lout ` blocks for `@RightDisplay { ... }`
(sender address), `@LeftDisplay { 21 May 2026 }`, the recipient block,
and the signature. Prose paragraphs in between are normal Markdown.

### CV / resume

Two-column flowed layout with no page headers; raw-Lout fences for the
name banner and the tagged-list of skills. Verified against
`examples/cv.md`.

```yaml
---
type: doc
title: Curriculum Vitae
font: Times Base 10p
page: Letter
top-margin: 1.8c
foot-margin: 1.8c
left-margin: 2.0c
right-margin: 2.0c
columns: 2
column-gap: 0.8c
para-gap: 0.6v
para-indent: 0f
page-headers: None
---
```

A `@CentredDisplay @Font { +6p } @B { name }` in a ` ```lout ` block
gives you the banner; `@TaggedList ... @EndList` is a clean
two-column-friendly skills list.

### Slides

One slide per `#` heading. The `slidesf` package has a few sharp edges
(`@Verbatim` doesn't escape `@End`, the symbol table collides with
`tab` and `diag`), so keep code, tables, and `@Diag` out of slides for
now — see `examples/slides_basic.md` for the documented workarounds.

```yaml
---
type: slides
title: An Introduction to Lout
author: James Clements III
---
```

Inline KaTeX math in slides is also currently unsupported; render the
equation externally and `![](eq.svg)` it in.

## 3. Embedding math correctly

In HTML mode mdlout routes math through `@Math`, which the SVG back end
emits as a `<foreignObject>` carrying a `<span class="math">…</span>`;
KaTeX then renders it client-side. That means **the entire KaTeX
supported-feature set is available** — see
<https://katex.org/docs/supported.html> for the authoritative list.

Common gotchas:

- **Inline vs display.** `$x^2$` is inline (KaTeX renders without
  display mode); `$$x^2$$` and ` ```math ` fences are display
  (centred, larger spacing). Inline `\(...\)` works too.
- **Line breaks in display.** Use `\\` inside `aligned`, `cases`,
  `pmatrix`, `bmatrix`, etc. Bare `\\` outside an environment does not
  work in KaTeX — wrap in `\begin{aligned} ... \end{aligned}`.
- **Backslashes in YAML.** If you put a math expression in
  frontmatter (e.g. `abstract: |`), YAML's `|` literal block keeps
  backslashes verbatim — no extra escaping needed.
- **Markdown intrusion.** A `_` inside an inline `$x_i$` will *not* be
  read as italics: mdlout protects math spans with a placeholder pass
  before inline markup runs. But check the rendered output anyway if
  you're typing something exotic.
- **PDF mode.** `@Math` is a stub on the PostScript back-end. For PDF,
  drop into raw Lout `@Eq` instead:

      ```lout
      @CentredDisplay @Eq { int from 0 to inf e sup { - x sup 2 } d x = sqrt pi over 2 }
      ```

  See `examples/04_math.md` (HTML) and `examples/07_raw_lout_and_svg.md`
  (raw `@Eq`) for working samples.

## 4. Embedding music

ABC notation in a ` ```abc ` fenced block is routed through the `@ABC`
macro and rendered by **abcjsharp** in the browser. abcjsharp is the
maintainer's fork of `abcjs` at
<https://github.com/clementsj/abcjsharp>; it's loaded from
`~/projects/abcjsharp/dist/` if present, otherwise from the abcjs CDN.

A minimal one-line melody (header lines first, then bars):

    ```abc
    X:1
    T:Frere Jacques
    M:4/4
    L:1/4
    K:G
    G A B G | G A B G | B c d2 | B c d2 |
    ```

What abcjsharp renders cleanly:

- Single-staff melodies with key/meter/tempo headers.
- Chord symbols in double quotes (`"G7" G B d f`).
- Multiple voices with `V:RH` / `V:LH`.
- The fork's **harp grand-staff** feature — a `%%score (RH | LH)`
  directive locks two staves into a brace-coupled system suitable for
  pedal harp parts. See block X:3 of `examples/05_music.md`.

What does *not* work today:

- ABC inside slides (`type: slides`) collides with `slidesf` flow
  routing — render externally and include as an SVG image.
- PDF mode (`--format=pdf`): `@ABC` is a stub. Pre-render with
  `abcjsharp` or `abcm2ps` and `![](score.svg)` the result.

## 5. Embedding diagrams

There are three ways to put a diagram in an mdlout document. Pick the
lowest-overhead one that works:

1. **Raw Lout `@Diag` (preferred for boxes/arrows/trees).** Wrap the
   diagram in a ` ```lout ` fenced block. mdlout auto-detects
   `@Diag` / `@Tree` / `@Node` / `@Link` usage and adds
   `@SysInclude { diag }` to the preamble for you. Example:

       ```lout
       @CentredDisplay @Diag {
       A:: @Node { A } ||1.5c B:: @Node { B }
       // @Link from { A } to { B } arrow { yes } arrowstyle { solid }
       }
       ```

   The full vocabulary (shapes `@Box`, `@CurveBox`, `@Diamond`,
   `@Polygon`, `@Ellipse`, `@Circle`; ten arrowstyles; `@Tree`) is
   exercised in `examples/diag_gallery.md`.

2. **Inline `@Math` / `@ABC` (passthrough macros).** For equations and
   music. Use the Markdown shortcuts (`$$...$$`, ` ```abc `) rather
   than the raw macros unless you need a Lout-specific knob.

3. **Raw SVG via `@SVG` or `![](file.svg)`.** When you have a
   pre-built SVG (from Graphviz, Inkscape, matplotlib, abcm2ps), drop
   it in. A ` ```svg ` fence inlines a literal fragment; a Markdown
   image of a `.svg` path goes through `@SVGFile` and is inlined as a
   `<g>` element in HTML or rasterised via `rsvg-convert` for PDF.

`@Diag` is currently best on the PDF back-end; complex diagrams render
only partially through the SVG back-end. See `examples/diag_gallery.md`
and `examples/complex_diag.md` for what does and doesn't survive.

## 6. Citations and references

mdlout implements pandoc-style citations: inline `[@key]` plus a
bibliography line `[@key]: entry text`. The first appearance of each
key gets a sequence number, and a numbered References list is appended
to the document.

Minimal example:

    Davis and Rabinowitz [@davis1984] tabulate these errors.

    ## References

    [@davis1984]: Davis, P. J. and Rabinowitz, P. *Methods of Numerical
    Integration.* Academic Press, 2nd ed., 1984.

A few notes:

- Locators are allowed: `[@davis1984, p. 87]` renders the locator
  alongside the number.
- Keys must match `[A-Za-z0-9_][A-Za-z0-9_-]*` — no spaces, no dots.
- Bibliography lines are stripped from the body before block parsing;
  they re-appear only inside the auto-generated References block.
- The numbering format is controlled by the `references_format`
  frontmatter key (or the hyphenated alias `references-format`):
  - `numeric` (default): `[1]`, `[2]`, …
  - `alpha`: `[a]`, `[b]`, … `[z]`, `[aa]`, …
- A cite whose key has no matching bibliography line falls back to a
  literal `[key]` in the rendered output — useful for grepping
  unresolved references.

## 7. Figure and table numbering

Figures get a numeric label when you attach `{#fig:label}` to the
trailing image:

    ![Convergence of Simpson's rule](sim.svg){#fig:sim}

Tables get a label by following the table immediately with a
stand-alone `[#tab:label]` line:

    | h     | error  |
    | ----- | ------ |
    | 0.1   | 1.2e-3 |
    | 0.05  | 7.5e-5 |

    [#tab:simpson]

Refer to either with `@fig:label` or `@tab:label` in running text:

    Convergence is plotted in figure @fig:sim; numerical values are in
    table @tab:simpson.

For `type: report` and `type: book`, labels are prefixed by the
top-level section / chapter counter (Figure 2.3 = third figure in
section 2). For other doc types numbering is flat. Unresolved refs
render as `?` — search the output for stray question marks if a
cross-reference looks wrong.

## 8. Code blocks with syntax highlighting

Tag your fenced code blocks with a language hint and the HTML output
loads **highlight.js** (v11.9.0) automatically:

    ```python
    def convert_inline(text: str) -> str:
        return _ph_restore(_convert_inline_inner(text))
    ```

mdlout tracks which languages actually appear in the document; if none
have a language hint, highlight.js is not loaded at all (saves about
150 kB). The library handles ~190 languages out of the box — Python,
C, C++, Rust, JS/TS, Bash, JSON, YAML, SQL, Go, Haskell, etc. Untagged
code blocks render in monospace without colour.

Useful flags:

- `--no-highlight` disables the highlight.js wiring entirely. The
  code still renders as `<pre><code>`, just without colours.
- `--external-assets` loads highlight.js (and KaTeX, abcjsharp) from
  CDN instead of inlining. Smaller HTML, requires network at view
  time.

Three fence languages are intercepted by mdlout itself and **do not**
go to highlight.js:

- ` ```lout ` — emitted verbatim into the Lout source.
- ` ```math ` — routed through `@Math`.
- ` ```abc ` — routed through `@ABC`.
- ` ```svg ` — routed through `@SVG`.

In PDF mode none of these have syntax highlighting; tagged blocks
render as plain `@Verbatim` paragraphs.

## 9. Debugging unrendered content

When the output is wrong the fastest path is usually to inspect the
intermediate Lout source rather than guess at the Markdown:

    ./mdlout.py input.md --lout-only -o /tmp/input.lt
    less /tmp/input.lt

This stops the pipeline at the Markdown → Lout step. You can then
hand-run `lout` against the `.lt` file to see what it complains about:

    cd lout
    ./lout -I include -D data -F font -C maps -H hyph /tmp/input.lt > /tmp/input.ps

In the normal pipeline `mdlout.py` discovers these `-I/-D/-F/-C/-H`
paths automatically; spelling them out manually is only useful when
debugging.

Useful flags during debugging:

- `--lout-only` (above): stop before invoking the back end.
- `--ps`: stop at PostScript, skip `ps2pdf`. Useful if Ghostscript is
  the failure mode.
- `--lout-args "..."`: pass extra arguments to the Lout invocation
  (e.g. `--lout-args "-V"` for the Lout version banner).

Common Lout error patterns you'll see on stderr:

- `lout file "X" not found` — a `@SysInclude { X }` or `@Include { X }`
  refers to something not in the library or working directory. If
  it's a system package, check that you're running the maintained
  `svg-backend` branch of the submodule.
- `lout syntax error in symbol Y` — usually means an unbalanced `{`/`}`
  in a raw `lout` fence or a stray `@End` inside `@Verbatim` (slides
  are especially prone to this).
- `unresolved cross reference: Z` — Lout normally needs three passes to
  resolve cross-refs. mdlout already runs lout up to three times; if
  the warning persists, the target really is missing.
- Mysterious blank output — frequently a missing `mydefs` file when a
  raw `lout` fence references a custom macro. Pass `--mydefs path/to/file`
  or put the file next to the input `.md`.

## 10. Performance tips

The default HTML output inlines KaTeX, abcjsharp, highlight.js, and
URW++ Nimbus web fonts so the page is a single self-contained file.
That's convenient but bulky (several MB). When size matters:

- `--external-assets` — load KaTeX / abcjsharp / highlight.js from
  CDN instead of inlining. Shaves the bulk of the size; requires
  network at view time.
- `--no-math-engine` — omit KaTeX entirely. Use only if the document
  contains no math.
- `--no-music-engine` — omit abcjsharp entirely. Use only if the
  document contains no ABC blocks.
- `--no-font-embedding` — skip the inlined `@font-face` URW++ Nimbus
  fonts. The SVG text falls back to system fonts and may drift
  slightly from the PostScript render — fine for drafts.
- `--no-highlight` — drop highlight.js. Code blocks still render as
  plain monospace.
- `--text-as-paths` — at the opposite extreme: replace every SVG
  `<text>` element with a `<path>` outline extracted from URW++
  Nimbus. Eliminates the browser's text rasteriser from the loop
  (HTML pixel-matches the PDF), at the cost of substantially larger
  output and a `fontTools` dependency.

For the PDF path, the only relevant knob is the Lout binary itself —
build with `PDF_COMPRESSION=1` (see `lout/makefile`) if you care about
final PDF size.

## 11. Where to go next

- [README](../README.md) — top-level overview, CLI flags, frontmatter
  reference, project layout.
- [docs/tutorial.md](tutorial.md) — end-to-end walkthrough from a
  fresh clone.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — how the converter is
  structured, where the SVG back end lives, why certain choices.
- [TODO.md](../TODO.md) — current roadmap; the long tail of `@Diag`,
  `@Eq`, and slide-specific work-in-progress.
- [examples/README.md](../examples/README.md) — sample documents,
  one per common task; the numbered ones are also the regression
  fixtures.
- [tests/README.md](../tests/README.md) — the regression suite.

External references:

- KaTeX supported features:
  <https://katex.org/docs/supported.html>
- abcjsharp (the maintainer's fork of abcjs):
  <https://github.com/clementsj/abcjsharp>
- Lout User's Guide (PDF): under `lout/doc/user/` after the submodule
  is built.
