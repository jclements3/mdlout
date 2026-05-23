---
type: doc
title: Marginalia and Side-Notes
author: mdlout regression suite
font: Times Base 11p
page: A4
top-margin: 2.5c
foot-margin: 2.5c
left-margin: 2.5c
right-margin: 5.5c
para-gap: 1.0v
para-indent: 0f
language: English
page-headers: None
---

<!--
  marginalia.md -- exercises Lout's @LeftNote / @RightNote / @OuterNote /
  @InnerNote machinery via raw-Lout fences.

  The right margin is widened to 5.5cm (the default 2.5cm is too cramped
  for legible margin notes; the Lout User's Guide explicitly recommends
  this) and the page-headers line is suppressed so the eye does not have
  to compete with running heads.

  Margin notes are NOT a markdown shorthand in mdlout; they live entirely
  in raw-Lout fences embedded mid-paragraph. The note attaches to the
  word immediately preceding the @RightNote / @LeftNote token. Lout then
  positions the note in the margin at the same vertical height as that
  word -- shifting downward if a previous note would overlap, but never
  forward onto the next page.
-->

# Marginalia and Side-Notes

This page is set up with an extra-wide right margin (5.5 cm against the
default 2.5 cm), which gives Lout's `@RightNote` machinery room to lay
out readable annotations alongside the main column. The pattern is
classic Tufte: keep the eye on a single column of prose, and let
commentary, definitions, and references ride in the margin without
breaking the flow.

```lout
@LP
The composite trapezoidal rule
@RightNote @I { Named for the polygon you get when you join successive samples
of @F { f } with straight lines. }
estimates the integral of a function by summing the areas of trapezoids
fitted under the integrand on a uniform grid. It converges at second order
in the step size for sufficiently smooth integrands.
@LP
```

The note above appears flush against the right margin, set in italic at
80% of the body size (Lout's default `@MarginNoteFont`). The body line
itself is not interrupted: Lout reflows the column as if the note were
not there, and only the margin column knows it exists.

## Multiple notes on one page

A second paragraph, with two notes:

```lout
@LP
Simpson's "1/3" rule
@RightNote { Sometimes just called @I { Simpson's rule. } The
"1/3" distinguishes it from the variant that uses a degree-three
polynomial on four nodes -- "Simpson's 3/8" rule -- which is mostly of
historical interest. }
goes one degree higher: it fits a quadratic to each triple of consecutive
samples and integrates the quadratic exactly. The resulting estimator has
@I { fourth-order } accuracy
@RightNote @I { Halving the step size cuts the error by a factor of
sixteen, not four. }
in the step size whenever the integrand is four times continuously
differentiable on the interval.
@LP
```

When two notes are close enough to overlap, Lout shifts the second one
downward so they sit cleanly. You can see this in the rendered output: the
second note above starts a line or two lower than the word it annotates.

## Footnotes vs side-notes

Markdown's `[^name]` footnotes go to the foot of the page; side-notes go
to the side. Both have their place. Footnotes are the right choice for
citations and substantive asides[^citation-note]; side-notes are the right
choice for *micro-glosses* -- a short definition, a reminder, or a
running commentary the reader can ignore without losing the thread.

[^citation-note]: Like this one. Footnotes are rendered by mdlout's
standard `[^name]` -> `@FootNote` pipeline; the side-notes elsewhere on
the page go through raw-Lout `@RightNote` fences instead.

## Layered annotation: an outer-margin gloss

`@OuterNote` is the binding-aware variant: it puts the note in the
*outer* margin -- the right margin on a recto (odd) page, the left margin
on a verso (even) page. On a single-page test document like this one
recto/verso don't differ, so `@OuterNote` is visually identical to
`@RightNote`; the value of the macro shows in a multi-page bound book.

```lout
@LP
The continuous extension of the harmonic series to complex arguments is
called the Riemann zeta function
@OuterNote @I { Riemann's 1859 memoir is eight pages long and contains
the still-unproven conjecture about the location of its non-trivial
zeros. }
and its non-trivial zeros are the subject of one of the seven
Millennium Prize Problems.
@LP
```

## A note inside a numbered list

Side-notes work inside structured environments too. Here is a short
numbered list, each item with its own marginal annotation:

```lout
@LP
@NumberedList
@ListItem { Locate the integrand and the interval of integration.
@RightNote @I { On computer algebra systems the integrand often arrives
already in symbolic form; the integration interval may not be obvious if
the user has assumed implicit bounds. } }
@ListItem { Choose a step size @F { h } or, equivalently, a number of
panels @F { n }.
@RightNote @I { Smaller @F { h } means more function evaluations and
lower truncation error. } }
@ListItem { Apply the rule and obtain the estimate.
@RightNote @I { The estimate is exact in floating-point only up to round-off
in the summation; for very large @F { n }, use Kahan compensation. } }
@EndList
@LP
```

## Closing observation

Margin notes are one of the features that justify having a real
typesetting engine underneath mdlout: TeX, Lout, and InDesign all do this
well, while every web-stack approximation involves CSS contortions and a
non-flowing column. Lout's stream model handles the column reflow for
free.

Tufte's *Visual Display of Quantitative Information* is the canonical
reference for the side-note idiom. Knuth's *Concrete Mathematics* is a
second touchstone: every page is structured around a wide right margin
that carries running commentary, jokes, and reference pointers in a hand
several decimal sizes smaller than the body. The same effect is possible
here with `@RightNote`, a fixed `right-margin: 5.5c` in the frontmatter,
and no further machinery.
