# mdlout examples

This directory is the project's worked-example corpus. Each Markdown file
is a self-contained document that exercises some specific corner of the
feature set; together they double as a regression bank (the numbered
`01_`...`08_` files in particular are referenced from
`tests/run_all.sh`). The intent is that anyone wanting to copy-paste a
starting point for a real document -- a paper, a CV, a slide deck, a
poster -- finds the right template here without having to read the full
README.

Build any file in either output format from the repo root:

```bash
./mdlout.py examples/01_hello.md                 # HTML (default)
./mdlout.py examples/01_hello.md --format=pdf    # PDF (PostScript path)
```

To rebuild the entire corpus in both formats (what
`examples/out/` is regenerated from):

```bash
for f in examples/*.md; do
  ./mdlout.py "$f" -o "examples/out/$(basename "${f%.md}.html")"
  ./mdlout.py "$f" --format=pdf -o "examples/out/$(basename "${f%.md}.pdf")"
done
```

The committed reference renderings live under `examples/out/`. A
self-contained gallery page indexes them at
[`examples/out/index.html`](out/index.html); each card carries a
page-1 thumbnail plus links to HTML, PDF, source, and a single-page
preview HTML.

## Getting started

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`01_hello.md`](01_hello.md) | doc | 1 | One paragraph. The smallest possible end-to-end smoke test. [[html](out/01_hello.html) - [pdf](out/01_hello.pdf)] |

## Typography and text

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`02_typography.md`](02_typography.md) | doc | 1 (HTML) | Inline spans -- bold, italic, bold-italic, `inline code`, strikethrough, superscript, nested formatting, and backslash escapes. PDF currently fails to build; tracked in `TODO.md`. [[html](out/02_typography.html)] |
| [`letter.md`](letter.md) | doc | 1 | US business letter built on `type: doc` plus raw-Lout passthrough for the right-aligned sender block, date, recipient block, and signature. Demonstrates `"@"` and `"/"` quoting to slip an email and a URL past Lout's metacharacters. The de-facto template for letters until `type: letter` lands. [[html](out/letter.html) - [pdf](out/letter.pdf)] |
| [`cv.md`](cv.md) | doc | 1 | Two-column CV (`columns: 2`, `page-headers: None`) for a fictitious senior audio DSP engineer. Raw-Lout `@TaggedList` for the skills section, raw-Lout banner heading, markdown prose for the bulk. Exercises the `font`, `page`, `top-margin`, and `column-gap` knobs. [[html](out/cv.html) - [pdf](out/cv.pdf)] |
| [`exam.md`](exam.md) | doc | 3 (PDF) / 6 (HTML) | Five-question calculus midterm with blank workspaces (`//Nc` vlist separators inside raw-Lout fences) between questions and a separate `# Answer Key` page. Prose math throughout so PDF and HTML stay in sync. The template for quizzes / worksheets / exam booklets. [[html](out/exam.html) - [pdf](out/exam.pdf)] |

## Lists and tables

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`03_lists_and_tables.md`](03_lists_and_tables.md) | doc | 2 | Bullet, numbered, task, and definition lists; pipe tables with `:--:` and `--:` alignment markers; grid tables; `page: Letter` frontmatter. [[html](out/03_lists_and_tables.html) - [pdf](out/03_lists_and_tables.pdf)] |

## Math and music

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`04_math.md`](04_math.md) | doc | 1 | `$$...$$` and ` ```math ` block math, inline `$...$`; integrals, sums, fractions, matrices, aligned equations. KaTeX in HTML mode; placeholder in PDF mode. [[html](out/04_math.html) - [pdf](out/04_math.pdf)] |
| [`05_music.md`](05_music.md) | doc | 1 | Three ` ```abc ` blocks of increasing complexity -- single-line melody, chord-symbol blues, and a `%%score`-locked harp grand-staff. Routes through `@ABC` and abcjsharp in HTML mode. [[html](out/05_music.html) - [pdf](out/05_music.pdf)] |

## Structured documents

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`06_report.md`](06_report.md) | report | 3 | `type: report` with cover, `[TOC]`, `@Section` nesting, code fences, math, footnotes, and a raw-Lout figure. The minimum a multi-section paper needs. [[html](out/06_report.html) - [pdf](out/06_report.pdf)] |
| [`scientific_paper.md`](scientific_paper.md) | report | 6 | A short workshop-style paper on trapezoidal and Simpson's quadrature. Abstract / introduction / methods / results / discussion / references layout, display and inline `@Math`, two pipe tables of error data, a `@Diag` figure with caption, manual bibliography. Use as a template for real scientific writing. [[html](out/scientific_paper.html) - [pdf](out/scientific_paper.pdf)] |
| [`book_chapter.md`](book_chapter.md) | book | 3 | A5 novel chapter with Roman chapter numerals, `@Section`-level subheadings, a raw-Lout pull-quote (`@CentredDisplay @I`), and an `@FootNote` invoked via raw Lout. Comment explains the missing drop-cap shorthand. [[html](out/book_chapter.html) - [pdf](out/book_chapter.pdf)] |
| [`slides_basic.md`](slides_basic.md) | slides | 9 | Six-slide intro to Lout: title slide, bullet list, math-as-prose, code-as-prose, a centred-display pipeline figure. Frontmatter intentionally minimal to avoid the `slidesf` + `@RefStyle` collision; in-slide `@Diag`, `@Math`, `@Verbatim`, and tables are documented as currently unsafe and rendered with workarounds. [[html](out/slides_basic.html) - [pdf](out/slides_basic.pdf)] |
| [`technical_manual.md`](technical_manual.md) | report | 25 | The mdlout technical manual itself -- the largest example, ~1250 lines of source, exercises every report-level idiom: cover, abstract, multi-page TOC, deeply nested sections, footnotes, citations, pipe tables, fenced code with hljs hints, and inline math. [[html](out/technical_manual.html) - [pdf](out/technical_manual.pdf)] |

## Posters and magazine layout

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`academic_poster.md`](academic_poster.md) | doc | 2 | A3 landscape, three columns, generous margins, large display heading via raw Lout. Abstract / introduction / method / results / discussion / references in a flowing three-column grid. The closest mdlout has to a poster template. [[html](out/academic_poster.html) - [pdf](out/academic_poster.pdf)] |
| [`magazine_layout.md`](magazine_layout.md) | doc | 3 | US Letter, two columns with a 1 cm gutter, raw-Lout masthead and pull-quotes. The narrative magazine equivalent of the CV's column layout. [[html](out/magazine_layout.html) - [pdf](out/magazine_layout.pdf)] |

## Diagrams (raw Lout)

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`diag_gallery.md`](diag_gallery.md) | doc | 7 | Exhaustive `@Diag` exercise: every arrowstyle, shape (`@Box`, `@CurveBox`, `@ShadowBox`, `@Square`, `@Diamond`, `@Polygon`, `@Isosceles`, `@Ellipse`, `@Circle`), and `@Tree`. Raw-Lout fences only. The reference for what survives the SVG back-end and what doesn't. [[html](out/diag_gallery.html) - [pdf](out/diag_gallery.pdf)] |
| [`complex_diag.md`](complex_diag.md) | doc | 4 | A demanding follow-up: arithmetic-expression grammar as `@SyntaxDiag` railroad diagrams, a binary search tree, a `paint`-filled subsystem box, a flowchart with five distinct arrowstyles, a composite figure mixing `@Tree` with embedded `@SyntaxDiag`. [[html](out/complex_diag.html) - [pdf](out/complex_diag.pdf)] |

## Raw passthrough

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`07_raw_lout_and_svg.md`](07_raw_lout_and_svg.md) | doc | 1 | ` ```lout ` and ` ```svg ` raw-passthrough fences for testing `@SVG` routing. Includes hand-rolled `@Eq` math and a boxed display block. [[html](out/07_raw_lout_and_svg.html) - [pdf](out/07_raw_lout_and_svg.pdf)] |

## Kitchen sink

| File | Type | Pages | What it shows |
|------|------|-------|---------------|
| [`08_kitchen_sink.md`](08_kitchen_sink.md) | report | 3 | Two-column `type: report` combining every feature above into one file: headings at three levels, lists, tables, math, music, code, raw Lout, and the full inline-formatting menagerie. The canonical end-to-end regression target. [[html](out/08_kitchen_sink.html) - [pdf](out/08_kitchen_sink.pdf)] |

## Visual gallery and regeneration

[`examples/out/index.html`](out/index.html) indexes every reference
rendering as a card with a page-1 PDF thumbnail. Examples that
currently fail to render to PDF (`02_typography.md` at the time of
writing) appear with a "known issue" banner so the gallery stays a
complete inventory.

Regenerate the gallery (and the `thumb-*.png` previews) after
refreshing the reference outputs:

```bash
python3 examples/generate_gallery.py
```

The generator is stdlib-only and shells out to `pdftoppm` and
ImageMagick `convert` -- the same tools used by the visual-regression
tests. It is idempotent: re-running it overwrites both the thumbnails
and the `index.html` in place.

## Where to look next

- [docs/cookbook.md](../docs/cookbook.md) -- task-oriented recipes
  ("how do I make a three-column poster?"). Cross-references the
  files above.
- [docs/best_practices.md](../docs/best_practices.md) -- idioms,
  format selection, debugging tips.
- [docs/tutorial.md](../docs/tutorial.md) -- end-to-end walkthrough
  from a fresh clone.
- [tests/README.md](../tests/README.md) -- regression-suite layout.
