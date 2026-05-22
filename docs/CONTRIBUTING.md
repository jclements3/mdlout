# Contributing to mdlout

A practical guide for filing issues and submitting pull requests. Read
[ARCHITECTURE.md](ARCHITECTURE.md) first for a deeper map of the codebase;
this file is just the contributor-facing summary.

## Codebase layout

```
mdlout/
  mdlout.py              # the Python converter (single file)
  lout/                  # git submodule -> jclements3/lout, branch svg-backend
  examples/              # sample .md documents
  tests/                 # regression framework (PS vs SVG diff)
  docs/                  # ARCHITECTURE.md, tutorial.md, this file, ...
  CLAUDE.md              # engineering notes (also a developer crib sheet)
  TODO.md                # current roadmap
  CHANGELOG.md           # release history
  README.md              # quickstart + CLI + frontmatter reference
```

The two first-party surfaces are `mdlout.py` (Python 3.10+, stdlib only) and
`lout/z53.c` plus `lout/include/svgmacros` inside the submodule. Everything
else under `lout/` is either upstream (Jeffrey Kingston's Lout, vendored
through the william8000 fork chain) or near-upstream library files with small
`@BackEnd @Case` branches grafted in. See
[docs/ARCHITECTURE.md](ARCHITECTURE.md) for the full breakdown including the
function map of `z53.c`, the embedded PostScript interpreter, and the
PS-vs-SVG agreement metrics.

## Where to put what

| You want to ...                                       | Edit this                                          |
| ----------------------------------------------------- | -------------------------------------------------- |
| Add a Markdown feature, fix conversion, tune CLI      | `mdlout.py`                                        |
| Add a YAML frontmatter key                            | `mdlout.py` (`parse_frontmatter`, `_generate_preamble`) |
| Add an SVG drawing primitive or a PS interpreter op   | `lout/z53.c` (submodule, branch `svg-backend`)     |
| Extend a Lout-language construct (`@Diag`, `@Fig`...) | `lout/include/*` (submodule)                       |
| Add a regression snippet                              | `tests/snippets/*.lt` + `tests/run_all.sh` (already picks up the directory) |
| Add a worked example                                  | `examples/*.md` + entry in `examples/README.md`    |
| Add or change docs                                    | `docs/*.md` (this directory)                       |

If a change touches both `mdlout.py` and `lout/`, expect two PRs: one against
mdlout, one against the lout submodule. See [The submodule
double-dance](#the-submodule-double-dance) below for the workflow.

## The ANSI C / tcc constraint

All C added to `lout/` must compile under both `gcc -ansi -std=c99 -pedantic
-Wall` and `tcc`. `tcc` compatibility is the hard floor and is more
restrictive than the gcc invocation. The rules in practice:

- **Declare all locals at the top of their block.** No mid-block
  declarations.
- **Use `/* ... */` comments only.** No `//` line comments.
- **Use positional struct initialisers.** No designated initialisers
  (`.field = ...`).
- **No GCC extensions.** No `__attribute__`, no statement expressions,
  no nested functions, no zero-length arrays, no VLAs, no `typeof`.
- **No C99-style mid-loop iterator declarations.** Write `int i; for (i = 0;
  ...)` not `for (int i = 0; ...)`.
- **Include only `externs.h`.** All shared types and prototypes live there.
  New module-internal helpers should be `static` and stay in their `.c` file.

Match the dialect already used in `z01.c`-`z52.c`. When in doubt, scan a
neighbouring file. New code that compiles under gcc but trips tcc is a
regression even if the makefile build passes.

## The "PS path is frozen" rule

`lout/z49.c` (the PostScript back end) is **never modified by this fork**.
Pull requests that touch `z49.c` will be sent back unless they are pulling
in a fix from upstream Lout that we are deliberately syncing. The PDF
pipeline (`mdlout.py --format=pdf` -> Lout PS back end -> `ps2pdf`) must
remain bit-identical to what upstream Lout would have produced.

All SVG-side work is additive: new code lives in `z53.c`, new macros live
in `include/svgmacros`, and existing library files in `include/` are
extended with `@BackEnd @Case { PostScript @Yield <existing> SVG @Yield
<new> }` branches that preserve the PostScript path.

If a change *needs* to touch behaviour upstream of the back-end split (the
galley engine, font service, hyphenation, etc.), call that out explicitly
in the PR description and explain why an additive solution was not viable.

## How to add a test

1. Drop a new file into `tests/snippets/`. Name it after the feature it
   exercises (e.g. `diag_arrow_curved.lt`). Keep it 5-30 lines of
   standalone Lout:

   ```
   @SysInclude { doc }
   @Doc @Text @Begin
   ... feature under test ...
   @End @Text
   ```

   Use `@SysInclude { eq }` or `@SysInclude { tbl }` before `doc` if the
   snippet needs equations or tables.

2. Run the suite:

   ```
   bash tests/run_all.sh
   ```

   This renders the snippet through both back ends at 150 dpi, diffs the
   PNGs with ImageMagick, computes SSIM if `scikit-image` is available,
   and rebuilds `tests/report.html`.

3. If the snippet is bitmap-heavy or otherwise expected to diverge between
   back ends (rotated text, raw `@Graphic` blocks, `@CurveBox`, ...), add
   its name to the `GRAPHICS_HEAVY` set in `tests/compare.py` to relax
   its threshold from 5% to 20% pixel diff.

See `tests/README.md` for the full description of how thresholds, statuses,
and verdicts are assigned.

## How to add an example

1. Create `examples/NN_short_name.md` (use the next free numeric prefix for
   the canonical sequence, or just a descriptive name for ad-hoc ones).

2. Build it through both pipelines to confirm it works:

   ```
   ./mdlout.py examples/NN_short_name.md                # produces .html
   ./mdlout.py examples/NN_short_name.md --format=pdf   # produces .pdf
   ```

3. Add a one-line entry in `examples/README.md` describing what the
   example demonstrates. If the example exercises a new feature, also add
   a focused snippet under `tests/snippets/` so the feature has regression
   coverage independent of the example.

The example markdown files are not run by `tests/run_all.sh` (which only
sweeps `tests/snippets/`); they are smoke-tested by hand and by the larger
`tests/user_guide_diff.sh` driver where applicable.

## Style guide

Documentation in `docs/` and the top-level `README.md` aims at one thing:
get the reader to the right command line as quickly as possible.

- **Factual and concise.** State what the tool does and how to invoke it.
  No marketing language ("powerful", "elegant", "blazing fast", etc.).
- **Command-line first.** Lead with the shell incantation, then explain.
  A reader who already knows what they want should not have to read a
  paragraph to find a `./mdlout.py ...` invocation.
- **Honest about limits.** If a feature is partial, say so and link to
  `TODO.md`. If a platform is untested, label it as such (see
  [build_notes.md](build_notes.md) for examples).
- **Numbers where they help.** Line counts, SSIM scores, page counts —
  cite them from the source when present.
- **No emojis** unless the user asks for them in the source file (markdown
  bodies are fine; meta-documentation should not contain them).
- **No "Conclusion" or "Summary" sections.** Most docs are short enough
  that a recap is filler.

Python code in `mdlout.py` follows roughly standard PEP 8 (4-space indent,
snake_case, module docstring). The file is deliberately monolithic; resist
splitting it into a package unless there is a concrete justification.

## Branch naming and commits

Branches:

- Feature work in the outer repo: descriptive names without a strict
  prefix scheme. Existing branches have used short topic names; there is
  no enforced `feature/` or `fix/` prefix.
- Submodule work: branch off `svg-backend` (the working branch), name
  similarly.

Commit messages observed in the repository, both outer and submodule:

- Subject line is a short summary (50-72 characters), present-tense,
  imperative or descriptive. No type prefix (`feat:` / `fix:` / etc.).
- Common subject patterns:
  - `Add <thing>` for new features (`Add CI status badge to README`)
  - `Fix <thing>` for bug fixes (`Fix @Graph axes: tighten eq/ne ...`)
  - `Bump lout submodule: <one-line summary>` for outer-repo commits
    whose only change is updating the submodule pointer
  - `mdlout: <short>` when the change is scoped to `mdlout.py`
  - `SVG perf: <short>` for `z53.c` performance work
- Body (when used) is plain prose paragraphs, no `Signed-off-by:` trailer,
  no `Co-authored-by:` unless actually co-authored. Quantitative results
  (`2.3x faster`, `327/327 pages`, `-5.3%`) are welcome when measured.

Pull request titles follow the same conventions as commit subjects.

## The submodule double-dance

The `lout/` directory is a git submodule pointing at
`https://github.com/jclements3/lout` (the maintainer's fork; the `.gitmodules`
entry on disk still references the older william8000 URL in some checkouts,
but the working branch is `svg-backend` on the jclements3 fork). Any change
that touches both repos requires coordinating two pull requests.

The procedure:

1. **Submodule PR first.** From `lout/`, branch off `svg-backend`, make the
   change, push, open a PR against `svg-backend` on the lout fork. Wait for
   merge.

   ```
   cd lout
   git checkout svg-backend
   git pull
   git checkout -b my-fix
   # ... edits, commits ...
   git push -u origin my-fix
   # open PR; once merged, fast-forward locally:
   git checkout svg-backend
   git pull
   ```

2. **Bump the outer repo's submodule pointer.** Once the submodule PR is
   merged and the new commit is on `svg-backend`:

   ```
   cd ..               # back to mdlout/ root
   git add lout        # stages the new submodule SHA
   git commit -m "Bump lout submodule: <one-line summary>"
   ```

   If the outer-repo change is *only* a submodule bump, the convention is
   to start the subject line with `Bump lout submodule:` and follow with
   the same one-liner as the submodule PR's subject.

3. **Outer PR.** If the change required matching mdlout.py edits, include
   those in the same outer-repo commit (or a follow-up). Open the outer PR.

**First-time setup for contributors.** A fresh clone is missing `lout/`
contents and is on the submodule's default branch (which lacks `z53.c`).
Always run:

```
git submodule update --init
cd lout && git checkout svg-backend && cd ..
```

The build target afterwards is `cd lout && make lout` (just the `lout`
binary; `make all` also builds `prg2lout` which mdlout does not use).

**Don't push submodule changes from inside the outer repo's commit.**
Always commit and push within `lout/` first, *then* bump the outer
pointer. The reverse order leaves the outer repo pointing at a SHA that
does not exist on the remote.

## Filing an issue

Useful contents for a bug report:

- The exact command line (`./mdlout.py ... --format=...`)
- The input markdown (or a minimal reduction)
- The expected output and the actual output
- The lout submodule SHA (`cd lout && git rev-parse HEAD`)
- The output of `./mdlout.py --version` if relevant
- Platform: OS, Python version, GCC/clang version for lout-side bugs

For rendering bugs, attaching both the PDF and the HTML (or screenshots
of each) makes the divergence easy to see. For the SVG path specifically,
including the intermediate `.svg` file (`./mdlout.py input.md --lout-only`
then run `lout -G` by hand, or grab it from a `--watch` build directory)
is the most useful data point.

## License

Lout under `lout/` is GPLv3, copyright 1994-2023 Jeffrey H. Kingston. The
mdlout converter (`mdlout.py`) follows the same license unless noted
otherwise. Contributions are accepted under the same terms.
