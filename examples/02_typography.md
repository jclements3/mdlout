# Typography sampler

mdlout supports the usual collection of inline spans. This paragraph mixes
**bold**, *italic*, and ***bold italic*** with a sprinkling of `inline code`
spans referring to things like `argv[0]` and `os.path.join`.

Strikethrough is rendered with a horizontal rule, so ~~deprecated APIs~~ stand
out clearly next to their replacements. Superscripts work too: water is H^2^O
and the squared term in E = mc^2^ should sit above the baseline.

A second paragraph for paragraph-gap testing. Notice that *underscored italic*
and _alternative italic_ both work, as do **double-star bold** and __double-
underscore bold__. The combination ___triple underscore___ should render the
same as the triple-star form above.

A final paragraph with mixed nesting: a phrase like **bold containing *italic
inside* it** exercises the recursive inline parser, and a backslash-escape such
as \*literal asterisks\* should appear verbatim — not as italics.
