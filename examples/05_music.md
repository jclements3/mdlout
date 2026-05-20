# Music sampler

Three ABC blocks of increasing complexity. The third one uses the `%%score`
directive to lock two staves into a piano/harp grand-staff layout.

A one-line melody — the opening of "Frère Jacques" in G:

```abc
X:1
T:Frere Jacques
M:4/4
L:1/4
K:G
G A B G | G A B G | B c d2 | B c d2 |
```

A short tune with chord symbols above the staff:

```abc
X:2
T:Twelve-Bar Blues in G
C:Traditional
M:4/4
L:1/4
K:G
"G7" G B d f | "G7" G B d f | "G7" G B d f | "G7" G B d f |
"C7" c e g b | "C7" c e g b | "G7" G B d f | "G7" G B d f |
"D7" A c e g | "C7" c e g b | "G7" G B d f | "D7" A c e g |
```

A harp grand-staff piece — treble (right hand) and bass (left hand) joined by
the `%%score` directive so they render as a single brace-coupled system:

```abc
X:3
T:Prelude for Harp
C:mdlout regression suite
M:3/4
L:1/8
Q:1/4=72
K:C
%%score (RH | LH)
V:RH clef=treble
V:LH clef=bass
[V:RH] "C" E2 G2 c2 | "F/C" F2 A2 c2 | "G/B" D2 G2 B2 | "C" E2 G2 c2 |
[V:LH] C,4   E,2   | C,4   F,2       | G,,4  G,2     | C,4   C2       |
[V:RH] "Am" A,2 C2 E2 | "Dm" D2 F2 A2 | "G7" G,2 B,2 D2 | "C" C2 E2 G2 |
[V:LH] A,,4 C,2      | D,,4 F,,2     | G,,4 D,2        | C,,4 C,2     |
```

These blocks currently render as code blocks — once the `@ABC` passthrough
macro lands, mdlout should reroute fenced `abc` blocks into engraved music.
