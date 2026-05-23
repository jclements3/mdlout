---
type: doc
title: Hand-rolled SVG diagrams
author: mdlout examples
font: Times Base 11p
page: A4
para-indent: 0f
para-gap: 1.0v
page-headers: None
---

<!--
  svg_diagram.md -- exercises the ```svg fenced-code passthrough.

  Every fenced ```svg block is routed through the @SVG macro (HTML
  mode) and inlined verbatim into the page. In PDF mode the macro
  is a stub: the block disappears with an apology, but the rest
  of the page still typesets cleanly.

  The point of the example is to show what hand-drawn SVG buys you
  when @Mermaid is too auto-magic and @Diag is too rigid: arbitrary
  shapes, gradients, text-on-path, hand-tuned coordinates, and a
  predictable output size.
-->

# Hand-rolled SVG diagrams

mdlout's `@Diag` package and the `@Mermaid` passthrough cover most
day-to-day diagrams, but they are both *programs* that emit a
layout. When a figure calls for hand-tuned coordinates, custom
gradients, or shapes the diagram engines do not ship -- a hex
grid, a phase portrait, a logo, a circuit symbol -- drop into a
` ```svg ` fenced block. The body of the fence is inlined
verbatim inside the page SVG via the `@SVG` macro.

## A traffic-light state machine

Three coloured nodes, one for each light, with directed arrows
labelled by their dwell times. The whole figure is 360 by 110
points, sized to sit between two paragraphs without forcing a
page break:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="360" height="110" viewBox="0 0 360 110">
  <defs>
    <marker id="arrowL" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#333"/>
    </marker>
  </defs>
  <circle cx="60"  cy="55" r="32" fill="#e63946" stroke="#222" stroke-width="1.5"/>
  <circle cx="180" cy="55" r="32" fill="#f4d35e" stroke="#222" stroke-width="1.5"/>
  <circle cx="300" cy="55" r="32" fill="#2a9d8f" stroke="#222" stroke-width="1.5"/>
  <text x="60"  y="60" text-anchor="middle" font-family="serif" font-size="13" fill="#111">RED</text>
  <text x="180" y="60" text-anchor="middle" font-family="serif" font-size="13" fill="#111">AMBER</text>
  <text x="300" y="60" text-anchor="middle" font-family="serif" font-size="13" fill="#fff">GREEN</text>
  <path d="M 92  55 L 148 55" stroke="#333" stroke-width="1.5" fill="none" marker-end="url(#arrowL)"/>
  <path d="M 212 55 L 268 55" stroke="#333" stroke-width="1.5" fill="none" marker-end="url(#arrowL)"/>
  <path d="M 300 87 C 300 105, 60 105, 60 87"
        stroke="#333" stroke-width="1.5" fill="none" marker-end="url(#arrowL)"/>
  <text x="120" y="48" text-anchor="middle" font-family="serif" font-size="10" fill="#333">30s</text>
  <text x="240" y="48" text-anchor="middle" font-family="serif" font-size="10" fill="#333">5s</text>
  <text x="180" y="103" text-anchor="middle" font-family="serif" font-size="10" fill="#333">25s</text>
</svg>
```

The transitions read left-to-right (RED to AMBER to GREEN at the
top) and the curved return loop closes the cycle. None of this is
expressible in `@Mermaid`'s `stateDiagram` syntax without losing
the fixed-pixel control over the loop curvature.

## A phase portrait sketch

Pure geometry: a unit circle, two crossing axes, and a spiral
trajectory drawn as a single cubic-Bezier path. mdlout's `@Diag`
package has no built-in spiral primitive; SVG's `<path d="..."/>`
syntax expresses one in a single line.

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" viewBox="-120 -120 240 240">
  <line x1="-110" y1="0" x2="110" y2="0" stroke="#888" stroke-width="0.6"/>
  <line x1="0" y1="-110" x2="0" y2="110" stroke="#888" stroke-width="0.6"/>
  <circle cx="0" cy="0" r="80" fill="none" stroke="#aac" stroke-dasharray="3 3"/>
  <path d="M 90 0
           C 90 -50, 30 -90, -30 -60
           C -90 -30, -60 30, 0 30
           C 60 30, 30 -10, 0 0"
        fill="none" stroke="#2c5aa0" stroke-width="1.6"
        stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="90" cy="0" r="3" fill="#2c5aa0"/>
  <circle cx="0" cy="0" r="2.5" fill="#111"/>
  <text x="100" y="-6"  font-family="serif" font-size="11" fill="#333">x</text>
  <text x="6"   y="-100" font-family="serif" font-size="11" fill="#333">y</text>
  <text x="95"  y="14" font-family="serif" font-size="10" fill="#2c5aa0">start</text>
  <text x="-12" y="-6" font-family="serif" font-size="10" fill="#111">0</text>
</svg>
```

The trajectory starts at the marked point on the positive x-axis,
loops inward toward the origin, and the dashed circle marks the
unit-radius sphere of attraction. The viewBox is centred on the
origin (negative-half to positive-half on each axis) so the SVG
coordinate system matches the math.

## A custom logo / mark

When a document needs a one-off mark -- a chapter ornament,
a publisher's colophon -- inline SVG is the lightest path. No
external asset to ship, no font to embed:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80" viewBox="0 0 200 80">
  <defs>
    <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="#f7c873"/>
      <stop offset="100%" stop-color="#b8862c"/>
    </linearGradient>
  </defs>
  <path d="M 20 60 L 50 12 L 80 60 L 65 60 L 50 35 L 35 60 z"
        fill="url(#gold)" stroke="#7a5a18" stroke-width="0.8"/>
  <text x="95" y="48" font-family="serif" font-size="22" font-style="italic"
        font-weight="bold" fill="#3a2a08">mdlout</text>
  <line x1="95" y1="54" x2="180" y2="54" stroke="#7a5a18" stroke-width="0.8"/>
  <text x="95" y="68" font-family="serif" font-size="9" fill="#5a3a14"
        letter-spacing="2">EST.  2026</text>
</svg>
```

The gradient `<linearGradient>` is what makes this hard to
duplicate in PostScript-only Lout: PostScript supports gradients,
but `z49.c` does not expose the syntax in a way that hand-rolled
content can drive. In the SVG back-end the gradient is just SVG.

## A coordinate grid for a manual layout

Sometimes you want a *blueprint* feel -- gridded background,
labelled axes, hand-placed shapes. Below is an architectural-style
floor plan, with grid lines, room outlines, and a door swing:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="340" height="200" viewBox="0 0 340 200">
  <defs>
    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e6eef7" stroke-width="0.6"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="340" height="200" fill="url(#grid)"/>
  <rect x="20"  y="20" width="140" height="80"  fill="#fafafa" stroke="#222" stroke-width="1.4"/>
  <rect x="160" y="20" width="160" height="80"  fill="#fafafa" stroke="#222" stroke-width="1.4"/>
  <rect x="20"  y="100" width="300" height="80" fill="#fafafa" stroke="#222" stroke-width="1.4"/>
  <line x1="80" y1="100" x2="120" y2="100" stroke="#fafafa" stroke-width="2"/>
  <path d="M 80 100 A 40 40 0 0 1 120 100" fill="none" stroke="#888" stroke-width="0.8"/>
  <text x="90"  y="65"  font-family="serif" font-size="12" fill="#222">Study</text>
  <text x="220" y="65"  font-family="serif" font-size="12" fill="#222">Library</text>
  <text x="150" y="145" font-family="serif" font-size="12" fill="#222">Hall</text>
  <text x="100" y="195" font-family="serif" font-size="9"  fill="#888">door (swing shown)</text>
</svg>
```

The `<pattern>` element gives the grid background; the door-swing
arc is a single arc-to (`A`) segment. None of this would be
practical to draw in `@Diag` -- the package is good at boxes-and-
arrows, not at architectural layout.

## When to reach for `@SVG`

A short decision rule:

- *Boxes-and-arrows*: stay in `@Diag` or `@Mermaid`. The auto-layout
  is faster than hand-placing nodes.
- *Mathematical/scientific figures*: `@Diag` if the figure is
  trees / graphs; raw SVG if it is geometry (phase portraits,
  contour plots, vector fields).
- *Logos, ornaments, blueprint backdrops*: raw SVG every time.
  These need pixel-level control and the diagram engines do not
  give it.
- *Charts*: usually pre-render in matplotlib / D3 / observable and
  `![](chart.svg)` the result. Hand-rolling a chart in inline SVG
  is possible but rarely worth the labour.

The PDF route is the catch: every `@SVG` block in PDF mode falls
back to a placeholder. If the figure must appear in the print
build, render it once with `--format=html`, screenshot or
`pdftocairo -svg` the result, save the file alongside the source,
and reference it as `![](figure.svg)` -- which the SVG back-end
inlines and the PostScript back-end ships through ImageMagick.
