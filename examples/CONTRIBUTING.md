# Contributing a new example

This page is the checklist for adding a new file to
[`examples/`](.) -- pick a topic, write the Markdown, verify it builds
in both pipelines, regenerate the gallery, run the regression suite,
and open a PR. Read [`docs/best_practices.md`](../docs/best_practices.md)
and [`docs/cookbook.md`](../docs/cookbook.md) first; both already
contain the idioms most new examples should reuse rather than
reinvent.

## 1. Why add an example?

Every file under `examples/` serves three audiences at once:

- **The regression bank.** [`tests/browser_test.sh`](../tests/browser_test.sh)
  picks up new examples automatically and audits the rendered HTML for
  structural regressions. A breakage in the converter or the SVG
  back-end usually shows up in the example corpus before it shows up
  anywhere else.
- **The reference template.** Real users copy `examples/letter.md` or
  `examples/scientific_paper.md` as the starting point for their own
  documents. A new example is also a *signal* that the feature it
  exercises is supported -- if there is no example for "type: book + a
  drop cap", new contributors will (correctly) assume drop caps are
  not a solved problem.
- **The gallery showcase.** [`examples/out/index.html`](out/index.html)
  is the public face of the project; every example becomes one card
  with a page-1 thumbnail and links to HTML, PDF, source, and a
  single-page preview.

If a change to mdlout adds or restores a user-visible capability, the
PR that lands it should also land an example demonstrating it.

## 2. Picking a topic

Two-step filter:

1. Read [`examples/README.md`](README.md) end to end. The corpus is
   grouped by category -- Getting started, Typography, Lists/tables,
   Math/music, Structured docs, Posters/magazine, Diagrams, Raw
   passthrough, Kitchen sink. **Don't duplicate.** If your idea
   overlaps an existing file, consider extending that file with a
   one-section appendix instead of adding a new top-level example.
2. Read [`docs/cookbook.md`](../docs/cookbook.md). Each numbered
   recipe points at a building example; if a recipe currently has no
   example (or only points at a snippet), an example file is the
   natural way to graduate it.

Strong candidates for new examples:

- **Real-world document types** not yet covered: business memo,
  invoice, conference programme, lab notebook, syllabus, knit
  pattern, screenplay, IETF-style RFC.
- **Feature corners** that already build but lack a worked file:
  `@Eq` math edge cases (multi-line, matrix layouts), multi-column
  tricks (`@DP` to break a column, spanning headers), raw Lout
  passthrough for `@FootNote`, `@PageMark`, `@Galley`-attached
  side-galleys.
- **Accessibility patterns:** large-print body font, dyslexia-friendly
  font choices, high-contrast colour overrides via `colour:` and raw
  `@Colour { ... }`, screen-reader-friendly heading nesting under
  `type: report`.

Weak candidates (consider before committing):

- A second file that uses the same frontmatter recipe as an existing
  example. Extend the existing file instead.
- A purely cosmetic variation on an existing template ("CV but in
  Helvetica"). Prefer the cookbook for that.
- A document that only builds in one pipeline. The corpus's hard rule
  is that every example builds in both HTML and PDF mode; see Section
  4. Single-pipeline failures belong in `tests/snippets/` or under
  `TODO.md`, not here.

## 3. Frontmatter conventions

Cross-reference [`docs/best_practices.md`](../docs/best_practices.md)
sections 2 ("Frontmatter recipes for common doc types") for the
verified templates. The conventions the corpus follows:

- `type:` -- pick one of `doc` (default), `report`, `book`, `slides`.
  Don't introduce new type strings; mdlout silently falls through to
  `doc` for unknown values.
- `title:` and `author:` -- always set both, even on one-paragraph
  examples. The gallery card prints them.
- `date:` -- in `YYYY-MM-DD` form for `type: report`, free-form for
  letters and book chapters. Omit on `type: doc` smoke tests.
- `page:` -- `A4` or `Letter` for prose; `A3` only when the example
  genuinely needs it (`academic_poster.md`); `A5` for novels.
- `font:` -- `Times Base 11p` is the corpus default; deviate only
  when the topic demands it (Helvetica for posters / CV banners).
- `columns:` -- 1 (the unspecified default) or 2 for `type: doc`; for
  `type: report` Lout paginates so 2 columns is safe across pages.
  Three columns is poster-only (see the gotchas below).

For non-trivial examples set `para-indent`, `para-gap`,
`page-headers`, `top-margin`, `foot-margin`, `left-margin`, and
`right-margin` explicitly rather than relying on package defaults --
it makes the example readable as a template.

## 4. Build verification

**Hard requirement: the example must succeed under both pipelines.**

```bash
./mdlout.py examples/foo.md                    # HTML (default, SVG back-end)
./mdlout.py examples/foo.md --format=pdf       # PDF (PostScript back-end)
```

Then write the committed renderings into `examples/out/`:

```bash
./mdlout.py examples/foo.md       -o examples/out/foo.html
./mdlout.py examples/foo.md --format=pdf -o examples/out/foo.pdf
```

Both files are tracked. The repo's `.gitignore` allowlists the
patterns that may live under `examples/out/`:

- `*.html` -- the per-example HTML rendering (mode default).
- `*.pdf` -- the PDF rendering (`--format=pdf`).
- `preview-*.svg` -- single-page SVG previews emitted by the gallery
  generator.
- `thumb-*.png` -- page-1 PNG thumbnails for the gallery cards.
- `index.html` -- the gallery itself.

Anything else under `examples/out/` is ignored by git. If a file you
expect to commit is invisible to `git status`, that allowlist is the
first place to check.

If the PDF path fails for a known back-end reason, do not commit a
broken `.md`: document the gap in `TODO.md` and shelve the example
until the fix lands. The single recorded exception (`02_typography.md`
at the time of writing) is a deliberate placeholder, not a template.

## 5. Gallery regeneration

After both renderings are in place, regenerate the gallery:

```bash
python3 examples/generate_gallery.py
```

It is stdlib-only, idempotent, and shells out to `pdftoppm` and
ImageMagick `convert` for the thumbnails. It rewrites `index.html`,
all `preview-*.html` (single-page wrappers), `preview-*.svg`, and
`thumb-*.png` in place. Commit the diff alongside your new example;
PRs that touch `examples/` but leave the gallery stale will be sent
back.

## 6. Common gotchas

These have all bitten previous contributors. Build a mental checklist
before opening the PR:

- **UTF-8 accented characters do not survive the round trip.** mdlout
  reads Markdown as UTF-8 but Lout's input is ISO-Latin-1, and
  multi-byte UTF-8 sequences come out wrong on the PostScript path.
  For accented Latin letters use a raw ` ```lout ` fence with
  `@Char "eacute"` (or the appropriate Adobe glyph name). See
  [`examples/multilingual.md`](multilingual.md).
- **`1/3` inside a raw-Lout fence becomes a division operator.** Lout
  treats `/` as a metacharacter. Wrap any literal slash in double
  quotes: write `"1/3"` (or `"Simpson's 1/3 rule"`). The same is true
  of bare `@` -- write `"@"`.
- **`type: doc` + `columns: 2` is single-page only.** Lout has no
  automatic continuation onto page 2 in this mode; if the body
  overflows the warning is `too little horizontal space for galley
  @DocumentBody` and the rest of the document is silently truncated.
  For longer multi-column content use `type: report` with
  `cover: No`, which paginates normally.
- **LaTeX math in PDF mode can truncate the document.** `@Math` on
  the PostScript back-end is a stub that emits the source string as a
  single unbreakable word; a long expression can wedge Lout's break
  engine and cause downstream content to vanish without an obvious
  error. For PDF prefer prose math ("x squared minus four"), raw
  `@Eq` (see cookbook recipe 7), or a pre-rendered SVG.
- **`@VSpace { 2c }` does not exist.** The canonical vertical-space
  primitive is the vlist separator `//Nc` between two `@LP` markers,
  all inside a raw-Lout fence -- see
  [`examples/exam.md`](exam.md) for the worked pattern.
- **`@Font { +Np }` does not.** The size adjuster must come *before*
  `@Font`: write `{ +6p } @Font @B { name }`, not
  `@Font { +6p } @B { name }`. The wrong form silently prints `+6p`
  as literal text alongside the styled output.

When in doubt, check `examples/cv.md`, `examples/letter.md`, and
`examples/exam.md` -- they collectively demonstrate every one of the
gotchas above.

## 7. Testing

Run the browser-test suite from the repo root:

```bash
bash tests/browser_test.sh
```

It picks up new examples automatically -- there is no manifest to
update. Verify that your example passes (the audit report at
`tests/out/browser_audit.json` shows per-example findings) **before**
committing. Then run the full regression suite if you touched a
shared piece of the converter:

```bash
bash tests/run_all.sh
```

That walks the `tests/snippets/` corpus through both back-ends. New
examples don't show up there directly, but a fix to a feature your
example depends on probably does -- so if the suite was passing on
`main` and is failing on your branch, you've found a regression worth
investigating before opening the PR.

## 8. PR conventions

- **One example per PR.** Reviewers compare the rendered HTML and PDF
  to the source side by side; bundling two new examples doubles that
  load. Land them one at a time.
- **Reference an issue if one exists** ("closes #123",
  "addresses #45"). For feature-driven examples, the example PR
  usually trails the feature PR by one or two commits.
- **Include the gallery rebuild** (`index.html`, `preview-*.html`,
  `preview-*.svg`, `thumb-*.png` for your new file) in the same PR.
  The reviewer should not have to run `generate_gallery.py` to see
  what your example looks like.
- **Title format:** `examples: add foo.md (...one-line summary...)`.
  Matches the existing log; `git log --oneline examples/` is the
  reference.
- **Don't change first-party Python or C** in an example PR. If your
  example needs a converter fix, land that fix in a separate PR
  first.

## 9. Where to look next

- [`README.md`](README.md) -- the example corpus grouped by category.
- [`docs/best_practices.md`](../docs/best_practices.md) -- idiom
  guide, frontmatter recipes, debugging.
- [`docs/cookbook.md`](../docs/cookbook.md) -- 20 task-oriented
  recipes, each pointing at a worked example.
- [`tests/README.md`](../tests/README.md) -- regression-suite layout
  and how `browser_test.sh` audits examples.
- [`TODO.md`](../TODO.md) -- known gaps; examples that would help
  close one of these are particularly welcome.
