---
title: Complex Diagrams
author: mdlout
type: doc
---

# Complex diagram examples

This document pushes Lout's `diag` package harder than `diag_gallery.md`: a
real grammar in railroad-diagram form, a binary search tree, a flowchart
with mixed arrow styles, and a single diagram that combines several
constructs at once. Every figure is emitted via the ` ```lout` raw
passthrough fence; mdlout auto-detects the `@Diag`/`@Tree`/`@SyntaxDiag`
macros and pulls in the right `@SysInclude` lines.

## A grammar for arithmetic expressions

The classic four-rule expression grammar:

    expr   = term   ( ( "+" | "-" ) term )* ;
    term   = factor ( ( "*" | "/" ) factor )* ;
    factor = number | identifier | "(" expr ")" ;
    number = digit+ ;

Below each rule is rendered as a railroad-style `@SyntaxDiag`. Sequencing
uses `@Sequence`, alternatives use `@Select`, and the trailing `*` uses
`@Loop` so the diagram visibly returns to the front.

### `expr`

```lout
@CentredDisplay @SyntaxDiag
   title { expr }
{
@StartRight @Loop
   A { @ACell term }
   B { @Select
          A { @CCell "+" }
          B { @CCell "-" }
     }
}
```

### `term`

```lout
@CentredDisplay @SyntaxDiag
   title { term }
{
@StartRight @Loop
   A { @ACell factor }
   B { @Select
          A { @CCell "*" }
          B { @CCell "/" }
     }
}
```

### `factor`

```lout
@CentredDisplay @SyntaxDiag
   title { factor }
{
@StartRight @Select
   A { @ACell number }
   B { @ACell identifier }
   C { @Sequence
          A { @CCell "(" }
          B { @ACell expr }
          C { @CCell ")" }
     }
}
```

### `number`

```lout
@CentredDisplay @SyntaxDiag
   title { number }
{
@StartRight @Repeat @ACell digit
}
```

## A binary search tree

A small BST holding the values `{ 8, 3, 10, 1, 6, 14, 4, 7, 13 }` after
in-order insertion. Note how `@Tree` nests three deep at the leaves and
how `@Circle` is used for the leaves to distinguish them from internal
nodes.

```lout
@CentredDisplay @Diag treehsep { 0.6c } treevsep { 0.8c } {
@Tree {
   @Node { 8 }
   @Sub { @Tree {
      @Node { 3 }
      @Sub { @Circle //1c ||1c { 1 } }
      @Sub { @Tree {
         @Node { 6 }
         @Sub { @Circle //1c ||1c { 4 } }
         @Sub { @Circle //1c ||1c { 7 } }
      } }
   } }
   @Sub { @Tree {
      @Node { 10 }
      @Sub { @Node {} }
      @Sub { @Tree {
         @Node { 14 }
         @Sub { @Circle //1c ||1c { 13 } }
         @Sub { @Node {} }
      } }
   } }
}
}
```

## A grey-painted box of labelled subsystems

The `paint` option on `@Box` (and its variants) fills the node background.
Below, a parent `@Box paint { lightgrey }` contains four labelled child
nodes representing modules of a small interpreter. The whole thing is the
nodelabel'd group `core`.

```lout
@CentredDisplay @Diag {
@Box paint { lightgrey } margin { 0.4f }
   nodelabel { core } nodelabelpos { N }
{
   L:: @Box paint { white } { lexer }    ||0.5c
   P:: @Box paint { white } { parser }   ||0.5c
   E:: @Box paint { white } { evaluator } ||0.5c
   R:: @Box paint { white } { repl }
}
}
```

## Flowchart with multiple distinct arrow styles

A single `@Diag` containing five labelled nodes and five links, each link
drawn with a different `arrowstyle` to verify that arrowhead variants
coexist correctly in one diagram. The shapes (`@Diamond` for a decision,
`@CurveBox` for I/O, `@Box` for processing) follow standard ANSI/ISO
flowchart conventions.

```lout
@CentredDisplay @Diag {
Start::  @Ellipse                  { start }      ||1.5c
Read::   @CurveBox margin { 0.3f } { read n }
//1c
Test::   @Diamond                  { n > 0 ? }    ||1.5c
Ok::     @Box                      { accept }
//1c
Stop::   @Ellipse                  { halt }       ||1.5c
Err::    @Box paint { lightgrey }  { reject }
//
@Link from { Start } to { Read } arrow { yes } arrowstyle { solid }
@Link from { Read }  to { Test } arrow { yes } arrowstyle { open }
@Link from { Test }  to { Ok }   arrow { yes } arrowstyle { solidwithbar }
   alabel { yes } alabelpos { N }
@Link from { Test }  to { Err }  arrow { yes } arrowstyle { halfopen }
   alabel { no  } alabelpos { S }
@Link from { Ok }    to { Stop } arrow { yes } arrowstyle { curvedsolid }
@Link from { Err }   to { Stop } arrow { yes } arrowstyle { curvedopen }
}
```

## Composite: a class diagram with one syntax diagram inside

A single page can mix `@Diag` with embedded `@SyntaxDiag` figures. Here a
class-hierarchy `@Tree` describes the AST of the arithmetic grammar
above, and a small `@SyntaxDiag` appears alongside it as a legend
fragment for the `digit` terminal.

### AST hierarchy

```lout
@CentredDisplay @Diag treehsep { 0.5c } treevsep { 0.7c } {
@Tree {
   @Box { ASTNode }
   @Sub { @Tree {
      @Box { BinaryOp }
      @Sub { @Box { Add } }
      @Sub { @Box { Sub } }
      @Sub { @Box { Mul } }
      @Sub { @Box { Div } }
   } }
   @Sub { @Tree {
      @Box { Leaf }
      @Sub { @Box { NumberLit } }
      @Sub { @Box { Ident } }
   } }
   @Sub { @Box { Paren } }
}
}
```

### `digit` (terminal legend)

```lout
@CentredDisplay @SyntaxDiag
   title { digit }
{
@StartRight @Select
   A { @CCell "0" }
   B { @CCell "1" }
   C { @CCell "2" }
   D { @CCell "3" }
   E { @CCell "4" }
   F { @CCell "5" }
   G { @CCell "6" }
   H { @CCell "7" }
   I { @CCell "8" }
   J { @CCell "9" }
}
```

## End

Everything above is raw Lout passthrough; the markdown surrounding it is
ordinary prose. If the build succeeded, the rendered HTML/PDF will show
ten distinct figures.
