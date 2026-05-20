# mdlout TODO

Roadmap for the SVG/HTML output path of mdlout, driven by the new SVG
back-end (`z53.c`) in the C Lout fork (`jclements3/lout`, branch
`svg-backend`).

## Status as of 2026-05-20

Working today:

  - Text content -- font family, size, weight, slope, colour, kerning,
    word spacing -- through the SVG back-end.
  - Page chrome -- `<svg>` per page, viewBox in points, coordinate flip.
  - Simple shapes from `@Graphic` (lines, circles, rectangles, basic paths).
  - The full `@Diag` arrowstyle gallery (solid / hollow / curved / etc.).
  - `@Math` passthrough via KaTeX (client-side render in HTML mode).
  - `@ABC` passthrough via abcjsharp (client-side render in HTML mode).
  - `@SVG` and `@SVGFile` raw passthrough.
  - HTML wrapper, `--format` flag, `--watch`, `--serve [PORT]`.
  - mdlout markdown routing to all three new macros.
  - 26-snippet regression suite under `tests/` (`bash tests/run_all.sh`).
  - 9 example documents under `examples/`.

Partial / in flight:

  - Long-tail of complex `@Diag` layouts (nested trees, dense link
    crossings, custom `@Node` shapes).
  - Graphics-heavy `@Fig` documents from `lout/doc/user`.
  - Corner-case `@Eq` typesetting (large matrices, multi-line aligned
    equations, hand-tuned spacing).
  - Raw PostScript-in-`@Graphic` translation (currently emitted as
    XML comment; only `<...>`-prefixed raw SVG passes through).
  - Pixel-parity tightening: graphics-heavy snippets are above the
    5% threshold but below the 20% relaxed bar.

Frozen / explicitly preserved:

  - PostScript back-end (`z49.c`) -- bit-identical PDF output.
  - PDF pipeline orchestration in `mdlout.py` (`--format=pdf`).


## 1. SVG Back-end (lout/z53.c)

### 1.4 Rule and graphic primitives -- remaining items

  - [ ] Translate the common PostScript ops emitted inside `@Graphic`
        blocks to SVG path data:
          moveto/lineto/curveto -> SVG path M/L/C
          stroke/fill            -> SVG stroke/fill attributes
          setrgbcolor            -> stroke="rgb(..)" / fill="rgb(..)"
          setlinewidth           -> stroke-width=".."
          dash patterns          -> stroke-dasharray=".."
          translate/rotate/scale -> nested <g transform="..">
        Right now the back-end emits the raw PS as an XML comment when
        the buffer doesn't start with `<`. See lout/SVG_PORTING.md.
  - [ ] Audit `@Fig` and complex `@Diag` against the PS reference and
        close the remaining diffs.

### 1.6 Embedded raster and SVG passthrough

  - [ ] Decide: base64-inline raster `@IncludeGraphic` images in self-
        contained HTML mode, or always link by relative path.

### 1.8 Regression baseline

  - [ ] Drive the threshold for graphics-heavy snippets down from 20%
        toward 5% as 1.4 lands.
  - [ ] Add 3-5 documents lifted from `lout/doc/user` to the corpus
        once 1.4 makes them feasible.


## 2. Examples and tests -- remaining items

  - [ ] Commit a representative subset of rendered outputs (HTML and PDF)
        as reference artefacts; current `tests/out/` is .gitignored and
        re-generated on every run.


## 3. Documentation -- remaining items

  - [ ] Keep `lout/SVG_PORTING.md` current as `z53.c` grows. (Living doc.)


## 4. Orthogonal Future Work (Not for This Cycle)

Explicitly out of scope. Listed only so they are not forgotten.

  - [ ] C Lout UTF-8 input layer (z02.c / z03.c / FULL_CHAR widening).
  - [ ] C Lout OpenType metrics loader in z37.c.
  - [ ] C Lout PDF colour completion in z48.c / z50.c (only relevant if
        the PDF path is ever unfrozen).
  - [ ] Font role abstraction in mdlout frontmatter.
  - [ ] CommonMark indented code blocks (currently unsupported).
