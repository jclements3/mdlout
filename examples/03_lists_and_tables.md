---
page: Letter
---

# Lists and tables

A bullet list of typesetting systems:

- TeX, the venerable original
- Lout, Kingston's stream-based alternative
- Groff, the troff descendant powering Unix man pages
- SILE, a modern Lua-driven engine

A numbered list of build steps:

1. Run the markdown parser to produce a block list.
2. Walk the blocks and emit Lout source.
3. Invoke the `lout` binary to render PostScript or SVG.
4. Wrap the result in HTML or convert to PDF.

A task list tracking the macros work:

- [x] Text emission
- [x] Page geometry
- [ ] Colour pipeline
- [ ] `@Math` / `@ABC` / `@SVG` passthrough macros

A definition list of Lout symbols:

Galley
:   Lout's fundamental unit of vertical flow — a column of text that gets
    attached into a target.

@Display
:   A centred, indented block — the workhorse for figures and equations.

@PP
:   Start a new paragraph with the configured paragraph gap.

A pipe table of common Lout document types (note the alignment markers in
the separator row: left-aligned, centred, right-aligned):

| Type    |  Package   |          Headings  |
|:--------|:----------:|-------------------:|
| doc     | `doc`      | `@Display` styled  |
| report  | `report`   | `@Section`         |
| book    | `book`     | `@Chapter`         |
| slides  | `slides`   | `@Overhead`        |

And a grid table for cell wrapping:

+---------------+-----------------------------+-------------+
| Feature       | Status                      | Owner       |
+===============+=============================+=============+
| Text          | Working                     | core        |
+---------------+-----------------------------+-------------+
| Fonts         | Working                     | core        |
+---------------+-----------------------------+-------------+
| Colour        | In progress                 | macros      |
+---------------+-----------------------------+-------------+
| SVG raw       | In progress                 | macros      |
+---------------+-----------------------------+-------------+
