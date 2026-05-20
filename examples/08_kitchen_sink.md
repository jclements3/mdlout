---
type: report
title: mdlout Kitchen Sink
author: Regression suite
page: A4
columns: 2
contents: Yes
section-numbers: Arabic
---

[TOC]

# Overview

This is the **kitchen-sink** regression document. It mixes every feature the
other examples exercise into one file: headings at three levels, lists, tables,
math, music, code, raw Lout, and the full inline-formatting menagerie. Use
this as the canonical end-to-end target.

## Why two columns?

The frontmatter sets `columns: 2`, which exercises Lout's column-balancing
machinery. Long lists and tables should reflow gracefully; figures and
displays should span both columns or be confined to one, depending on width.

# Inline and lists

A paragraph with the full inline kit: **bold**, *italic*, ***both***, `code`,
~~struck~~, super^script^, an [embedded link](https://example.org/mdlout) (which
mdlout renders as a footnote), and an escaped \*literal\* span.

Bullet list:

- Markdown extensions: tables, task lists, definition lists, math blocks.
- Frontmatter mapping: type, page, columns, headers, contents.
- Output formats: HTML (via `lout -G`) and PDF (via `ps2pdf`).

Numbered list:

1. Parse frontmatter.
2. Parse blocks.
3. Convert inline spans.
4. Emit Lout source.

Task list:

- [x] Inline formatting
- [x] Block-level parser
- [ ] `@Math` macro
- [ ] `@ABC` macro
- [ ] `@SVG` macro

# Tables, math, music

## A small table

| Module | Purpose                  | LOC |
|--------|--------------------------|-----|
| z01.c  | Supervisor and `main()`  | ~600 |
| z18.c  | Galley transfer          | ~1200 |
| z48.c  | PDF back end             | ~900 |
| z50.c  | PDF compression          | ~400 |

## A worked equation

Euler's identity, the canonical one-line proof that mathematicians have taste:

$$
e^{i\pi} + 1 = 0
$$

The Gaussian integral, repeated here because it never gets old:

$$
\int_{-\infty}^{\infty} e^{-x^2} \, dx = \sqrt{\pi}
$$

## A music snippet

A two-bar fragment for the harp's right hand, just to make sure that an ABC
fenced block survives the column break:

```abc
X:1
T:Fragment
M:4/4
L:1/8
K:C
"C" CEGc c2 GE | "G7" DGBd d2 BG |
```

# Code, raw Lout, and admonitions

A Python snippet showing the converter's main entry point:

```python
def main() -> None:
    args = parse_args()
    md_text = read_input(args.input)
    frontmatter, body = parse_frontmatter(md_text)
    blocks = parse_markdown(body)
    lout_src = generate_lout(blocks, frontmatter)
    render(lout_src, args)
```

A raw Lout escape hatch, useful when markdown's vocabulary runs out:

```lout
@CentredDisplay @B @I { "Hand-written Lout, embedded mid-document." }
```

!!! note "Heads up"
    This admonition block tests `mdlout`'s admonition-to-`@Box` mapping.
    Anything inside should be boxed and clearly set off from running text.

# Closing remarks

If this document renders cleanly in both HTML and PDF, the regression suite
has nothing to complain about today. *Onward to the next bug.*
