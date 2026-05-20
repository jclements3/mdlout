# mdlout TODO

Roadmap for the SVG/HTML output path of mdlout, driven by the new SVG
back-end (`z53.c`) in the C Lout fork (`jclements3/lout`, branch
`svg-backend`).

## Status as of 2026-05-20 (overnight session close)

Working:

  - Text content -- font family, size, weight, slope, colour, kerning,
    word spacing -- through the SVG back-end.
  - Page chrome -- `<svg>` per page, viewBox in points, coordinate flip.
  - Cross-references converge in SVG mode (bibliography / references /
    index back-matter all present); 327 SVG pages = 327 PS pages.
  - Shapes from `@Graphic`: lines, arcs, circles, rectangles, paths,
    arrows, curved boxes, shadow boxes -- all via the embedded PS
    interpreter inside z53.c (with mark-and-sweep dict GC).
  - The full `@Diag` arrowstyle gallery (solid / open / halfopen /
    curvedsolid / curvedopen / curvedhalfopen / solidwithbar / circle
    / box / many).
  - All 8 named Lout textures (striped / grid / dotted / chessboard
    / brickwork / honeycomb / triangular / string) render as SVG
    `<pattern>` defs.
  - `@Graph` plot symbols at the right size (font-scale propagates).
  - Colour propagation through `@Graphic` blocks (colour gallery,
    paint{}, fraction bars, painted boxes).
  - `@Math` passthrough via KaTeX (client-side render in HTML mode).
  - `@ABC` passthrough via abcjsharp (client-side render in HTML mode).
  - `@SVG` and `@SVGFile` raw passthrough.
  - HTML wrapper, `--format` flag, `--watch`, `--serve [PORT]`.
  - mdlout markdown routing to all three new macros.
  - 27-snippet regression suite under `tests/` (`bash tests/run_all.sh`).
  - 10 example documents under `examples/`, 18 reference outputs
    committed under `examples/out/`.
  - Per-page User's Guide diff report under `tests/user_guide_diff/`
    (327/327 pages, 0 BAD, 0 missing, 36 at <5%, 291 at 5-20%).

Partial / lower priority:

  - Pagination drift on long prose pages between the rsvg-rendered
    SVG and the Ghostscript-rendered PS.  Both back-ends emit
    IDENTICAL line breaks (same Lout galley engine, same font
    metrics) so the page COUNTS match (327 = 327), but the
    rasterisers pick subtly different glyphs for "Times" /
    "Helvetica" via OS font fallback, leaving cumulative pixel
    drift visible to the AE metric.

    Mitigation landed: mdlout's HTML wrapper now embeds the URW++
    Nimbus base-35 fonts as @font-face data URLs mapped to Times /
    Helvetica / Courier (Adobe metric equivalents that Ghostscript
    itself uses).  Browser rendering of mdlout's HTML output will
    therefore use the same metrics PS uses, eliminating the drift.
    The rsvg-convert pipeline used by `tests/user_guide_diff.sh`
    can't honour @font-face data URLs and so still shows the drift
    in that report.

  - Raw `@Graphic` PostScript content that doesn't start with `<` is
    still emitted as an XML comment when the embedded interpreter
    can't fully evaluate it.  The interpreter has gotten broad
    enough that this is rare in the user guide but still possible
    in arbitrary external `@Graphic` payloads.

Recently fixed (this overnight session):

  - 21-page bibliography/references/index gap (SVG_NullBackEnd
    rewire).
  - @Graph plot-symbol sizing (~5x bug) on user-guide pages 248,
    262.
  - @GraphSquare/Plus/Diamond/Circle/Triangle symbol-legend
    stroke-width on user-guide pages 256, 264 (was 5-25pt, now
    hairline).
  - Dict-pool leak via tag-dicts causing thin connector strokes to
    drop out on later @Diag pages (mark-and-sweep GC).
  - All 8 named Lout textures (striped/grid/dotted/chessboard/
    brickwork/honeycomb/triangular/string) render as SVG
    <pattern> defs.
  - Colour propagation through @Graphic blocks (chapter 8 colour
    gallery, @Box paint{...}, math fraction bars and radicals).

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
