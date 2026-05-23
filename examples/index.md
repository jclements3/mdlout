---
type: doc
title: mdlout documentation index
author: mdlout project
date: 2026-05-23
font: Helvetica Base 11p
page: A4
top-margin: 2.5c
foot-margin: 2.5c
left-margin: 2.5c
right-margin: 2.5c
para-indent: 0f
para-gap: 1.0v
page-headers: None
---

# mdlout documentation index

This page is the single jumping-off point for every piece of mdlout
documentation, every worked example, and every test report. Each link
below resolves relative to `examples/out/index.md.html`, the rendered
form of this file. The Markdown source lives at `examples/index.md`.

## Get started

- [Tutorial](../../docs/tutorial.md) -- a guided path from install to a
  rendered document in eight short sections.

## Browse examples

- [Example gallery (Markdown source)](../gallery.md) -- one entry per
  committed example with thumbnails, frontmatter, and rendered output
  links.
- [Example gallery (rendered HTML)](index.html) -- the same gallery as
  a browser-ready page with embedded thumbnails and preview links.

## Recipe by feature

The [cookbook](../../docs/cookbook.md) collects 35 short, self-contained
recipes. Each entry below jumps to the matching chapter.

- [1. Three-column poster](../../docs/cookbook.md#1-three-column-poster)
- [2. Math-heavy lecture notes](../../docs/cookbook.md#2-math-heavy-lecture-notes)
- [3. Multi-chapter book](../../docs/cookbook.md#3-multi-chapter-book)
- [4. Slides with images](../../docs/cookbook.md#4-slides-with-images)
- [5. Code-heavy manual](../../docs/cookbook.md#5-code-heavy-manual)
- [6. Letterhead / single-page form](../../docs/cookbook.md#6-letterhead--single-page-form)
- [7. Drop caps and pull quotes (raw Lout passthrough)](../../docs/cookbook.md#7-drop-caps-and-pull-quotes-raw-lout-passthrough)
- [8. Inline ABC music notation](../../docs/cookbook.md#8-inline-abc-music-notation)
- [9. Custom mydefs macros (the sidecar file convention)](../../docs/cookbook.md#9-custom-mydefs-macros-the-sidecar-file-convention)
- [10. Tables with alignment markers](../../docs/cookbook.md#10-tables-with-alignment-markers)
- [11. CV / resume layout](../../docs/cookbook.md#11-cv--resume-layout)
- [12. Conference handout](../../docs/cookbook.md#12-conference-handout)
- [13. Exam / quiz paper](../../docs/cookbook.md#13-exam--quiz-paper)
- [14. Scientific report with bibliography](../../docs/cookbook.md#14-scientific-report-with-bibliography)
- [15. Recipe / cookbook page](../../docs/cookbook.md#15-recipe--cookbook-page)
- [16. Mermaid flowchart](../../docs/cookbook.md#16-mermaid-flowchart)
- [17. Marginalia / sidenotes](../../docs/cookbook.md#17-marginalia--sidenotes)
- [18. Multilingual document](../../docs/cookbook.md#18-multilingual-document)
- [19. Footnoted poetry](../../docs/cookbook.md#19-footnoted-poetry)
- [20. Auto-generated TOC + cross-references](../../docs/cookbook.md#20-auto-generated-toc--cross-references)
- [21. Book chapter with epigraph + footnotes](../../docs/cookbook.md#21-book-chapter-with-epigraph--footnotes)
- [22. Two-sided letter](../../docs/cookbook.md#22-two-sided-letter)
- [23. Inline diagrams via @Mermaid in a math-heavy doc](../../docs/cookbook.md#23-inline-diagrams-via-mermaid-in-a-math-heavy-doc)
- [24. Hand-rolled @Graphic SVG diagram](../../docs/cookbook.md#24-hand-rolled-graphic-svg-diagram)
- [25. Embedded ABC sheet music with chord names](../../docs/cookbook.md#25-embedded-abc-sheet-music-with-chord-names)
- [26. Reusable mydefs macros across many documents](../../docs/cookbook.md#26-reusable-mydefs-macros-across-many-documents)
- [27. Tracking changes via @Strike / @Insert](../../docs/cookbook.md#27-tracking-changes-via-strike--insert)
- [28. Calendar grid](../../docs/cookbook.md#28-calendar-grid)
- [29. Index and glossary at the back](../../docs/cookbook.md#29-index-and-glossary-at-the-back)
- [30. Custom page headers/footers per chapter](../../docs/cookbook.md#30-custom-page-headersfooters-per-chapter)
- [31. Numbered theorems, lemmas, and proofs](../../docs/cookbook.md#31-numbered-theorems-lemmas-and-proofs)
- [32. Two-column code with side-by-side annotations](../../docs/cookbook.md#32-two-column-code-with-side-by-side-annotations)
- [33. Including SVG diagrams from external files](../../docs/cookbook.md#33-including-svg-diagrams-from-external-files)
- [34. Using @Strike (strikethrough) from Markdown](../../docs/cookbook.md#34-using-strike-strikethrough-from-markdown)
- [35. Combining columns: 2 with multi-page content](../../docs/cookbook.md#35-combining-columns-2-with-multi-page-content)

## Troubleshooting

- [FAQ](../../docs/FAQ.md) -- common errors, KaTeX/abcjsharp loading
  pitfalls, frontmatter gotchas, and the meaning of every Lout warning
  mdlout has been seen to emit.

## Contribute

- [CONTRIBUTING](../CONTRIBUTING.md) -- coding conventions, the
  examples gauntlet, and how to file a regression-safe PR.
- [ROADMAP](../../ROADMAP.md) -- shipped milestones and the next-up
  features (math autocomplete, native diagram DSL, more page styles).
- [CHANGELOG](../../CHANGELOG.md) -- every tagged release with date
  and one-line summaries of behaviour changes.

## Publish

- [Publishing your document](../PUBLISHING.md) -- author-facing notes
  on font embedding, paper sizes, hosting the rendered HTML, and the
  print-shop handoff.
- [PyPI release process](../../docs/PYPI.md) -- maintainer-facing
  notes on tagging, building the sdist, smoke-testing the wheel, and
  uploading.

## Deep dives

- [Best practices](../../docs/best_practices.md) -- patterns the
  examples corpus has converged on for frontmatter, mydefs hygiene,
  cross-reference stability, and PDF/HTML parity.
- [Architecture](../../docs/ARCHITECTURE.md) -- the four-phase mdlout
  pipeline, where each markdown extension is parsed, and how the SVG
  scaffolding wraps the Lout output.
- [z53.c internals](../../docs/z53_internals.md) -- the SVG back-end
  inside the Lout fork, function by function, with cross-references to
  z49.c.
- [CI](../../docs/CI.md) -- how `bash tests/run_all.sh` is wired into
  GitHub Actions, what each job gates, and where the artifacts land.
- [SVG porting plan](../../lout/SVG_PORTING.md) -- the living function
  table for porting z49.c (PostScript) operators to z53.c (SVG).
- [SVG performance notes](../../lout/SVG_PERFORMANCE.md) -- profiling
  numbers, hot paths in z53.c, and the budget for each emission
  primitive.

## Test reports

- [Snippet regression report](../../tests/report.html) -- per-snippet
  pass/fail with side-by-side PostScript vs SVG renderings.
- [User-guide diff report](../../tests/user_guide_diff/README.md) --
  the full Lout user guide, page-for-page, before and after the SVG
  back-end.
- [Lout doc renders](../../tests/lout_doc_renders/README.md) -- every
  document under `lout/doc/` rebuilt under both back-ends.
- [Profile output](../../tests/profile/README.md) -- gprof and
  callgrind captures from the heavy user-guide build.
- [Snippet history](../../tests/snippet_history.html) -- per-commit
  pass-rate trend across the snippet corpus.
- [Build benchmarks](../../tests/bench.html) -- wall-clock and memory
  numbers for the canonical workloads, tracked over time.
