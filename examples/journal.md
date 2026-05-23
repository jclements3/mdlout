---
type: report
title: On the Convergence of Stochastic Gradient Descent under Heavy-Tailed Noise
author: J. L. Clements and R. K. Aoyama
institution: mdlout project, Sydney; Department of Statistics, Kanazawa University
date: 2026-05-23
cover: No
contents: Yes
page: Letter
columns: 1
section-numbers: Arabic
para-indent: 1f
para-gap: 0.5v
language: English
font: Times Base 11p
abstract: |
  We revisit the convergence theory of stochastic gradient descent (SGD)
  in the regime where the gradient noise has only finite $p$-th moment
  for some $p \in (1, 2)$.  In this heavy-tailed regime the classical
  $O(1/\sqrt{n})$ rate for convex objectives no longer holds, and the
  step-size schedule that achieves the best attainable rate departs
  from the Robbins-Monro recipe of $\eta_k = \Theta(1/k)$.  We prove
  two main results: a tight upper bound of $O(n^{-(p-1)/p})$ on the
  optimisation gap of clipped SGD with a polynomial step-size schedule,
  and a matching lower bound under a fairly mild adversarial-noise
  oracle.  Numerical experiments on a synthetic generalised-linear
  model with Student-$t$ gradient noise confirm the rates to within
  small constants and illustrate the catastrophic failure mode of
  vanilla SGD without gradient clipping.  We close with practical
  recommendations for adaptive-clipping schemes and a discussion of the
  implications for high-dimensional optimisation on noisy hardware.
---

[TOC]

# Introduction

Stochastic gradient descent is the unrivalled workhorse of modern
large-scale optimisation, underpinning everything from logistic
regression on tabular data to the pre-training of trillion-parameter
language models.  Its convergence theory under *light-tailed* noise ---
that is, when the stochastic gradient has a finite variance and the
oracle returns samples with sub-Gaussian or at least sub-exponential
concentration --- is now classical and rests on a small handful of
inequalities tracing back to Robbins and Monro [@robbins1951],
Polyak [@polyak1990], and Nemirovsky and Yudin [@nemirovsky1983].
For a convex Lipschitz objective on a bounded domain, the iterates
of vanilla SGD with step size $\eta_k = \Theta(1/\sqrt{k})$ achieve an
optimisation gap of $O(1/\sqrt{n})$ after $n$ iterations, and this rate
is known to be unimprovable in the worst case [@agarwal2012].

The picture changes dramatically when the gradient noise has only a
finite $p$-th moment for some $p \in (1, 2)$ --- a regime that is far
from theoretical: gradient distributions in deep-learning workloads
have been documented as heavy-tailed [@simsekli2019; @gurbuzbalaban2021],
and the recent rise of low-precision and stochastic-rounding hardware
introduces noise that is bounded but skewed and only weakly
concentrated.  In this *heavy-tailed* regime several previously
innocuous algorithmic choices become load-bearing.  Step-size schedules
designed for the light-tailed regime can drive the iterates arbitrarily
far from the optimum after a single bad sample; gradient clipping,
which is a *practical* fix that virtually every deep-learning
practitioner already deploys, turns out to be a *theoretical* necessity
as well.[^clipping-history]

[^clipping-history]: Gradient clipping was introduced as a heuristic to
combat the exploding-gradient problem in recurrent network training
[@pascanu2013] long before its role in heavy-tailed convergence was
understood.  Its theoretical justification under heavy-tailed noise was
clarified by Zhang et al. [@zhang2020] and Gorbunov et al.
[@gorbunov2020], whose analyses we extend in this paper.

The questions we take up here are: *what is the optimal achievable rate
for SGD under finite-$p$-th-moment gradient noise, and what step-size
and clipping schedule attain it?*  Our two main results, stated
informally:

1. **Upper bound (Theorem @thm:upper).**  Clipped SGD with a polynomial
   step-size schedule $\eta_k = \eta_0 k^{-1/p}$ and clipping threshold
   $\tau_k = \tau_0 k^{1/p}$ achieves an optimisation gap of
   $O(n^{-(p-1)/p})$ on convex Lipschitz objectives with $p$-th-moment
   noise.
2. **Lower bound (Theorem @thm:lower).**  No first-order stochastic
   algorithm, clipped or not, can improve on $\Omega(n^{-(p-1)/p})$ over
   the class of heavy-tailed instances we consider.

Together the two results pin the minimax rate at $\Theta(n^{-(p-1)/p})$
and identify clipped SGD with a polynomial schedule as a minimax-optimal
algorithm.  At $p = 2$ we recover the familiar $O(1/\sqrt{n})$ rate; at
$p = 1.5$ the rate is $O(n^{-1/3})$, substantially slower; and as $p
\downarrow 1$ the rate degenerates to a logarithm of $n$, which is the
best one can hope for under barely-finite mean noise.

The remainder of the paper is organised as follows.  Section 2
reviews the relevant background on heavy-tailed concentration and
fixes notation.  Section 3 develops our method --- the clipped SGD
algorithm and its associated step-size schedule.  Section 4 proves
the upper and lower bounds and reports numerical experiments on a
synthetic generalised-linear model.  Section 5 discusses implications
for practice, with a focus on adaptive clipping.  Section 6 concludes.
Section 7 collects references and definitions.

# Background

## Heavy-tailed concentration

Let $X$ be a real-valued random variable with $\mathbb{E}|X|^p <
\infty$ for some $p \in (1, 2]$, and let $X_1, \ldots, X_n$ be
independent copies of $X$.  The classical central-limit theorem
guarantees that $n^{-1/2} \sum_k (X_k - \mathbb{E} X) \to \mathcal{N}(0,
\sigma^2)$ in distribution when $p = 2$, but no such universal limit
exists for $p < 2$: the appropriate limit is an $\alpha$-stable law
with index $\alpha = p$, and the rate of convergence is governed by
the tail behaviour of $X$.[^stable-laws]

[^stable-laws]: An $\alpha$-stable distribution has characteristic
function $\phi(t) = \exp(-|ct|^\alpha)$ for some scale $c > 0$ and
satisfies $\mathbb{E} |Y|^q < \infty$ iff $q < \alpha$.  When $\alpha
= 2$ it is the Gaussian; when $\alpha = 1$ it is the Cauchy.  See
Nolan [@nolan2020] for a modern treatment.

For finite-sample bounds the relevant tool is the *truncated moment
inequality*: for any threshold $\tau > 0$ and any $p \in (1, 2]$,

$$
\Pr\!\left[\,|S_n - \mu| \ge t\,\right] \;\le\; \frac{C\,\mathbb{E}|X|^p}{n^{p-1}\,t^p},
$$

where $S_n = n^{-1}\sum_k X_k$, $\mu = \mathbb{E} X$, and $C$ is a
universal constant.  This is
the heavy-tailed analogue of Hoeffding's inequality, and it is the
inequality we will deploy repeatedly in the proof of Theorem
@thm:upper.

## Stochastic optimisation under heavy-tailed noise

The earliest treatments of heavy-tailed stochastic optimisation are
due to Nemirovsky and Yudin [@nemirovsky1983] in the offline-oracle
setting and to Polyak and Tsypkin [@polyak1973] in the online
setting; both works essentially assume finite variance and adapt the
classical proofs.  The recent literature on truly heavy-tailed noise
begins with Zhang, Karimireddy, et al. [@zhang2020], who proved an
$O(n^{-(p-1)/(3p-2)})$ rate for clipped SGD on smooth strongly convex
objectives; this rate is suboptimal but holds without an exact moment
constant.  Gorbunov et al. [@gorbunov2020] improved this for general
convex objectives to $O(n^{-(p-1)/(2p-1)})$, and Cutkosky and
Mehta [@cutkosky2021] obtained the rate $O(n^{-(p-1)/p})$ that we
match in this paper, via a different (and more delicate) analysis
based on the implicit gradient method.  Our contribution is a direct
analysis of explicit clipped SGD with a polynomial step-size schedule,
which is the algorithm that practitioners actually run.

# Method

## Notation and assumptions

Let $f : \mathbb{R}^d \to \mathbb{R}$ be a convex objective and let
$x^* \in \arg\min f$ be a minimiser.  We assume $f$ is $G$-Lipschitz on
a convex bounded domain $\mathcal{X}$ of diameter $D$, and that we have
access to a *stochastic first-order oracle* $\mathcal{O}$ which, when
queried at a point $x \in \mathcal{X}$, returns a random vector
$g \in \mathbb{R}^d$ satisfying

$$
\mathbb{E}[g \mid x] = \nabla f(x), \quad
\mathbb{E}[\|g - \nabla f(x)\|^p \mid x] \le \sigma^p,
$$

for some $p \in (1, 2]$ and some $\sigma > 0$.  No higher-order
moments are assumed.  When $p = 2$ this is the standard bounded-variance
assumption; when $p < 2$ we are in the heavy-tailed regime.

## Clipped SGD with polynomial schedule

The algorithm we analyse is the following clipped-SGD scheme.  Fix
$x_0 \in \mathcal{X}$, step-size sequence $\eta_k > 0$, and clipping
threshold sequence $\tau_k > 0$.  For $k = 0, 1, 2, \ldots$:

1. Query the oracle at $x_k$ to obtain $g_k$.
2. Form the clipped gradient $\tilde{g}_k = \mathrm{clip}_{\tau_k}(g_k)$,
   where $\mathrm{clip}_\tau(v) = v \cdot \min\{1, \tau / \|v\|\}$.
3. Update $x_{k+1} = \Pi_\mathcal{X}(x_k - \eta_k \tilde{g}_k)$, where
   $\Pi_\mathcal{X}$ is the Euclidean projection onto $\mathcal{X}$.

The output is the *uniformly averaged iterate*
$\bar{x}_n = n^{-1} \sum_{k=0}^{n-1} x_k$.

The schedules that achieve the optimal rate are
$\eta_k = \eta_0 \cdot (k+1)^{-1/p}$ and $\tau_k = \tau_0 \cdot (k+1)^{1/p}$,
with the constants $\eta_0$ and $\tau_0$ to be chosen as functions of
$D$, $G$, $\sigma$, and $p$ alone.  Both schedules deviate from the
Robbins-Monro recipe of $\eta_k = \Theta(1/k)$ that is optimal under
light-tailed noise --- as we will see in the proof, the polynomial
schedule is precisely what is needed to balance the bias introduced by
clipping against the variance of the unclipped tail.

# Results

## Upper bound

Our first main result is the following.

```lout
@LP
@CD @B Theorem 1 (Upper bound).
@LP
{ @I Let } @F { f : R sup d -> R } @I { be convex, } @F { G } @I { -Lipschitz
on a convex bounded domain } @F { X } @I { of diameter } @F { D } @I { , and
suppose the stochastic first-order oracle satisfies } @F { E [ "||" g - grad f
(x) "||" sup q "|" x ] "<=" sigma sup q } @I { for some } @F { q element (1,
2] } @I { .  Then clipped SGD with } @F { eta sub k = eta sub 0 (k+1) sup {
"-1/q" } } @I { and } @F { tau sub k = tau sub 0 (k+1) sup { "1/q" } } @I {
satisfies }
@LP
@CD @F { E [ f ("bar x" sub n) - f (x sup *) ] "<=" C "*" n sup { "-(q-1)/q" } }
@LP
@I { where } @F { C = C ( D, G, sigma, q ) } @I { is a constant depending
only on the listed parameters, with } @F { eta sub 0 } @I { and } @F { tau
sub 0 } @I { chosen as polynomial functions of those parameters. }
```
[#thm:upper]

*Proof sketch.*  Let $r_k$ denote $x_k - x^*$.  Expanding the
recursion $x_{k+1} = \Pi(x_k - \eta_k \tilde{g}_k)$ and using
non-expansiveness of the projection $\Pi$, the standard descent
inequality bounds $\|r_{k+1}\|^2$ above by $\|r_k\|^2$ minus
$2 \eta_k \langle \tilde{g}_k, r_k \rangle$ plus the noise term
$\eta_k^2 \|\tilde{g}_k\|^2$, for every $k \ge 0$.

Taking conditional expectations, the cross term decomposes into an
exact-gradient piece and a *clipping bias* piece.  The exact-gradient
piece equals $\langle \nabla f(x_k), r_k \rangle$, which the convexity
of $f$ bounds below by $f(x_k) - f(x^*)$.  The clipping bias is
controlled by the truncated moment inequality of Section 2.1 and is
$O(\sigma^p / \tau_k^{p-1})$.  The final noise term
$\eta_k^2 \mathbb{E}\|\tilde{g}_k\|^2$ is bounded by
$\eta_k^2 (G^2 + \tau_k^2)$ via a separate truncation argument.

Summing from $k = 0$ to $n - 1$, dividing by $\sum \eta_k$, and
applying Jensen's inequality to the averaged iterate $\bar{x}_n$, the
telescoping leaves three error terms whose orders in $n$ are
$D^2 / \sum \eta_k$, $\sigma^p \sum \eta_k / \tau_k^{p-1}$, and
$\sum \eta_k^2 (G^2 + \tau_k^2)$.  Plugging in $\eta_k \propto k^{-1/p}$
and $\tau_k \propto k^{1/p}$, each of the three sums evaluates to
$\Theta(n^{(p-1)/p})$, and dividing by the harmonic-like sum of
step sizes (which is $\Theta(n^{(p-1)/p})$ as well) yields the
claimed rate.  The full computation, including the choice of the
constants $\eta_0$ and $\tau_0$ that balance the three terms, is in
Appendix A of the technical report [@clements2026].  $\square$

A few remarks on the proof.  First, the rate $n^{-(p-1)/p}$ is
attained simultaneously by all three error sources; this is no
coincidence but the consequence of the deliberate balancing of
$\eta_k$ and $\tau_k$.  Second, the schedule is *non-adaptive*: it
depends on $p$ only through the exponents.  An adaptive variant that
estimates $p$ on the fly is sketched in Section 5.

## Lower bound

The matching lower bound is the following.

```lout
@LP
@CD @B Theorem 2 (Lower bound).
@LP
{ @I For every } @F { q element (1, 2] } @I { and every } @F { n ">=" 1 }
@I { , there exists a convex Lipschitz function } @F { f } @I { on a bounded
domain and a heavy-tailed stochastic first-order oracle satisfying the
} @F { q } @I { -th-moment assumption of Section 3, such that any first-order
stochastic algorithm, clipped or otherwise, has an expected optimisation gap
of at least }
@LP
@CD @F { c ( q ) "*" n sup { "-(q-1)/q" } }
@LP
@I { after } @F { n } @I { oracle queries, where } @F { c ( q ) > 0 } @I {
is a universal constant depending only on } @F { q } @I { . }
```
[#thm:lower]

*Proof sketch.*  We use a hard one-dimensional instance: $f(x) =
|x|$ on $[-D, D]$, $x^* = 0$.  The oracle returns $g = \text{sign}(x)
+ \xi$, where $\xi$ is sampled from a Pareto distribution with
parameter $p$ (so that $\mathbb{E}|\xi|^q < \infty$ iff $q < p$).  The
sign of the gradient is occasionally flipped by a heavy-tailed shock
in $\xi$; any algorithm that follows the (noisy) gradient will
overshoot.  A Le Cam two-point reduction --- testing $f(x) = |x|$
against $f(x) = |x - \epsilon|$ --- then gives a lower bound that
matches the upper bound up to the constant $c(p)$.  Details are in
Appendix B of [@clements2026].  $\square$

Together, Theorems @thm:upper and @thm:lower pin the minimax rate at
$\Theta(n^{-(p-1)/p})$.  Note that the lower bound holds even for
algorithms that *know* the value of $p$; an adaptive algorithm that
estimates $p$ from the oracle history can therefore lose at most a
constant factor.

## A figure and a table

The empirical convergence rates of clipped SGD on a synthetic
generalised-linear model with Student-$t$ gradient noise are summarised
in Table @tab:rates and illustrated in Figure @fig:convergence.  The
problem is logistic regression on $d = 50$ Gaussian features with
$n = 10^4$ training samples, and the oracle's noise was added by
contaminating each mini-batch gradient with a Student-$t$ random
variable of degrees of freedom $\nu = 1 + 1/(p - 1)$, calibrated so
that the resulting noise has finite $p$-th moment and infinite higher
moments.

| $p$   | Theory rate         | Empirical slope | Const. $C$ |
|:-----:|:--------------------|:---------------:|:----------:|
| 1.25  | $n^{-0.20}$         | $-0.21$         | 2.84       |
| 1.50  | $n^{-0.33}$         | $-0.32$         | 1.97       |
| 1.75  | $n^{-0.43}$         | $-0.42$         | 1.51       |
| 2.00  | $n^{-0.50}$         | $-0.49$         | 1.18       |
[#tab:rates]

The empirical slopes match the theoretical exponents to within
two percent across the four values of $p$, well within the noise of a
single training run averaged over 32 seeds.  The constant $C$ shrinks
monotonically with $p$, consistent with the prediction of Theorem
@thm:upper that $C(D, G, \sigma, p) \to G \cdot D$ as $p \uparrow 2$.

![Log-log plot of the optimisation gap $f(\bar{x}_n) - f(x^*)$ against
iteration count $n$ for clipped SGD with the polynomial schedule of
Theorem @thm:upper, on the synthetic logistic-regression problem with
Student-$t$ gradient noise.  Each curve is averaged over 32 seeds;
shaded bands show one-sigma intervals.  Slopes match Table
@tab:rates to two percent across the four values of $p$.](trapezoid_convergence.svg){#fig:convergence}

## A diagnostic experiment

To verify that the polynomial schedule of Theorem @thm:upper is not
merely *sufficient* but actually *necessary* under heavy-tailed noise,
we re-ran the $p = 1.5$ experiment with three competing schedules:

1. **Vanilla SGD with $\eta_k = 1/\sqrt{k}$, no clipping.**  The
   iterates diverged: after $n = 10^4$ iterations the empirical
   optimisation gap was $1.4 \times 10^2$, four orders of magnitude
   worse than the clipped baseline.
2. **Robbins-Monro schedule $\eta_k = 1/k$, with clipping.**  The
   iterates converged but at a rate of approximately $n^{-0.17}$,
   noticeably slower than the theoretical $n^{-0.33}$.
3. **Polynomial schedule of Theorem @thm:upper.**  Recovered the
   theoretical rate to within two percent, as reported in Table
   @tab:rates.

The first experiment confirms that *clipping is necessary*; the
second confirms that the *polynomial schedule* is also necessary,
not merely a convenient choice.  Together they validate the
algorithmic prescription of Theorem @thm:upper as the right object to
implement in practice.

# Discussion

The bounds derived in Section 4 sharpen three observations and
expose one less-discussed subtlety.

First, **gradient clipping is theoretically necessary, not just a
heuristic.**  Vanilla SGD without clipping has an unbounded expected
optimisation gap whenever the gradient noise has infinite variance,
because a single bad sample can push the iterate arbitrarily far from
the optimum.  This is not a matter of constants: the failure is
catastrophic and qualitative.  The clipping threshold $\tau_k$ acts
as a *trust region* on the per-step update, and its polynomial growth
ensures that the trust region eventually exceeds the noise scale.

Second, **the step-size schedule must be polynomial.**  The
Robbins-Monro recipe of $\eta_k = \Theta(1/k)$ that is optimal under
light-tailed noise is too aggressive under heavy-tailed noise: it
shrinks the step size faster than the clipping bias can be tolerated,
and the resulting rate is worse by a factor of $n^{(2-p)/p}$.

Third, **the minimax rate $n^{-(p-1)/p}$ is fully described by the
moment exponent $p$.**  Specifically, the dependence on the moment
constant $\sigma^p$ enters only through the constant $C(D, G, \sigma,
p)$ and not through the exponent.  This is the heavy-tailed analogue
of the light-tailed result that the variance enters the
$O(\sigma/\sqrt{n})$ rate only as a constant.

The subtler observation, mentioned in passing in Section 4.3, is that
**adaptive estimation of $p$ is possible but tricky.**  A natural
adaptive scheme is to estimate $\widehat{p}_k$ from the empirical
distribution of $\|g_k\|$ via a Hill estimator
[@hill1975].[^hill-caveats]  The challenge is that the Hill estimator
itself has a slow convergence rate of $O(k^{-1/2})$, which translates
into a polylogarithmic loss in the final rate.  Whether the
polylogarithmic loss is fundamental or an artefact of the Hill
estimator remains an open question.

[^hill-caveats]: The Hill estimator is biased when applied to noise
distributions whose tail is exactly a regularly-varying function of
finite order, and the bias can dominate the variance for moderate
sample sizes.  A bias-corrected variant due to Drees [@drees1998]
mitigates this but introduces an additional tuning parameter.

## Implications for software libraries

Three concrete recommendations for practitioners follow.

1. **Always clip the per-sample gradient, not the per-batch gradient.**
   The minimax rate of Theorem @thm:upper depends on clipping the
   *individual* stochastic gradient, not on clipping the mean of a
   mini-batch.  This is because the heavy-tailed tail of a single
   sample is what drives the failure mode, and averaging within a
   mini-batch does not change the tail exponent.
2. **Tune the clipping threshold polynomially in $k$, not as a fixed
   constant.**  Most deep-learning libraries implement clipping with
   a fixed threshold, which is theoretically suboptimal: a fixed
   threshold combined with a vanishing step size produces a
   sub-Robbins-Monro rate of $O(n^{-(p-1)/(p+1)})$ rather than the
   minimax-optimal $O(n^{-(p-1)/p})$.
3. **Track empirical effective sample size, not the loss alone.**  The
   loss trajectory of clipped SGD under heavy-tailed noise is
   characteristically jagged --- much more so than under light-tailed
   noise.  A robust convergence diagnostic should track a moving
   median or trimmed mean of the loss rather than the raw running
   average.

# Conclusion

We have characterised the minimax-optimal convergence rate of
stochastic gradient descent under finite-$p$-th-moment gradient noise
for $p \in (1, 2]$, and we have shown that clipped SGD with a
polynomial step-size and clipping schedule attains this rate.  The
results unify and tighten a sequence of recent advances
[@zhang2020; @gorbunov2020; @cutkosky2021] and provide explicit
constants suitable for practical implementation.  A natural follow-up
is the *strongly convex* and *non-convex* settings, where the
combination of curvature with heavy-tailed noise raises subtle
questions about the trade-off between bias and variance that we have
not addressed here.  We leave these to future work.

# References

[@robbins1951]: H. Robbins and S. Monro. A stochastic approximation
method. *Annals of Mathematical Statistics*, 22(3):400-407, 1951.

[@polyak1990]: B. T. Polyak. New stochastic approximation type
procedures. *Automation and Remote Control*, 51:937-946, 1990.

[@nemirovsky1983]: A. Nemirovsky and D. Yudin. *Problem Complexity and
Method Efficiency in Optimization.* Wiley, 1983.

[@polyak1973]: B. T. Polyak and Ya. Z. Tsypkin. Pseudogradient adaptation
and training algorithms. *Automation and Remote Control*, 34(3):377-397,
1973.

[@agarwal2012]: A. Agarwal, P. L. Bartlett, P. Ravikumar, and M. J.
Wainwright. Information-theoretic lower bounds on the oracle complexity
of stochastic convex optimization. *IEEE Transactions on Information
Theory*, 58(5):3235-3249, 2012.

[@simsekli2019]: U. Simsekli, L. Sagun, and M. Gurbuzbalaban. A tail-index
analysis of stochastic gradient noise in deep neural networks. In
*International Conference on Machine Learning*, 2019.

[@gurbuzbalaban2021]: M. Gurbuzbalaban, U. Simsekli, and L. Zhu. The
heavy-tail phenomenon in SGD. In *International Conference on Machine
Learning*, 2021.

[@pascanu2013]: R. Pascanu, T. Mikolov, and Y. Bengio. On the difficulty
of training recurrent neural networks. In *International Conference on
Machine Learning*, 2013.

[@zhang2020]: J. Zhang, S. P. Karimireddy, A. Veit, S. Kim, S. J. Reddi,
S. Kumar, and S. Sra. Why are adaptive methods good for attention models?
In *Advances in Neural Information Processing Systems*, 2020.

[@gorbunov2020]: E. Gorbunov, M. Danilova, and A. Gasnikov. Stochastic
optimization with heavy-tailed noise via accelerated gradient clipping. In
*Advances in Neural Information Processing Systems*, 2020.

[@cutkosky2021]: A. Cutkosky and H. Mehta. High-probability bounds for
non-convex stochastic optimization with heavy tails. In *Advances in
Neural Information Processing Systems*, 2021.

[@nolan2020]: J. P. Nolan. *Univariate Stable Distributions: Models for
Heavy Tailed Data.* Springer, 2020.

[@hill1975]: B. M. Hill. A simple general approach to inference about
the tail of a distribution. *Annals of Statistics*, 3(5):1163-1174,
1975.

[@drees1998]: H. Drees. A general class of estimators of the extreme
value index. *Journal of Statistical Planning and Inference*,
66(1):95-112, 1998.

[@clements2026]: J. L. Clements and R. K. Aoyama. Heavy-tailed
stochastic optimisation: technical appendices. Technical report,
mdlout project, Sydney, 2026.
