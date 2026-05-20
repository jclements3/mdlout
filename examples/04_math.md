---
title: Math block sampler
author: mdlout regression suite
---

# Math block sampler

This file exercises both block-level math (`$$...$$` and fenced ```math` blocks)
and inline math (`$...$`). Real LaTeX math in every block.

An inline atom: the golden ratio $\varphi = (1 + \sqrt{5}) / 2$ sits in running
text. The fine-structure constant is approximately $\alpha \approx 1/137$.

A definite integral:

$$
\int_{-\infty}^{\infty} e^{-x^2} \, dx = \sqrt{\pi}
$$

A sum, in a fenced math block:

```math
\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}
```

A simple fraction and a binomial coefficient on one line:

$$
\frac{a}{b} + \frac{c}{d} = \frac{ad + bc}{bd}
\qquad
\binom{n}{k} = \frac{n!}{k!\,(n-k)!}
$$

A two-by-two matrix and its determinant:

$$
\det\begin{pmatrix} a & b \\ c & d \end{pmatrix} = ad - bc
$$

An aligned derivation:

$$
\begin{aligned}
(a + b)^2 &= a^2 + 2ab + b^2 \\
(a - b)^2 &= a^2 - 2ab + b^2 \\
(a + b)(a - b) &= a^2 - b^2
\end{aligned}
$$

The Pythagorean identity: $a^2 + b^2 = c^2$.
