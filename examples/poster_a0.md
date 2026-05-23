---
type: doc
title: "Sparse Mixture-of-Experts Routing for Long-Context Transformers"
author: "A. K. Nakamura, R. Patel, J. L. Clements, M. Okafor (mdlout group, Sydney)"
page: A0
orientation: portrait
columns: 3
column-gap: 1.5c
font: Helvetica Base 22p
top-margin: 3c
foot-margin: 3c
left-margin: 3c
right-margin: 3c
para-indent: 0f
para-gap: 1.4v
page-headers: None
---

```lout
@CentredDisplay @Font { 60p } @B {
Sparse MoE Routing
}
@CentredDisplay @Font { 60p } @B {
for Long Contexts
}
@CentredDisplay @Font { 26p } @I {
A. K. Nakamura, R. Patel, J. L. Clements, M. Okafor
}
@CentredDisplay @Font { 22p } {
mdlout group, School of Computer Science, University of Sydney
}
@DP
@CentredDisplay @Box margin { 0.5c } paint { lightgrey } {
@B { Abstract. }
We study top-@M{k} gating in mixture-of-experts (MoE) transformers
as the context window grows from 8K to 128K tokens.  At long
contexts the router becomes the bottleneck: load imbalance grows
super-linearly with sequence length and routing entropy collapses.
We propose @I { entropy-anchored routing }, a constant-overhead
modification that maintains expert utilisation within 8% of uniform
across all context lengths we tested, while improving perplexity by
0.34 nats on the PG-19 long-document benchmark.
}
@DP
```

## 1.  Introduction

Long-context language models stress every subsystem of a transformer,
but the routing layer in mixture-of-experts variants is the first to
break.  At a context of 128K tokens the per-token routing cost is
amortised across many more tokens than at 8K, yet the load distribution
across experts is observed to grow markedly more uneven.  The standard
top-@M{k} gate of Shazeer et al. [@shazeer2017] balances load via an
auxiliary loss that pulls gating logits toward uniform; at long context
this auxiliary loss is dominated by the cross-entropy term and
contributes negligibly to gradients.

The contribution of this poster is a single drop-in change to the gate
that re-introduces an explicit entropy floor.  We call this scheme
@I { entropy-anchored routing }.  The modification adds 0.4% to the
forward-pass FLOPs and no parameters.  We evaluate on three open MoE
checkpoints (Mixtral-8x7B, Switch-Base-128, and our own 1.3B-A0.3B
model) and on four long-context benchmarks.

## 2.  Method

Let $x_t \in \mathbb{R}^d$ be the token representation at position $t$
and let $W_r \in \mathbb{R}^{E \times d}$ be the router weight matrix
for $E$ experts.  The standard top-$k$ gate computes

$$
g_t \;=\; \mathrm{softmax}\!\bigl(W_r x_t\bigr), \qquad
y_t \;=\; \sum_{e \in \mathrm{TopK}(g_t)} \frac{g_{t,e}}{\sum_{e' \in \mathrm{TopK}(g_t)} g_{t,e'}} \; f_e(x_t).
$$

Our modification replaces the softmax with a tempered softmax whose
temperature $\tau_t$ is chosen, per token, to enforce a target entropy
$H^\star$:

$$
g_t \;=\; \mathrm{softmax}\!\bigl(W_r x_t / \tau_t\bigr), \qquad
\tau_t \;=\; \arg\min_{\tau > 0} \bigl( H(g_t(\tau)) - H^\star \bigr)^2.
$$

The one-dimensional minimisation is solved to within 0.01 nats in three
Newton steps -- the entropy is monotone in $\tau$, so convergence is
immediate.  Figure @fig:flow sketches the routing pipeline.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 200" width="520" height="200">
<rect width="520" height="200" fill="white"/>
<g font-family="Helvetica" font-size="13" text-anchor="middle">
<rect x="10" y="70" width="80" height="60" fill="#e6f0ff" stroke="black"/>
<text x="50" y="95">token</text><text x="50" y="115">x_t</text>
<rect x="120" y="70" width="100" height="60" fill="#fff2cc" stroke="black"/>
<text x="170" y="95">router</text><text x="170" y="115">W_r x_t</text>
<rect x="250" y="70" width="120" height="60" fill="#d5e8d4" stroke="black"/>
<text x="310" y="93">tempered</text><text x="310" y="110">softmax</text>
<rect x="400" y="20" width="100" height="50" fill="#f8cecc" stroke="black"/>
<text x="450" y="48">expert 1</text>
<rect x="400" y="80" width="100" height="50" fill="#f8cecc" stroke="black"/>
<text x="450" y="108">expert 2</text>
<rect x="400" y="140" width="100" height="50" fill="#f8cecc" stroke="black"/>
<text x="450" y="168">expert k</text>
<line x1="90" y1="100" x2="120" y2="100" stroke="black"/>
<line x1="220" y1="100" x2="250" y2="100" stroke="black"/>
<line x1="370" y1="100" x2="400" y2="45" stroke="black"/>
<line x1="370" y1="100" x2="400" y2="105" stroke="black"/>
<line x1="370" y1="100" x2="400" y2="165" stroke="black"/>
</g></svg>
```

*Figure 1.  Routing pipeline with the entropy-anchored gate.  The
tempered softmax block is the only departure from a vanilla top-$k$
gate; downstream experts are untouched.*

## 3.  Results

We compare three gating schemes -- vanilla top-2, top-2 with load loss
[@fedus2022], and entropy-anchored -- on four context lengths.  Across
all four lengths the entropy-anchored gate maintains expert utilisation
within 8% of uniform; the load-loss baseline drifts to 31% imbalance at
128K.  Perplexity on PG-19 improves by 0.34 nats over the load-loss
baseline at 128K and by 0.07 nats at 8K, suggesting the benefit grows
with context.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 240" width="360" height="240">
<rect width="360" height="240" fill="white"/>
<g font-family="Helvetica" font-size="11">
<line x1="50" y1="210" x2="340" y2="210" stroke="black"/>
<line x1="50" y1="20" x2="50" y2="210" stroke="black"/>
<text x="195" y="232" text-anchor="middle">context (tokens)</text>
<g text-anchor="middle">
<text x="80" y="225">8K</text><text x="150" y="225">16K</text>
<text x="220" y="225">32K</text><text x="290" y="225">64K</text>
<text x="340" y="225">128K</text>
</g>
<g text-anchor="end">
<text x="46" y="213">0</text><text x="46" y="166">10</text>
<text x="46" y="119">20</text><text x="46" y="72">30</text>
<text x="46" y="25">40</text>
</g>
<polyline points="80,205 150,193 220,170 290,135 340,95" fill="none" stroke="#c00" stroke-width="2"/>
<polyline points="80,202 150,194 220,178 290,153 340,121" fill="none" stroke="#06c" stroke-width="2"/>
<polyline points="80,200 150,198 220,194 290,189 340,184" fill="none" stroke="#093" stroke-width="2"/>
<g font-size="10">
<line x1="220" y1="40" x2="240" y2="40" stroke="#c00" stroke-width="2"/>
<text x="245" y="44">vanilla top-2</text>
<line x1="220" y1="55" x2="240" y2="55" stroke="#06c" stroke-width="2"/>
<text x="245" y="59">load loss</text>
<line x1="220" y1="70" x2="240" y2="70" stroke="#093" stroke-width="2"/>
<text x="245" y="74">entropy-anchored</text>
</g></g></svg>
```

*Figure 2.  Expert utilisation imbalance as context grows.  Vanilla
top-2 degrades fastest; the load-loss term [@fedus2022] only delays
the problem.  Entropy anchoring is essentially flat.*

|  context  | vanilla | load-loss | anchored |
|---------:|:-------:|:---------:|:--------:|
|       8K |   4.2%  |    3.8%   |   3.7%   |
|      16K |   7.1%  |    5.9%   |   4.1%   |
|      32K |  13.0%  |    9.4%   |   5.3%   |
|      64K |  22.0%  |   16.3%   |   6.8%   |
|     128K |  35.0%  |   31.0%   |   7.9%   |

## 4.  Discussion

The result that surprised us most was the @I { robustness } of the
anchored scheme to choice of $H^\star$: any target between 0.6 and 0.9
times $\log E$ gave indistinguishable downstream perplexity, even
though the realised temperatures differed by an order of magnitude.
This argues that the auxiliary loss in [@shazeer2017] is solving the
right problem -- enforce entropy -- but with the wrong tool, a soft
penalty whose strength dissolves at long context.

Two threats to validity.  First, our 1.3B model is small enough that
gate behaviour may not generalise to the 70B+ scale; we plan a replication
at 30B.  Second, our long-context evaluations rely on PG-19, which is
literary text; routing on code or scientific prose may differ.

## 5.  Conclusion

Entropy-anchored routing is a one-line change to the top-$k$ gate that
restores the load-balancing property load-loss methods lose at long
context.  The overhead is negligible (0.4% forward FLOPs, zero
parameters) and the perplexity gain grows with context length.  Source
and pretrained gates are available at the mdlout group GitHub.

## References

[@shazeer2017]: N. Shazeer et al. Outrageously large neural networks: the sparsely-gated mixture-of-experts layer. *ICLR*, 2017.

[@fedus2022]: W. Fedus, B. Zoph, N. Shazeer. Switch transformer: scaling to trillion parameter models. *JMLR*, 23(120):1-39, 2022.

[@zoph2022]: B. Zoph et al. ST-MoE: designing stable and transferable sparse expert models. *arXiv:2202.08906*, 2022.

[@beltagy2020]: I. Beltagy, M. E. Peters, A. Cohan. Longformer: the long-document transformer. *arXiv:2004.05150*, 2020.
