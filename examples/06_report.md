---
type: report
title: Markdown-to-Lout Pipeline Status
author: James Clements III
institution: mdlout project
date: 2026-05-19
cover: Yes
contents: Yes
page: A4
section-numbers: Arabic
---

[TOC]

# Introduction

This report documents the current state of the **mdlout** Markdown-to-Lout
converter. The toolchain is split into three layers: a single-file Python
front end that parses Markdown and emits Lout source, a forked C implementation
of Lout (3.43, William8000 fork) that turns Lout into PostScript or SVG, and a
thin wrapper that produces PDF (via `ps2pdf`) or HTML (by wrapping the SVG back
end's output).

## Architecture

The front end runs four phases: frontmatter extraction, block-level parsing,
inline conversion via a placeholder system that protects code and links from
double-escaping, and Lout generation. For `report` and `book` document types,
heading levels are mapped to nested `@Section` / `@SubSection` constructs;
for the default `doc` type, headings render as styled `@Display` blocks.

### Why Lout?

Lout's stream model — galleys flowing into targets — is uniquely well-suited
to mixing engraved music, mathematics, and prose without resorting to a
TeX-style box-and-glue model. The trade-off is a smaller community and a
narrower set of available macros, which is exactly the gap mdlout is filling.

# Implementation notes

A representative slice of the inline conversion code:

```python
def convert_inline(text: str) -> str:
    _ph_reset()
    result = _convert_inline_inner(text)
    return _ph_restore(result)
```

The placeholder dance keeps Lout's `@` and `{}` metacharacters out of harm's
way while inline spans are extracted, then restores them once plain-text
escaping is finished.

## A worked equation

The closed form for the n-th Fibonacci number, useful as a sanity check that
math blocks survive the round-trip:

$$
F_n = \frac{1}{\sqrt{5}} \left( \varphi^n - \psi^n \right),
\quad \varphi = \frac{1 + \sqrt{5}}{2}, \quad \psi = \frac{1 - \sqrt{5}}{2}
$$

## A figure block

```lout
@CentredDisplay @Box margin { 0.5c } paint { lightgrey } {
  @B { Figure 1. } The pipeline:
  Markdown @Arrow Lout @Arrow PostScript @Arrow PDF
}
```

# Status and next steps

Working today: text emission, font lookup, page geometry, transforms, and
underlining. In progress: the colour pipeline, raw SVG passthrough, and the
three macro shims `@Math`, `@ABC`, `@SVG`. Once those land, mdlout will be
able to typeset prose, math, and engraved music in one document — which is
the original goal.
