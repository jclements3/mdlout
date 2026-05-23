---
type: doc
title: A Multilingual Sampler
author: mdlout regression suite
font: Times Base 11p
page: A4
top-margin: 2.5c
foot-margin: 2.5c
left-margin: 2.5c
right-margin: 2.5c
para-gap: 1.0v
para-indent: 0f
language: English
page-headers: None
---

<!--
  multilingual.md -- exercises three orthogonal axes of non-English text
  rendering in mdlout/Lout:

  1. Latin / Western-European prose with accented characters. mdlout's
     markdown source is UTF-8, but the Lout binary reads ISO-Latin-1, so
     UTF-8 multi-byte sequences round-trip incorrectly. The robust path
     is to drop into a raw-Lout fence and use @Char "eacute" / "agrave"
     etc., or the bsf shorthands "``" "''" "--" "---" "..." for
     punctuation. Both back-ends honour this route.

  2. Greek letters via the Adobe Symbol font (@Sym alpha, @Sym Pi, ...).
     Recent z53.c work (commit ec987be) wired the Symbol glyph table into
     the SVG back-end, so HTML output now matches the PostScript
     reference glyph-for-glyph.

  3. A KaTeX math equation that itself uses Greek + the Symbol math
     operators. Renders fully in HTML; PDF mode falls back to the @Math
     placeholder.

  A small Cyrillic specimen at the bottom shows how to invoke Lout's
  built-in Russian language pack via raw-Lout passthrough; see
  cookbook.md recipe 18 for the gotcha discussion.
-->

# A Multilingual Sampler

This page exercises mdlout's handling of three character regimes in one
document: accented Latin glyphs that ride on the document's base font, Greek
letters drawn from the Adobe Symbol font via `@Sym`, and a `$...$` /
`$$...$$` math block whose LaTeX commands include further Greek and math
operators.

## Latin: accented Western-European text

Lout's standard ISO-Latin-1 character map covers the routine
Western-European accent menagerie. Because mdlout reads UTF-8 markdown but
Lout reads ISO-Latin-1, the safest path for accented letters is to drop
into a raw-Lout fence and request each glyph by Adobe PostScript name with
`@Char`:

```lout
@LP
@CentredDisplay {
Le caf @Char "eacute" -- la place @Char "Eacute" toile -- na @Char "idieresis" ve
M @Char "udieresis" nchner -- cr @Char "ecircumflex" pes Suzette -- l'
@Char "acircumflex" ne -- El Ni @Char "ntilde" o -- S @Char "atilde" o Paulo
}
@LP
```

Punctuation has shorthands in `bsf`: `` `` `` and `''` render directional
quotes, `--` is an en-dash, `---` an em-dash, `...` ellipsis. Those work
inline without leaving markdown. A short worked sentence: this manual
uses ``directional quotes'' and the occasional em-dash---like so---in
ordinary prose.

## Greek: the Symbol font via `@Sym`

The Adobe Symbol font supplies a full lowercase + uppercase Greek alphabet
plus the standard math operators. Lout exposes it through the `@Sym`
macro in the `bsf` library. Recent z53.c work wired the Symbol glyph table
through the SVG back-end, so the HTML output below is glyph-identical to
the PostScript reference.

```lout
@LP
@CentredDisplay { Helvetica Base 12p } @Font {
@Sym alpha   @Sym beta    @Sym gamma   @Sym delta   @Sym epsilon  @Sym zeta
//
@Sym eta     @Sym theta   @Sym iota    @Sym kappa   @Sym lambda   @Sym mu
//
@Sym nu      @Sym xi      @Sym pi      @Sym rho     @Sym sigma    @Sym tau
//
@Sym phi     @Sym chi     @Sym psi     @Sym omega
}
@LP
@CentredDisplay { Helvetica Base 12p } @Font {
@Sym Alpha   @Sym Beta    @Sym Gamma   @Sym Delta   @Sym Epsilon  @Sym Zeta
//
@Sym Eta     @Sym Theta   @Sym Iota    @Sym Kappa   @Sym Lambda   @Sym Mu
//
@Sym Nu      @Sym Xi      @Sym Pi      @Sym Rho     @Sym Sigma    @Sym Tau
//
@Sym Phi     @Sym Chi     @Sym Psi     @Sym Omega
}
@LP
```

A handful of Symbol operators used in scientific text: integration,
summation, square root, infinity, partial derivative, gradient, and the
usual plus-or-minus / multiply / less-or-equal / greater-or-equal /
set-membership glyphs.

```lout
@LP
@CentredDisplay { Helvetica Base 14p } @Font {
@Sym integral  @Sym summation  @Sym radical  @Sym infinity
||1.0c
@Sym partialdiff  @Sym gradient  @Sym plusminus  @Sym multiply
||1.0c
@Sym lessequal  @Sym greaterequal  @Sym element  @Sym arrowright
}
@LP
```

## Math: a Greek-laden equation block

KaTeX handles the LaTeX command set in HTML mode; in PDF mode the same
block falls back to the `@Math` placeholder. The Euler identity, the
golden ratio, and an integral over the real line:

$$
e^{i\pi} + 1 = 0, \qquad \varphi = \frac{1 + \sqrt{5}}{2}, \qquad
\int_{-\infty}^{\infty} e^{-x^2}\, dx = \sqrt{\pi}.
$$

A second display, showing the Riemann zeta function at $s = 2$ and the
Gauss-Bonnet formula:

$$
\zeta(2) = \sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6},
\qquad \int_M K\, dA + \int_{\partial M} k_g\, ds = 2\pi\, \chi(M).
$$

Inline math also flows through: the fine-structure constant
$\alpha \approx 1/137$, the Planck relation $E = h\nu$, and the spin-half
operator commutator $[\sigma_x, \sigma_y] = 2i\sigma_z$.

## Cyrillic: a Russian-language paragraph

Lout ships a Russian language pack (`@SysInclude { russian }`) that wires
KOI8-R input through the Russian PostScript fonts. Driving it from the
markdown layer is a two-step dance: switch the document language inside a
raw-Lout fence with `{ Russian } @Language`, then type the Cyrillic text
inside that fence. A Roman-letter transliteration is shown here because
the SVG back-end does not yet ship the Cyrillic glyph table.

```lout
@LP
{ Russian } @Language {
@CentredDisplay @I { "Privet, mir!" -- a Roman-letter transliteration. }
}
@LP
```

The Russian package itself is the reference for what genuine Cyrillic
input looks like; see `lout/include/russian` and the `KOI8-R.LCM`
character map in `lout/maps/`. Wiring full UTF-8 Cyrillic through z53.c
is tracked in `TODO.md`.

## Closing observation

Three writing systems, one Lout pass. The PDF pipeline (`mdlout
--format=pdf`) is the canonical archival format for the Latin and Greek
sections; HTML is the canonical format for the math (KaTeX) and for
copy-and-paste fidelity of accented characters.
