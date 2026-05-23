# Contributing to mdlout

Thanks for your interest in contributing. This guide covers the whole
project; for the example-corpus checklist see
[`examples/CONTRIBUTING.md`](examples/CONTRIBUTING.md), and for the
deeper engineering map see [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md).

## 1. Reporting bugs and requesting features

Open an issue on GitHub. Useful contents:

- The exact command line (`./mdlout.py ... --format=...`).
- The input Markdown, ideally reduced to a minimal failing case.
- Expected output vs. actual output. For rendering bugs attach the
  HTML and the PDF (or screenshots of each); divergence between the
  two pipelines is the most common symptom.
- The lout submodule SHA (`cd lout && git rev-parse HEAD`).
- Platform: OS, Python version, gcc/tcc version for `lout/`-side bugs.

When labelling or describing the change, use the same categories
that [`CHANGELOG.md`](CHANGELOG.md) tracks (Keep a Changelog 1.1.0):

- **Added** — new features or capabilities.
- **Changed** — behaviour or interface changes to existing features.
- **Fixed** — bug fixes.
- **Performance** — non-functional speed or size improvements.
- **Tests** — additions or changes under `tests/`.
- **Docs** — `docs/`, `README.md`, `CHANGELOG.md`, and similar.

Submodule-only entries are tagged `[lout]` in the CHANGELOG; PRs that
touch only the submodule pointer should follow the same convention.

## 2. Development setup

A fresh clone is missing the `lout/` submodule contents. Run:

```bash
git clone https://github.com/jclements3/mdlout.git
cd mdlout
git submodule update --init
cd lout && git checkout svg-backend && make lout && cd ..
```

The build floor is gcc with `-ansi -std=c99 -pedantic -Wall -O3`; tcc
must also compile every C source unchanged (see Section 4).

Two ways to run the converter:

```bash
./mdlout.py input.md                     # direct script invocation
pip install -e .                         # editable install (when published)
mdlout input.md                          # installed entry point
```

The script is pure stdlib Python 3.10+ and has no install-time
dependencies. The PDF pipeline additionally needs `ghostscript`
(`ps2pdf`); the HTML pipeline needs nothing extra at build time, though
`librsvg2-bin`, `poppler-utils`, and `imagemagick` are useful for the
test suite.

## 3. Where to find the docs

All under [`docs/`](docs/) unless noted:

- [`docs/tutorial.md`](docs/tutorial.md) — end-to-end walkthrough from
  a fresh clone to a rendered document.
- [`docs/FAQ.md`](docs/FAQ.md) — common gotchas and troubleshooting.
- [`docs/cookbook.md`](docs/cookbook.md) — 38 task-oriented recipes,
  each pointing at a worked example.
- [`docs/best_practices.md`](docs/best_practices.md) — idiom guide,
  frontmatter recipes, debugging.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how the converter
  is structured and where the SVG back-end fits in.
- [`docs/z53_internals.md`](docs/z53_internals.md) — function-by-function
  guide to the SVG back-end, the canonical reference for new C work.
- [`docs/CI.md`](docs/CI.md) — the GitHub Actions workflows and how to
  reproduce them locally.

The top-level [`README.md`](README.md) is the CLI and frontmatter
reference. [`CLAUDE.md`](CLAUDE.md) is the engineering crib sheet for
the maintainers' coding agent and doubles as a developer overview.

## 4. Code style

### C (`lout/`)

All C added under `lout/` must compile under both
`gcc -ansi -std=c99 -pedantic -Wall` and `tcc`. `tcc` is the hard
floor and is the stricter of the two. The rules:

- Declare all locals at the top of their block. No mid-block
  declarations.
- `/* ... */` comments only. No `//` line comments.
- Positional struct initialisers only. No `.field = ...` designated
  initialisers.
- No GCC extensions: no `__attribute__`, statement expressions,
  nested functions, zero-length arrays, VLAs, or `typeof`.
- No C99-style mid-loop iterator declarations. Write
  `int i; for (i = 0; ...)`, not `for (int i = 0; ...)`.
- Include only `externs.h`. Module-internal helpers should be
  `static` and stay in their own `.c` file.

When in doubt, match a neighbouring file (`z01.c`–`z52.c`).
[`docs/z53_internals.md`](docs/z53_internals.md) contains worked
examples of every idiom the back-end uses.

`z49.c` (PostScript) is frozen — every SVG-side change is additive.

### Python (`mdlout.py`)

- Standard library only. No third-party imports at runtime.
- Type hints on every public function; aim for hints on internal
  helpers too.
- Four-space indent, snake_case, PEP 8 spacing.
- One module file. Resist splitting `mdlout.py` into a package
  unless there is a concrete justification.
- Follow the existing patterns: the placeholder system in
  `convert_inline`, the `Block`/`BlockType` dataclass in the block
  parser, `_lout_string_encode` for raw-string emission.

### Markdown / docs

- Wrap prose at roughly 80 columns. Long URLs and code lines may
  exceed.
- Fenced code blocks with a language hint (` ```bash `, ` ```python `,
  ` ```yaml `, ` ```lout `). Untagged fences render as plain
  monospace.
- Factual and concise. No marketing language. No emojis unless the
  source document genuinely needs them.

## 5. Testing

Run all four suites before submitting a PR that touches `mdlout.py`,
`lout/`, or shared infrastructure. Docs-only PRs need none of them.

```bash
bash tests/run_all.sh                    # snippet regression (PS vs SVG)
bash tests/browser_test.sh               # HTML structural audit of examples
bash tests/user_guide_diff.sh            # User's Guide PS-vs-SVG SSIM diff
bash tests/lout_doc_renders/build.sh     # four bundled Lout docs render gate
```

What each one covers:

- `run_all.sh` walks `tests/snippets/` through both back-ends,
  rasterises at 150 dpi, compares with ImageMagick AE, and writes
  `tests/report.html`. Default thresholds are 5% pixel diff for text
  and 20% for graphics-heavy snippets (the `GRAPHICS_HEAVY` set in
  `tests/compare.py`).
- `browser_test.sh` audits every `examples/*.md` for HTML structural
  regressions; new examples are picked up automatically.
- `user_guide_diff.sh` rebuilds `lout/doc/user/all` as both PostScript
  and SVG, then reports per-page SSIM. The current floor is mean SSIM
  >= 0.9283 across 327 pages.
- `lout_doc_renders/build.sh` builds the four bundled Lout reference
  documents (user guide, expert guide, design notes, slides) under
  both back-ends and writes a side-by-side diff gallery.

If you only touched one path, run the matching suite during
iteration, then all four before opening the PR.

## 6. Submitting changes

1. Branch from `main` with a descriptive topic name (no enforced
   prefix scheme).
2. Make your changes. Update [`CHANGELOG.md`](CHANGELOG.md) under
   `## [Unreleased]` with one entry per logical change, slotted into
   the right category.
3. Run the four test suites above; resolve any regressions.
4. Push to your fork and open a PR via the `gh` CLI:

   ```bash
   git push -u origin my-topic
   gh pr create --title "..." --body "..."
   ```

5. Reference any related issues (`closes #123`, `addresses #45`).
   Reviewers should be able to see the rationale, the test plan, and
   any rendered artefacts (linked or attached) without leaving the
   PR description.

If your change spans both `mdlout.py` and `lout/`, follow the
submodule double-dance in
[`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md): submodule PR first
(against `svg-backend` on the `jclements3/lout` fork), wait for
merge, then bump the outer-repo pointer.

## 7. Commit-message style

Match the existing log (`git log --oneline`):

- Subject line: short summary (50–72 characters), present-tense,
  imperative or descriptive. No type prefix (`feat:`/`fix:`/etc.).
- Blank line, then a bulleted body when the change warrants
  explanation. One bullet per logical sub-change.
- Quantitative results are welcome (`2.3x faster`, `mean SSIM
  0.9234 -> 0.9283`, `327/327 pages`) when measured.
- No `Signed-off-by`, no `Co-Authored-By` unless the user explicitly
  adds it for a genuinely co-authored change, and no automated
  footer or branding lines.

Common subject patterns in the existing log:

- `Add <thing>` for new features.
- `Fix <thing>` for bug fixes.
- `Bump lout submodule: <one-line summary>` for outer-repo commits
  whose only change is the submodule pointer.
- `mdlout: <short>` when the change is scoped to `mdlout.py`.
- `docs: <short>`, `tests: <short>`, `examples: <short>` for
  category-scoped changes.

PR titles follow the same conventions.

## 8. Example-specific contributions

Adding a new file under [`examples/`](examples/) has its own
checklist (gallery regeneration, frontmatter conventions, dual-pipeline
build verification). See [`examples/CONTRIBUTING.md`](examples/CONTRIBUTING.md)
for that workflow.

## License

Lout under `lout/` is GPLv3, copyright 1994–2023 Jeffrey H. Kingston.
The mdlout converter (`mdlout.py`) follows the same license unless
noted otherwise. Contributions are accepted under the same terms.
