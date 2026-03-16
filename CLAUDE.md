# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **Lout** (version 3.43), a document formatting system written in ANSI C. It reads high-level document descriptions (similar to LaTeX) and produces PostScript, PDF, or plain text output. Created by Jeffrey H. Kingston at the University of Sydney, licensed under GPLv3.

## Build Commands

All commands run from the `lout/` directory:

```bash
cd lout
make all          # Build both lout and prg2lout binaries
make lout         # Build just the lout binary
make prg2lout     # Build just the prg2lout auxiliary program
make clean        # Remove compiled objects and binaries
make test         # Regression test: compares doc/user output against an older lout version
make testclean    # Remove test artifacts from doc/user/
```

The compiler is gcc with `-ansi -std=c99 -pedantic -Wall -O3`. Object files are built in the `lout/` directory (not `src/`). All source files include `externs.h` (in `src/`) as their sole header.

For installation: `make install` copies binaries to `$(PREFIX)/bin` (default `/usr/local`) and libraries to `$(PREFIX)/share/lout-3.43/lib`. The install step also runs `lout -x` to initialize hyphenation and database index files.

## Source Architecture

All C source lives in `lout/src/`. The codebase is split into ~52 modules (`z01.c`–`z52.c`) plus `prg2lout.c` and a single shared header `externs.h`.

Key module groups:

- **Supervisor & main**: `z01.c` — contains `main()`, entry point
- **Lexer/Parser pipeline**: `z02.c` (lexical analyser), `z03.c` (file service), `z04.c` (token service), `z05.c` (definition reader), `z06.c` (parser)
- **Object system**: `z07.c` (object service), `z08.c` (object manifest), `z09.c` (closure expansion)
- **Galley system** (Lout's core layout engine): `z18.c`–`z22.c` — galley transfer, attaching, flushing, sizing, and service
- **Output backends**: `z48.c`/`z50.c` (PDF), `z49.c` (PostScript), `z51.c` (plain text)
- **Typography**: `z11.c` (style), `z13.c` (object breaking), `z14.c` (fill/paragraph breaking), `z36.c` (hyphenation), `z37.c` (font service)
- **Cross-references & databases**: `z10.c`, `z33.c`
- **Symbol table**: `z29.c`, `z30.c`
- **Support**: `z28.c` (errors), `z31.c` (memory allocator), `z39.c` (string handler), `z42.c` (colour), `z43.c` (language), `z52.c` (texture)

`externs.h` defines all shared types, macros, and function prototypes. Build-time configuration (OS, library paths, character sets, locale, debug flags) is set via `-D` flags in the makefile.

## Library Files

- `lout/include/` — Lout package definitions (the standard library): `doc`, `book`, `slides`, `eq` (equations), `fig` (figures), `diag` (diagrams), `graph`, `tab`/`tbl` (tables), language-specific formatting, etc.
- `lout/data/` — database files (`.ld`) and their indexes (`.li`)
- `lout/font/` — Adobe AFM font metrics
- `lout/maps/` — LCM character mapping files
- `lout/hyph/` — hyphenation pattern files (`.lh` source, `.lp` packed)
- `lout/doc/` — documentation source (in Lout format) and pre-built PDFs

## Key Makefile Variables

- `DEBUGGING=1` + `TRACING=-g` enables debug/tracing mode (slower, larger binary)
- `PDF_COMPRESSION=1` + `ZLIB`/`ZLIBPATH` enables compressed PDF output (requires zlib)
- `CHARIN=1` (ISO-LATIN-1 input), `CHAROUT=0` (7-bit ASCII PostScript output) — recommended defaults
- `DESTDIR` support for staged installs

## Testing

`make test` compares PostScript output of `doc/user/all` between the current build and a reference older version (`lout-3.40-18sep20`). The older binary must be installed at `/usr/local/bin/lout-3.40-18sep20`. Output is diffed with `diff --text`.

## mdlout — Markdown to Lout Converter

`mdlout.py` (in repo root) converts Markdown files to Lout source. It's a single-file Python 3.10+ script with no external dependencies.

```bash
./mdlout.py input.md              # produces input.pdf (full pipeline)
./mdlout.py input.md -o out.pdf   # custom output path
./mdlout.py input.md --ps         # stop at PostScript (input.ps)
./mdlout.py input.md --lout-only  # print Lout source to stdout
./mdlout.py input.md --lout-only -o out.lt  # write Lout source to file
```

### Supported Markdown extensions

Headings (H1-H6, ATX and setext), **bold**, *italic*, `inline code`, ~~strikethrough~~, ^superscript^, [links](url) (rendered as footnotes), images, bullet/numbered/task/definition lists, blockquotes, fenced code blocks, pipe and grid tables, horizontal rules, math blocks (`$$` or ````math`), admonitions (`!!! type "title"`), page breaks (`\newpage`), `[TOC]` placeholders, HTML entities, and backslash escapes.

### Raw Lout passthrough

Use a ````lout` fenced code block to inject raw Lout source directly into the output:

    ```lout
    @CentredDisplay @Eq { a sup 2 + b sup 2 = c sup 2 }
    ```

### YAML frontmatter → Lout styling

YAML frontmatter maps to Lout `@Use { @BasicSetup }`, `@Use { @DocumentSetup }`, and type-specific setup clauses. When frontmatter is present, mdlout generates a custom setup instead of using `@SysInclude { doc }`.

```yaml
---
type: report           # doc (default), report, book, slides
title: My Report
author: Jane Doe
font: Helvetica Base 11p
page: Letter           # A4, Letter, etc.
para-indent: 0f
para-gap: 1.0v
page-headers: None     # None, Simple, Titles
columns: 2
---
```

Key frontmatter fields: `font`, `page`, `orientation`, `top-margin`, `foot-margin`, `left-margin`, `right-margin`, `para-gap`, `para-indent`, `language`, `colour`, `heading-font`, `fixed-font`, `columns`, `page-headers`, `contents`, `optimize-pages`. Report adds: `cover`, `date`, `section-numbers`. Book adds: `title-font`, `chapter-font`, `chapter-start`, `chapter-numbers`.

For `type: report`/`book`, markdown `#` headings become Lout `@Section`/`@Chapter` with automatic numbering. For `type: doc` (default), headings render as styled `@Display` blocks.

### mydefs

A `mydefs` file next to the input `.md` is automatically copied into the build directory for Lout to pick up via `@Include { mydefs }`. Use it for raw Lout macro definitions. Alternatively pass `--mydefs path/to/mydefs`.

### Architecture

The converter has four phases: (1) `parse_frontmatter()` extracts YAML config, (2) block-level parser splits markdown into `Block` objects, (3) `convert_inline()` handles inline formatting using a placeholder system that protects code/links from double-escaping, (4) `generate_lout()` produces the preamble (setup clauses from frontmatter) and maps blocks to Lout constructs. For `report`/`book` types, `_generate_sectioned_body()` wraps headings in `@Section @Begin`/`@End` nesting.

The default CLI pipeline is md → .lt → .ps → .pdf. It auto-discovers the lout binary and library paths relative to the script, writes intermediates to a temp directory, runs lout up to 3 times for cross-reference resolution, then calls ps2pdf (Ghostscript) for the final PDF.
