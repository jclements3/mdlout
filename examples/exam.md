---
type: doc
font: Times Base 11p
page: Letter
top-margin: 2.2c
foot-margin: 2.2c
left-margin: 2.5c
right-margin: 2.5c
para-gap: 0.9v
para-indent: 0f
page-headers: None
---

```lout
@CentredDisplay @B { Calculus I "--" Midterm Examination }
@CentredDisplay { Spring 2026  "  --  "  90 minutes  "  --  "  100 points }
@LP
```

**Name:** _(write name here)_  **Student ID:** _(write ID here)_

**Instructions.** Answer all five questions in the space provided. Show
your work; partial credit is awarded for correct method even when the
final number is wrong. Calculators are *not* permitted. A blank Answer
Key appears at the end of the booklet for grader use only -- students
should not write in that section.

---

## Question 1.  Limits  (15 points)

Evaluate the limit of (x squared minus four) divided by (x minus two)
as x approaches two. Show each algebraic step, especially the factoring
that removes the indeterminate form.

```lout
@LP
//3.5c
@LP
```

## Question 2.  Differentiation  (20 points)

Let f(x) equal x cubed times sine of x. Compute the derivative f-prime
of x using the product rule, then evaluate f-prime at pi.

```lout
@LP
//4.0c
@LP
```

## Question 3.  Chain rule  (20 points)

Differentiate g(x) equal to the square root of (one plus cosine of two-x)
with respect to x. Simplify your answer until no double-angle identities
remain.

```lout
@LP
//4.0c
@LP
```

## Question 4.  Definite integration  (20 points)

Evaluate the definite integral, from zero to pi-over-two, of sine of x
times cosine of x with respect to x. A u-substitution will make this
routine -- identify it explicitly before integrating.

```lout
@LP
//4.5c
@LP
```

## Question 5.  Application  (25 points)

A spherical balloon is being inflated so that its radius increases at a
constant rate of 2 cm/s. At the instant the radius reaches 10 cm, how
fast is the volume increasing? Recall that the volume of a sphere is
four-thirds pi r-cubed.

```lout
@LP
//5.0c
@LP
```

---

# Answer Key

*This page is for grader use only. Students should not write here.*

**Q1.** Factor the numerator as (x - 2)(x + 2). The factor of (x - 2)
cancels, leaving the limit of (x + 2) as x approaches 2, which is 4.

**Q2.** By the product rule, f-prime(x) equals
3 x-squared sine(x) plus x-cubed cosine(x). Evaluating at x = pi gives
f-prime(pi) = 3 pi-squared times 0 plus pi-cubed times (-1) = -pi-cubed.

**Q3.** Let u = 1 + cos(2x), so g = sqrt(u). Then
g-prime(x) = (1 / (2 sqrt(u))) times (-2 sin(2x))
           = -sin(2x) / sqrt(1 + cos(2x)).
Using 1 + cos(2x) = 2 cos-squared(x) and sin(2x) = 2 sin(x) cos(x), this
simplifies to g-prime(x) = -sqrt(2) sin(x) times sgn(cos(x)).

**Q4.** With u = sin(x), du = cos(x) dx, the integral becomes the
integral from 0 to 1 of u du, which is 1/2.

**Q5.** Differentiating V = (4/3) pi r-cubed gives
dV/dt = 4 pi r-squared dr/dt. With r = 10 cm and dr/dt = 2 cm/s,
dV/dt = 800 pi, approximately 2513.3 cubic centimetres per second.
