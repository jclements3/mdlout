# Test snippets

Per-feature regression corpus for mdlout's SVG back end (`lout/z53.c`).
Each `.lt` is a minimal Lout document that targets one or two features,
small enough to read top-to-bottom in under a minute and to render in
under a second through either back end.

The orchestrator `bash tests/run_all.sh` (one level up) feeds every
`*.lt` here through both back ends, rasterises the two outputs to PNG,
diffs them, and writes `tests/report.html`.  See
[`../README.md`](../README.md) for the framework and
[`../../docs/z53_internals.md`](../../docs/z53_internals.md) for what
the SVG back end actually does with each construct exercised below.

## Tiers and thresholds

Two tiers are used.  The classifier (`tests/compare.py`) decides which
applies by checking the snippet name against the `GRAPHICS_HEAVY`
manifest at the top of that file.

| Tier       | Pixel-diff threshold | SSIM threshold       | Used for                                                |
|------------|----------------------|----------------------|---------------------------------------------------------|
| `strict`   | AE-ratio &lt; 5 %    | SSIM &ge; 0.85       | Text-heavy snippets.  Excellent gate: SSIM &ge; 0.95.   |
| `graphics` | AE-ratio &lt; 2 %    | SSIM &ge; 0.95       | Anything in the `GRAPHICS_HEAVY` set in `compare.py`.   |

The graphics-heavy tier used to be `< 20 %` / `>= 0.75` SSIM back when
the `@Graphic` raw-PostScript path emitted an XML comment fallback.
With the embedded PS interpreter and the Symbol-font glyph table now
in place, every graphics-heavy snippet on the current corpus clears
the strict text gate (worst case as of 2026-05-22: `colour_mixed` at
0.49 % AE-ratio / SSIM 0.9926). The tightened bar above leaves a
~1.5 % pixel-diff margin and a ~0.04 SSIM margin above the
worst-passing snippet to absorb CI jitter; any future regression past
those should be fixed in `z53.c` rather than absorbed by reloosening
the threshold.

A snippet that clears the strict pixel gate and the 0.95 SSIM gate is
recorded as `PASS-EXCELLENT`; one that only clears the looser pair is
`PASS`; anything else is `FAIL`.

## Index

Snippets are listed alphabetically.  "Doc-source chapter" cross-refs the
Lout User's Guide chapter (`lout/doc/user/`) whose features the snippet
exercises; an em-dash means the snippet is purely an mdlout / pipeline
fixture rather than a slice of the User's Guide.

| Snippet                       | Doc-source chapter          | Feature(s)                                              | Tier      | Notes |
|---|---|---|---|---|
| `abc_chords.lt`               | --                          | Two-row `@Tab` standing in for an ABC music progression (chord names over beat counts) | strict    | `@ABC` itself diverges between back ends (SVG passes the source to abcjs; PS prints a bracketed fallback), so the snippet uses a plain table that both back ends can render. |
| `arrow_into_circle.lt`        | Diagrams: arrowheads        | Curved arrowhead tangency on circle boundary           | graphics  |       |
| `box_curve.lt`                | Basic objects: shapes       | `@CurveBox`                                            | strict    |       |
| `box_shadow.lt`               | Basic objects: shapes       | `@ShadowBox`                                           | graphics  |       |
| `box_shadow_overlap.lt`       | Basic objects: shapes       | Multiple overlapping `@ShadowBox`, z-order             | strict    |       |
| `box_simple.lt`               | Basic objects: shapes       | `@Box`                                                 | strict    |       |
| `bullet_list.lt`              | Lists                       | `@WideTaggedList` with `@Bullet`                       | strict    |       |
| `cite_basic.lt`               | References                  | Manual `[1]`/`[2]` references + handmade bibliography  | strict    |       |
| `code_highlight.lt`           | --                          | mdlout's PDF-mode `@Verbatim` fallback for fenced code | strict    |       |
| `colour_mixed.lt`             | Colour                      | Coloured text + `@Box` + raw-PS line side by side      | graphics  |       |
| `colour_text.lt`              | Colour                      | Multi-colour text runs                                 | strict    |       |
| `crossref_pageof.lt`          | Cross references and links  | `@PageOf` / `@NumberOf` / `@TitleOf` + `@Tag`          | strict    | Single-pass build leaves placeholders empty in both back ends, so the diff is symmetric.  See `../user_guide_diff/README.md` for the multi-pass story. |
| `diag_arrow_curved.lt`        | Diagrams: arrowheads        | `arrowstyle { curvedsolid }`                           | strict    |       |
| `diag_arrow_solid.lt`         | Diagrams: arrowheads        | `arrowstyle { solid }`                                 | strict    |       |
| `diag_arrowstyle_gallery.lt`  | Diagrams: arrowheads        | Full arrowstyle audit (solid / open / halfopen / solidwithbar / curvedsolid / curvedopen / curvedhalfopen) | strict    | Audit-style snippet; flips colour the moment any arrowhead shape regresses in `z53.c`. |
| `diag_dashed_lines.lt`        | Diagrams: links             | `@Link` with `pathstyle { dashed }`                    | strict    |       |
| `diag_ellipse_with_tag.lt`    | Diagrams: nodes             | `@Ellipse` + external `nodelabel`                      | strict    |       |
| `diag_labels_complex.lt`      | Diagrams: labels            | `nodelabel` / `clabel` / `alabel` / `blabel` / `linklabel` | graphics  |       |
| `diag_multi_link.lt`          | Diagrams                    | K3 node graph                                          | strict    |       |
| `diag_multicol.lt`            | Diagrams                    | `@Diag` inside a multi-column galley                   | strict    |       |
| `diag_syntax.lt`              | Diagrams: syntax diagrams   | `@SyntaxDiag` `@Loop`                                  | strict    |       |
| `diag_tree_simple.lt`         | Diagrams: trees             | `@Tree`, three children                                | strict    |       |
| `display_overhead.lt`         | Displays                    | `@Overhead` (slides) with nested `@Display`            | strict    |       |
| `eq_alignment.lt`             | Equations: matrices         | Multi-line equation system aligned on `=` via `matrix` + `rcol`/`ccol`/`lcol` | strict    |       |
| `eq_basic.lt`                 | Equations                   | `sup` / `sub` baseline cases                           | strict    |       |
| `eq_braced_systems.lt`        | Equations: large fences     | Piecewise function with `left "{"`, column vector with `left [ ... right ]` | strict    |       |
| `eq_continued_fraction.lt`    | Equations: fractions        | Three-level nested `over` (continued + compound)       | strict    |       |
| `eq_integral_summation.lt`    | Equations                   | `int` / `sum` / `over` with limits                     | graphics  |       |
| `eq_matrix.lt`                | Equations: matrices         | 2x2 bracketed matrix                                   | graphics  |       |
| `eq_matrix_3x3.lt`            | Equations: matrices         | 3x3 bracketed matrix                                   | graphics  |       |
| `eq_matrix_4x4.lt`            | Equations: matrices         | 4x4 bracketed matrix with scripted entries             | strict    |       |
| `eq_nested_supsub.lt`         | Equations                   | Deep `sub` / `sup` nesting                             | strict    |       |
| `fig_multi.lt`                | Figures                     | Three `@Fig` figures laid out side-by-side             | graphics  |       |
| `fig_numbering.lt`            | Figures                     | Numbered `@Figure` / `@Table` references               | strict    |       |
| `figure_with_caption.lt`      | Figures                     | `@Figure` float with formal `@Caption` wrapping a `@Diag` | strict    |       |
| `footnote_multiple.lt`        | Footnotes                   | Three `@FootNote` bodies attached to one paragraph     | strict    |       |
| `footnote_wired.lt`           | --                          | mdlout's pandoc-style `@FootNote` wiring               | strict    |       |
| `graph_axes_negative.lt`      | Graphs                      | `@Graph` with origin-crossing axes and negative tick labels (`y = x^3 / 20`) | strict    |       |
| `graph_bar_chart.lt`          | Graphs                      | `@Graph` with `filledyhisto` pairs (bar chart variant) | strict    |       |
| `graph_log_scale.lt`          | Graphs                      | `@Graph` with `ylog { 10 }` exponential plot           | strict    |       |
| `graphic_circle.lt`           | Graphics                    | Filled circle via raw PostScript                       | graphics  |       |
| `graphic_line.lt`             | Graphics                    | Horizontal line via raw PostScript                     | graphics  |       |
| `graphic_stress.lt`           | Graphics                    | CTM + curves + fills + strokes                         | graphics  |       |
| `graphic_trig.lt`             | Graphics                    | Sin/cos/atan inside raw `@Graphic`                     | strict    |       |
| `headings.lt`                 | Displays                    | Three sizes of centred display headings                | strict    |       |
| `include_basic.lt`            | --                          | `@Include` of a tiny fragment file (`include_basic_frag`) co-located in the snippets dir, quoted because of the `../` separator | strict    |       |
| `indented_code.lt`            | --                          | mdlout's `@IndentedDisplay @F @Verbatim` form          | strict    |       |
| `index_basic.lt`              | Indexes                     | `@MakeIndex` + multiple `@Index` entries               | strict    | Single-pass build leaves the index part empty in both back ends; identical symmetric output. |
| `multi_column.lt`             | Galley layout               | Two text blocks composed horizontally                  | strict    |       |
| `numbered_list.lt`            | Lists                       | `@NumberedList` / `@ListItem`                          | strict    |       |
| `paragraph_fill.lt`           | Paragraph breaking          | Lorem ipsum line breaking                              | strict    |       |
| `raw_postscript.lt`           | Graphics                    | Minimal raw-PS `@Graphic`: moveto / lineto / stroke + Times-Roman `show`, exercising the four core primitives of z53.c's PS interpreter | graphics  |       |
| `references_basic.lt`         | References                  | `@SysDatabase` + `@Cite { ... }`                       | strict    | Single-pass build leaves bibliography slot empty in both back ends. |
| `rule_full.lt`                | Displays: rules             | `@FullWidthRule`                                       | graphics  |       |
| `rule_local.lt`               | Displays: rules             | `@LocalWidthRule`                                      | graphics  |       |
| `sym_greek_full.lt`           | Symbols                     | 24 lower/upper Greek pairs                             | strict    | **Waits on Symbol-font glyph table from #90.** Today both back ends produce the same wrong glyphs in lockstep, so the snippet passes; once z53.c picks up the Symbol-glyph map, this becomes the canonical regression detector for that work.  See `../user_guide_diff/README.md`. |
| `sym_special.lt`              | Symbols                     | `@Sym` Greek + maths + arrow                           | strict    | Same caveat as `sym_greek_full.lt`. |
| `syntax_diag_repeat.lt`       | Diagrams: syntax diagrams   | `@SyntaxDiag` `@Repeat`                                | graphics  |       |
| `table_align.lt`              | Tables                      | `@Cell A indent { left | ctr | right }`                | strict    |       |
| `table_longtable.lt`          | Tables                      | Multi-page `@Tbl` via `@NP`                            | strict    |       |
| `table_multi_row.lt`          | Tables                      | Inter-row rules + simulated header band                | strict    |       |
| `table_rotated.lt`            | Tables                      | `@Tab` with `@Rotate { 60d }` header cells             | strict    |       |
| `table_simple.lt`             | Tables                      | `@Tab` with three columns                              | strict    |       |
| `table_spanned_columns.lt`    | Tables: spanning            | `@StartHSpan` / `@HSpan` + `@StartVSpan` / `@VSpan`    | strict    |       |
| `text_basic.lt`               | Galley layout               | Plain paragraph, simple line breaking                  | strict    |       |
| `text_sizes.lt`               | Fonts                       | Six sizes from 8 p to 24 p                             | strict    |       |
| `text_styles.lt`              | Fonts                       | `@B` / `@I` / `@II` runs                               | strict    |       |
| `text_subscript_superscript.lt` | --                        | Chained plain-text `@Sub` / `@Sup` (chemistry, ordinals, indexed bounds) | strict    |       |
| `toc_auto.lt`                 | --                          | mdlout's `[TOC]` placeholder round-trip                | strict    |       |
| `transform_rotate.lt`         | Graphics                    | `@Rotate { 30d }` text                                 | graphics  |       |
| `tree_4level.lt`              | Diagrams: trees             | Four-level `@Tree` with mixed leaf decorations         | strict    |       |
| `tree_deep.lt`                | Diagrams: trees             | Recursive `@Sub` depth                                 | graphics  |       |

## Known to diverge

Currently no snippet here renders as `FAIL` -- every entry above is
`PASS-EXCELLENT` in the latest run (see `tests/report.html`).  The two
named snippets that *will* drift once parallel work lands are:

- **`sym_greek_full.lt`**, **`sym_special.lt`** -- waiting on the
  Symbol-font glyph table being threaded through `z53.c` (issue #90).
  Today the SVG back end emits the same Symbol-font glyph indices that
  the PostScript back end does, so when both are rasterised the pixels
  agree.  Once #90 lands, the SVG side starts emitting *correct* Greek
  glyphs while the PS reference keeps emitting whatever the Symbol-font
  fallback produces.  At that point both of these snippets are expected
  to flip to `FAIL` for one cycle until the PS reference is regenerated
  or the comparison baseline is updated -- the visible diff is the
  point.  See `../user_guide_diff/README.md` for a per-page rendering
  of the same divergence.

If new snippets ever fail, document them in this section with a
one-line "why" and either a tracking issue number or a link to the
relevant entry in `../../TODO.md` / `../../lout/SVG_PORTING.md`.

## Adding a snippet

1. Pick a single feature or interaction that the existing corpus does
   not yet exercise.  Skim `tests/report.html` and the table above to
   confirm.
2. Aim for 5-30 lines of Lout.  Use `@SysInclude { doc }` plus
   whichever package the feature lives in (`eq`, `tbl`, `diag`,
   `graph`, `fig`, ...).  Wrap an `@Doc @Text @Begin` ... `@End @Text`
   block around the body.  For `@Section`-bearing snippets use
   `@SysInclude { report }` (see `references_basic.lt` or
   `crossref_pageof.lt`).
3. Build it once with the SVG back end from `lout/` to confirm no
   crash:

   ```
   cd lout
   ./lout -s -G -I include -D data -F font -C maps -H hyph \
          ../tests/snippets/your_snippet.lt > /tmp/out.svg
   ```

4. Run `bash tests/run_all.sh` from the repo root and check
   `tests/report.html`.  If the snippet is graphics-heavy, also add it
   to the `GRAPHICS_HEAVY` set in `tests/compare.py` -- but coordinate
   that change with whoever maintains `compare.py` rather than editing
   it from this directory.
5. Append a row to the table above.
