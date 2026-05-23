# mdlout FAQ

Accumulated gotchas, surprising error modes, and "why is this
happening?" questions from the issue tracker and the
`tests/lout_doc_renders/` bring-up. Most entries cross-reference a
deeper section in [`docs/best_practices.md`](best_practices.md), a
working recipe in [`docs/cookbook.md`](cookbook.md), or a verified
example under [`examples/`](../examples/).

If your question is not here, try
[`docs/tutorial.md`](tutorial.md) for the end-to-end walkthrough,
the [README](../README.md) for CLI flags and frontmatter keys, or
[`TODO.md`](../TODO.md) for known gaps.

---

## Math, music, and SVG passthrough

### Why does my LaTeX math truncate the PDF document?

In **HTML mode** `$..$` / `$$..$$` / ` ```math ` blocks route through
`@Math`, which the SVG back-end wraps in a `<foreignObject>` that
KaTeX paints client-side. The full LaTeX menu is available.

In **`--format=pdf` mode** `@Math` is a *stub*. It emits the source
expression as a single unbreakable Lout word. A short fragment
renders as a literal token; a long one (a multi-line `aligned`
environment, say) overflows the galley's measure, wedges the
paragraph break engine, and silently truncates everything that
should have followed. No exception is raised -- the document just
ends early.

Three fixes: switch to HTML; rewrite the math as raw Lout `@Eq`
inside a ` ```lout ` fence (see
[cookbook recipe 7](cookbook.md#7-drop-caps-and-pull-quotes-raw-lout-passthrough)
and [`examples/04_math.md`](../examples/04_math.md)); or pre-render
to SVG and inline with `![equation](eq.svg)`. See
[`docs/best_practices.md` section 1](best_practices.md#1-when-to-choose-html-vs-pdf)
for the full HTML-vs-PDF decision tree.

### Why does my UTF-8 accented character become a question mark?

Lout's input encoding is **ISO-Latin-1** (the only configuration the
SVG branch supports). mdlout reads Markdown as UTF-8, but multi-byte
sequences that encode `é`, `ñ`, `Ø`, or any non-Latin-1 codepoint do
not survive the hand-off to `lout`. The PostScript pipeline turns
them into `?` glyphs; the SVG pipeline emits them as literal
mojibake.

The supported route for accented Latin letters is the `@Char` glyph
name inside a raw-Lout fence:

```lout
caf@Char "eacute"
```

For Greek use `@Sym`, for Cyrillic use `@Language { Russian }`. See
[`examples/multilingual.md`](../examples/multilingual.md) and
[cookbook recipe 18](cookbook.md#18-multilingual-document). Full
Unicode coverage in the SVG back-end is tracked in `TODO.md`.

### Why does `1/3` in a raw-Lout fence parse strangely?

Lout treats `/` as the **vertical-list separator** metacharacter. A
bare `1/3` inside a ` ```lout ` fence parses as "the object `1`
vertically above the object `3`" -- not as a fraction. The same is
true of `@`, `{`, `}`, `&`, `|`, and `#`; all are Lout
metacharacters.

The fix is to quote the literal:

```lout
Use Simpson's "1/3" rule for n even.
@LP
The fraction "1/3" appears in @F "1/3".
```

Double quotes turn the contents into a literal Lout string with no
metacharacter interpretation. This is also how you spell a literal
`@` (`"@"`) or a `{` (`"{"`) inside raw passthrough.

For *displayed* fractions use the `eq` package: `1 over 3` inside
`@Eq` typesets a real fraction with a numerator and denominator. See
[cookbook recipe 7](cookbook.md#7-drop-caps-and-pull-quotes-raw-lout-passthrough)
and [`examples/04_math.md`](../examples/04_math.md).

## Layout and pagination

### Why does my two-column doc silently overflow?

`type: doc` is Lout's **single-page** document type. With
`columns: 2` and enough body content to fill column 1 and column 2 on
page 1, the third column's worth of material has nowhere to go -- Lout
emits the warning

    too little horizontal space for galley @DocumentBody

on stderr and **silently truncates** the rest of the document. No
exception is raised; the build "succeeds" with a short PDF / HTML.

Two pagination-aware document types do continue onto page 2:

- `type: report` -- multi-page, paginated, optional cover sheet and
  TOC.
- `type: book` -- multi-page, paginated, with chapters / sections.

For a long multi-column document switch to `type: report` with
`cover: No` and `contents: No` if you want the column behaviour
without a title block. See
[`examples/scientific_paper.md`](../examples/scientific_paper.md)
and the
[best-practices frontmatter recipes](best_practices.md#2-frontmatter-recipes-for-common-doc-types).

Posters (three columns, landscape A3) are the one exception -- they
are deliberately single-page, so `type: doc` is correct there. See
[cookbook recipe 1](cookbook.md#1-three-column-poster) and
[`examples/academic_poster.md`](../examples/academic_poster.md).

### Why does my `@Font { +Np }` print `+Np` literally?

The Lout `@Font` symbol takes the **size adjuster as a left
argument**, not as part of the brace body. The wrong form

```lout
@Font { +6p } @B { Heading }
```

emits the literal characters `+6p` as a styled paragraph beside
`Heading`, because Lout reads the brace body as a list of words to
typeset.

The right form puts the size argument before the symbol name:

```lout
{ +6p } @Font @B { Heading }
```

The same convention applies to `@Break`, `@Space`, `@SetColour`, and
the other left-argument-taking Lout symbols. The rule of thumb: if
the User's Guide spells it `@SymName { ... }`, the braces are the
body; if it spells it `arg @SymName { body }`, the left of `@SymName`
is a modifier.

This bites every contributor at least once. See
[`examples/CONTRIBUTING.md` section 6](../examples/CONTRIBUTING.md#6-common-gotchas)
for the rest of the list.

### Why does my second build produce different output than the first?

Lout writes per-document **index files** (`lout.li`, `lout.lix`,
`lout.ldx`, `<docname>.ld`) to the current working directory as it
resolves cross-references. If you build `paper.md` and then
`report.md` in the same cwd, `report.md`'s build picks up stale
entries from `paper.md`'s `lout.li`. mdlout runs `lout` up to three
times per build to converge cross-refs, but those passes operate on
the *current* `lout.li` -- they do not clean it first.

Symptoms: phantom TOC entries, wrong page numbers, `unresolved cross
reference` warnings that go away on the third build, mysterious
layout shifts between runs.

Fix: `rm lout.l*` between builds when switching documents, or build
each document in its own directory (`./mdlout.py paper.md -o
out/paper/paper.html` writes the index files next to the output).
This was the root cause of the concurrent-runner damage in
`tests/lout_doc_renders/build.sh` tracked in commit `a4a20df`; the
test harness now copies each doc to a per-run scratch dir.

## SVG back-end and dark mode

### Why does the SVG output have XML-comment "unimplemented PostScript op" lines?

`z53.c`'s embedded PostScript interpreter covers the operators that
appear in Lout's standard `@Graphic` prologues (`moveto`, `lineto`,
`curveto`, `stroke`, `fill`, `setrgbcolor`, `setlinewidth`, the
arc / Bezier family, and the `LoutPageDict` / `LoutMargSet` family
hashed in v0.2.2). Custom `@Graphic` bodies (and a long tail of less
common Lout prologue ops) can reach for operators the interpreter
does not yet know.

When that happens, `z53.c` emits

    <!-- z53.c: unimplemented PostScript op 'OpName' -->

into the SVG instead of silently dropping the operation. The
comment documents which op was missing so you can either rewrite the
diagram to use the supported subset or file an issue with the op
name attached.

The Lout-tag-shaped names (uppercase ASCII starting with a letter,
e.g. `A1`, `M2`) that used to leak into these comments through
`@Diag` / `@Fig` macro expansion are now silently dropped (commit
`f33d25a` in v0.2.1); only genuine PS-operator misses surface.

For the current operator coverage map and the next-priority gaps see
[`lout/SVG_PORTING.md`](../lout/SVG_PORTING.md) in the submodule.

### Why is the @Diag arrowhead orientation wrong?

`@Diag` arrowheads on rotated links used to point in the wrong
direction in SVG output -- the rotation angle was dropped when the
embedded interpreter saw a `translate N rotate moveto show` idiom.
The compass-point label demo on User's Guide page 207
(`ldiagshowtags` in `diagf.lpg`) and any `@Diag` link using
`linklabelangle` were the canonical reproducers.

The fix landed in lout commits `78244cc` / `a0a5c28` (mdlout
`61471c6`) and shipped in **v0.2.1**. If your output still has
mis-rotated arrowheads, you are building against pre-v0.2.1 sources:

```bash
cd lout
git fetch origin svg-backend
git checkout svg-backend
git pull
make lout
```

The regression test for this is
[`tests/snippets/graphic_rotated_show.lt`](../tests/snippets/graphic_rotated_show.lt)
(SSIM 0.9927, Pass-Excellent).

### Why doesn't dark mode invert my photos?

`--dark` (or `theme: dark` in frontmatter) turns on a CSS class on
the page wrapper. Until v0.2.2 the implementation was `filter:
invert(1) hue-rotate(180deg)` applied per page, which dutifully
inverted embedded raster images alongside the text -- photographs
came out with reversed luminance.

The v0.2.3 implementation (commit `b6baaa4`) is a proper CSS
`currentColor` cascade. `z53.c` folds default-black ink to
`fill="currentColor"` / `stroke="currentColor"` (lout `346b335`),
and the dark-mode body class only sets `color: #e8e8e8` on the
container. So glyphs and rules pick up the dark-mode foreground;
embedded `<image>` elements keep their original luminance and hue;
authored colours (chart fills, syntax highlighting, callouts) are
preserved untouched.

The trade-off: documents built before v0.2.3 carry literal
`fill="rgb(0,0,0)"` in their SVG and stay black in dark mode. Just
re-render with the current lout to pick up the cascade. The CSS
shape is documented in
[`docs/best_practices.md` section 10](best_practices.md#10-performance-tips)
and the CHANGELOG entry for v0.2.3.

### Why does the URW Nimbus inlined font payload bloat my HTML?

The default HTML output inlines twelve URW++ Nimbus base-35 faces as
base64 in `@font-face` rules so the page is self-contained and
renders identically offline. Full faces are about 1.1 MB each, so
the inlined font payload alone runs ~13 MB on a math-heavy document.

`--subset-fonts` (commit `e42b157`, v0.2.2) scans the emitted SVG
for every `<text>` / `<tspan>` family + codepoint, builds a
per-family subset (with a printable-ASCII baseline for KaTeX /
abcjs runtime needs), and runs each face through
`fontTools.subset.Subsetter` before the base64 embed. Per-document
savings sit in the 50-60% range; font payload alone shrinks ~81%.

**The flag is on by default since v0.2.3** (commit `deaa546`). Pass
`--no-subset-fonts` (or `subset-fonts: false` in frontmatter) to
restore the v0.2.2 opt-in behaviour. fontTools is an optional
dependency; if it is missing the converter warns once to stderr and
falls back to full-face inline so the build does not break.

For other size-reduction knobs (`--external-assets`, `--no-math-engine`,
`--no-music-engine`, `--no-highlight`, `--no-font-embedding`) see
[`docs/best_practices.md` section 10](best_practices.md#10-performance-tips).

## Build and test failures

### Why does my doc/expert build fail with "assert failed in Parse: *token!"?

If you run `tests/lout_doc_renders/build.sh` (or otherwise invoke
`lout` repeatedly against `lout/doc/expert/all`) from two shells at
once, Lout's per-cwd cross-reference files (`*.li`, `*.ldx`,
`lout.lix`) get interleaved between the two runs. The downstream
symptoms are not subtle:

    assert failed in Parse: *token!
    rename(expert.ldx, expert.ld) failed
    fatal error: line too long when reading index file lout.lix

A single-runner reproduction against `cp -r doc/expert /tmp/expert &&
cd /tmp/expert && lout all` passes 7/7 PostScript passes cleanly,
which is what gave the diagnosis away.

The fix in `tests/lout_doc_renders/build.sh` (commit `a4a20df`,
v0.2.3) is to copy each doc to a per-run scratch dir before running
lout. The original `lout/doc/$d` source is untouched and parallel
agent processes can no longer race on the index files.

The same pattern applies to your own builds: if you script multiple
`mdlout.py` invocations in parallel, write each one's output into
its own subdirectory rather than letting them share a cwd. See the
"Why does my second build..." entry above for the same race in
single-runner form.

### Why is the User's Guide SVG build slow?

It used to be **~7 minutes** when the SVG back-end first landed.
After four rounds of profiler-guided optimisation it is now
**~22.6 s real / 19.8 s user** (lout `f234cde` -> mdlout `94277d7`,
v0.2.4) on the reference host -- a 94% wall-clock reduction.

Highlights: round 2 (v0.2.2) hashed the glyph-to-unicode table and
added a face-flag cache; round 3 (v0.2.3) consolidated stdio in
`SVG_PrintWord`; round 4 (v0.2.4) hand-rolled itoa/ftoa3 for page
chrome and coord-folded the Y-flip into a matrix on each `<text>`
element (-13.5% SVG size). If your build is still slow, you are
probably running a pre-v0.2.3 binary -- update the submodule
(`cd lout && git pull && make lout`). The full hot-spot breakdown
is in [`tests/profile/README.md`](../tests/profile/README.md). The
`--format=pdf` pipeline was never the slow path; this only affects
HTML mode.

## Tooling and workflow

### What's the difference between --watch and --serve?

Both watch `args.input` for mtime changes (500 ms polling via
`os.path.getmtime`) and rebuild on every save. The initial build
runs immediately; transient errors (parse failures, lout failures,
file races) are caught and logged so the loop keeps going. Only
SIGINT exits.

- `--watch` writes the HTML / PDF to disk on each rebuild. You open
  the file in your browser and reload manually. Useful when the file
  is the artefact (e.g. building into a shared dropbox).
- `--serve [PORT]` (default 8080) adds a stdlib
  `http.server.ThreadingHTTPServer` bound to `127.0.0.1:PORT` with
  two routes: `GET /` reads the freshly-built HTML off disk and
  streams it back; `GET /events` is an SSE long-poll that sends
  `event: reload` on every rebuild (with a 15 s heartbeat). A 5-line
  `<script>` injected before `</body>` opens an
  `EventSource("/events")` and calls `location.reload()` on the
  reload event. The browser tab refreshes automatically -- no manual
  reload needed.

`--serve` only supports HTML output (it overrides `--format=pdf` to
HTML if asked). Use `--watch` if you specifically need a live PDF
rebuild loop.

Both are stdlib-only, no extra dependencies. The HTTP server is a
daemon thread, the watch loop runs in the main thread, and Ctrl-C
tears both down cleanly.

### How do I add a new example?

See [`examples/CONTRIBUTING.md`](../examples/CONTRIBUTING.md). The
short version: pick a topic that does not duplicate an existing
example, write the Markdown, verify it builds in **both** HTML and
PDF mode (the hard rule of the example corpus), regenerate the
gallery with `python3 examples/generate_gallery.py`, run
`bash tests/browser_test.sh`, and open a PR titled
`examples: add foo.md (...one-line summary...)`.

The corpus's hard rules are documented in
[`examples/CONTRIBUTING.md` section 4](../examples/CONTRIBUTING.md#4-build-verification)
(both pipelines build) and section 5 (gallery regenerated in the
same PR). Single-pipeline failures belong in `tests/snippets/`, not
`examples/`.

### How do I publish HTML to GitHub Pages?

See [`examples/PUBLISHING.md`](../examples/PUBLISHING.md). It walks
through the single-file output shape, the `/docs`-on-main vs
`gh-pages`-branch layouts, the CI-driven publish via
`.github/workflows/publish.yml`, the custom-domain DNS cheat-sheet,
the accessibility checklist (screen-reader smoke test, alt-text
audit, contrast check), and the recommended `src/` + `docs/` layout
for downstream users who want the same pattern in their own repo.

The publish workflow needs the `workflow` OAuth scope to push from
CI; if `git push` complains about `refusing to allow an OAuth App to
create or update workflow`, run `gh auth refresh -s workflow` once.
That is also covered in [`docs/CI.md`](CI.md).

### How do I publish mdlout to PyPI?

See [`docs/PYPI.md`](PYPI.md). The current release process is
manual: `python -m build` produces a clean sdist + wheel,
`python -m twine upload --repository testpypi dist/*` smoke-tests
against TestPyPI, then `python -m twine upload dist/*` cuts the
real release. The CI-driven path uses PyPI's OIDC trusted
publishing so no token secret needs to live in repo settings; the
trusted-publisher config lives at
<https://pypi.org/manage/project/mdlout/settings/publishing/>.

Version bumps touch `pyproject.toml`, `mdlout.VERSION`, and
`CHANGELOG.md` together; see `docs/PYPI.md` for the exact sequence
and the publish-after-rollback recovery path if you cut a broken
release.

---

## Where to go next

- [`docs/tutorial.md`](tutorial.md) -- end-to-end walkthrough from a
  fresh clone.
- [`docs/best_practices.md`](best_practices.md) -- idiom guide,
  frontmatter recipes, debugging.
- [`docs/cookbook.md`](cookbook.md) -- 30+ task-oriented recipes.
- [`examples/README.md`](../examples/README.md) -- sample documents
  grouped by category.
- [`TODO.md`](../TODO.md) -- known gaps; if your question is about
  something on this list, it is a known limitation.
- [`CHANGELOG.md`](../CHANGELOG.md) -- when each fix landed and
  which commit carried it.
