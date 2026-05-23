---
type: doc
title: Math proofs with sequence diagrams
author: J. L. Clements
font: Times Base 11p
page: A4
para-indent: 0f
para-gap: 1.0v
page-headers: None
---

# Math proofs illustrated by sequence diagrams

This document pairs short mathematical derivations with mermaid sequence
diagrams that narrate, step by step, what the proof is *doing*. The math
renders through KaTeX in HTML mode; the diagrams render through mermaid.js
in the same `foreignObject` channel. Both engines coexist in the same flow.

## 1. The sum of the first n integers

The classical Gauss anecdote: pair the first and last terms of the sum
$1 + 2 + \cdots + n$, then the second and second-last, and so on. Each pair
sums to $n+1$, and there are $n/2$ pairs.

$$
S = 1 + 2 + \cdots + n
\qquad
2S = (n+1) + (n+1) + \cdots + (n+1) = n(n+1)
\qquad
S = \frac{n(n+1)}{2}.
$$

The pairing as a sequence of moves, with a "scribe" actor that writes the
intermediate result and a "checker" that verifies it:

```mermaid
sequenceDiagram
    participant G as Gauss
    participant S as Scribe
    participant C as Checker
    G->>S: Write 1, 2, ..., n
    G->>S: Pair (1, n), (2, n-1), ...
    S->>C: Each pair sums to n+1
    C-->>S: Confirmed, n/2 pairs
    S-->>G: Total = n(n+1)/2
```

## 2. The infinite geometric series

For $|r| < 1$, the geometric series $\sum_{k=0}^{\infty} r^k$ converges to
$1/(1-r)$. The proof multiplies the partial sum $S_n$ by $r$, subtracts,
and takes the limit.

$$
\begin{aligned}
S_n      &= 1 + r + r^2 + \cdots + r^n \\
r S_n    &= \quad\; r + r^2 + \cdots + r^n + r^{n+1} \\
(1-r)S_n &= 1 - r^{n+1} \\
S_n      &= \frac{1 - r^{n+1}}{1 - r}
         \xrightarrow{n \to \infty}
         \frac{1}{1 - r}.
\end{aligned}
$$

As a dialogue between the "student" who proposes each manipulation and the
"book" that confirms what is allowed:

```mermaid
sequenceDiagram
    participant ST as Student
    participant BK as Book
    ST->>BK: Multiply S_n by r
    BK-->>ST: Allowed, terms shift by one
    ST->>BK: Subtract r S_n from S_n
    BK-->>ST: Telescopes to 1 - r^(n+1)
    ST->>BK: Divide by (1 - r)
    BK-->>ST: Valid since r != 1
    ST->>BK: Send n to infinity
    BK-->>ST: r^(n+1) goes to 0 for |r| < 1
```

## 3. The derivative of x squared from first principles

The limit definition of the derivative:

$$
f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}.
$$

For $f(x) = x^2$:

$$
\frac{(x+h)^2 - x^2}{h}
= \frac{x^2 + 2xh + h^2 - x^2}{h}
= \frac{2xh + h^2}{h}
= 2x + h
\xrightarrow{h \to 0}
2x.
$$

The same calculation as a back-and-forth between "calculus" and "algebra":

```mermaid
sequenceDiagram
    participant CA as Calculus
    participant AL as Algebra
    CA->>AL: Expand (x + h)^2
    AL-->>CA: x^2 + 2xh + h^2
    CA->>AL: Subtract x^2, divide by h
    AL-->>CA: 2x + h
    CA->>AL: Take limit as h to 0
    AL-->>CA: 2x
```

## 4. The Cauchy-Schwarz inequality

For real vectors $\mathbf{u}, \mathbf{v}$, the inequality
$|\langle \mathbf{u}, \mathbf{v} \rangle| \le \|\mathbf{u}\|\,\|\mathbf{v}\|$
follows from the non-negativity of the squared norm
$\|\mathbf{u} - t\mathbf{v}\|^2$ for all real $t$. The discriminant of the
resulting quadratic in $t$ must be non-positive.

$$
\|\mathbf{u} - t\mathbf{v}\|^2
= \|\mathbf{u}\|^2 - 2t\,\langle \mathbf{u}, \mathbf{v} \rangle + t^2 \|\mathbf{v}\|^2
\;\ge\; 0.
$$

Treating this as a quadratic in $t$ with non-positive discriminant:

$$
\bigl(2\,\langle \mathbf{u}, \mathbf{v} \rangle\bigr)^2
- 4\,\|\mathbf{u}\|^2 \|\mathbf{v}\|^2 \le 0
\;\Longrightarrow\;
\langle \mathbf{u}, \mathbf{v} \rangle^2 \le \|\mathbf{u}\|^2 \|\mathbf{v}\|^2.
$$

The proof as a passing-the-baton between three reviewers:

```mermaid
sequenceDiagram
    participant A as Analyst
    participant Q as Quadratic
    participant D as Discriminant
    A->>Q: Form ||u - tv||^2 in t
    Q-->>A: Coefficients in u, v, t
    A->>D: Quadratic is non-negative for all real t
    D-->>A: Discriminant <= 0
    A->>D: Read off the inequality
    D-->>A: <u, v>^2 <= ||u||^2 ||v||^2
```

## Section summary

Each of the four proofs exercises a single algebraic move
(pairing, telescoping, the limit definition, a non-negative quadratic) and
each is shadowed by a mermaid sequence diagram in which the move is voiced
by named actors. The HTML build engraves all four diagrams alongside the
KaTeX-rendered math; the PDF build keeps the math via `@Math`'s placeholder
and renders each mermaid block as `[Mermaid diagram omitted in non-SVG
back-end]`. For an archival PDF that includes the diagrams, pre-render each
fence with `mmdc -i diag.mmd -o diag.svg` and inline the result via
`![](diag.svg)`.
