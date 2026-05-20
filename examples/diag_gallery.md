---
title: Lout Diagram Gallery
author: mdlout
type: doc
---

# Diagram gallery

This document exercises every documented feature of Lout's `@Diag` package
(the `diag` library, from chapter 9 of the Lout User's Guide). Each
example uses the ` ```lout` raw passthrough fence -- mdlout does not yet
have a markdown shortcut for diagrams.

mdlout auto-detects `@Diag` / `@Tree` / `@Node` / `@Link` / shape macros
in raw Lout fenced blocks and adds `@SysInclude { diag }` to the preamble.
Inside `@Diag { ... }` the available shape macros are `@Box` (the default
for `@Node`), `@CurveBox`, `@ShadowBox`, `@Square`, `@Diamond`,
`@Polygon`, `@Isosceles`, `@Ellipse`, `@Circle`, plus `@Tree` for tree
diagrams.

## Arrowstyles

Lout's diagram links support ten arrowhead styles. Each example below
draws two nodes connected by a directed link, varying only the
`arrowstyle` option.

### solid (filled triangle, the default)

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { solid }
}
```

### solidwithbar (filled triangle behind a perpendicular bar)

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { solidwithbar }
}
```

### halfopen (open V, only one barb)

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { halfopen }
}
```

### open (open V, both barbs)

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { open }
}
```

### curvedsolid

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { curvedsolid }
}
```

### curvedhalfopen

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { curvedhalfopen }
}
```

### curvedopen

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { curvedopen }
}
```

### circle

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { circle }
}
```

### box

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { box }
}
```

### many

```lout
@CentredDisplay @Diag {
A:: @Node { A } ||1.5c B:: @Node { B }
// @Link from { A } to { B } arrow { yes } arrowstyle { many }
}
```

## Node outlines

`@Diag` offers several built-in outlines via shape macros. Each one is
shorthand for `@Node outline { name }`.

### Box (`@Box` / `@Node`, the default)

```lout
@CentredDisplay @Diag {
@Box { Box outline }
}
```

### CurveBox (rounded)

```lout
@CentredDisplay @Diag {
@CurveBox { CurveBox outline }
}
```

### ShadowBox

```lout
@CentredDisplay @Diag {
@ShadowBox { ShadowBox outline }
}
```

### Square

```lout
@CentredDisplay @Diag {
@Square { Sq }
}
```

### Ellipse

```lout
@CentredDisplay @Diag {
@Ellipse { Ellipse outline }
}
```

### Circle

```lout
@CentredDisplay @Diag {
@Circle //1.2c ||1.2c { Cir }
}
```

### Diamond

```lout
@CentredDisplay @Diag {
@Diamond { Diamond outline }
}
```

### Polygon (3-sided -> triangle)

```lout
@CentredDisplay @Diag {
@Polygon sides { 3 } { Tri }
}
```

### Isosceles (a tall triangle)

```lout
@CentredDisplay @Diag {
@Isosceles { Iso }
}
```

### Row of all available shapes

```lout
@CentredDisplay @Diag {
A:: @Box       { Box }     ||0.4c
B:: @CurveBox  { Curve }   ||0.4c
C:: @ShadowBox { Shadow }  ||0.4c
D:: @Square    { Sq }      ||0.4c
E:: @Ellipse   { Ell }     ||0.4c
F:: @Circle //1.0c ||1.0c { Ci } ||0.4c
G:: @Diamond   { Dia }     ||0.4c
H:: @Polygon sides { 3 } { Tri }
}
```

## Tree diagrams (`@Tree` inside `@Diag`)

`@Tree` lays out a node with subtree children attached underneath via
`@LeftSub`, `@RightSub`, `@Sub`. Inside it, the same shape macros work
as `@TNode`-flavoured nodes.

### Simple two-level tree

```lout
@CentredDisplay @Diag {
@Tree {
@Node { root }
@Sub { @Node { left } }
@Sub { @Node { middle } }
@Sub { @Node { right } }
}
}
```

### Three-level tree

```lout
@CentredDisplay @Diag {
@Tree {
@Node { CEO }
@Sub { @Tree {
   @Node { VP-Eng }
   @Sub { @Node { Alice } }
   @Sub { @Node { Bob } }
} }
@Sub { @Tree {
   @Node { VP-Sales }
   @Sub { @Node { Carol } }
   @Sub { @Node { Dave } }
} }
}
}
```

## Multi-link diagrams

Three or more nodes connected by various paths.

### Triangle of three nodes, all pairs linked

```lout
@CentredDisplay @Diag {
A:: @Node //2c { A } ||3c
B:: @Node { B }
// @Node {}
// C:: @Node //2c { C }
//
@Link from { A } to { B } arrow { yes } arrowstyle { solid }
@Link from { B } to { C } arrow { yes } arrowstyle { solid }
@Link from { A } to { C } arrow { yes } arrowstyle { solid }
}
```

### Branching graph (1-to-many)

```lout
@CentredDisplay @Diag {
Root:: @Node { start } ||2c
A:: @Node { A } //1c
B:: @Node { B } //1c
C:: @Node { C }
//
@Link from { Root } to { A } arrow { yes }
@Link from { Root } to { B } arrow { yes }
@Link from { Root } to { C } arrow { yes }
}
```

### Cycle with labelled links

```lout
@CentredDisplay @Diag {
A:: @Node //2c { A } ||3c
B:: @Node { B }
// @Node {}
// C:: @Node //2c { C }
//
@Link from { A } to { B } arrow { yes } alabel { a-to-b } alabelpos { N }
@Link from { B } to { C } arrow { yes } alabel { b-to-c } alabelpos { E }
@Link from { C } to { A } arrow { yes } alabel { c-to-a } alabelpos { W }
}
```

## `@Ellipse` with tag labels (state machine)

State-machine-style example: ellipse nodes with external labels at
their boundary.

```lout
@CentredDisplay @Diag {
A:: @Ellipse nodelabel { state A } nodelabelpos { N }
   { start }
||2c
B:: @Ellipse nodelabel { state B } nodelabelpos { N }
   { middle }
||2c
C:: @Ellipse nodelabel { accepting } nodelabelpos { N }
   { end }
//
@Link from { A } to { B } arrow { yes } alabel { x } alabelpos { S }
@Link from { B } to { C } arrow { yes } alabel { y } alabelpos { S }
}
```

## Syntax-diagram style (railroad)

Lout's diag library does not ship a dedicated `@SyntaxDiag` macro, but
the same effect is straightforward to build with `@CurveBox` for terminal
boxes and explicit `@Link` paths. The classic page-220 examples become:

### Identifier sequence: letter -> digit -> underscore

```lout
@CentredDisplay @Diag {
S:: @Node {} ||0.6c
A:: @CurveBox margin { 0.3f } { letter } ||1c
B:: @CurveBox margin { 0.3f } { digit }  ||1c
C:: @CurveBox margin { 0.3f } { _ } ||0.6c
E:: @Node {}
//
@Link from { S } to { A } arrow { yes }
@Link from { A } to { B } arrow { yes }
@Link from { B } to { C } arrow { yes }
@Link from { C } to { E } arrow { yes }
}
```

### Optional element (skip path)

```lout
@CentredDisplay @Diag {
S:: @Node {} ||0.8c
A:: @CurveBox margin { 0.3f } { keyword } ||0.8c
E:: @Node {}
//
@Link from { S } to { A } arrow { yes }
@Link from { A } to { E } arrow { yes }
@Link from { S } to { E } arrow { yes } path { line }
}
```

## End

This concludes the `@Diag` gallery. If your build succeeded, every
section above produced a rendered diagram in the output HTML/PDF.
