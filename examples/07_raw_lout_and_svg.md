# Raw passthrough sampler

This file exercises the two raw-passthrough fenced-code conventions: ` ```lout `
for arbitrary Lout source and ` ```svg ` for arbitrary SVG snippets. The latter
should be routed through the `@SVG` macro once it lands.

## Raw Lout

A centred display, hand-written in Lout:

```lout
@CentredDisplay @B { Hand-written Lout passthrough }
```

A boxed paragraph with custom margin:

```lout
@CentredDisplay @Box margin { 0.4c } {
  This box was emitted by a raw Lout fenced block, not by any markdown
  construct.  The surrounding paragraphs were assembled the normal way.
}
```

Some hand-rolled Lout math using the `eq` package directly (rather than the
markdown-level `$$` block):

```lout
@CentredDisplay @Eq { int from 0 to inf e sup { - x sup 2 } d x = sqrt pi over 2 }
```

## Raw SVG

A simple SVG snippet with a red circle and a labelled rectangle. In HTML mode
this should appear inline; in PDF mode it currently passes through to the
`@SVG` macro (not yet implemented — expect graceful degradation):

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80" viewBox="0 0 120 80">
  <rect x="5" y="5" width="110" height="70" fill="#eef" stroke="#446" stroke-width="1"/>
  <circle cx="40" cy="40" r="20" fill="crimson" stroke="black" stroke-width="1"/>
  <text x="70" y="45" font-family="serif" font-size="14" fill="#223">SVG ok</text>
</svg>
```

A second SVG snippet — a line graph sketch:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="80" viewBox="0 0 160 80">
  <polyline points="10,70 40,55 70,40 100,30 130,15 150,10"
            fill="none" stroke="steelblue" stroke-width="2"/>
  <line x1="10" y1="70" x2="150" y2="70" stroke="black"/>
  <line x1="10" y1="10" x2="10"  y2="70" stroke="black"/>
</svg>
```

Closing paragraph — making sure that normal markdown still flows correctly
*after* a stack of raw fences.
