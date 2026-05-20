# mdlout TODO

Roadmap for adding HTML/SVG output to mdlout, driven by a new SVG
back-end in the C Lout fork. No prose outside the bracketed task
lists. ASCII only.

## Goal

Add HTML/SVG output as mdlout's primary format. Implement a new SVG
back-end (z53.c) in the C Lout fork that mirrors z49.c (PostScript)
capability-for-capability -- galleys, line breaking, @Graphic, @Diag,
@Fig, @Tab, every drawing primitive -- emitting SVG drawing commands
instead of PostScript. mdlout wraps that SVG in an HTML scaffold and
loads KaTeX (for @Math) and abcjsharp (for @ABC) for the two
capabilities Lout does not have natively. @SVG is a third passthrough
macro for raw SVG inclusion.

The existing PostScript path (z49.c -> ps -> pdf) is FROZEN. The
work is purely additive: new z53.c, new macros in lout/include/, and
HTML-wrapping + --format flag in mdlout.py.

## Strategy

  Markdown -> .lt (mdlout)   [unchanged, but emits new macros for
                              math, music, raw SVG]

  .lt -> .svg (Lout, NEW)    [new SVG back-end z53.c selected by
                              -Z svg or similar Lout flag]

  .svg -> .html (mdlout)     [thin wrapper: <html><body>{svg}</body>
                              + KaTeX script + abcjsharp script]

mdlout default flips to --format=html. --format=pdf preserves the
existing PostScript-via-Lout pipeline bit-identically.


## 1. SVG Back-end (lout/z53.c)

### 1.1 Survey and scaffolding

  - [ ] Read z49.c (PostScript back-end) end-to-end. Map every
        emission point (text, rule, path, font setup, page begin/end,
        color command, graphic include) to its SVG equivalent.
        Output a short porting plan as a file in the repo
        (lout/SVG_PORTING.md or similar).
  - [ ] Read externs.h:2073-2116 to confirm the BACK_END struct's
        function-pointer signatures. List every callback the SVG
        back-end must implement.
  - [ ] Create lout/z53.c with stub implementations of every
        BACK_END callback (no emission yet); register it in
        z01.c:689-705 alongside Plain/PS/PDF.
  - [ ] Add a Lout CLI flag (-Z svg or similar) to select the new
        back-end. Compile clean with the existing makefile.

### 1.2 Page and document setup

  - [ ] PrintInitialize: emit the <?xml ...?> declaration and root
        <svg> with appropriate width/height and viewBox derived
        from Lout's page geometry (points; convert to SVG units).
  - [ ] BeforeFile / AfterFile: open/close <svg> tags per page,
        OR emit one <g class="page"> per page if multi-page output
        is wrapped in one root <svg>. Decide multi-page strategy
        early; prefer one-svg-per-page for clean print CSS.
  - [ ] Coordinate system: SVG origin is top-left; Lout's is
        bottom-left. Choose: emit a viewBox flip, or transform
        every y coordinate. The viewBox approach is cleaner.

### 1.3 Text emission

  - [ ] PrintWord: emit <text x=".." y=".." font-family=".."
        font-size="..">...</text> with proper escaping (XML entities
        for <, >, &, ", ').
  - [ ] Font setup callbacks (PrintFontDef, etc.): map Lout font
        names to font-family CSS strings; for now use the literal
        Lout font name as the family value (Times, Helvetica, etc.).
        Real font embedding is later work.
  - [ ] Kerning and word spacing: SVG can use letter-spacing or
        explicit x positions per glyph; default to per-word
        positioning to match Lout's expectations.

### 1.4 Rule and graphic primitives

  - [ ] PrintRule / horizontal and vertical rules: emit <line> or
        <rect> in SVG.
  - [ ] Path emission for @Graphic content: Lout's @Graphic passes
        raw PostScript drawing commands through. The SVG back-end
        must translate the common PS ops to SVG path data:
          moveto/lineto/curveto -> SVG path M/L/C
          stroke/fill            -> SVG stroke/fill attributes
          setrgbcolor            -> stroke="rgb(..)" / fill="rgb(..)"
          setlinewidth           -> stroke-width=".."
          dash patterns          -> stroke-dasharray=".."
          translate/rotate/scale -> nested <g transform="..">
        Document the unsupported ops; emit a comment marker for any
        op the translator cannot handle so output remains valid SVG.
  - [ ] @Diag / @Fig / @Tab use the same underlying primitives;
        verify they render correctly after the above translation.

### 1.5 Colour

  - [ ] Use the same colour-name table the PostScript back-end
        consults (z42.c). Map ColourCommand output (PS string like
        "0.5 0.5 0.5 setrgbcolor") into SVG fill/stroke attributes.

### 1.6 Embedded raster and SVG passthrough

  - [ ] @IncludeGraphic { foo.eps }: for SVG output, support
        @IncludeGraphic { foo.svg } directly (raw SVG file
        inclusion as a nested <svg> or <use href="..">). EPS files
        are not supported in SVG mode (document this).
  - [ ] @IncludeGraphic { foo.png } / .jpg: emit as <image>
        with the file path or base64-embedded data.

### 1.7 Cross-references and links

  - [ ] @PageMark / @PageOf produce SVG <a xlink:href="#anchor">
        wrappers when the target is in the same document.

### 1.8 Regression baseline

  - [ ] Pick 3-5 small documents from lout/doc/user that exercise
        text, rules, tables, figures, diagrams, and equations. For
        each, generate both PS (existing) and SVG (new). Convert PS
        to PDF and SVG to PDF (via rsvg-convert or chromium-headless)
        and pixel-diff with ImageMagick compare. Commit the
        reference outputs to a test corpus. Target initial parity
        at >95% pixel-identical for text-only docs, >80% for
        graphics-heavy docs.


## 2. New Lout Macros

### 2.1 @Math (LaTeX math passthrough)

  - [ ] Define @Math in lout/include/ such that:
          @Math { x sup 2 + y sup 2 = z sup 2 }
        is recognized.
  - [ ] In the SVG back-end, @Math emits a <foreignObject> wrapping
        a <span class="math">LATEX SOURCE</span> that KaTeX renders
        client-side on page load.
  - [ ] Width/height of the foreignObject: estimate from the LaTeX
        source length (heuristic for now); rely on KaTeX's actual
        rendered geometry post-load (CSS handles overflow). This is
        the one place SVG output cannot be fully build-time-sized.

### 2.2 @ABC (music passthrough)

  - [ ] Define @ABC in lout/include/.
  - [ ] SVG back-end: emit <foreignObject><div class="abc-music"
        data-abc="..."></div></foreignObject>. Startup script
        in the HTML wrapper calls ABCJS.renderAbc on each.
  - [ ] Sizing same caveat as @Math: client-side render decides
        final geometry.

### 2.3 @SVG (raw SVG passthrough)

  - [ ] Define @SVG in lout/include/.
  - [ ] SVG back-end: emit the macro argument verbatim as nested
        SVG. The argument is assumed to be well-formed SVG fragment
        markup.
  - [ ] @SVGFile { path.svg }: read external SVG file and inline its
        <svg> root as <g>.


## 3. mdlout HTML Wrapper

### 3.1 --format flag

  - [ ] Add --format={html,pdf} CLI argument; default html.
  - [ ] --format=pdf preserves today's full pipeline
        (md -> .lt -> .ps -> .pdf) bit-identically.
  - [ ] --format=html runs the pipeline md -> .lt -> .svg (via Lout
        with the new SVG back-end) -> .html (wrap and inject
        KaTeX/abcjsharp).
  - [ ] Output extension inference: in.md -> in.html under html
        mode; in.pdf under pdf mode.

### 3.2 Markdown to macro routing

  - [ ] $$..$$ and ```math fences -> @Math { ... } in the generated
        .lt.
  - [ ] $..$ inline math -> @Math { ... } inline.
  - [ ] ```abc fences -> @ABC { ... }.
  - [ ] ```svg fences -> @SVG { ... }.
  - [ ] Raw SVG file references (e.g. image markdown to a .svg
        file) -> @SVGFile { path }.

### 3.3 HTML scaffold

  - [ ] Single template: <!DOCTYPE html><html><head>...</head>
        <body><main>{svg}</main><script>... KaTeX, abcjsharp ...
        </script></body></html>.
  - [ ] Inline KaTeX (CSS + JS + fonts as base64 woff2) and
        abcjsharp (from /home/clementsj/projects/abcjsharp/dist/)
        in default self-contained mode. Add --external-assets to
        pull from CDN instead.
  - [ ] Page-level CSS: print stylesheet so @page rules and the
        Lout-emitted SVG translate to physical pages when the user
        hits browser Print.

### 3.4 Build orchestration

  - [ ] In html mode, mdlout runs Lout with the SVG back-end flag,
        captures SVG output (single file or per-page concatenation
        depending on 1.2 decision), and runs the wrapper template.
  - [ ] Cache intermediate SVG by source-hash so reruns are fast.


## 4. Examples and Tests

### 4.1 Examples

  - [ ] examples/ with sample .md inputs covering: tables, math
        (@Math), music (@ABC), raw SVG (@SVG), diagrams (Lout's
        @Diag), figures (@Fig), arbitrary @Graphic, multi-column
        report, slide deck.
  - [ ] Each example builds in both html and pdf mode (where Lout
        macros allow). Commit a representative subset of outputs.

### 4.2 Regression test

  - [ ] tests/ with a runner script that walks examples/ and builds
        each in both modes, comparing against committed reference
        outputs. Pixel-diff PDFs via ImageMagick compare; DOM-diff
        HTML via a small Python helper that strips dynamic IDs.


## 5. Documentation

  - [ ] Top-level README.md (currently absent) covering install,
        the two output formats, the new macros, and the new
        --format flag.
  - [ ] Update CLAUDE.md: the new SVG pipeline, --format flag,
        z53.c addition, the three passthrough macros, and where the
        PostScript path lives (untouched).
  - [ ] lout/SVG_PORTING.md: the z49.c -> z53.c emission mapping
        from task 1.1 -- a living doc useful both during initial
        implementation and for future maintenance.


## 6. Orthogonal Future Work (Not for This Cycle)

These are NOT on the critical path and are explicitly out of scope
for this cycle. Listed only so they are not forgotten.

  - [ ] C Lout UTF-8 input layer (z02.c / z03.c / FULL_CHAR widening).
  - [ ] C Lout OpenType metrics loader in z37.c.
  - [ ] C Lout PDF colour completion in z48.c / z50.c (note: only
        relevant if PDF path is ever revisited; PostScript path is
        frozen so PDF is downstream of frozen code).
  - [ ] Font role abstraction in mdlout frontmatter.
  - [ ] CommonMark indented code blocks (currently unsupported).
  - [ ] --watch / --serve modes for live preview.
