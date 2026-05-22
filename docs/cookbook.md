# mdlout cookbook

Task-oriented recipes. Each section: motivation, source skeleton,
rendered result, and the non-obvious "gotcha". For the full
frontmatter table and CLI flags see the top-level
[`README.md`](../README.md); for HTML-vs-PDF selection, citations,
figure numbering, and debugging see
[`docs/best_practices.md`](best_practices.md).

Each recipe points at a building example under
[`examples/`](../examples/) -- copy that file rather than this
snippet when you want a verified starting point.

## 1. Three-column poster

Conference posters want landscape A3, three even columns, and a
tall display title strip. mdlout has no `type: poster`; combine
`type: doc` + `orientation: Landscape` + `columns: 3` with a
raw-Lout title block.

```yaml
---
type: doc
title: Convergence of Newton-Cotes Quadrature on Singular Integrands
author: J. L. Clements
page: A3
orientation: Landscape
columns: 3
column-gap: 1.0c
top-margin: 2.5c
para-indent: 0f
para-gap: 1.4v
font: Helvetica Base 14p
page-headers: None
---

```lout
@CentredDisplay @Font { +24p } @B { Poster Title Here }
@CentredDisplay @Font { +12p } @I { Author -- Affiliation -- email }
@DP
```

## Abstract
...
```

Rendered: A3 landscape, three column-balanced flows, no page
header, a single tall title strip spanning all three columns.

**Gotcha:** the `@DP` after the title strip ends the spanning
display; without it the body inherits the centred-display style.
Working example:
[`examples/academic_poster.md`](../examples/academic_poster.md).

## 2. Math-heavy lecture notes

Notes are light on chrome and heavy on display math. KaTeX in HTML
mode handles the full LaTeX math menu; PDF mode falls back to a
placeholder. Pick HTML for the web, PDF only when archival
fidelity matters.

```yaml
---
type: doc
title: Lecture 04 - Newton-Cotes Quadrature
author: J. L. Clements
page: A4
font: Times Base 11p
para-gap: 1.0v
para-indent: 0f
---

# Definite integrals

A definite integral is the limit of a Riemann sum:

$$
\int_a^b f(x)\, dx = \lim_{n \to \infty} \sum_{i=1}^n f(x_i^*)\,\Delta x.
$$

The trapezoidal rule:

```math
T_n = \frac{h}{2}\left[f(a) + 2\sum_{i=1}^{n-1} f(x_i) + f(b)\right].
```
```

Rendered: A4 Times 11pt, `$$...$$` and ` ```math ` blocks centred,
inline `$...$` riding the line.

**Gotcha:** KaTeX renders `\\` only inside an environment
(`aligned`, `cases`, `pmatrix`, etc.). Bare `\\` at top level
silently does nothing. For PDF, swap `$$...$$` for raw Lout `@Eq`
(see recipe #7). Working example:
[`examples/04_math.md`](../examples/04_math.md).

## 3. Multi-chapter book

Long-form prose wants `type: book`: Roman chapter numbers, no
section numbers, running heads carrying the chapter title, generous
margins, indented paragraphs with zero gap.

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

# The Map That Drew Itself

Opening paragraph. `#` becomes `@Chapter` (Chapter I).

## A subsection within the chapter

`##` becomes `@Section`. With `section-numbers: None`, no prefix.
```

Rendered: A5 with running heads, Roman-numbered chapter openers,
body Times 11pt.

**Gotcha:** multiple chapters in one file work, but one chapter per
file is the conventional layout. mdlout has no drop-cap shorthand;
`@DropCapTwo` from `bsf` collides with chapter opening and must be
inserted in post. Working example:
[`examples/book_chapter.md`](../examples/book_chapter.md).

## 4. Slides with images

`type: slides` uses Lout's `slidesf`. Each `#` opens a new
`@Overhead`. The package has sharp edges in the current fork
(`@Verbatim` doesn't escape `@End`, symbol-table collisions with
`tab` and `diag`), so put code as prose and `@SVGFile` external
images.

```yaml
---
type: slides
title: An Introduction to Lout
author: James Clements III
---

# An Introduction to Lout

*A six-slide tour of the document formatting system*

# What is Lout?

- A high-level **document formatting language** in ANSI C
- Authored by Jeffrey H. Kingston (University of Sydney, 1991)

# A diagram (rendered externally)

![Pipeline diagram](pipeline.svg)

# Thank you
```

Rendered: each `#` is a full slide; `![](pipeline.svg)` routes
through `@SVGFile` (inlined as `<image>` in HTML, rasterised via
`rsvg-convert` for PDF).

**Gotcha:** frontmatter beyond `type` / `title` / `author`
currently trips an `slidesf` + `@RefStyle` collision. KaTeX,
abcjsharp, and `@Diag` are off-limits on slides until that lands
-- pre-render and `![](...)` instead. Working example:
[`examples/slides_basic.md`](../examples/slides_basic.md).

## 5. Code-heavy manual

Manuals lean hard on syntax-highlighted code. mdlout autoloads
highlight.js (v11.9.0) for any fenced block with a language tag;
~190 languages work out of the box.

```yaml
---
type: report
title: My Project Technical Manual
author: Project Maintainers
cover: Yes
contents: Yes
page: A4
section-numbers: Arabic
para-indent: 0f
para-gap: 1.0v
font: Times Base 11p
---

[TOC]

# Installation

```bash
git clone https://example.com/project.git
cd project && make
```

# API surface

```python
def convert(text: str) -> str:
    return _convert_inner(text)
```
```

Rendered: A4 report with cover, multi-page TOC, prose interleaved
with syntax-highlighted listings.

**Gotcha:** highlight.js is **only loaded if at least one fenced
block has a language tag**. Untagged fences render in plain
monospace. Pass `--no-highlight` to suppress. Four fence languages
are intercepted by mdlout itself and never reach highlight.js:
` ```lout `, ` ```math `, ` ```abc `, ` ```svg `. Working example:
[`examples/technical_manual.md`](../examples/technical_manual.md)
(25 pages including a troubleshooting appendix).

## 6. Letterhead / single-page form

No `type: letter` exists. Use `type: doc` with symmetric margins,
no page header, zero indent, `1.2v` paragraph gap. Sender block,
date, recipient, and signature each ride in their own
` ```lout ` fence.

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

```lout
@RightDisplay {
James Clements III
//
1742 Larkspur Lane
//
james.l.clements.iii "@" gmail.com
}
```

```lout
@LeftDisplay { 21 May 2026 }
```

Dear Dr. Whitcombe,

Body of the letter as ordinary markdown paragraphs.
```

Rendered: US Letter, no header, sender block flush right, date
flush left, prose body.

**Gotcha:** `@` and `/` are Lout metacharacters -- quote them as
`"@"` and `"/"` to print literally. The `//` between address lines
is Lout's vertical-list separator, not a forward slash. Working
example: [`examples/letter.md`](../examples/letter.md).

## 7. Drop caps and pull quotes (raw Lout passthrough)

Markdown has no shorthand for either. Drop a ` ```lout ` fence
where you want the flourish. A pull quote is
`@CentredDisplay @I { ... }` with an attribution below. Drop caps
need `bsf` and currently fight with chapter openings -- insert
them in post.

```lout
@LP
@CentredDisplay @I {
"A map that lies is a nuisance. A map that prophesies is a calamity."
}
@CentredDisplay { --- Bertrand Velasquez, @I { Cartographic Ethics } (1974) }
@LP
```

Rendered: body paragraph, centred italic pull quote on its own
line, centred attribution beneath, body resumes.

**Gotcha:** the leading and trailing `@LP` are required -- without
them the quote glues to the surrounding paragraphs. Double-quoting
the string (`"A map..."`) keeps the apostrophes from being
reinterpreted by Lout. Pattern taken from
[`examples/book_chapter.md`](../examples/book_chapter.md).

For raw Lout `@Eq` math in PDF mode (the recipe-2 swap):

```lout
@CentredDisplay @Eq { int from 0 to inf e sup { - x sup 2 } d x = sqrt pi over 2 }
```

See
[`examples/07_raw_lout_and_svg.md`](../examples/07_raw_lout_and_svg.md).

## 8. Inline ABC music notation

` ```abc ` fenced blocks route through `@ABC` and are engraved by
**abcjsharp** in the browser (HTML mode only). The fork lives at
<https://github.com/clementsj/abcjsharp> and supports harp
grand-staff via `%%score (RH | LH)`.

```abc
X:1
T:Frere Jacques
M:4/4
L:1/4
K:G
G A B G | G A B G | B c d2 | B c d2 |
```

```abc
X:2
T:Twelve-Bar Blues in G
M:4/4
L:1/4
K:G
"G" G B d g | "G" g B d B | "C" c e g c' |
```

Rendered: each fence engraves as a score in the HTML. Chord
symbols sit above the staff; multiple voices and the fork's
grand-staff layout both work.

**Gotcha:** PDF mode treats `@ABC` as a stub -- the block renders
as `[ABC music notation: ...]` literal text. For PDF, pre-render
with `abcm2ps` or `abcjsharp` and `![](score.svg)` it. ABC inside
`type: slides` is also broken (collides with `slidesf` flow).
Three blocks of increasing complexity, including the harp
grand-staff, in
[`examples/05_music.md`](../examples/05_music.md).

## 9. Custom mydefs macros (the sidecar file convention)

When a document needs a one-off Lout macro -- a project display
style, a custom font size, a hand-built `@SyntaxDiag` shortcut --
the convention is a sidecar file called `mydefs` next to the input
`.md`. mdlout auto-copies it into the build directory and Lout
picks it up via `@Include { mydefs }`.

`mydefs`:

```lout
def @ProjectTitle right name
{
  @CentredDisplay @Font { +18p } @B { name }
}
```

`mypage.md`:

```yaml
---
type: doc
title: A Custom-Styled Document
font: Times Base 11p
---

```lout
@ProjectTitle { Project Alpha }
```

Body paragraphs as ordinary markdown.
```

Rendered: `@ProjectTitle` emits the centred-display heading at
+18 pt; the macro is available everywhere in the body via raw
Lout.

**Gotcha:** the sidecar must literally be named `mydefs` (no
extension) and sit next to the `.md` file -- or pass
`--mydefs path/to/file`. `def`s **must** match Lout's
right-name / left-name parameter convention; syntax errors surface
as "lout syntax error in symbol ..." on stderr.

## 10. Tables with alignment markers

Pipe tables accept `:---`, `:---:`, `---:` on the separator row;
mdlout translates these into Lout `@Cell indent { right }` /
`indent { ctr }`. Header rows auto-bold.

```yaml
---
type: doc
page: A4
font: Times Base 11p
---

# Convergence data

| n     |   error |   ratio |
|:------|--------:|--------:|
| 4     | 8.3e-2  |     -   |
| 8     | 2.1e-2  |    3.95 |
| 16    | 5.2e-3  |    4.04 |
| 32    | 1.3e-3  |    4.00 |

Numeric data follows the textbook $O(h^4)$ Simpson rate.
```

Rendered: four-row pipe table, left column left-aligned (default),
numeric columns right-aligned, header row bold, surrounding rule
drawn by Lout.

**Gotcha:** mdlout pipe tables **do not** support spanned cells
(no rowspan/colspan in the markdown). For spanning, drop into a
raw ` ```lout ` fence with `@Tab` directly -- the `@StartHSpan` /
`@StartVSpan` markers are in chapter 8 of the Lout User's Guide.
A "table" with no separator row renders as plain paragraphs. See
[`examples/03_lists_and_tables.md`](../examples/03_lists_and_tables.md)
for pipe and grid tables side by side, and
[`examples/scientific_paper.md`](../examples/scientific_paper.md)
for the numeric-data worked example.

## Where to look next

- [`docs/best_practices.md`](best_practices.md) -- idiom guide:
  format selection (HTML vs PDF), citations, figure/table
  numbering, debugging unrendered content.
- [`docs/z53_internals.md`](z53_internals.md) -- contributor-facing
  deep-dive on the SVG back-end (`z53.c`).
- [`docs/tutorial.md`](tutorial.md) -- end-to-end walkthrough from
  a fresh clone.
- [`tests/snippets/`](../tests/snippets/) -- 62 single-feature Lout
  snippets, the first place to look when a feature stops
  rendering.
- [`tests/user_guide_diff/`](../tests/user_guide_diff/) -- the
  page-by-page parity report between SVG and PostScript for the
  Lout User's Guide.
- [`examples/README.md`](../examples/README.md) -- the example
  corpus grouped by category, with HTML/PDF links per file.
- [Lout User's Guide PDF](../lout/doc/user/) -- the underlying
  formatter's reference.
