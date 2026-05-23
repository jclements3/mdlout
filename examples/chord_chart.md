---
type: doc
title: Chord chart with multi-line scores
author: mdlout examples
font: Times Base 11p
page: Letter
para-indent: 0f
para-gap: 1.0v
page-headers: None
---

<!--
  chord_chart.md -- exercises the ```abc passthrough at a heavier
  workload than 05_music.md: multi-line scores, multiple voices,
  and dense chord-symbol annotations above each bar.

  All blocks are HTML-mode only.  In PDF mode the ABC fences
  become "[ABC music notation: ...]" literal placeholders; the
  prose around them still typesets cleanly so the document does
  not collapse.
-->

# Chord chart with multi-line scores

This page exercises the ` ```abc ` passthrough at the
density a working musician's chord chart wants: chord symbols
above every bar, multiple staves per piece, and -- in the last
example -- a two-voice arrangement with a melody line and a bass
line on the same staff.

## A twelve-bar blues with chord changes

Twelve bars, four bars per line, with `"G7"`, `"C7"`, and `"D7"`
chord symbols sitting above each downbeat. The melody is a
quarter-note walking line. The trailing `|]` is the closing
double bar.

```abc
X:1
T:Twelve-Bar Blues in G
M:4/4
L:1/4
K:G
"G7" G B d f | "G7" G B d f | "G7" G B d f | "G7" G B d f |
"C7" c e g b | "C7" c e g b | "G7" G B d f | "G7" G B d f |
"D7" A c e g | "C7" c e g b | "G7" G B d f | "D7" A c e g |]
```

Once abcjsharp engraves the block in the browser, the chord
symbols sit above the staff at a fixed offset (configured by
abcjs's `chordfont` parameter), the bars wrap to a fresh line on
the engraver's natural break-points, and each line aligns by bar
rather than by absolute width.

## Eight-bar phrase, two lines on the page

Some tunes -- folk melodies, hymns, jazz standards -- want a
specific bar-per-line layout to match the verse structure.
Force a break with a Lout-style line-break (`$$$` in ABC syntax
is the explicit *score linebreak*) so each phrase ends a line.

```abc
X:2
T:Folk Tune in D
M:3/4
L:1/4
K:D
"D" A B c | "G" B A G | "D" A F D | "A" A2 z |
"D" A B c | "G" d c B | "D" A F D | "D" D3 |]
```

Without the linebreak (`$$$` is optional; here we let abcjs
break naturally), abcjsharp will fit as many bars per line as the
container width allows. On a US Letter page with the default
side-margins the engraver lays this out as two lines of four bars
each.

## Two-voice arrangement on one staff

A melody-and-bass arrangement using ABC's voice tags. The lower
voice (V:2) is set in stem-down notation; abcjsharp engraves
both voices on the same staff, separating them by stem direction.

```abc
X:3
T:Two-Voice Sketch
M:4/4
L:1/4
K:C
V:1
"C"   e g e c | "F"   f a f c | "G"   d g d B | "C"   c e g c |
V:2
"C"  C, E, G, C, | "F"  F,, A, C, F,, | "G"  G,, D, G, B,, | "C"  C, E, G, C, |
```

In abcjsharp the two voices share a single five-line staff: V:1
stems point up, V:2 stems point down. The chord symbols only need
to appear on V:1 -- duplicating them on the bass line would
clutter the engraving.

## A long-form chord chart -- jazz standard

Sixteen bars, a B-section with key change implied by the chord
extensions. The piece does not modulate -- the key signature stays
in C -- but the chord changes carry the harmony forward.

```abc
X:4
T:Standard Changes (16 bars)
C:mdlout examples
M:4/4
L:1/4
K:C
"Cmaj7" C E G B | "Dm7" D F A c | "G7" G B d f | "Cmaj7" C E G B |
"Cmaj7" C E G B | "Dm7" D F A c | "G7" G B d f | "Em7" E G B d |
"Am7" A, C E A | "Dm7" D F A c | "G7" G B d f | "Cmaj7" C E G c |
"Fmaj7" F A c f | "Bm7b5" B, D F A | "E7" E, G, B, e | "Am" A, C E A |]
```

The chord symbols include slash-chords (`"F/C"`), half-diminished
(`"Bm7b5"`), and major-seven extensions -- abcjsharp parses all
the standard pop/jazz chord conventions and engraves them without
further configuration. If a chord name does not parse the engraver
falls back to printing the literal string above the bar.

## Harp grand-staff with chord names

The fork at <https://github.com/clementsj/abcjsharp> supports the
`%%score (RH | LH)` directive: two voices, brace-coupled, one staff
each. Chord symbols above the RH staff only:

```abc
X:5
T:Harp Sketch
C:mdlout examples
M:3/4
L:1/8
Q:1/4=72
K:C
%%score (RH | LH)
V:RH clef=treble
V:LH clef=bass
[V:RH] "C" E2 G2 c2  | "F/C" F2 A2 c2  | "G/B" D2 G2 B2  | "C" E2 G2 c2  |
[V:LH] C,4   E,2     | C,4   F,2       | G,,4  G,2       | C,4   C2       |
[V:RH] "Am" A,2 C2 E2 | "Dm" D2 F2 A2  | "G7" G,2 B,2 D2 | "C" C2 E2 G2  |
[V:LH] A,,4 C,2       | D,,4 F,,2      | G,,4 D,2        | C,,4 C,2      |
```

The brace at the left of the system is what `%%score (RH | LH)`
buys you -- without it the two voices render as two separate
staves with no visual coupling.

## A note on PDF mode

Every ` ```abc ` fence above falls back to a placeholder in
`--format=pdf`: the block renders as the literal `[ABC music
notation: X:1 T:Twelve-Bar Blues...]`. For an archival PDF chord
chart, pre-render the scores with `abcm2ps` or with the abcjsharp
CLI, save the result as `.svg` (one file per piece), and reference
them as `![twelve-bar blues](twelve_bar.svg)` from the markdown.
The HTML route stays the same; the PDF route picks up the
pre-rendered images via mdlout's standard image-include path.

The `abcm2ps` invocation that matches the abcjsharp default
engraving is approximately:

```shell
abcm2ps -O = -g chart.abc      # writes chart.svg
```

For abcjsharp specifically:

```shell
abcjs render-cli chart.abc --svg --out chart.svg
```

The latter respects the `%%score`, `chordfont`, and `staffsep`
parameters that the in-browser engraver uses; `abcm2ps` predates
those and will reformat the brace coupling slightly differently.
