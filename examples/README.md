# mdlout examples

Self-contained Markdown documents that exercise the mdlout feature set. Each
file is meant to be built in both HTML mode (default) and PDF mode, e.g.:

```bash
# from the repo root
./mdlout.py examples/01_hello.md                 # → examples/01_hello.html
./mdlout.py examples/01_hello.md --format=pdf    # → examples/01_hello.pdf
```

| File | Demonstrates |
|------|--------------|
| `01_hello.md`              | Smallest possible smoke test — one paragraph. |
| `02_typography.md`         | Inline spans: bold, italic, bold-italic, code, strikethrough, superscript, nested formatting, backslash escapes. |
| `03_lists_and_tables.md`   | Bullet, numbered, task, and definition lists; pipe and grid tables; `page: Letter` frontmatter. |
| `04_math.md`               | `$$…$$` and fenced ```` ```math ```` blocks, inline `$…$`; integrals, sums, fractions, matrices, aligned equations. |
| `05_music.md`              | Three ABC fenced blocks (melody, melody with chords, harp grand-staff via `%%score`). Routes through `@ABC` when that macro lands. |
| `06_report.md`             | `type: report` frontmatter with cover, TOC, `@Section` nesting, code, math, and a raw-Lout figure block. |
| `07_raw_lout_and_svg.md`   | ```` ```lout ```` and ```` ```svg ```` raw passthrough fences for testing `@SVG` routing. |
| `08_kitchen_sink.md`       | Two-column `type: report` combining every feature above — canonical regression target. |
| `diag_gallery.md`          | Exhaustive `@Diag` gallery: every arrowstyle, shape macro (`@Box`, `@CurveBox`, `@ShadowBox`, `@Square`, `@Diamond`, `@Polygon`, `@Isosceles`, `@Ellipse`, `@Circle`), and `@Tree`. Raw-Lout fences only. |

## Smoke-testing the whole set

```bash
for f in examples/*.md; do
  echo "=== $f ==="
  ./mdlout.py "$f" -o "/tmp/$(basename "${f%.md}.html")" 2>&1 | tail -3
done
```
