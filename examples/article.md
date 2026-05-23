---
type: report
title: Spectral Gap Bounds for Random-Walk Metropolis Samplers on Log-Concave Targets
author: J. L. Clements, R. K. Aoyama, and M. Bertrand
institution: mdlout project, Sydney; Department of Statistics, Kanazawa University
date: 2026-05-23
cover: Yes
contents: Yes
page: A4
columns: 2
section-numbers: Arabic
para-indent: 1f
para-gap: 0.4v
language: English
font: Times Base 10p
abstract: |
  We derive sharpened upper and lower bounds on the spectral gap of the
  Random-Walk Metropolis (RWM) algorithm targeting a strongly log-concave
  density on $\mathbb{R}^d$.  Building on the conductance arguments of
  Lovasz and Simonovits and the canonical-path machinery of Diaconis and
  Stroock, we show that the optimal Gaussian proposal variance scales as
  $\sigma^2 = \Theta(d^{-1})$ and that the resulting gap is bounded below
  by $c\,L\,d^{-1}$ for a strong-convexity constant $L > 0$ and a universal
  constant $c \in (0, 1)$.  A complementary upper bound, obtained by
  exhibiting an explicit slow-mixing test function, shows the rate is
  tight up to a factor logarithmic in the condition number.  Numerical
  experiments on a battery of three benchmark targets --- the isotropic
  Gaussian, a moderately ill-conditioned anisotropic Gaussian, and a
  Bayesian logistic-regression posterior --- corroborate the theory and
  expose the role of preconditioning.  We close with implications for
  adaptive samplers, in which the proposal covariance is learned on the
  fly from the chain's empirical second moment.
---

[TOC]

# Introduction

Markov chain Monte Carlo (MCMC) is the workhorse of modern Bayesian
computation.  Given a target density $\pi$ on $\mathbb{R}^d$ known only up
to its normalising constant, MCMC algorithms construct a Markov chain
whose stationary distribution coincides with $\pi$ and whose ergodic
averages approximate posterior expectations.  Among such algorithms the
Random-Walk Metropolis (RWM) sampler of Metropolis et al. [@metropolis1953]
and its symmetric-proposal generalisation due to Hastings [@hastings1970]
remain the simplest and most widely deployed: their only tuning parameter
is the proposal step size, and they require nothing more than pointwise
evaluation of $\log \pi$.

The Achilles' heel of RWM is its $O(d)$ slowdown as the dimension of the
target grows --- a phenomenon first quantified by Roberts, Gelman, and
Gilks [@roberts1997] for product targets and subsequently extended to a
broader class of log-concave densities by Bedard [@bedard2007] and by
Beskos, Roberts, and Stuart [@beskos2009].  These optimal-scaling results
identify $\sigma^2 = O(d^{-1})$ as the right asymptotic regime for the
proposal variance and pin the optimal expected acceptance rate at the
celebrated value $0.234$.  What they leave open is a tight bound on the
spectral gap[^gap-defn] --- the quantity controlling the relaxation time
of the chain.

[^gap-defn]: The spectral gap of a reversible chain with transition kernel
$P$ and stationary distribution $\pi$ is $1 - \lambda_2$, where
$\lambda_2$ is the second-largest eigenvalue of $P$ acting on
$L^2(\pi)$.  Larger is better: a gap of $g$ implies relaxation in
$O(g^{-1})$ steps from any $L^2(\pi)$-bounded initial distribution.

In this paper we close the gap (no pun intended) by combining two
classical tools: the *conductance* framework of Lovasz and Simonovits
[@lovasz1993] --- the Markov-chain analogue of Cheeger's inequality ---
and the *canonical-paths* technique of Diaconis and Stroock
[@diaconis1991].  For a strongly log-concave target with strong-convexity
constant $L$, we prove (Theorem @thm:gap below) that the gap of RWM with
optimally-tuned step size is at least $c L / d$ for a universal constant
$c > 0$; the upper bound, established in section 3, matches this rate up
to logarithmic factors in the condition number of the target's Hessian.

The remainder of the paper is structured as follows.  Section 2 fixes
notation and states the assumptions.  Section 3 develops the lower and
upper spectral-gap bounds and gives a worked proof of the lower bound.
Section 4 reports numerical experiments on three benchmark targets,
including a figure summarising the autocorrelation decay (Figure
@fig:acf) and tables documenting the empirical effective sample size
(Tables @tab:targets and @tab:ess).  Section 5 discusses the implications
for adaptive samplers, and section 6 collects references.

# Method

Throughout the paper $\pi$ denotes a probability density on
$\mathbb{R}^d$ with respect to Lebesgue measure, normalised so that
$\int \pi(x)\, dx = 1$.  We write $U(x) = -\log \pi(x) + \text{const}$
for the associated potential and assume $U \in C^2(\mathbb{R}^d)$ with
Hessian satisfying

$$
L\,I_d \;\preceq\; \nabla^2 U(x) \;\preceq\; M\,I_d, \qquad \forall x \in \mathbb{R}^d,
$$

where $0 < L \le M < \infty$ are the strong-convexity and smoothness
constants and $I_d$ is the $d \times d$ identity.  The *condition number*
of the target is $\kappa = M / L$; small $\kappa$ means a well-rounded
target, large $\kappa$ a pencil-shaped one.

The Random-Walk Metropolis chain with isotropic Gaussian proposal is
defined by the transition kernel

$$
P(x, A) = \int_A \alpha(x, y)\, q_\sigma(x, y)\, dy
        + \delta_x(A)\, \left[1 - \int \alpha(x, y) q_\sigma(x, y)\, dy\right],
$$

where $q_\sigma(x, y) \propto \exp(-\|y - x\|^2 / 2\sigma^2)$ is the
proposal density and $\alpha(x, y) = \min\{1, \pi(y) / \pi(x)\}$ is the
Metropolis acceptance probability.  Reversibility with respect to $\pi$
is immediate from the symmetry of the proposal[^reversibility].

[^reversibility]: A symmetric proposal $q(x, y) = q(y, x)$ together with
the Metropolis acceptance probability $\alpha(x, y) = \min\{1,
\pi(y)/\pi(x)\}$ always yields a $\pi$-reversible chain.  This is one
of the principal practical advantages of RWM over alternatives such as
Hamiltonian Monte Carlo, which require a more delicate symplectic
integrator to preserve detailed balance.

## Conductance and the Cheeger inequality

Recall that the *conductance* of a $\pi$-reversible Markov chain $P$ is

$$
\Phi(P) = \inf_{0 < \pi(S) \le 1/2}\;
  \frac{\int_S P(x, S^c)\, \pi(dx)}{\pi(S)}.
$$

The discrete Cheeger inequality [@lawler1988] then bounds the spectral
gap by

$$
\frac{\Phi^2}{2} \;\le\; \text{gap}(P) \;\le\; 2\Phi.
$$

The strategy of section 3 is to lower-bound $\Phi$ directly, via an
isoperimetric inequality for log-concave measures, and then upper-bound
$\text{gap}(P)$ via an explicit slow-mixing test function.

## Canonical paths

The complementary canonical-paths machinery of Diaconis and Stroock
[@diaconis1991] expresses the gap in terms of the maximum congestion
along a system of paths connecting every pair of states.  For our
continuous-state RWM chain we discretise via the standard lattice
covering of the target's effective support and apply the canonical-paths
bound to the resulting random walk on a graph.  The full derivation,
which we will not reproduce here, follows the template laid out by
Vempala [@vempala2005] for hit-and-run.

## Test targets

We verify the theory on three target families summarised in Table
@tab:targets.  The isotropic Gaussian is the textbook well-conditioned
target ($\kappa = 1$); the anisotropic Gaussian probes the effect of
moderate ill-conditioning; the logistic-regression posterior is a
realistic non-Gaussian target with both curvature variation and a
high-dimensional parameter space.

| Target                       | $d$   | $\kappa$    | log-concave? |
|:-----------------------------|:------|:------------|:-------------|
| Isotropic Gaussian           | 32    | 1           | yes          |
| Anisotropic Gaussian         | 32    | $10^2$      | yes          |
| Bayesian logistic posterior  | 64    | $\approx 8$ | yes          |
[#tab:targets]

For each target we run RWM at the asymptotically optimal step size
$\sigma^2 = 2.38^2 / d$ recommended by Roberts et al. [@roberts1997] and
record the integrated autocorrelation time and the effective sample size
per second of wall clock.

# Results

## Spectral-gap lower bound

Our principal theoretical contribution is the following.

```lout
@LP
@Theorem { Let @F { pi } be a probability density on @F { R sup d } whose
  potential @F { U = - log pi } satisfies @F { L I "<=" grad sup 2 U "<="
  M I } pointwise, with @F { 0 < L "<=" M < infinity }.  Then the
  Random-Walk Metropolis chain with proposal variance @F {
  sigma sup 2 = c sub 1 / d } and proposal covariance equal to a scalar
  multiple of the identity satisfies
  @CentredDisplay @F { "gap" (P) ">=" c sub 2 L / d } where @F { c sub 1
  } and @F { c sub 2 } are universal constants depending only on the
  acceptance rate, not on @F { d }, @F { L }, or @F { M }. }
@LP
@Proof { By Cheeger's inequality it suffices to show
  @F { Phi (P) ">=" c sub 3 sqrt { L / d } } for some universal
  @F { c sub 3 > 0 }.  For any measurable @F { S } with
  @F { pi (S) "<=" "1/2" }, the numerator
  @F { integral sub S P (x, S sup c) pi (dx) } is bounded below by the
  probability that an @F { N (0, sigma sup 2 I) }-distributed proposal
  crosses the boundary of @F { S } and is then accepted.  Strong
  log-concavity ensures that the chord-length distribution from any
  interior point to the boundary of @F { S } is sub-exponential with
  rate @F { sqrt L }; standard Gaussian small-ball estimates then give
  the crossing probability as @F { Omega ( sigma sqrt L ) }.  Choosing
  @F { sigma = sqrt { c sub 1 / d } } yields @F { Phi ">=" c sub 3
  sqrt { L / d } }.  The lower bound on the gap then follows from
  @F { "gap" ">=" Phi sup 2 / 2 ">=" c sub 3 sup 2 L / 2 d ":=" c sub
  2 L / d }, as required. }
@LP
```
[#thm:gap]

The constants in the proof above are not optimal; tightening them
requires a more delicate use of the Bakry-Emery criterion and is left to
future work.

## Spectral-gap upper bound

For the upper bound we exhibit the explicit test function $f(x) =
x_1 - \mathbb{E}_\pi[X_1]$ (the first coordinate, centred) and compute the
Dirichlet form $\mathcal{E}(f, f)$.  A short calculation shows

$$
\mathcal{E}(f, f) \;\le\; \frac{C\,L}{d}\,\text{Var}_\pi(f),
$$

which by the variational characterisation of the spectral gap implies
$\text{gap}(P) \le C L / d$ up to a $\log \kappa$ factor.  Combined with
Theorem @thm:gap, this pins the gap at $\Theta(L / d)$ in the
well-conditioned case.

## Empirical effective sample size

Table @tab:ess reports effective-sample-size-per-iteration ($\text{ESS}/n$)
estimates from $n = 10^6$ post-burn-in samples on each of the three
benchmark targets, averaged over $32$ independent chains.

| Target              | $\sigma^2$  | Acceptance | $\text{ESS}/n$ | $\tau_{int}$ |
|:--------------------|:------------|:-----------|:---------------|:-------------|
| Isotropic Gaussian  | $2.38^2/d$  | 0.236      | $1.34 \times 10^{-2}$ | 37.3 |
| Anisotropic         | $2.38^2/d$  | 0.218      | $2.05 \times 10^{-3}$ | 244  |
| Logistic posterior  | $2.38^2/d$  | 0.231      | $5.81 \times 10^{-3}$ | 86.1 |
[#tab:ess]

The isotropic-Gaussian column matches the theoretical rate $\text{gap} =
\Theta(d^{-1})$ to within a factor of two; the anisotropic column shows
the $\kappa^{-1}$ penalty predicted by the upper bound; the logistic
posterior sits between the two, consistent with its modest effective
condition number.

![Empirical autocorrelation of the first coordinate for the three
benchmark targets at $n = 10^6$ samples each.  The isotropic target
relaxes within $\approx 40$ steps; the anisotropic target requires
$\approx 250$; the logistic posterior is intermediate.  Data drawn from
Table @tab:ess.](trapezoid_convergence.svg){#fig:acf}

The autocorrelation curves in Figure @fig:acf decay at rates consistent
with the spectral gaps derived in Theorem @thm:gap.  Empirically the
slope of the log-autocorrelation plot tracks $L / d$ to within a factor
of three across all three targets, suggesting that the universal
constant $c_2$ of Theorem @thm:gap is closer to $1/3$ than to $1/100$.

## A diagnostic: trace-plot stationarity

For each of the three chains we monitored the cumulative running mean
$\bar{X}_n^{(1)} = n^{-1} \sum_{i=1}^n X_i^{(1)}$ of the first
coordinate and the Gelman-Rubin potential-scale-reduction factor
$\widehat{R}$ across 32 independent replicates.  All chains achieved
$\widehat{R} < 1.01$ within the burn-in window of $5 \times 10^4$
iterations; the anisotropic target was the slowest to converge by this
diagnostic, requiring $\approx 3 \times 10^4$ iterations against the
isotropic target's $\approx 5 \times 10^3$ --- a factor-of-six gap that
again matches the $\kappa^{-1}$ penalty predicted by the upper bound.

## Robustness to the proposal-variance choice

To confirm that the asymptotically optimal scaling $\sigma^2 \propto
d^{-1}$ is not an artefact of our particular constant of
proportionality, we re-ran the isotropic Gaussian experiment with
$\sigma^2 = c \times 2.38^2 / d$ for $c \in \{0.25, 0.5, 1, 2, 4\}$.
The resulting $\text{ESS}/n$ varied by no more than a factor of two
across the five settings, with the maximum at $c = 1$, in agreement
with the prediction of Roberts et al. [@roberts1997].  This wide
plateau is one of the redeeming features of RWM in practice: the chain
is forgiving of a step-size misspecification of up to a factor of two
in either direction, which makes hand-tuning realistic in
moderate-dimensional applications.

# Discussion

The analysis above sharpens three folk theorems and exposes one less
familiar subtlety.

First, the celebrated $0.234$ optimal acceptance rate
[@roberts1997] is *not* an artefact of product targets: our Theorem
@thm:gap holds for any strongly log-concave target and recovers the same
asymptotic rate $\sigma^2 = \Theta(d^{-1})$ as the right scaling for the
proposal step size.  The universal constant $c_2$ does depend, weakly,
on the chosen acceptance rate, but the dependence is non-monotone and
shallow --- our Theorem holds for any acceptance rate bounded away from
$0$ and $1$.

Second, *preconditioning matters*.  The naive isotropic-proposal RWM
pays a factor $\kappa$ in mixing time for ill-conditioned targets; the
preconditioned variant in which the proposal covariance is set to the
inverse Hessian of $U$ at the mode (or, more practically, to a
running estimate of the chain's empirical covariance) recovers the
well-conditioned rate.  This is the principal practical justification
for adaptive samplers such as the Haario-Saksman-Tamminen adaptive
Metropolis [@haario2001] and the more recent Metropolis-adjusted Langevin
algorithm with preconditioning by the empirical Fisher information
[@girolami2011].

Third, the *gap-vs.-mixing-time gap* (the factor $\log(1/\epsilon)$ that
appears when converting a spectral-gap bound into a total-variation
mixing-time bound) is well controlled in our setting.  Strong
log-concavity of the target implies a logarithmic Sobolev inequality
with constant $L$, which in turn upgrades the spectral-gap bound to a
TV-mixing-time bound of $\widetilde{O}(d / L)$ steps for any target
accuracy $\epsilon \in (0, 1)$.

The subtler observation, mentioned only in passing in section 4, is that
the *anisotropy penalty* for RWM is sharper than for Hamiltonian Monte
Carlo or for Langevin-based samplers.  Where RWM pays a factor $\kappa$
in the mixing time, HMC with a suitably-tuned integrator pays only
$\sqrt{\kappa}$, and Langevin-based samplers pay a factor that depends
on the integrator's order.  Quantifying this trade-off in the spectral-gap
language remains open; we view it as the most interesting avenue for
follow-up work.

## Implications for software libraries

Three concrete recommendations follow for practitioners.

1. **Use an adaptive preconditioner.** The Haario-Saksman-Tamminen
   recipe [@haario2001] of replacing the isotropic proposal covariance
   with a running estimate of the empirical chain covariance recovers
   the $\kappa$ penalty essentially for free, at the cost of a modest
   bookkeeping burden.  All mainstream MCMC libraries (Stan, PyMC,
   Turing.jl, BUGS) already implement this in some form.
2. **Monitor the spectral gap, not the acceptance rate.** While the
   $0.234$ acceptance rate is a useful indicator of *near-optimal*
   tuning, it is a one-dimensional summary of a multi-dimensional
   object.  An adaptive sampler that targets a fixed acceptance rate
   can be fooled by anisotropic targets into accepting too eagerly in
   the well-conditioned directions and too rarely in the
   ill-conditioned ones.  The integrated autocorrelation time $\tau_{int}$
   is a more robust monitor.
3. **Prefer Hamiltonian or Langevin variants for $d \gtrsim 50$.**
   The $\sqrt{\kappa}$-vs.-$\kappa$ scaling advantage compounds in high
   dimensions; for $d \ge 50$ the cost of the gradient evaluations
   required by HMC or MALA is usually amortised within a single
   relaxation time.

# Conclusion

We have provided matching spectral-gap upper and lower bounds for the
Random-Walk Metropolis algorithm targeting a strongly log-concave
density on $\mathbb{R}^d$.  The bounds match in the well-conditioned
case ($\kappa = O(1)$) and disagree by at most a $\log \kappa$ factor in
the ill-conditioned case; empirical evidence on the three benchmark
targets (Table @tab:ess, Figure @fig:acf) corroborates the rates to
within small constants.  A natural follow-up would be a parallel
analysis of preconditioned variants of RWM, in which the proposal
covariance is learned adaptively from the chain's empirical
moments[^adaptive-pitfalls] --- a setting in which the spectral-gap
techniques applied here will require modification to handle the loss of
the Markov property.

[^adaptive-pitfalls]: Adaptive samplers lose the Markov property
because the proposal at step $n$ depends on the entire history
$X_0, \dots, X_{n-1}$.  Ergodicity is then restored via a diminishing-adaptation
condition.  The relevant theory is laid out in Roberts and Rosenthal's
review [@roberts2009].

# References

[@metropolis1953]: N. Metropolis, A. W. Rosenbluth, M. N. Rosenbluth,
A. H. Teller, and E. Teller. Equation of state calculations by fast
computing machines. *Journal of Chemical Physics*, 21(6):1087-1092,
1953.

[@hastings1970]: W. K. Hastings. Monte Carlo sampling methods using
Markov chains and their applications. *Biometrika*, 57(1):97-109,
1970.

[@roberts1997]: G. O. Roberts, A. Gelman, and W. R. Gilks. Weak
convergence and optimal scaling of random walk Metropolis algorithms.
*Annals of Applied Probability*, 7(1):110-120, 1997.

[@bedard2007]: M. Bedard. Weak convergence of Metropolis algorithms
for non-i.i.d. target distributions. *Annals of Applied Probability*,
17(4):1222-1244, 2007.

[@beskos2009]: A. Beskos, G. O. Roberts, and A. M. Stuart. Optimal
scalings for local Metropolis-Hastings chains on nonproduct targets in
high dimensions. *Annals of Applied Probability*, 19(3):863-898, 2009.

[@lovasz1993]: L. Lovasz and M. Simonovits. Random walks in a convex
body and an improved volume algorithm. *Random Structures and
Algorithms*, 4(4):359-412, 1993.

[@diaconis1991]: P. Diaconis and D. Stroock. Geometric bounds for
eigenvalues of Markov chains. *Annals of Applied Probability*,
1(1):36-61, 1991.

[@lawler1988]: G. F. Lawler and A. D. Sokal. Bounds on the L^2
spectrum for Markov chains and Markov processes. *Transactions of the
American Mathematical Society*, 309(2):557-580, 1988.

[@vempala2005]: S. Vempala. Geometric random walks: a survey. In
*Combinatorial and Computational Geometry*, MSRI Publications, 52:577-616,
2005.

[@haario2001]: H. Haario, E. Saksman, and J. Tamminen. An adaptive
Metropolis algorithm. *Bernoulli*, 7(2):223-242, 2001.

[@girolami2011]: M. Girolami and B. Calderhead. Riemann manifold
Langevin and Hamiltonian Monte Carlo methods. *Journal of the Royal
Statistical Society: Series B*, 73(2):123-214, 2011.

[@roberts2009]: G. O. Roberts and J. S. Rosenthal. Examples of
adaptive MCMC. *Journal of Computational and Graphical Statistics*,
18(2):349-367, 2009.
