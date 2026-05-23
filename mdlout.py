#!/usr/bin/env python3
"""mdlout - Markdown to Lout converter.

Converts Markdown to Lout, then renders to HTML (via Lout's SVG back end)
or to PDF (via Lout's PostScript back end + ps2pdf).

Usage:
    ./mdlout input.md                    # produces input.html (default)
    ./mdlout input.md --format=pdf       # produces input.pdf
    ./mdlout input.md -o out.html        # custom output path
    ./mdlout input.md --lout-only        # print Lout source to stdout
    ./mdlout input.md --ps               # stop at PostScript (input.ps)
"""

from __future__ import annotations

import argparse
import base64
import io
import mimetypes
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


VERSION = "0.2.6"


# ---------------------------------------------------------------------------
# Lout special-character escaping
# ---------------------------------------------------------------------------

# Characters special in Lout: { } @ / | \ & # " ^ ~
_LOUT_SPECIAL = re.compile(r'([{}@/|\\&#"^~])')


def lout_escape(text: str) -> str:
    """Escape characters that are special to Lout.

    Each special char c becomes "c" (Lout's quoting mechanism).
    Double-quote and backslash need an extra layer because '\\' is the
    in-string escape character: '"' -> '"\\""' and '\\' -> '"\\\\"'.
    """
    def _repl(m: re.Match) -> str:
        ch = m.group(1)
        if ch == '"':
            return '"\\""'
        if ch == '\\':
            return '"\\\\"'
        return f'"{ch}"'
    return _LOUT_SPECIAL.sub(_repl, text)


# ---------------------------------------------------------------------------
# Inline Markdown → Lout conversion
# ---------------------------------------------------------------------------
# Strategy: process all markdown formatting spans recursively, converting
# each span's inner text. Only leaf text (no more markdown markers) gets
# lout_escape'd. Protected spans (code, links, images) are extracted first
# into placeholders to prevent their content from being parsed as markdown.

_PH_PREFIX = '\x00PH'
_ph_counter = 0
_ph_store: dict[str, str] = {}

# Global tracker: set to True by any feature that requires the svgmacros
# include (inline math, display math, ABC blocks, raw SVG blocks, SVG image
# refs). Read by _generate_preamble().
_needs_svgmacros: bool = False


# ---------------------------------------------------------------------------
# Citation, figure, and table cross-reference registries
# ---------------------------------------------------------------------------
# These are populated by a pre-pass over the markdown before block parsing
# and read by convert_inline / generate_lout. Cleared at the start of every
# top-level conversion via _reset_xref_state().

# Maps citation key -> sequence number (1-based, first-appearance order)
_cite_order: dict[str, int] = {}
# Maps citation key -> bibliography body markdown string (None if no entry)
_cite_bib: dict[str, str] = {}
# Format ('numeric' or 'alpha'): numeric -> "1", alpha -> "a"
_cite_format: str = 'numeric'

# Maps fig:label -> assigned label string (e.g. "1" or "2.3")
_fig_labels: dict[str, str] = {}
# Maps tab:label -> assigned label string
_tab_labels: dict[str, str] = {}

# Pandoc-style footnotes: [^label] inline ref + [^label]: body definition.
# `_fn_order` records first-appearance order of each label so the rendered
# number matches the position the reader first encounters the ref. `_fn_defs`
# stores the body (markdown) so we can emit it next to the reference (Lout
# @FootNote) and as an HTML footnotes section.
_fn_order: dict[str, int] = {}
_fn_defs: dict[str, str] = {}

# HTML mode capture state.
#   _html_headings:   (level, text, anchor) for every markdown heading, in
#                     document order. Anchors are slugified + deduped. Used
#                     to build the TOC <ul> and the hidden <h1 id="..."> anchor
#                     elements that the scaffold injects above the SVG.
#   _html_toc_requested:
#                     True if [TOC] appeared anywhere in the document; the
#                     scaffold uses this to decide whether to render the
#                     <nav class="toc"> block.
_html_headings: list[tuple[int, str, str]] = []
_html_toc_requested: bool = False

# Alt text for every markdown image / @SVGFile / @IncludeGraphic emitted in
# this build, in document order. Lout's SVG back end produces opaque graphics
# that don't surface their source path or alt text; we keep the markdown
# `![alt](url)` text here so the HTML scaffold can announce them to screen
# readers via a visually-hidden landmark list (one <figure role="img"
# aria-label="..."> per entry).
_html_image_alts: list[tuple[str, str]] = []  # (alt, url)

# Output format the current build targets. Set by _build_once before
# generate_lout runs. Read by code paths that need to emit HTML-specific
# markers (e.g. footnote refs, TOC placeholders) into the Lout stream.
_output_format: str = 'pdf'

# Whether highlight.js syntax highlighting is wired into the HTML output.
# Off when --no-highlight is passed or no code blocks have a language hint.
_highlight_enabled: bool = True
# Set of code-block languages encountered so we know whether to bother
# loading highlight.js at all. Populated by _block_to_lout in HTML mode.
_highlight_langs: set[str] = set()

# True when at least one ```mermaid fence appeared in the document. Read by
# the HTML scaffold to decide whether to inject the mermaid.js engine.
# Cleared by _reset_xref_state at the start of every build.
_has_mermaid: bool = False


def _reset_xref_state() -> None:
    _cite_order.clear()
    _cite_bib.clear()
    _fig_labels.clear()
    _tab_labels.clear()
    _fn_order.clear()
    _fn_defs.clear()
    _html_headings.clear()
    _highlight_langs.clear()
    _html_image_alts.clear()
    global _cite_format, _html_toc_requested, _has_mermaid
    _cite_format = 'numeric'
    _html_toc_requested = False
    _has_mermaid = False


def _cite_render_number(n: int) -> str:
    """Render a 1-based citation number per the configured format."""
    if _cite_format == 'alpha':
        # 1 -> a, 2 -> b, ... 26 -> z, 27 -> aa, etc.
        s = ''
        x = n
        while x > 0:
            x, r = divmod(x - 1, 26)
            s = chr(ord('a') + r) + s
        return s
    return str(n)


# Patterns for citation pre-scanning. Inline cite: [@key] or [@key, locator].
# Bibliography entry (whole line): [@key]: text...
_CITE_BIB_RE = re.compile(r'^\s*\[@([A-Za-z0-9_][A-Za-z0-9_-]*)\]:\s*(.*)$')
_CITE_INLINE_RE = re.compile(r'\[@([A-Za-z0-9_][A-Za-z0-9_-]*)(?:,\s*([^\]]+))?\]')

# Pandoc-style footnotes.
#   - Inline ref:  [^label]   (label = word chars; numeric like ^1 also works)
#   - Definition:  [^label]: body text on this line
# The inline regex deliberately excludes the colon that starts a definition
# so a line like "[^1]: foo" is parsed as a def, not a ref.
_FN_DEF_RE = re.compile(r'^\s*\[\^([A-Za-z0-9_][A-Za-z0-9_-]*)\]:\s*(.*)$')
_FN_INLINE_RE = re.compile(r'\[\^([A-Za-z0-9_][A-Za-z0-9_-]*)\](?!:)')


_SLUG_STRIP_RE = re.compile(r'[^a-z0-9\s-]')
_SLUG_SPACE_RE = re.compile(r'[\s_]+')


def _slugify(text: str) -> str:
    """Markdown-style heading slug: lowercase, non-alnum dropped, runs of
    whitespace/underscores collapsed to a single hyphen. Empty falls back
    to 'section'."""
    s = text.lower()
    s = _SLUG_STRIP_RE.sub('', s)
    s = _SLUG_SPACE_RE.sub('-', s).strip('-')
    return s or 'section'


def _strip_md_inline(text: str) -> str:
    """Quick pass to strip markdown inline markers from heading text so the
    HTML TOC and ids reflect rendered text, not raw markup."""
    s = re.sub(r'`([^`]+)`', r'\1', text)
    s = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'\*(.+?)\*', r'\1', s)
    s = re.sub(r'__(.+?)__', r'\1', s)
    s = re.sub(r'_(.+?)_', r'\1', s)
    s = re.sub(r'~~(.+?)~~', r'\1', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    return s.strip()


def _scan_html_headings(blocks: list[Block]) -> None:
    """Walk parsed blocks once to record (level, text, anchor) for headings.

    Anchors are deduped by appending -2, -3, ... to repeats. Also flips
    _html_toc_requested if any [TOC] block is present.
    """
    global _html_toc_requested
    seen: dict[str, int] = {}
    for b in blocks:
        if b.type == BlockType.TOC:
            _html_toc_requested = True
            continue
        if b.type != BlockType.HEADING:
            continue
        text = _strip_md_inline(b.content)
        base = _slugify(text)
        n = seen.get(base, 0)
        anchor = base if n == 0 else f'{base}-{n + 1}'
        seen[base] = n + 1
        _html_headings.append((b.level, text, anchor))


def _scan_footnotes(md_text: str) -> str:
    """Pre-scan for [^label] refs and [^label]: defs.

    Records first-appearance order in _fn_order and stores bodies in _fn_defs.
    Strips definition lines from the markdown (they'll be re-emitted as the
    HTML footnotes section / are inlined at the Lout reference site).
    """
    out_lines: list[str] = []
    for line in md_text.split('\n'):
        m = _FN_DEF_RE.match(line)
        if m:
            _fn_defs[m.group(1)] = m.group(2).rstrip()
            continue
        for fm in _FN_INLINE_RE.finditer(line):
            lbl = fm.group(1)
            if lbl not in _fn_order:
                _fn_order[lbl] = len(_fn_order) + 1
        out_lines.append(line)
    return '\n'.join(out_lines)


def _scan_citations(md_text: str) -> str:
    """Pre-scan markdown for [@key] cites and [@key]: bibliography entries.

    Side effects:
      - populates _cite_order with first-appearance order of inline cites
      - populates _cite_bib with key -> body for explicit bib entries
    Returns markdown with bibliography lines stripped out (we re-emit them
    later, in cite-order, under the References/Bibliography section). The
    inline [@key] tokens are left in place; convert_inline turns them into
    the rendered number / fallback.
    """
    out_lines: list[str] = []
    for line in md_text.split('\n'):
        m = _CITE_BIB_RE.match(line)
        if m:
            key = m.group(1)
            body = m.group(2).rstrip()
            _cite_bib[key] = body
            # Drop the line entirely; rendering happens via the bib block.
            continue
        # Record inline cite order (first appearance wins).
        for cm in _CITE_INLINE_RE.finditer(line):
            ck = cm.group(1)
            if ck not in _cite_order:
                _cite_order[ck] = len(_cite_order) + 1
        out_lines.append(line)
    return '\n'.join(out_lines)


# Figure label tag: appears immediately after a markdown image, e.g.
#   ![cap](url){#fig:label}
# We only support the leading anchor form (no extra attrs).
_FIG_LABEL_TAG_RE = re.compile(r'\{#(fig:[A-Za-z0-9_-]+)\}')
# Image-with-label pattern: ![alt](url){#fig:label}
_IMG_WITH_LABEL_RE = re.compile(
    r'!\[([^\]]*)\]\(([^)]+)\)\s*\{#(fig:[A-Za-z0-9_-]+)\}'
)
# Table label tag: stand-alone line after a pipe table, e.g. [#tab:label]
_TAB_LABEL_LINE_RE = re.compile(r'^\s*\[#(tab:[A-Za-z0-9_-]+)\]\s*$')


def _scan_fig_tab_labels(md_text: str, doc_type: str) -> None:
    """Walk markdown once to assign figure / table numbers.

    For type='report' or 'book' we prefix the chapter / section-1 counter:
    Figure 2.3 = third figure within the second top-level # heading.
    For other doc types numbers are flat (Figure 1, Figure 2, ...).
    """
    is_sectioned = doc_type in ('report', 'book')
    section_counter = 0
    fig_counter = 0  # in-section count when sectioned, global otherwise
    tab_counter = 0

    lines = md_text.split('\n')
    in_fence = False
    fence_marker = ''
    for raw in lines:
        line = raw.rstrip('\n')
        stripped = line.strip()
        # Track fenced code blocks so labels inside them aren't picked up.
        if not in_fence:
            fm = _FENCED_START_RE.match(stripped) if _indent_level(line) < 4 else None
            if fm:
                in_fence = True
                fence_marker = fm.group(1)[0]
                continue
        else:
            if stripped and stripped[0] == fence_marker and set(stripped) == {fence_marker} and len(stripped) >= 3:
                in_fence = False
            continue

        # Top-level heading bumps the section counter and resets per-section.
        hm = _HEADING_RE.match(stripped)
        if hm and len(hm.group(1)) == 1 and is_sectioned:
            section_counter += 1
            fig_counter = 0
            tab_counter = 0
            continue

        # Figure labels — count every image-with-label occurrence on the line.
        for fm2 in _IMG_WITH_LABEL_RE.finditer(line):
            label = fm2.group(3)
            fig_counter += 1
            if is_sectioned and section_counter > 0:
                _fig_labels[label] = f'{section_counter}.{fig_counter}'
            else:
                _fig_labels[label] = str(fig_counter)

        # Table label: a [#tab:label] line directly after the pipe table.
        tm = _TAB_LABEL_LINE_RE.match(line)
        if tm:
            label = tm.group(1)
            tab_counter += 1
            if is_sectioned and section_counter > 0:
                _tab_labels[label] = f'{section_counter}.{tab_counter}'
            else:
                _tab_labels[label] = str(tab_counter)


# Cross-ref pattern in inline text: @fig:label or @tab:label.
# Trailing punctuation (.,;:!?) is excluded from the label so "see @fig:x."
# leaves the period intact.
_XREF_RE = re.compile(r'@((?:fig|tab):[A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)*)')


def _lout_string_encode(body: str) -> str:
    """Encode an arbitrary string as the body of a Lout "..." literal.

    Lout's lexer:
      - bans literal newlines inside quoted strings (treated as unterminated);
      - treats `\\` as escape: `\\NNN` is octal, anything else is literal.

    So to embed a backslash we double it, a double-quote is `\\"`, and a
    newline becomes `\\012` (octal LF). The encoded body is what goes
    *between* the surrounding double quotes.
    """
    out = []
    for ch in body:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\012')
        elif ch == '\r':
            out.append('\\015')
        else:
            out.append(ch)
    return ''.join(out)


def _ph_put(lout_content: str) -> str:
    """Store Lout content and return a placeholder token."""
    global _ph_counter
    key = f'{_PH_PREFIX}{_ph_counter}\x00'
    _ph_counter += 1
    _ph_store[key] = lout_content
    return key


def _ph_restore(text: str) -> str:
    """Replace all placeholder tokens with their stored Lout content.

    Placeholders are stored in creation order. When a recursive call inside
    an inline span (e.g. ``***x***`` or ``**a *b* c**``) builds a placeholder
    whose stored value itself references earlier placeholders, we must
    substitute outer (later-created) placeholders first so the inner ones
    reappear in ``text`` and can be replaced on subsequent iterations.

    A simple way to guarantee that is to iterate in reverse insertion order:
    a later placeholder's value can only reference *earlier* placeholders
    (they had to exist at the time it was constructed), so by the time we
    reach an earlier key all of its references have been expanded into the
    working text. As a defensive backstop we also loop until the text is
    stable, in case future code introduces forward references.
    """
    while True:
        before = text
        for key, val in reversed(_ph_store.items()):
            text = text.replace(key, val)
        if text == before:
            return text


def _ph_reset() -> None:
    global _ph_counter
    _ph_counter = 0
    _ph_store.clear()


def convert_inline(text: str) -> str:
    """Convert a line of Markdown inline formatting to Lout markup."""
    _ph_reset()
    result = _convert_inline_inner(text)
    return _ph_restore(result)


def _convert_inline_inner(text: str) -> str:
    """Recursive inner conversion — processes markdown spans and escapes leaf text."""
    result = text

    # Phase 1: Extract protected spans (order matters)

    # Inline code FIRST — before math/links/images so that `$...$` inside
    # backticks survives as literal code, and so an inline math expression
    # containing brackets doesn't trigger image/link parsing.
    result = re.sub(
        r'`([^`]+)`',
        lambda m: _ph_put('@F { ' + lout_escape(m.group(1)) + ' }'),
        result,
    )

    # Inline math: \(...\) — body is passed verbatim into @Math as a Lout
    # string. We escape backslashes and double quotes so the body survives
    # Lout's lexer (KaTeX sees the un-doubled backslashes when reading).
    def _math_paren_repl(m: re.Match) -> str:
        body = m.group(1)
        global _needs_svgmacros
        _needs_svgmacros = True
        return _ph_put('@Math { "' + _lout_string_encode(body) + '" }')
    result = re.sub(r'\\\((.+?)\\\)', _math_paren_repl, result, flags=re.DOTALL)

    # Inline math: $...$ — single-dollar pairs. Avoid $$..$$ adjacency, and
    # only match when the content is on one line.
    def _math_dollar_repl(m: re.Match) -> str:
        body = m.group(1)
        global _needs_svgmacros
        _needs_svgmacros = True
        return _ph_put('@Math { "' + _lout_string_encode(body) + '" }')
    result = re.sub(
        r'(?<![\$\\])\$(?!\$)([^\$\n]+?)(?<!\\)\$(?!\$)',
        _math_dollar_repl,
        result,
    )

    # Backslash escapes: \@ \* \_ \` \\ etc.
    result = re.sub(
        r'\\([\\`*_{}[\]()#+\-.!~@|>])',
        lambda m: _ph_put(lout_escape(m.group(1))),
        result,
    )

    # Images-with-label: ![caption](url){#fig:label} — auto-numbered figure.
    # We render a centred display containing the image followed by a
    # caption line "Figure N. <caption>".
    def _labelled_image_repl(m: re.Match) -> str:
        alt = m.group(1)
        url = m.group(2)
        label = m.group(3)
        num = _fig_labels.get(label, '?')
        global _needs_svgmacros
        # Record alt text for HTML a11y annotation. The visible caption is
        # already rendered by Lout below; this list feeds the scaffold's
        # hidden <figure role="img" aria-label> sidecar (screen readers).
        _html_image_alts.append((alt or f'Figure {num}', url))
        if url.lower().endswith('.svg'):
            _needs_svgmacros = True
            graphic = f'@SVGFile {{ "{url}" }}'
        else:
            graphic = f'@IncludeGraphic {{ "{url}" }}'
        cap_inner = _convert_inline_inner(alt) if alt else ''
        cap = (
            f'@CentredDisplay {{ {graphic} }}\n'
            f'@CentredDisplay @B {{ Figure {num}. }} {cap_inner}'
        )
        return _ph_put(cap)
    result = _IMG_WITH_LABEL_RE.sub(_labelled_image_repl, result)

    # Images: ![alt](url) — SVG files get routed through @SVGFile (the SVG
    # back-end inlines the file's contents verbatim); everything else falls
    # back to @IncludeGraphic.
    def _image_repl(m: re.Match) -> str:
        alt = m.group(1)
        url = m.group(2)
        global _needs_svgmacros
        # Capture alt for HTML a11y; Lout's SVG back end doesn't propagate
        # this so we surface it through a hidden landmark in the scaffold.
        _html_image_alts.append((alt or url, url))
        if url.lower().endswith('.svg'):
            _needs_svgmacros = True
            return _ph_put(f'@SVGFile {{ "{url}" }}')
        return _ph_put(f'@IncludeGraphic {{ "{url}" }}')
    result = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _image_repl, result)

    # Pandoc-style citations: [@key] or [@key, locator]. We replace with a
    # superscripted number rendered per _cite_format. If the cite key has
    # no bibliography entry we still number it (the bib block falls back to
    # the cite key in brackets).
    def _cite_repl(m: re.Match) -> str:
        key = m.group(1)
        n = _cite_order.get(key)
        if n is None:
            # Defensive — _scan_citations should have already registered it.
            n = len(_cite_order) + 1
            _cite_order[key] = n
        label = _cite_render_number(n)
        # Numbered superscript: "[1]" raised. Lout's @Sup raises its left arg.
        rendered = '{ "[' + label + ']" } @Sup {}'
        return _ph_put(rendered)
    result = _CITE_INLINE_RE.sub(_cite_repl, result)

    # Cross-references: @fig:label / @tab:label resolved to the assigned
    # number. Unresolved refs render as the literal token so authors notice.
    def _xref_repl(m: re.Match) -> str:
        key = m.group(1)
        if key.startswith('fig:'):
            return _ph_put(_fig_labels.get(key, '?'))
        if key.startswith('tab:'):
            return _ph_put(_tab_labels.get(key, '?'))
        return m.group(0)
    result = _XREF_RE.sub(_xref_repl, result)

    # Pandoc-style footnote refs: [^label]. PDF mode emits a Lout @FootNote
    # so Lout handles page-bottom placement; HTML mode emits only a numbered
    # superscript (the footnotes section is appended once at end-of-doc) so
    # the HTML post-processor can wrap markers in <a> links.
    def _fn_repl(m: re.Match) -> str:
        lbl = m.group(1)
        n = _fn_order.get(lbl)
        if n is None:
            n = len(_fn_order) + 1
            _fn_order[lbl] = n
        if _output_format == 'html':
            return _ph_put(f'{{ "[{n}]" }} @Sup {{}}')
        body_md = _fn_defs.get(lbl, f'[^{lbl}]')
        body_lout = _convert_inline_inner(body_md)
        return _ph_put(
            f'{{ "[{n}]" }} @Sup {{}} @FootNote {{ {body_lout} }}'
        )
    result = _FN_INLINE_RE.sub(_fn_repl, result)

    # Links: [text](url)
    def _link_repl(m: re.Match) -> str:
        link_text = _convert_inline_inner(m.group(1))
        url = m.group(2)
        return _ph_put(f'{link_text} @FootNote {{ @F {{ {lout_escape(url)} }} }}')
    result = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link_repl, result)

    # Phase 2: Convert formatting spans (extract into placeholders so the
    # delimiters don't get escaped and the inner text is recursively processed)

    # Bold+italic: ***text***
    result = re.sub(
        r'\*\*\*(.+?)\*\*\*',
        lambda m: _ph_put('@BI { ' + _convert_inline_inner(m.group(1)) + ' }'),
        result,
    )
    result = re.sub(
        r'___(.+?)___',
        lambda m: _ph_put('@BI { ' + _convert_inline_inner(m.group(1)) + ' }'),
        result,
    )

    # Bold: **text**
    result = re.sub(
        r'\*\*(.+?)\*\*',
        lambda m: _ph_put('@B { ' + _convert_inline_inner(m.group(1)) + ' }'),
        result,
    )
    result = re.sub(
        r'__(.+?)__',
        lambda m: _ph_put('@B { ' + _convert_inline_inner(m.group(1)) + ' }'),
        result,
    )

    # Italic: *text*
    result = re.sub(
        r'(?<![*\w])\*([^*]+?)\*(?![*\w])',
        lambda m: _ph_put('@I { ' + _convert_inline_inner(m.group(1)) + ' }'),
        result,
    )
    result = re.sub(
        r'(?<!\w)_([^_]+?)_(?!\w)',
        lambda m: _ph_put('@I { ' + _convert_inline_inner(m.group(1)) + ' }'),
        result,
    )

    # Strikethrough: ~~text~~ — draw a horizontal rule through the text
    result = re.sub(
        r'~~(.+?)~~',
        lambda m: _ph_put(
            '{ "0 ymark moveto xsize ymark lineto stroke" } @Graphic @OneCol { '
            + _convert_inline_inner(m.group(1)) + ' }'
        ),
        result,
    )

    # Superscript: ^text^
    result = re.sub(
        r'\^([^^]+)\^',
        lambda m: _ph_put('{ ' + _convert_inline_inner(m.group(1)) + ' } @Sup {}'),
        result,
    )

    # Phase 3: Escape remaining plain text (everything not inside a placeholder)
    parts = re.split(f'({re.escape(_PH_PREFIX)}\\d+\x00)', result)
    escaped = []
    for part in parts:
        if part.startswith(_PH_PREFIX):
            escaped.append(part)
        else:
            escaped.append(lout_escape(part))
    result = ''.join(escaped)

    # Phase 4: Handle <br> and HTML entities in the escaped text

    result = result.replace('<br>', '@LP\n')
    result = result.replace('<br"/">', '@LP\n')
    result = result.replace('<br "/">', '@LP\n')

    # HTML entities (after escaping, & became "&", so patterns are "&"entity;)
    _entities = {
        '"&"amp;': '"&"',
        '"&"lt;': '"<"',
        '"&"gt;': '">"',
        '"&"nbsp;': '~',
        '"&"mdash;': '---',
        '"&"ndash;': '--',
        '"&"copy;': '@CopyRight',
        '"&"reg;': '@Register',
        '"&"trade;': '@TradeMark',
        '"&"euro;': '@Euro',
        '"&"pound;': '@Sterling',
        '"&"deg;': '@Degree',
    }
    for ent, repl in _entities.items():
        result = result.replace(ent, repl)

    return result


# ---------------------------------------------------------------------------
# Block-level types
# ---------------------------------------------------------------------------

class BlockType(Enum):
    PARAGRAPH = auto()
    HEADING = auto()
    CODE_BLOCK = auto()
    LOUT_RAW = auto()
    BULLET_LIST = auto()
    NUMBERED_LIST = auto()
    BLOCKQUOTE = auto()
    HORIZONTAL_RULE = auto()
    TABLE = auto()
    DEFINITION_LIST = auto()
    TASK_LIST = auto()
    FOOTNOTE_DEF = auto()
    MATH_BLOCK = auto()
    TOC = auto()
    PAGE_BREAK = auto()
    ADMONITION = auto()
    ABC = auto()
    SVG_RAW = auto()
    MERMAID_BLOCK = auto()


@dataclass
class Block:
    type: BlockType
    content: str = ''
    level: int = 0
    language: str = ''
    rows: list = field(default_factory=list)
    children: list = field(default_factory=list)
    checked: bool | None = None
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)(?:\s+#+)?$')
_BULLET_RE = re.compile(r'^(\s*)[*+-]\s+(.*)')
_NUMBERED_RE = re.compile(r'^(\s*)\d+[.)]\s+(.*)')
_TASK_RE = re.compile(r'^(\s*)[*+-]\s+\[([ xX])\]\s+(.*)')
_BLOCKQUOTE_RE = re.compile(r'^>\s?(.*)')
_HR_RE = re.compile(r'^([-*_])\s*\1\s*\1[\s\1]*$')
_TABLE_SEP_RE = re.compile(r'^\|?[\s:]*-+[\s:|-]*\|?$')
_TABLE_ROW_RE = re.compile(r'^\|(.+)\|$')
_GRID_TABLE_BORDER_RE = re.compile(r'^\+[-=+]+\+$')
_FENCED_START_RE = re.compile(r'^(`{3,}|~{3,})\s*(\w*)\s*$')
_DEF_BODY_RE = re.compile(r'^:\s+(.*)')
_FOOTNOTE_DEF_RE = re.compile(r'^\[\^(\w+)\]:\s+(.*)')
_MATH_BLOCK_RE = re.compile(r'^\$\$\s*$')
_PAGE_BREAK_RE = re.compile(r'^\\newpage\s*$|^---pagebreak---\s*$', re.IGNORECASE)
_TOC_RE = re.compile(r'^\[TOC\]\s*$', re.IGNORECASE)
_ADMONITION_RE = re.compile(r'^!!!\s+(\w+)\s*("([^"]*)")?\s*$')


def _indent_level(line: str) -> int:
    return len(line) - len(line.lstrip())


def _is_grid_table_line(line: str) -> bool:
    s = line.strip()
    return bool(_GRID_TABLE_BORDER_RE.match(s)) or (s.startswith('|') and s.endswith('|'))


def parse_markdown(text: str) -> list[Block]:
    lines = text.split('\n')
    blocks: list[Block] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Page break
        if _PAGE_BREAK_RE.match(stripped):
            blocks.append(Block(type=BlockType.PAGE_BREAK))
            i += 1
            continue

        # TOC
        if _TOC_RE.match(stripped):
            blocks.append(Block(type=BlockType.TOC))
            i += 1
            continue

        # Admonition
        m = _ADMONITION_RE.match(stripped)
        if m:
            adm_type = m.group(1).lower()
            adm_title = m.group(3) or adm_type.capitalize()
            adm_lines = []
            i += 1
            while i < n and (lines[i].startswith('    ') or lines[i].strip() == ''):
                adm_lines.append(lines[i][4:] if lines[i].startswith('    ') else '')
                i += 1
            blocks.append(Block(
                type=BlockType.ADMONITION,
                content='\n'.join(adm_lines).strip(),
                meta={'adm_type': adm_type, 'title': adm_title},
            ))
            continue

        # Fenced code block. A fence indented 4+ spaces is not a fence
        # (CommonMark: indented code block territory); skip the match so
        # documentation that *shows* a fenced block by indenting it doesn't
        # get re-interpreted as a real fence.
        m = _FENCED_START_RE.match(stripped) if _indent_level(line) < 4 else None
        if m:
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            lang = m.group(2).lower()
            code_lines = []
            i += 1
            while i < n:
                cl = lines[i]
                cs = cl.strip()
                if cs == fence_char * len(cs) and len(cs) >= fence_len and len(cs) > 0 and cs[0] == fence_char:
                    i += 1
                    break
                code_lines.append(cl)
                i += 1
            code_text = '\n'.join(code_lines)
            if lang == 'lout':
                blocks.append(Block(type=BlockType.LOUT_RAW, content=code_text))
            elif lang in ('math', 'latex'):
                blocks.append(Block(type=BlockType.MATH_BLOCK, content=code_text))
            elif lang == 'abc':
                blocks.append(Block(type=BlockType.ABC, content=code_text))
            elif lang == 'svg':
                blocks.append(Block(type=BlockType.SVG_RAW, content=code_text))
            elif lang == 'mermaid':
                blocks.append(Block(type=BlockType.MERMAID_BLOCK, content=code_text))
            else:
                blocks.append(Block(type=BlockType.CODE_BLOCK, content=code_text, language=lang))
            continue

        # Math block: $$
        if _MATH_BLOCK_RE.match(stripped):
            math_lines = []
            i += 1
            while i < n and not _MATH_BLOCK_RE.match(lines[i].strip()):
                math_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1
            blocks.append(Block(type=BlockType.MATH_BLOCK, content='\n'.join(math_lines)))
            continue

        # Horizontal rule
        if _HR_RE.match(stripped):
            blocks.append(Block(type=BlockType.HORIZONTAL_RULE))
            i += 1
            continue

        # Heading (ATX)
        m = _HEADING_RE.match(stripped)
        if m:
            blocks.append(Block(type=BlockType.HEADING, level=len(m.group(1)), content=m.group(2)))
            i += 1
            continue

        # Setext headings
        if i + 1 < n:
            ns = lines[i + 1].strip()
            if ns and len(ns) >= 3:
                if all(c == '=' for c in ns):
                    blocks.append(Block(type=BlockType.HEADING, level=1, content=stripped))
                    i += 2
                    continue
                if all(c == '-' for c in ns):
                    blocks.append(Block(type=BlockType.HEADING, level=2, content=stripped))
                    i += 2
                    continue

        # Footnote definition
        m = _FOOTNOTE_DEF_RE.match(stripped)
        if m:
            blocks.append(Block(type=BlockType.FOOTNOTE_DEF, content=m.group(2), meta={'id': m.group(1)}))
            i += 1
            continue

        # Grid table
        if _GRID_TABLE_BORDER_RE.match(stripped):
            table_lines = []
            while i < n and _is_grid_table_line(lines[i]):
                table_lines.append(lines[i])
                i += 1
            blocks.append(_parse_grid_table(table_lines))
            continue

        # Pipe table
        if _TABLE_ROW_RE.match(stripped):
            table_lines = []
            while i < n and (_TABLE_ROW_RE.match(lines[i].strip()) or _TABLE_SEP_RE.match(lines[i].strip())):
                table_lines.append(lines[i].strip())
                i += 1
            tbl = _parse_pipe_table(table_lines)
            # Optional trailing label: a [#tab:label] line directly after.
            # Skip a single blank line between the table and its label.
            j = i
            if j < n and lines[j].strip() == '':
                j += 1
            if j < n:
                tm = _TAB_LABEL_LINE_RE.match(lines[j])
                if tm:
                    tbl.meta['label'] = tm.group(1)
                    i = j + 1
            blocks.append(tbl)
            continue

        # Task list
        m = _TASK_RE.match(line)
        if m:
            items = []
            while i < n and (tm := _TASK_RE.match(lines[i])):
                items.append(Block(type=BlockType.TASK_LIST, content=tm.group(3), checked=tm.group(2).lower() == 'x'))
                i += 1
            blocks.append(Block(type=BlockType.TASK_LIST, children=items))
            continue

        # Bullet list
        if _BULLET_RE.match(line):
            items, i = _parse_list(lines, i, bullet=True)
            blocks.append(Block(type=BlockType.BULLET_LIST, children=items))
            continue

        # Numbered list
        if _NUMBERED_RE.match(line):
            items, i = _parse_list(lines, i, bullet=False)
            blocks.append(Block(type=BlockType.NUMBERED_LIST, children=items))
            continue

        # Definition list
        if i + 1 < n and _DEF_BODY_RE.match(lines[i + 1].strip()):
            dl_items = []
            while i < n:
                term_line = lines[i].strip()
                if not term_line:
                    i += 1
                    continue
                if i + 1 >= n:
                    break
                dm = _DEF_BODY_RE.match(lines[i + 1].strip())
                if not dm:
                    break
                dl_items.append((term_line, dm.group(1)))
                i += 2
            blocks.append(Block(type=BlockType.DEFINITION_LIST, children=dl_items))
            continue

        # Blockquote
        if _BLOCKQUOTE_RE.match(stripped):
            bq_lines = []
            while i < n:
                bm = _BLOCKQUOTE_RE.match(lines[i].strip())
                if bm:
                    bq_lines.append(bm.group(1))
                elif lines[i].strip() == '':
                    bq_lines.append('')
                else:
                    break
                i += 1
            blocks.append(Block(type=BlockType.BLOCKQUOTE, content='\n'.join(bq_lines).strip()))
            continue

        # Indented code block (CommonMark): at a block boundary, a run of
        # lines indented by 4+ spaces (with blank lines optionally between
        # them) is a code block. The leading 4 spaces are stripped from each
        # line. Trailing blank lines are not included in the block.
        if _indent_level(line) >= 4:
            code_lines: list[str] = []
            pending_blanks: list[str] = []
            while i < n:
                cl = lines[i]
                if cl.strip() == '':
                    # Blank lines join the block only if more indented code
                    # follows; otherwise they end it.
                    pending_blanks.append('')
                    i += 1
                    continue
                if _indent_level(cl) >= 4:
                    if pending_blanks:
                        code_lines.extend(pending_blanks)
                        pending_blanks = []
                    code_lines.append(cl[4:])
                    i += 1
                    continue
                break
            # Roll back over any trailing blanks we consumed but didn't
            # attribute to the block, so a following block sees them.
            if pending_blanks:
                i -= len(pending_blanks)
            blocks.append(Block(
                type=BlockType.CODE_BLOCK,
                content='\n'.join(code_lines),
            ))
            continue

        # Paragraph
        para_lines = []
        while i < n:
            cl = lines[i]
            cs = cl.strip()
            if not cs:
                break
            if _HEADING_RE.match(cs) or _HR_RE.match(cs):
                break
            if _indent_level(cl) < 4 and _FENCED_START_RE.match(cs):
                break
            if _BULLET_RE.match(cl) or _NUMBERED_RE.match(cl) or _TASK_RE.match(cl):
                break
            if _BLOCKQUOTE_RE.match(cs):
                break
            if _TABLE_ROW_RE.match(cs) or _GRID_TABLE_BORDER_RE.match(cs):
                break
            if _MATH_BLOCK_RE.match(cs) or _PAGE_BREAK_RE.match(cs) or _TOC_RE.match(cs):
                break
            if _ADMONITION_RE.match(cs):
                break
            if i + 1 < n:
                ns = lines[i + 1].strip()
                if ns and len(ns) >= 3 and (all(c == '=' for c in ns) or all(c == '-' for c in ns)):
                    if para_lines:
                        break
            para_lines.append(cs)
            i += 1

        if para_lines:
            blocks.append(Block(type=BlockType.PARAGRAPH, content=' '.join(para_lines)))
        elif i < n:
            # Safety net: a non-empty line the parser couldn't classify
            # would otherwise loop forever (paragraph loop's lookahead
            # bailed before consuming anything). Treat it as a one-line
            # paragraph and advance.
            blocks.append(Block(type=BlockType.PARAGRAPH, content=stripped))
            i += 1

    return blocks


def _parse_list(lines: list[str], start: int, bullet: bool) -> tuple[list[Block], int]:
    items: list[Block] = []
    pattern = _BULLET_RE if bullet else _NUMBERED_RE
    i = start
    n = len(lines)
    while i < n:
        m = pattern.match(lines[i])
        if m:
            item_text = m.group(2)
            base_indent = len(m.group(1))
            i += 1
            while i < n and lines[i].strip() and not pattern.match(lines[i]) and _indent_level(lines[i]) > base_indent:
                item_text += ' ' + lines[i].strip()
                i += 1
            items.append(Block(
                type=BlockType.BULLET_LIST if bullet else BlockType.NUMBERED_LIST,
                content=item_text,
            ))
        elif lines[i].strip() == '':
            if i + 1 < n and pattern.match(lines[i + 1]):
                i += 1
                continue
            break
        else:
            break
    return items, i


def _parse_pipe_table(table_lines: list[str]) -> Block:
    rows = []
    has_header = False
    aligns: list[str] = []
    for line in table_lines:
        if _TABLE_SEP_RE.match(line):
            has_header = True
            # CommonMark alignment markers:
            #   :---   -> left   (default; explicit)
            #   ---:   -> right
            #   :---:  -> center
            #   ---    -> left   (no marker = default)
            for cell in line.strip().strip('|').split('|'):
                c = cell.strip()
                left = c.startswith(':')
                right = c.endswith(':')
                if left and right:
                    aligns.append('ctr')
                elif right:
                    aligns.append('right')
                elif left:
                    aligns.append('left')
                else:
                    aligns.append('')
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)
    return Block(
        type=BlockType.TABLE,
        rows=rows,
        meta={'has_header': has_header, 'aligns': aligns},
    )


def _parse_grid_table(table_lines: list[str]) -> Block:
    rows = []
    has_header = False
    for line in table_lines:
        stripped = line.strip()
        if _GRID_TABLE_BORDER_RE.match(stripped):
            if '=' in stripped:
                has_header = True
            continue
        if stripped.startswith('|'):
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            rows.append(cells)
    return Block(type=BlockType.TABLE, rows=rows, meta={'has_header': has_header})


# ---------------------------------------------------------------------------
# YAML frontmatter → Lout setup
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown text.

    Returns (frontmatter_dict, remaining_markdown).
    If no frontmatter, returns ({}, original_text).
    """
    if not text.startswith('---'):
        return {}, text
    end = text.find('\n---', 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    rest = text[end + 4:]  # skip past closing ---

    # Simple YAML parser — key: value pairs, plus `key: |` literal blocks for
    # multi-line values (e.g. abstract). The literal block consumes all
    # subsequent indented lines until a less-indented line appears.
    fm: dict[str, str] = {}
    raw_lines = yaml_block.split('\n')
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        if ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip().lower()
            val = val.strip()
            # Literal block: `key: |` (optionally with -/+ chomping marker we ignore)
            if val in ('|', '|-', '|+', '>', '>-', '>+'):
                # Determine base indent from the first non-blank child line.
                fold = val.startswith('>')
                child_lines: list[str] = []
                base_indent = None
                i += 1
                while i < len(raw_lines):
                    child = raw_lines[i]
                    if child.strip() == '':
                        child_lines.append('')
                        i += 1
                        continue
                    ind = len(child) - len(child.lstrip())
                    if base_indent is None:
                        base_indent = ind
                    if ind < base_indent:
                        break
                    child_lines.append(child[base_indent:] if ind >= base_indent else child)
                    i += 1
                # Trim trailing blank lines (default chomp '|' keeps one).
                while child_lines and child_lines[-1] == '':
                    child_lines.pop()
                if fold:
                    # Folded: blank line -> newline, other newlines -> space.
                    text_out: list[str] = []
                    buf: list[str] = []
                    for cl in child_lines:
                        if cl == '':
                            if buf:
                                text_out.append(' '.join(buf))
                                buf = []
                            text_out.append('')
                        else:
                            buf.append(cl)
                    if buf:
                        text_out.append(' '.join(buf))
                    fm[key] = '\n'.join(text_out)
                else:
                    fm[key] = '\n'.join(child_lines)
                continue
            fm[key] = val.strip('"').strip("'")
        i += 1
    return fm, rest


# Map friendly frontmatter keys → Lout @Use option names
_BASIC_SETUP_MAP = {
    'font':             '@InitialFont',
    'break':            '@InitialBreak',
    'language':         '@InitialLanguage',
    'colour':           '@InitialColour',
    'color':            '@InitialColour',
    'background':       '@InitialBackgroundColour',
    'heading-font':     '@HeadingFont',
    'fixed-font':       '@FixedWidthFont',
    'para-gap':         '@ParaGap',
    'para-indent':      '@ParaIndent',
    'display-gap':      '@DisplayGap',
    'display-indent':   '@DisplayIndent',
    'list-gap':         '@ListGap',
    'list-indent':      '@ListIndent',
    'optimize-pages':   '@OptimizePages',
}

_DOC_SETUP_MAP = {
    'page':             '@PageType',
    'page-width':       '@PageWidth',
    'page-height':      '@PageHeight',
    'orientation':      '@PageOrientation',
    'top-margin':       '@TopMargin',
    'foot-margin':      '@FootMargin',
    'left-margin':      '@OddLeftMargin',
    'right-margin':     '@OddRightMargin',
    'columns':          '@ColumnNumber',
    'column-gap':       '@ColumnGap',
    'page-headers':     '@PageHeaders',
    'page-numbers':     '@PageNumbers',
    'contents':         '@MakeContents',
    'index':            '@MakeIndex',
}

# Report-specific
_REPORT_SETUP_MAP = {
    'cover':            '@CoverSheet',
    'date':             '@DateLine',
    'abstract-title':   '@AbstractTitle',
    'section-numbers':  '@SectionNumbers',
}

# Book-specific
_BOOK_SETUP_MAP = {
    'title-font':       '@TitlePageFont',
    'chapter-font':     '@ChapterHeadingFont',
    'chapter-start':    '@ChapterStartPages',
    'section-numbers':  '@SectionNumbers',
    'chapter-numbers':  '@ChapterNumbers',
}

# Slides-specific
_SLIDES_SETUP_MAP = {
    'date':             '@DateLine',
    'title-font':       '@TitlePageFont',
    'lecture-font':     '@LectureHeadingFont',
    'overhead-font':    '@OverheadHeadingFont',
}

# Document type → (package name, setup clause name, type-specific map, entry syntax)
_DOC_TYPES = {
    'doc':     ('doc',    'OrdinarySetup', {},                  '@Doc @Text @Begin', '@End @Text'),
    'report':  ('report', 'ReportSetup',   _REPORT_SETUP_MAP,   None, None),  # special handling
    'book':    ('book',   'BookSetup',      _BOOK_SETUP_MAP,     None, None),
    'slides':  ('slides', 'OverheadSetup',  _SLIDES_SETUP_MAP,   None, None),
}


def _generate_use_block(clause_name: str, option_map: dict, frontmatter: dict) -> str:
    """Generate a @Use { @ClauseName ... } block from frontmatter values."""
    opts = []
    for fm_key, lout_opt in option_map.items():
        if fm_key in frontmatter:
            opts.append(f'  {lout_opt} {{ {frontmatter[fm_key]} }}')
    if opts:
        return f'@Use {{ @{clause_name}\n' + '\n'.join(opts) + '\n}'
    return ''


def _abstract_to_lout(abstract: str) -> str:
    """Convert an abstract value (possibly multi-paragraph) to Lout markup.

    Paragraphs are separated by blank lines and joined with @PP so they fit
    inside an @Abstract { ... } argument. Inline markdown formatting is
    routed through convert_inline so emphasis / cites / xrefs work.
    """
    paras = [p.strip() for p in re.split(r'\n\s*\n', abstract) if p.strip()]
    if not paras:
        return ''
    out = convert_inline(' '.join(paras[0].split()))
    for p in paras[1:]:
        out += '\n@PP\n' + convert_inline(' '.join(p.split()))
    return out


# Heading content that, if seen, indicates the bibliography section where
# auto-generated cite entries should be appended. Case-insensitive.
_BIB_HEADINGS = ('references', 'bibliography', 'works cited')


def _inject_bibliography(blocks: list[Block]) -> list[Block]:
    """Append a numbered list of cited works after the References heading.

    If the markdown contains any [@key] cites, we build a NUMBERED_LIST
    block whose items are the bib bodies in cite-order. The list is
    inserted directly after the last `# References` / `# Bibliography`
    heading. If no such heading exists but we do have cites, we append a
    new H1 plus the list at the end of the document.

    Cites without a matching [@key]: entry render as the literal `[key]`.
    """
    if not _cite_order:
        return blocks
    # Build the list items in cite-order.
    items: list[Block] = []
    for key, _n in sorted(_cite_order.items(), key=lambda kv: kv[1]):
        body = _cite_bib.get(key)
        if body is None:
            body = f'\\[{key}\\]'  # fallback: literal cite key in brackets
        items.append(Block(type=BlockType.NUMBERED_LIST, content=body))
    bib_list = Block(type=BlockType.NUMBERED_LIST, children=items)

    # Find the last References/Bibliography heading.
    insert_after = -1
    for idx, b in enumerate(blocks):
        if b.type == BlockType.HEADING and b.level == 1:
            title_lc = b.content.strip().lower()
            if title_lc in _BIB_HEADINGS:
                insert_after = idx
    if insert_after >= 0:
        # Insert the list right after this heading, replacing any
        # subsequent paragraph blocks that were left over from stripped
        # [@key]: lines (the lines are already gone but stray manually
        # written "[1] ..." paragraphs would still be present — we leave
        # them alone so existing hand-curated reference lists survive).
        return blocks[:insert_after + 1] + [bib_list] + blocks[insert_after + 1:]
    # No References heading: append one.
    return blocks + [
        Block(type=BlockType.HEADING, level=1, content='References'),
        bib_list,
    ]


def _generate_preamble(frontmatter: dict, blocks: list[Block]) -> list[str]:
    """Generate the Lout preamble (includes, @Use blocks, document entry)."""
    parts: list[str] = []

    doc_type = frontmatter.get('type', 'doc').lower()
    if doc_type not in _DOC_TYPES:
        doc_type = 'doc'

    pkg, type_clause, type_map, _, _ = _DOC_TYPES[doc_type]

    needs_tbl = any(b.type == BlockType.TABLE for b in blocks)
    # Math blocks now route through @Math (svgmacros), not @Eq — keep the
    # @SysInclude { eq } off unless someone re-introduces a need for it.
    needs_eq = False
    # Auto-detect: if any raw Lout block uses @Diag/@DiagTree/@SyntaxDiag
    # (or the diag-specific shape symbols @Ellipse/@Circle/@Diamond/@Triangle
    # at top level), pull in the diag package. Mirrors the needs_tbl logic.
    # Also strip any user-written `@SysInclude { diag }` from raw lout
    # passthrough so it doesn't appear inside the document body (where it
    # would be a parse error).
    _diag_pat = re.compile(
        r'@(?:Diag|DiagTree|SyntaxDiag|Ellipse|Circle|Diamond|Triangle|Node|Link)\b'
    )
    _diag_include_pat = re.compile(r'@SysInclude\s*\{\s*diag\s*\}')
    needs_diag = False
    for b in blocks:
        if b.type == BlockType.LOUT_RAW:
            if _diag_pat.search(b.content) or _diag_include_pat.search(b.content):
                needs_diag = True
            # Strip user-injected `@SysInclude { diag }`; we'll emit it ourselves
            # in the preamble.
            b.content = _diag_include_pat.sub('', b.content)

    # If no frontmatter overrides, just use @SysInclude { pkg } directly
    has_overrides = any(
        k in frontmatter
        for k in list(_BASIC_SETUP_MAP) + list(_DOC_SETUP_MAP) + list(type_map)
    )

    if not has_overrides:
        if needs_tbl:
            parts.append('@SysInclude { tbl }')
        if needs_eq:
            parts.append('@SysInclude { eq }')
        if needs_diag:
            parts.append('@SysInclude { diag }')
        parts.append(f'@SysInclude {{ {pkg} }}')
        if _needs_svgmacros:
            parts.append('@SysInclude { svgmacros }')
    else:
        # Generate a custom setup: include base packages, mydefs, then @Use blocks
        parts.append('@SysInclude { langdefs }')
        parts.append('@SysInclude { bsf }')
        parts.append('@SysInclude { dsf }')
        if needs_tbl:
            parts.append('@SysInclude { tbl }')
        if needs_eq:
            parts.append('@SysInclude { eq }')
        if needs_diag:
            parts.append('@SysInclude { diag }')

        # Package-specific setup include
        type_include = {'doc': 'docf', 'report': 'reportf', 'book': 'bookf', 'slides': 'slidesf'}
        parts.append(f'@SysInclude {{ {type_include[doc_type]} }}')
        if _needs_svgmacros:
            parts.append('@SysInclude { svgmacros }')
        parts.append('@Include { mydefs }')
        parts.append('')

        # @BasicSetup — slides needs larger font/ragged break by default
        basic_fm = dict(frontmatter)
        if doc_type == 'slides':
            basic_fm.setdefault('font', 'Times Base 20p')
            basic_fm.setdefault('break', 'ragged 1.2fx nohyphen')
        basic = _generate_use_block('BasicSetup', _BASIC_SETUP_MAP, basic_fm)
        parts.append(basic if basic else '@Use { @BasicSetup }')

        # @DocumentSetup
        doc_setup = _generate_use_block('DocumentSetup', _DOC_SETUP_MAP, frontmatter)
        parts.append(doc_setup if doc_setup else '@Use { @DocumentSetup }')

        # Type-specific setup
        if type_map:
            type_setup = _generate_use_block(type_clause, type_map, frontmatter)
            parts.append(type_setup if type_setup else f'@Use {{ @{type_clause} }}')
        else:
            parts.append(f'@Use {{ @{type_clause} }}')

        parts.append('')
        parts.append('@SysDatabase @FontDef { fontdefs }')
        parts.append('@SysDatabase @RefStyle { refstyle }')

    parts.append('')

    # Document entry point
    if doc_type == 'doc':
        parts.append('@Doc @Text @Begin')
    elif doc_type == 'report':
        title = frontmatter.get('title', '')
        author = frontmatter.get('author', '')
        institution = frontmatter.get('institution', '')
        abstract = frontmatter.get('abstract', '')
        entry = '@Report'
        if title:
            entry += f'\n  @Title {{ {title} }}'
        if author:
            entry += f'\n  @Author {{ {author} }}'
        if institution:
            entry += f'\n  @Institution {{ {institution} }}'
        if abstract:
            # Convert markdown inline formatting in the abstract; paragraphs
            # separated by blank lines become @PP-joined.
            abs_lout = _abstract_to_lout(abstract)
            entry += f'\n  @Abstract {{ {abs_lout} }}'
        entry += '\n//'
        parts.append(entry)
    elif doc_type == 'book':
        title = frontmatter.get('title', '')
        author = frontmatter.get('author', '')
        abstract = frontmatter.get('abstract', '')
        entry = '@Book'
        if title:
            entry += f'\n  @Title {{ {title} }}'
        if author:
            entry += f'\n  @Author {{ {author} }}'
        if abstract:
            abs_lout = _abstract_to_lout(abstract)
            entry += f'\n  @Abstract {{ {abs_lout} }}'
        entry += '\n//'
        parts.append(entry)
    elif doc_type == 'slides':
        title = frontmatter.get('title', '')
        author = frontmatter.get('author', '')
        institution = frontmatter.get('institution', '')
        entry = '@OverheadTransparencies'
        if title:
            entry += f'\n  @Title {{ {title} }}'
        if author:
            entry += f'\n  @Author {{ {author} }}'
        if institution:
            entry += f'\n  @Institution {{ {institution} }}'
        entry += '\n//'
        parts.append(entry)

    parts.append('')
    return parts


def _generate_closing(frontmatter: dict) -> str:
    """Generate the document closing tag."""
    doc_type = frontmatter.get('type', 'doc').lower()
    if doc_type == 'doc':
        return '@End @Text'
    # report, book, slides don't need an explicit @End
    return ''


# ---------------------------------------------------------------------------
# Lout code generator
# ---------------------------------------------------------------------------

_HEADING_FONTS = {
    1: '{ Helvetica Bold } @Font { +6p } @Font',
    2: '{ Helvetica Bold } @Font { +4p } @Font',
    3: '{ Helvetica Bold } @Font { +2p } @Font',
    4: '{ Helvetica Bold } @Font { +1p } @Font',
    5: '{ Helvetica Bold } @Font',
    6: '{ Helvetica Base } @Font',
}

_HEADING_GAP = {1: '@DP', 2: '@DP', 3: '@LP', 4: '@LP', 5: '@LP', 6: '@LP'}


def generate_lout(blocks: list[Block], frontmatter: dict | None = None) -> str:
    fm = frontmatter or {}
    doc_type = fm.get('type', 'doc').lower()

    # Generate the body first so `_needs_svgmacros` accumulates from any
    # block that references @Math / @ABC / @SVG / @SVGFile. The preamble
    # then reads that flag to decide whether to @SysInclude { svgmacros }.
    global _needs_svgmacros
    _needs_svgmacros = False

    body_parts: list[str] = []
    if doc_type in ('report', 'book'):
        body_parts.extend(_generate_sectioned_body(blocks, doc_type))
    elif doc_type == 'slides':
        body_parts.extend(_generate_slides_body(blocks))
    else:
        for block in blocks:
            lout = _block_to_lout(block)
            if lout:
                body_parts.append(lout)
                body_parts.append('')

    parts: list[str] = _generate_preamble(fm, blocks)
    parts.extend(body_parts)

    closing = _generate_closing(fm)
    if closing:
        parts.append(closing)
    return '\n'.join(parts)


# Heading level → (Lout command name, Begin/End markers for child sections)
# For book: # → Chapter, ## → Section (children need @BeginSections/@EndSections),
#           ### → SubSection, #### → SubSubSection
# For report: # → Section, ## → SubSection, ### → SubSubSection

_REPORT_LEVELS = {
    1: 'Section',
    2: 'SubSection',
    3: 'SubSubSection',
}

_BOOK_LEVELS = {
    1: 'Chapter',
    2: 'Section',
    3: 'SubSection',
    4: 'SubSubSection',
}

# What @Begin/@End marker wraps child sections at each level
# e.g. Sections inside a Chapter need @BeginSections/@EndSections
_BOOK_CHILD_MARKERS = {
    1: ('Sections', 'Sections'),        # Chapter contains Sections
    2: ('SubSections', 'SubSections'),   # Section contains SubSections
    3: ('SubSubSections', 'SubSubSections'),
}

_REPORT_CHILD_MARKERS = {
    1: ('SubSections', 'SubSections'),   # Section contains SubSections
    2: ('SubSubSections', 'SubSubSections'),
}


def _generate_sectioned_body(blocks: list[Block], doc_type: str) -> list[str]:
    """Generate body with proper @Begin/@End and @BeginXxx/@EndXxx nesting."""
    levels = _BOOK_LEVELS if doc_type == 'book' else _REPORT_LEVELS
    child_markers = _BOOK_CHILD_MARKERS if doc_type == 'book' else _REPORT_CHILD_MARKERS
    parts: list[str] = []

    # Stack tracks (level, has_emitted_begin_children)
    # has_emitted_begin_children is True once we've emitted @BeginSections etc.
    open_stack: list[tuple[int, bool]] = []

    def _close_to(target_level: int) -> None:
        """Close all open levels >= target_level."""
        while open_stack and open_stack[-1][0] >= target_level:
            closed_level, had_children = open_stack.pop()
            cmd = levels[closed_level]
            if had_children and closed_level in child_markers:
                marker = child_markers[closed_level][1]
                parts.append(f'@End{marker}')
                parts.append('')
            parts.append(f'@End @{cmd}')
            parts.append('')

    def _ensure_child_begin(parent_level: int) -> None:
        """Emit @BeginSections etc. for the parent if not already done."""
        if not open_stack:
            return
        top_level, had_children = open_stack[-1]
        if top_level == parent_level and not had_children and parent_level in child_markers:
            marker = child_markers[parent_level][0]
            parts.append(f'@Begin{marker}')
            open_stack[-1] = (top_level, True)

    for block in blocks:
        if block.type == BlockType.HEADING and block.level in levels:
            level = block.level
            # Close sections at this level or deeper
            _close_to(level)
            # If there's a parent, ensure its child-begin marker is emitted
            if open_stack:
                _ensure_child_begin(open_stack[-1][0])
            # Open new section
            cmd = levels[level]
            title = convert_inline(block.content)
            parts.append(f'@{cmd} @Title {{ {title} }} @Begin')
            parts.append('')
            open_stack.append((level, False))
        elif block.type == BlockType.HEADING:
            lout = _block_to_lout(block)
            if lout:
                parts.append(lout)
                parts.append('')
        else:
            lout = _block_to_lout(block)
            if lout:
                parts.append(lout)
                parts.append('')

    # Close all remaining open sections
    _close_to(0)
    return parts


def _generate_slides_body(blocks: list[Block]) -> list[str]:
    """Generate slides body — # headings become @Overhead entries."""
    parts: list[str] = []
    overhead_open = False

    for block in blocks:
        if block.type == BlockType.HEADING and block.level == 1:
            if overhead_open:
                parts.append('@End @Overhead')
                parts.append('')
            title = convert_inline(block.content)
            parts.append(f'@Overhead @Title {{ {title} }} @Begin')
            parts.append('')
            overhead_open = True
        elif block.type == BlockType.HEADING:
            # Sub-headings within a slide render as display headings
            lout = _block_to_lout(block)
            if lout:
                parts.append(lout)
                parts.append('')
        else:
            lout = _block_to_lout(block)
            if lout:
                parts.append(lout)
                parts.append('')

    if overhead_open:
        parts.append('@End @Overhead')
        parts.append('')

    return parts


def _block_to_lout(block: Block) -> str:
    global _needs_svgmacros, _has_mermaid
    match block.type:
        case BlockType.PARAGRAPH:
            return f'@PP\n{convert_inline(block.content)}'
        case BlockType.HEADING:
            level = min(block.level, 6)
            return f'{_HEADING_GAP[level]}\n@Display {_HEADING_FONTS[level]} {{ {convert_inline(block.content)} }}'
        case BlockType.CODE_BLOCK:
            # In HTML mode, route language-tagged code blocks through
            # @SVG so the actual <pre><code class="language-X"> reaches
            # the browser and highlight.js can colour it. Untagged blocks
            # (or PDF/PS mode) still use Lout's @Verbatim layout so the
            # block appears as monospaced text in the printed page.
            lang = (block.language or '').strip().lower()
            if (
                _output_format == 'html'
                and _highlight_enabled
                and lang
                and lang not in ('lout', 'abc', 'svg', 'math', 'latex')
            ):
                _highlight_langs.add(lang)
                _needs_svgmacros = True
                # Each line is one SVG <text>/foreignObject row -- we
                # encode the entire <pre> as one opaque string.
                inner = (
                    f'<foreignObject width="100%" height="100%" '
                    f'class="mdlout-code-fo">'
                    f'<pre class="mdlout-code" '
                    f'xmlns="http://www.w3.org/1999/xhtml">'
                    f'<code class="language-{_html_escape(lang)}">'
                    f'{_html_escape(block.content)}'
                    f'</code></pre></foreignObject>'
                )
                return f'@LP\n@SVG {{ "{_lout_string_encode(inner)}" }}'
            tag = f'# language: {block.language}\n' if block.language else ''
            return f'{tag}@LP\n@IndentedDisplay @F @Verbatim @Begin\n{block.content}\n@End @Verbatim'
        case BlockType.LOUT_RAW:
            return block.content
        case BlockType.BULLET_LIST:
            return _list_to_lout(block, '@BulletList')
        case BlockType.NUMBERED_LIST:
            return _list_to_lout(block, '@NumberedList')
        case BlockType.BLOCKQUOTE:
            inner = parse_markdown(block.content)
            inner_lout = '\n'.join(l for b in inner if (l := _block_to_lout(b)))
            return f'@LP\n@QuotedDisplay @I {{\n{inner_lout or convert_inline(block.content)}\n}}'
        case BlockType.HORIZONTAL_RULE:
            return '@DP\n@FullWidthRule\n@DP'
        case BlockType.TABLE:
            return _table_to_lout(block)
        case BlockType.DEFINITION_LIST:
            parts = ['@LP', '@TaggedList']
            for term, defn in block.children:
                parts.append(f'@TagItem {{ @B {{ {convert_inline(term)} }} }} {{ {convert_inline(defn)} }}')
            parts.append('@EndList')
            return '\n'.join(parts)
        case BlockType.TASK_LIST:
            parts = ['@LP', '@BulletList']
            for item in block.children:
                check = '@B { "[" "x" "]" }' if item.checked else '"[" " " "]"'
                parts.append(f'@ListItem {{ {check} {convert_inline(item.content)} }}')
            parts.append('@EndList')
            return '\n'.join(parts)
        case BlockType.FOOTNOTE_DEF:
            return f'# footnote [{block.meta.get("id", "")}]: {lout_escape(block.content)}'
        case BlockType.MATH_BLOCK:
            _needs_svgmacros = True
            # Pass LaTeX body opaquely through @Math as one Lout string.
            # Normalise newlines: Lout's PS back end emits a
            # "character \012 replaced by space" warning when literal LFs
            # reach @Math (it tries to render them as glyphs). Rules:
            #   * blank line  ->  ' \\ '    (LaTeX line break -- preserves
            #                                visual paragraph separation
            #                                authors typed in the source)
            #   * single LF   ->  ' '        (just whitespace)
            # KaTeX accepts both forms; the warning disappears in PS mode.
            raw = block.content.strip()
            # Split on blank lines first so we can put \\ between groups.
            groups = re.split(r'\n[ \t]*\n', raw)
            joined = []
            for g in groups:
                joined.append(re.sub(r'[\s\t\n]+', ' ', g).strip())
            body = ' \\\\ '.join(p for p in joined if p)
            return f'@LP\n@CentredDisplay @DMath {{ "{_lout_string_encode(body)}" }}'
        case BlockType.ABC:
            _needs_svgmacros = True
            # svgmacros wraps the body in <div data-abc="@Body">.  If the
            # ABC source contains `"`, `<`, `>`, or `&` the surrounding HTML
            # attribute (or, for @Mermaid below, the element text) gets
            # mangled by the browser parser before abcjs/mermaid sees it.
            # HTML-encode first; both engines DOM-decode the textContent /
            # attribute back to the original characters at render time, so
            # the original notation reaches the engine intact.
            return (
                f'@LP\n@ABC {{ '
                f'"{_lout_string_encode(_html_escape(block.content))}" }}'
            )
        case BlockType.MERMAID_BLOCK:
            _needs_svgmacros = True
            _has_mermaid = True
            return (
                f'@LP\n@Mermaid {{ '
                f'"{_lout_string_encode(_html_escape(block.content))}" }}'
            )
        case BlockType.SVG_RAW:
            _needs_svgmacros = True
            return f'@LP\n@SVG {{ "{_lout_string_encode(block.content)}" }}'
        case BlockType.TOC:
            # PDF/PS: Lout's native TOC is emitted automatically by the
            # report/book preamble when `contents: Yes` is in YAML
            # frontmatter -- there's no per-position macro for it. We
            # leave a comment marker so the inline [TOC] position
            # roughly survives in the Lout source for debugging.
            # HTML mode handles the visible TOC via _build_html_toc.
            return '# [Table of Contents placeholder]'
        case BlockType.PAGE_BREAK:
            return '@NP'
        case BlockType.ADMONITION:
            title = block.meta.get('title', 'Note')
            return f'@LP\n@Box margin {{ 0.4c }} {{\n@B {{ {lout_escape(title)} }}\n@LP\n{convert_inline(block.content)}\n}}'
        case _:
            return ''


def _list_to_lout(block: Block, cmd: str) -> str:
    parts = ['@LP', cmd]
    for item in block.children:
        parts.append(f'@ListItem {{ {convert_inline(item.content)} }}')
    parts.append('@EndList')
    return '\n'.join(parts)


def _table_to_lout(block: Block) -> str:
    if not block.rows:
        return ''
    num_cols = max(len(row) for row in block.rows)
    has_header = block.meta.get('has_header', False)
    label = block.meta.get('label')
    # Per-column alignment from the pipe-table separator row
    # (:---/:---:/---:). Missing entries default to left.
    aligns = block.meta.get('aligns', []) or []
    cols = [chr(ord('A') + i) for i in range(min(num_cols, 26))]
    fmt_parts = []
    for idx, c in enumerate(cols[:num_cols]):
        a = aligns[idx] if idx < len(aligns) else ''
        if a in ('right', 'ctr'):
            fmt_parts.append(f'@Cell {c} indent {{ {a} }}')
        else:
            # left is Lout's default -- omit the option to keep the
            # snippet small and the diff vs. pre-alignment output minimal.
            fmt_parts.append(f'@Cell {c}')
    fmt = ' | '.join(fmt_parts)

    parts = ['@LP', '@DP', '@Tbl', f'  rule {{ yes }}', f'  aformat {{ {fmt} }}', '{']
    for ri, row in enumerate(block.rows):
        padded = row + [''] * (num_cols - len(row))
        bold = has_header and ri == 0
        cells = []
        for ci in range(num_cols):
            val = convert_inline(padded[ci])
            if bold:
                val = f'@B {{ {val} }}'
            cells.append(f'{cols[ci]} {{ {val} }}')
        parts.append(f'@Rowa {" ".join(cells)}')
    parts.append('}')
    if label:
        num = _tab_labels.get(label, '?')
        parts.append(f'@CentredDisplay @B {{ Table {num}. }}')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# Lout / ps2pdf runner
# ---------------------------------------------------------------------------

def _find_lout_bin(explicit: str | None) -> str:
    """Locate the lout binary."""
    if explicit:
        return explicit
    # Check next to this script first (common layout: mdlout.py + lout/ dir)
    script_dir = Path(__file__).resolve().parent
    local_lout = script_dir / 'lout' / 'lout'
    if local_lout.is_file() and os.access(local_lout, os.X_OK):
        return str(local_lout)
    return shutil.which('lout') or 'lout'


def _find_lout_lib(lout_bin: str) -> list[str]:
    """Build -I/-H/-D/-C/-F flags if the lout binary lives inside a source tree."""
    lout_path = Path(lout_bin).resolve()
    lout_dir = lout_path.parent
    # Check if the standard library dirs exist next to the binary
    dirs = {
        '-I': 'include',
        '-H': 'hyph',
        '-D': 'data',
        '-C': 'maps',
        '-F': 'font',
    }
    flags: list[str] = []
    for flag, subdir in dirs.items():
        p = lout_dir / subdir
        if p.is_dir():
            flags.extend([flag, str(p)])
    return flags


def _run_lout(lout_bin: str, lout_flags: list[str], lt_file: str, ps_file: str,
              env: dict | None = None) -> None:
    """Run lout up to 3 times to resolve cross-references.

    The optional `env` dict is merged onto the parent environment so
    callers can inject back-end-specific knobs (e.g. LOUT_SVG_FONT_FEATURES
    for the SVG GSUB consumer path) without touching the parent process's
    environment.
    """
    cmd = [lout_bin] + lout_flags + [lt_file, '-o', ps_file]
    if env is not None:
        child_env = os.environ.copy()
        child_env.update(env)
    else:
        child_env = None
    result = None
    for _ in range(3):
        result = subprocess.run(cmd, capture_output=True, text=True,
                                env=child_env)
        if result.stderr and 'unresolved cross reference' in result.stderr:
            continue
        break

    # Print non-cross-ref warnings
    if result and result.stderr:
        for line in result.stderr.splitlines():
            if 'unresolved cross reference' not in line:
                print(line, file=sys.stderr)

    if result and result.returncode != 0:
        print(f'lout exited with code {result.returncode}', file=sys.stderr)
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# HTML scaffold (SVG output + KaTeX + abcjs)
# ---------------------------------------------------------------------------

# Candidate filesystem locations for a locally-installed copy of KaTeX's
# stylesheet. We search these in order; the first match is inlined into the
# generated HTML (so the page renders offline). If none match, we fall
# back to the CDN <link> tag.
_KATEX_CSS_CANDIDATES = (
    '/usr/lib/node_modules/katex/dist/katex.min.css',
    '/usr/share/javascript/katex/katex.min.css',
    '/usr/share/nodejs/katex/dist/katex.min.css',
)

_KATEX_JS_CANDIDATES = (
    '/usr/lib/node_modules/katex/dist/katex.min.js',
    '/usr/share/javascript/katex/katex.min.js',
)

_KATEX_AUTORENDER_CANDIDATES = (
    '/usr/lib/node_modules/katex/dist/contrib/auto-render.min.js',
    '/usr/share/javascript/katex/contrib/auto-render.min.js',
)

_KATEX_CDN_BASE = 'https://cdn.jsdelivr.net/npm/katex@0.16.10/dist'

# abcjsharp lives in the user's fork at ~/projects/abcjsharp.
_ABCJS_DIST_CANDIDATES = (
    str(Path.home() / 'projects' / 'abcjsharp' / 'dist' / 'abcjs-basic-min.js'),
    '/usr/lib/node_modules/abcjs/dist/abcjs-basic-min.js',
)

_ABCJS_CDN = 'https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js'

# Mermaid.js -- flowchart / sequence / class diagram rendering.
# Mirrors the abcjs pattern: prefer a local copy if present, otherwise CDN.
# The CDN URL is overridable via the MDLOUT_MERMAID_URL env var so air-gapped
# builds (or pinning to a specific minor version) need no code change.
_MERMAID_DIST_CANDIDATES = (
    '/usr/lib/node_modules/mermaid/dist/mermaid.min.js',
    '/usr/share/javascript/mermaid/mermaid.min.js',
)
_MERMAID_CDN = os.environ.get(
    'MDLOUT_MERMAID_URL',
    'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js',
)

# highlight.js -- syntax highlighting for fenced code blocks in HTML mode.
# The full common bundle ships ~30 languages and is small enough (~50 kB
# minified) that the CDN cost on the first view is negligible. We don't
# attempt to inline it (no canonical system path exists across distros);
# the spec explicitly allows CDN here.
_HLJS_VERSION = '11.9.0'
_HLJS_CDN_JS = (
    f'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/'
    f'{_HLJS_VERSION}/highlight.min.js'
)
_HLJS_CDN_CSS = (
    f'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/'
    f'{_HLJS_VERSION}/styles/github.min.css'
)
# Local-inline fallback locations (uncommon but supported for offline builds).
_HLJS_JS_CANDIDATES = (
    '/usr/lib/node_modules/highlight.js/lib/highlight.min.js',
    '/usr/share/javascript/highlight.js/highlight.min.js',
)
_HLJS_CSS_CANDIDATES = (
    '/usr/share/javascript/highlight.js/styles/github.min.css',
    '/usr/lib/node_modules/highlight.js/styles/github.min.css',
)


# ---------------------------------------------------------------------------
# Font embedding (PS/SVG metric alignment)
# ---------------------------------------------------------------------------
#
# Lout's PostScript back-end references the 14 Adobe base fonts (Times,
# Helvetica, Courier and their bold/italic variants) using Adobe AFM metrics
# from lout/font/.  Ghostscript ships matching outlines (URW++ Nimbus) so the
# rendered PS pages use those metrics.  Lout's SVG back-end (z53.c) emits
# `font-family="Times"` / `Helvetica` / `Courier` with `font-weight="bold"`
# and `font-style="italic"` attributes — but browsers and librsvg map those
# generic names to whatever system "Times" the OS exposes (Liberation /
# DejaVu / etc.), whose metrics differ slightly from Adobe's.  Cumulative
# drift across a page = misaligned text wraps even though Lout itself
# already broke the lines identically (z37 is the shared font service for
# both back-ends, so positions are byte-identical).
#
# Fix: embed URW++ Nimbus (which Ghostscript itself uses to render the
# Adobe base 14) as @font-face web fonts in the HTML wrapper, mapped to the
# family names the SVG actually references.  Nimbus Roman / Sans / MonoPS
# are open-source equivalents of Adobe Times / Helvetica / Courier with
# nearly identical metrics.
#
# Each entry: (css_family, css_style, css_weight, font_path_candidates).
# Order within each candidate tuple is preferred-first.

_FONT_EMBED_SPECS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    # ---- Times / Nimbus Roman --------------------------------------------
    ('Times', 'normal', 'normal', (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf',
    )),
    ('Times', 'normal', 'bold', (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Bold.otf',
    )),
    ('Times', 'italic', 'normal', (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Italic.otf',
    )),
    ('Times', 'italic', 'bold', (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-BoldItalic.otf',
    )),
    # ---- Helvetica / Nimbus Sans -----------------------------------------
    ('Helvetica', 'normal', 'normal', (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf',
    )),
    ('Helvetica', 'normal', 'bold', (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf',
    )),
    ('Helvetica', 'italic', 'normal', (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Italic.otf',
    )),
    ('Helvetica', 'italic', 'bold', (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-BoldItalic.otf',
    )),
    # ---- Courier / Nimbus Mono PS ----------------------------------------
    ('Courier', 'normal', 'normal', (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf',
    )),
    ('Courier', 'normal', 'bold', (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Bold.otf',
    )),
    ('Courier', 'italic', 'normal', (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Italic.otf',
    )),
    ('Courier', 'italic', 'bold', (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-BoldItalic.otf',
    )),
)


# Regex matching <text>/<tspan> elements in Lout's SVG output and capturing
# their font-family attribute (if any) and inner text.  Lout never nests
# <tspan> with a different family, and never sets font-family on a
# container <g>, so a flat scan is sufficient.  font-weight / font-style
# capture (extracted from the rest of the attrs blob via _ATTR_RE) tells
# us which of the four faces inside a family the run actually uses, but
# from a *subsetting* standpoint we union the codepoints across all four
# faces of a family since users routinely mix weights mid-document and
# the marginal saving from per-face cmap differentiation is small.
_SUBSET_TEXT_RE = re.compile(
    r'<(?:text|tspan)\b([^>]*)>([^<]*)</(?:text|tspan)>',
    re.DOTALL,
)
_SUBSET_FAMILY_RE = re.compile(r'font-family="([^"]*)"')

# Module-level latch: emit the "fontTools not installed" warning at most
# once per process even when --subset-fonts is requested across many
# faces in a single build, or across many builds in --watch / --serve.
_SUBSET_FONTS_WARNED = False


def _subset_fonts(
    svg_text: str,
    fonts_dict: dict[str, bytes],
) -> dict[str, bytes]:
    """Return a dict of {fontname: subsetted_font_bytes}, keeping only
    codepoints actually used in the SVG.

    `fonts_dict` is keyed by the css family name Lout writes into <text>
    (one of "Times", "Helvetica", "Courier" today).  All faces sharing a
    family receive the same codepoint set -- a slight over-keep that
    avoids splitting weight/style buckets across a hot scan, but is still
    typically 90%+ smaller than the full Nimbus base-35 CFF tables.

    If fontTools is unavailable, a warning is emitted to stderr and the
    input dict is returned unchanged so the caller's fallback (full font
    inline) still works.
    """
    try:
        from fontTools.subset import Subsetter, Options
        from fontTools.ttLib import TTFont
    except ImportError:
        global _SUBSET_FONTS_WARNED
        if not _SUBSET_FONTS_WARNED:
            print(
                'mdlout: --subset-fonts requested but fontTools is not '
                'installed; inlining full fonts. '
                'Install with: pip install --user fonttools',
                file=sys.stderr,
            )
            _SUBSET_FONTS_WARNED = True
        return fonts_dict

    # Codepoints in literal Lout-emitted text & XML entity references.
    # We also union in ASCII printable so glyphs used by KaTeX/abcjs at
    # runtime (rendered client-side after page load) keep working when
    # those engines render into the inherited body font-family.  That's
    # a low cost (~95 cps) versus the savings.
    cps_per_family: dict[str, set[int]] = {}
    default_family = 'Times'
    ascii_baseline = set(range(0x20, 0x7F))
    for fam in fonts_dict:
        cps_per_family[fam] = set(ascii_baseline)

    for attrs, body in _SUBSET_TEXT_RE.findall(svg_text):
        m = _SUBSET_FAMILY_RE.search(attrs)
        family = m.group(1) if m else default_family
        if family not in cps_per_family:
            # Skip families we don't have a font for (e.g. Symbol).
            continue
        if not body:
            continue
        # Reverse Lout's five named-entity escapes first.
        body = (body.replace('&lt;', '<')
                    .replace('&gt;', '>')
                    .replace('&quot;', '"')
                    .replace('&apos;', "'")
                    .replace('&amp;', '&'))
        # Numeric character references: &#NNN; / &#xNN;
        def _decode_numref(m: re.Match) -> str:
            try:
                if m.group(1):
                    return chr(int(m.group(1), 16))
                return chr(int(m.group(2)))
            except (ValueError, OverflowError):
                return ''
        body = re.sub(r'&#x([0-9A-Fa-f]+);|&#([0-9]+);', _decode_numref, body)
        cps_per_family[family].update(ord(c) for c in body)

    out: dict[str, bytes] = {}
    for fam, raw in fonts_dict.items():
        cps = cps_per_family.get(fam) or ascii_baseline
        try:
            import io
            font = TTFont(io.BytesIO(raw))
            # Conservative options: drop hinting, layout tables we don't
            # need; keep notdef glyph; ignore missing unicodes so the
            # subset succeeds even if a codepoint isn't in the cmap.
            opts = Options()
            opts.ignore_missing_unicodes = True
            opts.ignore_missing_glyphs = True
            opts.drop_tables += ['DSIG']
            opts.notdef_outline = True
            opts.recommended_glyphs = True
            opts.name_IDs = ['*']
            sub = Subsetter(options=opts)
            sub.populate(unicodes=sorted(cps))
            sub.subset(font)
            buf = io.BytesIO()
            font.save(buf)
            out[fam] = buf.getvalue()
        except Exception as e:
            print(
                f'mdlout: subset of {fam!r} failed ({e}); inlining full font',
                file=sys.stderr,
            )
            out[fam] = raw
    return out


def _build_font_face_css(
    svg_for_subset: str | None = None,
) -> tuple[str, list[str], dict[str, int]]:
    """Build @font-face CSS embedding Nimbus fonts as base64 data URLs.

    Returns (css, used_paths, stats).  If no source files are available
    the CSS is empty and used_paths is [].  Each face is mapped to the
    Adobe family name Lout's SVG back-end references ("Times" /
    "Helvetica" / "Courier"), so an SVG `<text font-family="Times"
    font-weight="bold">` resolves to the embedded Nimbus Roman Bold
    outlines (Ghostscript's own metric source for the Adobe base 14).

    If `svg_for_subset` is non-None, each face is first reduced via
    `_subset_fonts` to the codepoints actually used in that SVG -- a
    typical 70-95% size reduction.  Falls back to full-font inline if
    fontTools is unavailable.
    """
    import base64

    # First pass: load raw bytes for every present face.  We keep the
    # path string around as a stable dict key (face files are unique by
    # path, whereas (family, style, weight) collisions are possible if
    # the spec gains synthetic faces later).
    raw_per_face: list[tuple[str, str, str, str, bytes]] = []  # (family, style, weight, path, bytes)
    for family, style, weight, candidates in _FONT_EMBED_SPECS:
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if path is None:
            continue
        try:
            with open(path, 'rb') as f:
                raw = f.read()
        except OSError:
            continue
        raw_per_face.append((family, style, weight, path, raw))

    stats: dict[str, int] = {'bytes_before': 0, 'bytes_after': 0, 'faces': 0}

    # Optional subset stage.  `_subset_fonts` takes a family-keyed
    # {fontname: bytes} dict and returns the same shape with each face's
    # glyph table reduced to the SVG's actual codepoint set.  We call it
    # once per face -- a single-entry dict each time -- so the function
    # processes each face's table individually while reusing the
    # codepoint-extraction work (the SVG scan is family-scoped and
    # identical across all faces in that family).
    if svg_for_subset is not None and raw_per_face:
        new_raw_per_face: list[tuple[str, str, str, str, bytes]] = []
        for family, style, weight, path, raw in raw_per_face:
            stats['bytes_before'] += len(raw)
            sub_out = _subset_fonts(svg_for_subset, {family: raw})
            new_raw = sub_out.get(family, raw)
            stats['bytes_after'] += len(new_raw)
            stats['faces'] += 1
            new_raw_per_face.append((family, style, weight, path, new_raw))
        raw_per_face = new_raw_per_face

    pieces: list[str] = []
    used: list[str] = []
    for family, style, weight, path, raw in raw_per_face:
        fmt = 'opentype' if path.endswith('.otf') else 'truetype'
        b64 = base64.b64encode(raw).decode('ascii')
        pieces.append(
            "@font-face{"
            f"font-family:'{family}';"
            f"font-style:{style};"
            f"font-weight:{weight};"
            "font-display:block;"
            f"src:url(data:font/{fmt};base64,{b64}) format('{fmt}');"
            "}"
        )
        used.append(path)
    return ''.join(pieces), used, stats


# ---------------------------------------------------------------------------
# Text -> outline paths (closing the last text-rasteriser gap)
# ---------------------------------------------------------------------------
#
# Even with URW++ Nimbus embedded as @font-face, Chrome (Skia) and
# rsvg-convert (Cairo) still rasterise <text> through their own pipelines,
# which paint glyphs slightly differently from Ghostscript when laying out
# the matching PostScript file.  The remaining drift is ~10-20% per page on
# the User's Guide.
#
# To eliminate the text rasteriser entirely we replace every Lout-emitted
# <text> element with vector <path> outlines, taken directly from the
# URW++ Nimbus OpenType files.  Both PS (via Ghostscript's own glyph
# outlines) and the SVG renderers then paint pure vector geometry and the
# anti-aliasing differences shrink to a sub-pixel residue.
#
# Approach:  fontTools loads each Nimbus face once, walks the glyph table
# through an SVGPathPen, and caches glyph_id -> (svg_path_d, advance) on
# disk so repeated builds are cheap.  At convert time _convert_text_to_paths
# scans the SVG with a regex, looks up each character's outline, and emits
# a <g><path .../></g> tree in place of the original <text>.

# Maps Lout-emitted font-family attribute + (bold,italic) tuple to a list of
# candidate OTF paths.  First existing file wins.  Order matters: regional
# package layouts may differ.
_NIMBUS_FACE_CANDIDATES: dict[tuple[str, bool, bool], tuple[str, ...]] = {
    ('Times', False, False): (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf',
    ),
    ('Times', True, False): (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Bold.otf',
    ),
    ('Times', False, True): (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Italic.otf',
    ),
    ('Times', True, True): (
        '/usr/share/fonts/opentype/urw-base35/NimbusRoman-BoldItalic.otf',
    ),
    ('Helvetica', False, False): (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf',
    ),
    ('Helvetica', True, False): (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf',
    ),
    ('Helvetica', False, True): (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-Italic.otf',
    ),
    ('Helvetica', True, True): (
        '/usr/share/fonts/opentype/urw-base35/NimbusSans-BoldItalic.otf',
    ),
    ('Courier', False, False): (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf',
    ),
    ('Courier', True, False): (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Bold.otf',
    ),
    ('Courier', False, True): (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Italic.otf',
    ),
    ('Courier', True, True): (
        '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-BoldItalic.otf',
    ),
}

# Cached glyph DB shared across calls in one process.
# Structure: { (family, bold, italic): (upem, {codepoint: (path_d, advance)}) }
_GLYPH_DB: dict[tuple[str, bool, bool], tuple[int, dict[int, tuple[str, int]]]] | None = None
# Set of (family, bold, italic) keys we already warned about as missing.
_GLYPH_DB_MISSING: set[tuple[str, bool, bool]] = set()


def _glyph_cache_path() -> str:
    """Disk-cache path for the extracted glyph DB.  Keyed by Python+fontTools version."""
    import platform
    pyver = platform.python_version()
    return f'/tmp/mdlout_glyph_cache_py{pyver}.pkl'


def _load_glyph_db() -> dict[tuple[str, bool, bool], tuple[int, dict[int, tuple[str, int]]]]:
    """Load (and cache) glyph outlines for the 12 Adobe-base-14 text faces.

    On first call this opens each Nimbus OTF, walks its glyph table through
    an SVGPathPen and stashes (svg-path-d, advance-width-in-em-units) for
    every codepoint in the font's best cmap.  Result is pickled to /tmp so
    subsequent runs reuse it (~10s -> <100ms).
    """
    global _GLYPH_DB
    if _GLYPH_DB is not None:
        return _GLYPH_DB

    import pickle
    cache = _glyph_cache_path()
    # Validate: cache must be newer than every source font we end up loading.
    paths_needed: list[str] = []
    for cands in _NIMBUS_FACE_CANDIDATES.values():
        for p in cands:
            if os.path.isfile(p):
                paths_needed.append(p)
                break
    cache_ok = False
    if os.path.isfile(cache) and paths_needed:
        try:
            cache_mtime = os.path.getmtime(cache)
            src_mtime = max(os.path.getmtime(p) for p in paths_needed)
            if cache_mtime >= src_mtime:
                with open(cache, 'rb') as f:
                    _GLYPH_DB = pickle.load(f)
                cache_ok = True
        except (OSError, pickle.UnpicklingError, EOFError):
            cache_ok = False
    if cache_ok and _GLYPH_DB is not None:
        return _GLYPH_DB

    try:
        from fontTools.ttLib import TTFont
        from fontTools.pens.svgPathPen import SVGPathPen
    except ImportError as e:
        raise RuntimeError(
            'fontTools is required for --text-as-paths but is not installed. '
            'Install with: pip install fonttools'
        ) from e

    db: dict[tuple[str, bool, bool], tuple[int, dict[int, tuple[str, int]]]] = {}
    for key, cands in _NIMBUS_FACE_CANDIDATES.items():
        path = next((p for p in cands if os.path.isfile(p)), None)
        if path is None:
            continue
        try:
            font = TTFont(path)
        except Exception:
            continue
        upem = font['head'].unitsPerEm
        cmap = font.getBestCmap()
        gs = font.getGlyphSet()
        entries: dict[int, tuple[str, int]] = {}
        for cp, gname in cmap.items():
            try:
                pen = SVGPathPen(gs)
                gs[gname].draw(pen)
                d = pen.getCommands()
            except Exception:
                continue
            try:
                w = int(gs[gname].width)
            except Exception:
                w = 0
            entries[cp] = (d, w)
        db[key] = (int(upem), entries)

    _GLYPH_DB = db
    try:
        with open(cache, 'wb') as f:
            pickle.dump(db, f, protocol=pickle.HIGHEST_PROTOCOL)
    except OSError:
        pass
    return db


# Lout-emitted text elements:
#   <text x="0" y="0" font-family="X" font-size="N.NNN" [font-weight="bold"]
#         [font-style="italic"] [fill="..."]>...</text>
# We deliberately only match elements with x="0" y="0" so the texture
# pattern's <text x="1" y="10" ...>*</text> (inside <defs>) is left alone.
_TEXT_ELEM_RE = re.compile(
    r'<text\s+x="0"\s+y="0"\s+font-family="(?P<family>[^"]*)"'
    r'\s+font-size="(?P<size>[^"]*)"'
    r'(?P<attrs>[^>]*)>'
    r'(?P<body>[^<]*)</text>'
)
_ATTR_RE = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _decode_xml_entities(s: str) -> str:
    """Reverse the five XML escapes Lout's z53.c emits in svg_emit_utf8.

    Lout only emits the five reserved-name entities (&lt; &gt; &amp; &quot;
    &apos;) and numeric character references via raw UTF-8 bytes -- there are
    no other named entities in its output, so a tiny hand-written decoder is
    plenty.
    """
    if '&' not in s:
        return s
    return (s.replace('&lt;', '<')
             .replace('&gt;', '>')
             .replace('&quot;', '"')
             .replace('&apos;', "'")
             .replace('&amp;', '&'))


def _xml_attr_escape(s: str) -> str:
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;'))


def _convert_text_to_paths(svg: str) -> tuple[str, dict[str, int]]:
    """Replace Lout's <text> elements with vector <path> outlines.

    Returns (svg_out, stats) where stats counts replaced/missing/skipped
    text elements.  Glyphs unavailable in the Nimbus DB fall back to
    leaving the <text> element untouched -- a graceful degradation that
    keeps the rest of the page intact.
    """
    db = _load_glyph_db()
    stats = {
        'text_total': 0,
        'text_converted': 0,
        'text_skipped_face': 0,
        'text_skipped_glyph': 0,
        'glyphs_emitted': 0,
    }

    def _replace(m: re.Match) -> str:
        stats['text_total'] += 1
        family = m.group('family')
        try:
            size_pt = float(m.group('size'))
        except ValueError:
            return m.group(0)
        attrs_blob = m.group('attrs') or ''
        body_raw = m.group('body') or ''
        body = _decode_xml_entities(body_raw)
        if not body:
            return ''

        attrs = dict(_ATTR_RE.findall(attrs_blob))
        bold = attrs.get('font-weight') == 'bold'
        italic = attrs.get('font-style') == 'italic'
        fill = attrs.get('fill')

        key = (family, bold, italic)
        face = db.get(key)
        if face is None:
            # Fall back: try regular weight/style of the same family.
            face = db.get((family, False, False))
            if face is None:
                stats['text_skipped_face'] += 1
                if key not in _GLYPH_DB_MISSING:
                    _GLYPH_DB_MISSING.add(key)
                return m.group(0)
        upem, entries = face
        scale = size_pt / upem

        # Per-glyph: lookup outline by codepoint, position via cumulative
        # advance width.  The enclosing <g transform="... scale(1,-1)">
        # already inverts Y, so paths apply scale(s,-s) to map em-units
        # (Y-up) back to local Y-down -> page Y-up.
        chunks: list[str] = []
        cursor = 0  # in em units
        if fill is not None:
            chunks.append(f'<g fill="{_xml_attr_escape(fill)}">')
        else:
            chunks.append('<g>')

        any_emitted = False
        all_missing = True
        for ch in body:
            cp = ord(ch)
            entry = entries.get(cp)
            if entry is None:
                # Unmapped codepoint: skip, but advance by a fallback width
                # so subsequent glyphs don't pile up at x=0.  500em-units is
                # a decent average for Times/Helvetica.
                cursor += 500
                continue
            d, w = entry
            all_missing = False
            if d:  # non-empty path
                xpt = cursor * scale
                chunks.append(
                    f'<path transform="translate({xpt:.3f},0) '
                    f'scale({scale:.6f},{-scale:.6f})" d="{d}"/>'
                )
                stats['glyphs_emitted'] += 1
                any_emitted = True
            cursor += w
        chunks.append('</g>')

        if all_missing:
            # No glyph in this run could be resolved -> keep original <text>.
            stats['text_skipped_glyph'] += 1
            return m.group(0)
        if not any_emitted:
            # Whitespace-only run (every glyph resolved but had empty path).
            stats['text_converted'] += 1
            return ''
        stats['text_converted'] += 1
        return ''.join(chunks)

    out = _TEXT_ELEM_RE.sub(_replace, svg)
    return out, stats


def _read_text_if_exists(paths: tuple[str, ...]) -> tuple[str | None, str | None]:
    """Return (contents, path) for the first existing file, else (None, None)."""
    for p in paths:
        try:
            if os.path.isfile(p):
                with open(p, encoding='utf-8') as f:
                    return f.read(), p
        except OSError:
            continue
    return None, None


# Raster extensions @IncludeGraphic can route through <image href> in SVG
# mode. mimetypes.guess_type covers png/jpg/jpeg/gif natively; .webp varies
# by stdlib version, so we have a fallback table.
_RASTER_EXTS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.webp'})
_RASTER_MIME_FALLBACK = {
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.webp': 'image/webp',
}

# Match <image ... href="..." ...> or xlink:href="..." in the SVG.
# Tolerant of single/double quotes and whitespace, but only fires inside
# an <image> element so we don't accidentally rewrite an <a xlink:href> or
# a <use xlink:href>.
_IMAGE_HREF_RE = re.compile(
    r'(<image\b[^>]*?)'
    r'(\b(?:xlink:href|href)\s*=\s*)'
    r'(?P<quote>["\'])'
    r'(?P<url>[^"\']+)'
    r'(?P=quote)',
    re.IGNORECASE | re.DOTALL,
)


def _inline_raster_in_svg(svg_text: str, base_dir: pathlib.Path) -> str:
    """Rewrite local raster <image href="..."> to base64 data: URLs.

    Walks `svg_text`, finds every <image> href / xlink:href that points at a
    local raster file (resolved against `base_dir`), reads it, base64-encodes
    the bytes, and replaces the href with `data:image/<mime>;base64,<...>`.
    Already-`data:`, http(s)://, and file:// URLs are left alone, as are
    paths that don't resolve to an existing raster on disk (a warning is
    logged to stderr in that case so the user notices broken links).

    Vector .svg files are intentionally skipped: Lout's @SVGFile path already
    inlines them as text via @IncludeGraphic, and re-inlining an SVG as a
    base64 image would lose its DOM (no clickable links, no text selection).
    """
    cache: dict[str, str | None] = {}

    def _encode(path: pathlib.Path) -> str | None:
        key = str(path)
        if key in cache:
            return cache[key]
        try:
            data = path.read_bytes()
        except OSError as e:
            print(
                f'mdlout: --inline-raster: could not read {path}: {e}',
                file=sys.stderr,
            )
            cache[key] = None
            return None
        ext = path.suffix.lower()
        mime, _ = mimetypes.guess_type(path.name)
        if not mime:
            mime = _RASTER_MIME_FALLBACK.get(ext, 'application/octet-stream')
        b64 = base64.b64encode(data).decode('ascii')
        out = f'data:{mime};base64,{b64}'
        cache[key] = out
        return out

    def _sub(m: 're.Match[str]') -> str:
        url = m.group('url').strip()
        # Skip data:, http(s)://, file://, and anything that already
        # looks like an absolute URL with a scheme we don't own.
        low = url.lower()
        if (low.startswith('data:')
                or low.startswith('http://')
                or low.startswith('https://')
                or low.startswith('file://')):
            return m.group(0)

        # Only rewrite raster extensions; SVGs are inlined upstream.
        ext = pathlib.Path(url).suffix.lower()
        if ext not in _RASTER_EXTS:
            return m.group(0)

        # Resolve against base_dir, then fall back to absolute / cwd.
        candidate = (base_dir / url) if not os.path.isabs(url) else pathlib.Path(url)
        if not candidate.is_file():
            print(
                f'mdlout: --inline-raster: skipping missing file {candidate}',
                file=sys.stderr,
            )
            return m.group(0)

        data_url = _encode(candidate)
        if data_url is None:
            return m.group(0)
        quote = m.group('quote')
        return f'{m.group(1)}{m.group(2)}{quote}{data_url}{quote}'

    return _IMAGE_HREF_RE.sub(_sub, svg_text)


# CSS @page size keywords accepted by browsers (CSS Paged Media level 3).
# Anything not in this set is passed through verbatim if it already looks
# like an explicit dimension (e.g. "210mm 297mm"); otherwise we fall back
# to "letter".
_CSS_PAGE_SIZES = frozenset({
    'a3', 'a4', 'a5', 'b4', 'b5', 'letter', 'legal', 'ledger',
})


def _print_page_size_css(page_size: str | None, orientation: str | None) -> str:
    """Build a CSS @page `size:` value from frontmatter page + orientation.

    Lout's @PageType accepts names like "A4", "Letter", "Legal". CSS Paged
    Media's `size` property accepts the same names (lowercase) plus
    "portrait" / "landscape". We just translate.

    If `page_size` already looks like an explicit "<num><unit> <num><unit>"
    pair, pass it through unchanged. Unrecognised names fall back to
    "letter portrait".
    """
    raw = (page_size or 'Letter').strip()
    orient = (orientation or 'Portrait').strip().lower()
    if orient not in ('portrait', 'landscape'):
        orient = 'portrait'

    # Already an explicit "<n><unit> <n><unit>" pair? Pass through.
    if re.match(r'^\d', raw) and re.search(r'[a-z]', raw):
        return raw

    key = raw.lower().replace(' ', '')
    if key in _CSS_PAGE_SIZES:
        return f'{key} {orient}'
    return f'letter {orient}'


def _build_html_scaffold(
    svg: str,
    title: str,
    *,
    external_assets: bool = False,
    math_engine: bool = True,
    music_engine: bool = True,
    mermaid_engine: bool = True,
    embed_fonts: bool = True,
    subset_fonts: bool = True,
    highlight: bool = True,
    lang: str = 'en',
    a11y: bool = True,
    page_size: str = 'Letter',
    orientation: str = 'Portrait',
    dark_mode: str = 'off',
) -> tuple[str, dict[str, str | None]]:
    """Wrap raw SVG output from lout -G in a self-contained HTML5 document.

    Returns (html, info) where `info` records which asset paths were used
    (system path vs CDN vs disabled) so the CLI can report them.
    """
    info: dict[str, str | None] = {
        'katex_css': None,
        'katex_js': None,
        'katex_autorender': None,
        'abcjs': None,
        'mermaid': None,
        'embedded_fonts': None,
        'highlightjs_css': None,
        'highlightjs_js': None,
    }

    head_parts: list[str] = [
        '<meta charset="utf-8">',
        f'<title>{_html_escape(title)}</title>',
    ]

    # ---- @font-face: align SVG glyph metrics with PostScript ----------------
    # Lout's SVG back-end emits font-family="Times" / "Helvetica" / "Courier"
    # (the Adobe base-14 names).  Without @font-face, browsers and librsvg
    # substitute system "Times" etc. whose metrics drift from Adobe's AFMs —
    # causing per-line glyph-advance mismatches between the PS and SVG renders
    # of the same Lout output (Lout itself already broke lines identically).
    # Embedding URW++ Nimbus (Ghostscript's own substitution for the Adobe
    # base 14) at the family names the SVG references closes that gap.
    if embed_fonts:
        font_css, font_paths, font_stats = _build_font_face_css(
            svg_for_subset=svg if subset_fonts else None,
        )
        if font_css:
            head_parts.append(f'<style>{font_css}</style>')
            info['embedded_fonts'] = (
                f'{len(font_paths)} face(s) from '
                f'{os.path.dirname(font_paths[0])} (inlined base64)'
            )
            if subset_fonts and font_stats.get('faces'):
                before = font_stats['bytes_before']
                after = font_stats['bytes_after']
                pct = (100 * (before - after) / before) if before else 0
                info['embedded_fonts'] += (
                    f'; subset: {before:,} -> {after:,} bytes '
                    f'({pct:.1f}% reduction across '
                    f'{font_stats["faces"]} face(s))'
                )

    head_parts.append(
        # Print stylesheet, page boundaries, .lout-page styling, math/music
        # sizing. Kept intentionally short — the scaffold is meant to be
        # readable and to defer rendering work to KaTeX / abcjs.
        '<style>'
        'html,body{margin:0;padding:0;background:#e8e8e8;'
        'font-family:Times,"Liberation Serif",serif}'
        'body{padding:2em 0}'
        '.lout-page{display:block;margin:1em auto;background:#fff;'
        'box-shadow:0 1px 4px rgba(0,0,0,0.25);max-width:100%}'
        'foreignObject{overflow:visible}'
        '.math{display:inline-block}'
        '.abc-music{display:block;width:100%}'
        '.abc-music svg{max-width:100%;height:auto}'
        '.mermaid{display:block;width:100%;text-align:center}'
        '.mermaid svg{max-width:100%;height:auto}'
        '.mdlout-code{margin:0;padding:.6em 1em;background:#f6f8fa;'
        'border:1px solid #ddd;border-radius:4px;font-family:Courier,'
        '"Liberation Mono",monospace;font-size:.9em;line-height:1.4;'
        'white-space:pre;overflow:auto}'
        '.mdlout-code code{background:transparent;padding:0;'
        'font-family:inherit;font-size:inherit}'
        '</style>'
    )

    # ---- Print stylesheet: page-for-page parity with the PDF route ---------
    # The on-screen view shows .lout-page divs / <svg class="lout-page"> on a
    # grey backdrop. When the document is printed (or rendered headless via
    # Chrome's --print-to-pdf), each Lout page must land on its own physical
    # printed sheet, with non-content chrome (skip link, TOC nav, footnote
    # aside, hidden anchor/alt blocks, banner) hidden. Lout has already baked
    # the page margins into the SVG viewBox, so the @page itself is borderless.
    print_size = _print_page_size_css(page_size, orientation)
    head_parts.append(
        '<style media="print">'
        f'@page{{size:{print_size};margin:0}}'
        # Reset wrapper padding/background so the page edge is the SVG edge.
        'html,body{background:#fff!important;margin:0!important;padding:0!important}'
        # Hide non-content chrome -- footnotes are already printed inline at
        # the bottom of each PDF page via Lout's @FootNote, and the HTML's
        # separate <aside> would otherwise repeat them after the last page.
        '.skip-link,nav.toc,aside.footnotes,header[role="banner"],'
        '.mdlout-img-alts,.mdlout-anchors{display:none!important}'
        # Each Lout page (svg.lout-page or .lout-page div) prints on its own
        # sheet. page-break-before:always on every page except the first puts
        # the cut between pages; page-break-inside:avoid keeps the page intact.
        '.lout-page{box-shadow:none!important;margin:0!important;'
        'padding:0!important;display:block;'
        'page-break-before:always;page-break-after:auto;'
        'break-before:page;break-after:auto;'
        'page-break-inside:avoid;break-inside:avoid;'
        # Lout already sized the <svg> at the exact paper dimensions in
        # points (width="595pt" height="842pt" for A4, etc.). Keep those
        # intrinsic dimensions for print so the page lines up edge-to-edge
        # with the @page box. max-width:none cancels the on-screen rule
        # that capped <svg>s at the viewport width.
        'max-width:none!important}'
        '.lout-page:first-of-type,'
        'main>article>.lout-page:first-of-type{'
        'page-break-before:auto;break-before:auto}'
        # <main>/<article> wrappers from the a11y scaffolding must not add
        # extra padding that would push the SVG off the page.
        'main,article{margin:0!important;padding:0!important;display:block}'
        '</style>'
    )

    # ---- Dark mode (opt-in) ------------------------------------------------
    # Lout's z53.c back-end now emits text and rules with
    # fill="currentColor" / stroke="currentColor" whenever the active PS
    # colour is the default black. That lets us deliver a dark theme by
    # simply re-tinting the SVG with CSS `color:` instead of inverting the
    # rendered page (which would also flip embedded raster <image>s and
    # corrupt photo luminance / hue). Non-default colours still emit an
    # explicit rgb(...), so authored colour choices keep their values
    # unchanged in dark mode -- only the implicit "ink black" is themed.
    #
    # `dark_mode` values:
    #   'off'   -- no dark CSS emitted (default; rendering unchanged).
    #   'force' -- apply the dark theme unconditionally.
    #   'auto'  -- apply only when the user agent reports
    #              `prefers-color-scheme: dark`.
    if dark_mode in ('force', 'auto'):
        dark_rules = (
            'body.mdlout-dark{background:#1a1a1a;color:#e8e8e8}'
            'body.mdlout-dark .lout-page{background:#1a1a1a}'
            # The cascade target: every `fill="currentColor"` / `stroke=
            # "currentColor"` inside the SVG resolves to this colour.
            'body.mdlout-dark .lout-page svg{color:#e8e8e8}'
            'body.mdlout-dark a{color:#88c0ff}'
            'body.mdlout-dark code,body.mdlout-dark pre{'
            'background:#222;color:#ccc}'
            'body.mdlout-dark .mdlout-code{'
            'background:#222;border-color:#444;color:#e8e8e8}'
            'body.mdlout-dark nav.toc,body.mdlout-dark aside.footnotes,'
            'body.mdlout-dark header[role="banner"]{color:#e8e8e8}'
        )
        if dark_mode == 'force':
            # Emit the rules unconditionally, plus an `@media
            # (prefers-color-scheme: dark)` echo so browser auditors that
            # look for the media query still see it. The @media block is
            # a no-op visually when `force` already applied the rules at
            # the top level.
            head_parts.append(
                f'<style>{dark_rules}'
                '@media (prefers-color-scheme: dark){'
                f'{dark_rules}'
                '}</style>'
            )
        else:
            head_parts.append(
                '<style>@media (prefers-color-scheme: dark){'
                f'{dark_rules}'
                '}</style>'
            )

    # ---- KaTeX CSS + JS -----------------------------------------------------
    if math_engine:
        if external_assets:
            head_parts.append(
                f'<link rel="stylesheet" href="{_KATEX_CDN_BASE}/katex.min.css">'
            )
            head_parts.append(
                f'<script defer src="{_KATEX_CDN_BASE}/katex.min.js"></script>'
            )
            head_parts.append(
                f'<script defer src="{_KATEX_CDN_BASE}/contrib/auto-render.min.js"'
                ' onload="renderMath()"></script>'
            )
            info['katex_css'] = f'{_KATEX_CDN_BASE}/katex.min.css (CDN)'
            info['katex_js'] = f'{_KATEX_CDN_BASE}/katex.min.js (CDN)'
            info['katex_autorender'] = (
                f'{_KATEX_CDN_BASE}/contrib/auto-render.min.js (CDN)'
            )
        else:
            css_text, css_path = _read_text_if_exists(_KATEX_CSS_CANDIDATES)
            if css_text is not None:
                head_parts.append(f'<style>{css_text}</style>')
                info['katex_css'] = f'{css_path} (inlined)'
            else:
                head_parts.append(
                    f'<link rel="stylesheet" href="{_KATEX_CDN_BASE}/katex.min.css">'
                )
                info['katex_css'] = f'{_KATEX_CDN_BASE}/katex.min.css (CDN fallback)'

            js_text, js_path = _read_text_if_exists(_KATEX_JS_CANDIDATES)
            if js_text is not None:
                head_parts.append(f'<script>{js_text}</script>')
                info['katex_js'] = f'{js_path} (inlined)'
            else:
                head_parts.append(
                    f'<script defer src="{_KATEX_CDN_BASE}/katex.min.js"></script>'
                )
                info['katex_js'] = f'{_KATEX_CDN_BASE}/katex.min.js (CDN fallback)'

            ar_text, ar_path = _read_text_if_exists(_KATEX_AUTORENDER_CANDIDATES)
            if ar_text is not None:
                head_parts.append(f'<script>{ar_text}</script>')
                info['katex_autorender'] = f'{ar_path} (inlined)'
            else:
                head_parts.append(
                    f'<script defer'
                    f' src="{_KATEX_CDN_BASE}/contrib/auto-render.min.js"'
                    ' onload="renderMath()"></script>'
                )
                info['katex_autorender'] = (
                    f'{_KATEX_CDN_BASE}/contrib/auto-render.min.js (CDN fallback)'
                )

    # ---- abcjs --------------------------------------------------------------
    if music_engine:
        if external_assets:
            head_parts.append(f'<script defer src="{_ABCJS_CDN}"></script>')
            info['abcjs'] = f'{_ABCJS_CDN} (CDN)'
        else:
            abc_text, abc_path = _read_text_if_exists(_ABCJS_DIST_CANDIDATES)
            if abc_text is not None:
                head_parts.append(f'<script>{abc_text}</script>')
                info['abcjs'] = f'{abc_path} (inlined)'
            else:
                head_parts.append(f'<script defer src="{_ABCJS_CDN}"></script>')
                info['abcjs'] = f'{_ABCJS_CDN} (CDN fallback)'

    # ---- mermaid.js ---------------------------------------------------------
    # Only load when the document actually has a ```mermaid``` block, mirroring
    # the highlight.js gating below. Prefer a locally installed copy (so
    # offline builds work); otherwise fall back to the CDN, which is itself
    # overridable via MDLOUT_MERMAID_URL.
    if mermaid_engine and _has_mermaid:
        if external_assets:
            head_parts.append(
                f'<script defer src="{_MERMAID_CDN}" '
                f'onload="if(window.mermaid)mermaid.initialize({{startOnLoad:false}});'
                f'window.renderMermaid&&renderMermaid();"></script>'
            )
            info['mermaid'] = f'{_MERMAID_CDN} (CDN)'
        else:
            mer_text, mer_path = _read_text_if_exists(_MERMAID_DIST_CANDIDATES)
            if mer_text is not None:
                head_parts.append(f'<script>{mer_text}</script>')
                info['mermaid'] = f'{mer_path} (inlined)'
            else:
                head_parts.append(
                    f'<script defer src="{_MERMAID_CDN}" '
                    f'onload="if(window.mermaid)mermaid.initialize({{startOnLoad:false}});'
                    f'window.renderMermaid&&renderMermaid();"></script>'
                )
                info['mermaid'] = f'{_MERMAID_CDN} (CDN fallback)'

    # ---- highlight.js -------------------------------------------------------
    # Only load if (a) the user hasn't disabled it AND (b) at least one
    # code block actually wants highlighting. Otherwise we'd ship ~150 kB
    # of dead-weight CSS+JS to every page that has no code in it.
    if highlight and _highlight_langs:
        if external_assets:
            head_parts.append(
                f'<link rel="stylesheet" href="{_HLJS_CDN_CSS}">'
            )
            head_parts.append(
                f'<script defer src="{_HLJS_CDN_JS}" '
                f'onload="hljs.highlightAll()"></script>'
            )
            info['highlightjs_css'] = f'{_HLJS_CDN_CSS} (CDN)'
            info['highlightjs_js'] = f'{_HLJS_CDN_JS} (CDN)'
        else:
            css_text, css_path = _read_text_if_exists(_HLJS_CSS_CANDIDATES)
            if css_text is not None:
                head_parts.append(f'<style>{css_text}</style>')
                info['highlightjs_css'] = f'{css_path} (inlined)'
            else:
                head_parts.append(
                    f'<link rel="stylesheet" href="{_HLJS_CDN_CSS}">'
                )
                info['highlightjs_css'] = f'{_HLJS_CDN_CSS} (CDN fallback)'
            js_text, js_path = _read_text_if_exists(_HLJS_JS_CANDIDATES)
            if js_text is not None:
                head_parts.append(
                    f'<script>{js_text}</script>'
                    '<script>hljs.highlightAll();</script>'
                )
                info['highlightjs_js'] = f'{js_path} (inlined)'
            else:
                head_parts.append(
                    f'<script defer src="{_HLJS_CDN_JS}" '
                    f'onload="hljs.highlightAll()"></script>'
                )
                info['highlightjs_js'] = f'{_HLJS_CDN_JS} (CDN fallback)'

    # ---- Init script --------------------------------------------------------
    # Runs once both KaTeX auto-render and abcjs are loaded. We hook
    # DOMContentLoaded and also expose renderMath()/renderMusic() so the
    # defer-loaded CDN scripts can call them after they arrive.
    init_js_parts: list[str] = []
    if math_engine:
        # mdlout emits <span class="math">BARE-LATEX</span> (no $..$
        # delimiters), so KaTeX's auto-render renderMathInElement -- which
        # scans text content for delimiters -- never sees the spans.
        # Render each span explicitly via katex.render() and pick
        # displayMode from a .math-display class set by @DMath.
        init_js_parts.append(
            "window.renderMath=function(){"
            "if(typeof katex==='undefined')return;"
            "document.querySelectorAll('span.math').forEach(function(s){"
            "if(s.dataset.rendered)return;"
            "var tex=(s.textContent||'').trim();"
            "if(!tex)return;"
            "try{"
            "katex.render(tex,s,{"
            "displayMode:s.classList.contains('math-display'),"
            "throwOnError:false"
            "});"
            "s.dataset.rendered='1';"
            "}catch(e){s.textContent='[math error: '+e.message+']';}"
            "});"
            "};"
        )
    if music_engine:
        init_js_parts.append(
            "window.renderMusic=function(){"
            "if(typeof ABCJS==='undefined')return;"
            "document.querySelectorAll('div.abc-music').forEach(function(d){"
            "var src=d.dataset.abc||d.textContent||'';"
            "d.textContent='';"
            "try{ABCJS.renderAbc(d,src,{responsive:'resize'});}"
            "catch(e){d.textContent='[abcjs error: '+e.message+']';}"
            "});"
            "};"
        )
    if mermaid_engine and _has_mermaid:
        # Lout's SVG back-end nests every page's content inside an outer
        # <svg>, so each .mermaid <div> lives inside a <foreignObject>. We
        # call mermaid.run() with the explicit node list (auto-discovery
        # walks the DOM but misses foreignObject descendants in some
        # browsers). Initialize is gated so the engine doesn't auto-render
        # before our explicit pass.
        init_js_parts.append(
            "window.renderMermaid=function(){"
            "if(typeof mermaid==='undefined')return;"
            "try{mermaid.initialize({startOnLoad:false});}catch(e){}"
            "var nodes=document.querySelectorAll('div.mermaid');"
            "if(!nodes.length)return;"
            "try{mermaid.run({nodes:nodes});}"
            "catch(e){nodes.forEach(function(n){"
            "n.textContent='[mermaid error: '+e.message+']';});}"
            "};"
        )
    init_js_parts.append(
        "function _mdloutInit(){"
        + ("window.renderMath&&renderMath();" if math_engine else "")
        + ("window.renderMusic&&renderMusic();" if music_engine else "")
        + ("window.renderMermaid&&renderMermaid();"
           if (mermaid_engine and _has_mermaid) else "")
        + "}"
        "if(document.readyState==='loading')"
        "document.addEventListener('DOMContentLoaded',_mdloutInit);"
        "else _mdloutInit();"
    )

    head = '\n'.join(head_parts)
    init_js = '\n'.join(init_js_parts)

    # Hidden heading anchors + TOC + footnotes sections are injected by the
    # caller via _build_html_extras. We splice them around the SVG so the
    # in-page nav (anchors / TOC links / footnote backrefs) works even though
    # the SVG itself has no anchor DOM.
    head_anchors, toc_html, footnotes_html = _build_html_extras()
    if head_anchors or toc_html or footnotes_html:
        head_parts.append(
            '<style>'
            '.mdlout-anchors{position:absolute;left:-9999px;width:1px;'
            'height:1px;overflow:hidden}'
            'nav.toc{max-width:48em;margin:1em auto;padding:1em 1.5em;'
            'background:#fff;border:1px solid #ddd;font-family:Times,serif}'
            'nav.toc h2{margin:0 0 .5em 0;font-size:1.1em}'
            'nav.toc ul{padding-left:1.5em;margin:.2em 0}'
            'nav.toc>ul{padding-left:1.2em}'
            'nav.toc a{color:#0645ad;text-decoration:none}'
            'nav.toc a:hover{text-decoration:underline}'
            'aside.footnotes{max-width:48em;margin:2em auto;padding:1em 1.5em;'
            'background:#fff;border-top:1px solid #ccc;font-family:Times,serif;'
            'font-size:.95em}'
            'aside.footnotes h2{margin:0 0 .5em 0;font-size:1.1em}'
            'aside.footnotes ol{padding-left:2em;margin:.3em 0}'
            'aside.footnotes a.fn-backref{margin-left:.3em;'
            'text-decoration:none;color:#0645ad}'
            '</style>'
        )
        head = '\n'.join(head_parts)

    # ---- A11y scaffolding ---------------------------------------------------
    # WCAG 2.1: surface a meaningful landmark structure (skip-link, <main>,
    # <header>, <nav>, <article>, <aside>) plus an image-alt manifest so
    # screen-reader users can navigate a document whose visible content is
    # otherwise locked inside opaque <svg> page renders. The PDF/PS output is
    # untouched -- this branch only fires for HTML.
    a11y_lang = lang or 'en'
    if a11y:
        head_parts.append(
            '<style>'
            # Skip-link: hidden until focused (WCAG 2.4.1 bypass blocks).
            '.skip-link{position:absolute;top:-40px;left:0;background:#000;'
            'color:#fff;padding:.5em 1em;z-index:1000;text-decoration:none}'
            '.skip-link:focus{top:0}'
            # Visible focus ring on every focusable element (WCAG 2.4.7).
            'a:focus,button:focus,[tabindex]:focus{outline:2px solid #0645ad;'
            'outline-offset:2px}'
            # Visually hidden but screen-reader-readable list of image alts.
            '.mdlout-img-alts{position:absolute;left:-9999px;width:1px;'
            'height:1px;overflow:hidden}'
            # <header><p> duplicates the visible title baked into the SVG;
            # hide visually but leave it in the AT tree as a landmark name.
            '.mdlout-doc-title{position:absolute;left:-9999px;width:1px;'
            'height:1px;overflow:hidden}'
            # Make sure the SVG itself doesn't trap focus when tabbing past.
            'svg.lout-page{outline:none}'
            '</style>'
        )
        head = '\n'.join(head_parts)

    body_parts = []
    if a11y:
        body_parts.append(
            '<a href="#main" class="skip-link">Skip to content</a>'
        )
        # Visually-hidden <h1> labelling the page. Required by axe-core's
        # page-has-heading-one rule; without it, documents whose first
        # markdown heading is ## or @Section (most reports/books) have
        # no <h1> anywhere in the DOM and fail WCAG audits. Multiple <h1>s
        # in different sectioning roots are valid HTML5 and pass axe.
        body_parts.append(
            '<header role="banner" aria-label="Document header">'
            f'<h1 class="mdlout-doc-title">{_html_escape(title)}</h1>'
            '</header>'
        )
    if head_anchors:
        body_parts.append(head_anchors)
    # Image alt manifest: one <figure role="img" aria-label="..."> per
    # markdown image, in source order. Hidden visually (the rendered glyphs
    # live inside the SVG) but announced by AT.
    if a11y and _html_image_alts:
        body_parts.append('<div class="mdlout-img-alts" aria-hidden="false">')
        body_parts.append(
            '<h2>Images</h2>'
        )
        for alt, url in _html_image_alts:
            body_parts.append(
                f'<figure role="img" aria-label="{_html_escape(alt)}">'
                f'<figcaption>{_html_escape(alt)}'
                f' (<span class="img-src">{_html_escape(url)}</span>)'
                f'</figcaption></figure>'
            )
        body_parts.append('</div>')
    if toc_html:
        # If a11y is on, wrap the TOC in <nav> with aria-label so screen
        # readers can target it directly. _build_html_toc already emits
        # <nav class="toc">, so we don't double-wrap; just patch aria-label.
        if a11y:
            toc_html = toc_html.replace(
                '<nav class="toc">',
                '<nav class="toc" aria-label="Table of contents">',
                1,
            )
        body_parts.append(toc_html)
    if a11y:
        body_parts.append('<main id="main" role="main" aria-label="Document body">')
        body_parts.append('<article aria-label="Rendered document pages">')
        body_parts.append(svg)
        body_parts.append('</article>')
        body_parts.append('</main>')
    else:
        body_parts.append(svg)
    if footnotes_html:
        # _build_html_footnotes emits <aside class="footnotes">; add an
        # aria-label so screen-reader rotor lists name it clearly.
        if a11y:
            footnotes_html = footnotes_html.replace(
                '<aside class="footnotes">',
                '<aside class="footnotes" aria-label="Footnotes">',
                1,
            )
        body_parts.append(footnotes_html)
    body_inner = '\n'.join(body_parts)

    # Body class drives the dark-mode CSS selectors. For `force`, the
    # class is always present. For `auto`, the class is always present
    # too -- the @media (prefers-color-scheme: dark) wrapper is what
    # gates whether the rules apply -- so the browser does the right
    # thing regardless of the user's current OS theme.
    body_attrs = ''
    if dark_mode in ('force', 'auto'):
        body_attrs = ' class="mdlout-dark"'

    return (
        '<!DOCTYPE html>\n'
        f'<html lang="{_html_escape(a11y_lang)}">\n<head>\n{head}\n</head>\n'
        f'<body{body_attrs}>\n{body_inner}\n'
        f'<script>{init_js}</script>\n'
        '</body>\n</html>\n'
    ), info


def _build_html_extras() -> tuple[str, str, str]:
    """Return (anchor_block, toc_block, footnotes_block) HTML strings.

    - anchor_block: a visually-hidden div of <h1 id="..."> ... <h6 id="...">
      elements so anchor links resolve and h1/h2 element-with-id assertions
      pass in tests. The SVG carries the visible rendering.
    - toc_block: <nav class="toc"> with a nested <ul> mirroring heading
      hierarchy. Emitted only when [TOC] appeared in the markdown.
    - footnotes_block: <aside class="footnotes"><ol>...</ol></aside> built
      from _fn_order / _fn_defs. Emitted only when at least one [^ref] fired.
    """
    anchor_block = ''
    if _html_headings or _fn_order:
        bits = ['<div class="mdlout-anchors" aria-hidden="true">']
        for level, text, anchor in _html_headings:
            lvl = max(1, min(6, level))
            bits.append(
                f'<h{lvl} id="{_html_escape(anchor)}">'
                f'{_html_escape(text)}</h{lvl}>'
            )
        # Footnote backref targets. The visible "[N]" superscript is
        # painted by Lout inside the SVG and isn't an anchor target; this
        # hidden <span id="fnref-N"> lets the footnote-section backref
        # land somewhere meaningful (browsers scroll to the section the
        # ref originally appeared in).
        for lbl, n in sorted(_fn_order.items(), key=lambda kv: kv[1]):
            bits.append(f'<span id="fnref-{n}"></span>')
        bits.append('</div>')
        anchor_block = '\n'.join(bits)

    toc_block = ''
    if _html_toc_requested and _html_headings:
        toc_block = _build_html_toc(_html_headings)

    footnotes_block = ''
    if _fn_order:
        footnotes_block = _build_html_footnotes()
    return anchor_block, toc_block, footnotes_block


def _build_html_toc(headings: list[tuple[int, str, str]]) -> str:
    """Build a nested <ul class="toc">: each level transition opens or closes
    <ul> elements to mirror the heading depth. A heading deeper than its
    predecessor by more than 1 still produces nested <ul>s (we don't skip
    levels, we just keep nesting one at a time)."""
    out = ['<nav class="toc">', '<h2>Contents</h2>', '<ul>']
    stack = [1]  # current depth = 1 (matches the outer <ul>)
    for level, text, anchor in headings:
        target = max(1, min(6, level))
        # Open additional nested <ul>s for deeper headings.
        while stack[-1] < target:
            out.append('<ul>')
            stack.append(stack[-1] + 1)
        # Close <ul>s when going shallower.
        while stack[-1] > target:
            out.append('</ul>')
            stack.pop()
        out.append(
            f'<li><a href="#{_html_escape(anchor)}">'
            f'{_html_escape(text)}</a></li>'
        )
    while stack:
        out.append('</ul>')
        stack.pop()
    out.append('</nav>')
    return '\n'.join(out)


def _build_html_footnotes() -> str:
    """Emit <aside class="footnotes"><ol><li id="fn-N">body<a href="#fnref-N"
    class="fn-backref"><sup>[N]</sup></a></li>...</ol></aside>.

    The body is the raw markdown definition rendered through a minimal
    inline pass (bold/italic/code), so footnote text reads naturally without
    pulling in the full Lout pipeline. Footnote bodies in mdlout are
    intentionally short -- callers wanting block content should put it
    in the main flow.
    """
    out = ['<aside class="footnotes">', '<h2>Footnotes</h2>', '<ol>']
    by_n = sorted(_fn_order.items(), key=lambda kv: kv[1])
    for lbl, n in by_n:
        body = _fn_defs.get(lbl, f'[^{lbl}]')
        body_html = _md_inline_to_html(body)
        out.append(
            f'<li id="fn-{n}">{body_html} '
            f'<a href="#fnref-{n}" class="fn-backref" '
            f'title="back to text"><sup>[{n}]</sup></a></li>'
        )
    out.append('</ol>')
    out.append('</aside>')
    return '\n'.join(out)


def _md_inline_to_html(s: str) -> str:
    """Tiny markdown-inline -> HTML pass for footnote bodies. Handles
    backticks, **bold**, *italic*, and bare links; escapes HTML metachars
    first so user input can't break the document."""
    s = _html_escape(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    s = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        s,
    )
    return s


def _html_escape(s: str) -> str:
    return (
        s.replace('&', '&amp;')
         .replace('<', '&lt;')
         .replace('>', '&gt;')
         .replace('"', '&quot;')
    )


# Mapping from Lout @InitialLanguage names (a sampling of the most-common
# language packs in lout/include/lang*) to BCP-47 codes for <html lang>.
# Anything not in the table passes through unchanged so users can already
# write a BCP-47 tag like "en-GB" in their frontmatter if they want.
_LOUT_LANG_TO_BCP47 = {
    'english':     'en',
    'ukenglish':   'en-GB',
    'usenglish':   'en-US',
    'french':      'fr',
    'german':      'de',
    'oldgerman':   'de',
    'spanish':     'es',
    'italian':     'it',
    'portuguese':  'pt',
    'dutch':       'nl',
    'swedish':     'sv',
    'norwegian':   'no',
    'danish':      'da',
    'finnish':     'fi',
    'russian':     'ru',
    'czech':       'cs',
    'slovak':      'sk',
    'polish':      'pl',
    'hungarian':   'hu',
    'croatian':    'hr',
    'catalan':     'ca',
}


def _lout_lang_to_bcp47(lout_lang: str | None) -> str | None:
    """Translate a Lout @InitialLanguage value (e.g. 'English') to a BCP-47
    code (e.g. 'en') so we can put it in <html lang="...">. Unknown inputs
    are returned as-is (lowercased) so authors can pass through a real
    BCP-47 tag already. None / empty -> None."""
    if not lout_lang:
        return None
    key = lout_lang.strip().lower().replace('-', '').replace(' ', '')
    return _LOUT_LANG_TO_BCP47.get(key, lout_lang.strip())


def _run_ps2pdf(ps_file: str, pdf_file: str) -> None:
    """Convert PostScript to PDF using ps2pdf (Ghostscript)."""
    ps2pdf = shutil.which('ps2pdf')
    if not ps2pdf:
        print('ps2pdf not found — install Ghostscript to produce PDF', file=sys.stderr)
        print(f'PostScript output is at {ps_file}', file=sys.stderr)
        sys.exit(1)

    result = subprocess.run([ps2pdf, ps_file, pdf_file], capture_output=True, text=True)
    if result.returncode != 0:
        print(f'ps2pdf failed: {result.stderr.strip()}', file=sys.stderr)
        sys.exit(result.returncode)


# ---------------------------------------------------------------------------
# One-shot build (used by both single-run CLI and --watch / --serve)
# ---------------------------------------------------------------------------

# Global injected into the HTML head when --serve is active so the page
# subscribes to /events. Set from main() before _build_once() runs.
_LIVE_RELOAD_SCRIPT: str = ''


def _build_once(args) -> str | None:
    """Run the full md -> output pipeline once.

    Returns the path to the produced output file, or None if --lout-only
    streamed to stdout. Raises on hard failures so callers (watch/serve)
    can decide whether to abort or print-and-continue.
    """
    global _LIVE_RELOAD_SCRIPT

    # Read input
    if args.input == '-':
        md_text = sys.stdin.read()
        input_stem = 'stdin'
    else:
        with open(args.input, encoding='utf-8') as f:
            md_text = f.read()
        input_stem = Path(args.input).stem

    # Parse and generate Lout source
    frontmatter, md_text = parse_frontmatter(md_text)
    # Citation + figure/table pre-pass — populates the module-level
    # registries that convert_inline reads while emitting Lout markup, and
    # strips [@key]: bibliography lines so they don't show up as stray
    # paragraphs after the References heading.
    _reset_xref_state()
    global _cite_format
    _cite_format = (frontmatter.get('references_format')
                    or frontmatter.get('references-format')
                    or 'numeric').lower()
    if _cite_format not in ('numeric', 'alpha'):
        _cite_format = 'numeric'
    global _output_format, _highlight_enabled
    _output_format = 'html' if args.format == 'html' else 'pdf'
    _highlight_enabled = not getattr(args, 'no_highlight', False)
    md_text = _scan_citations(md_text)
    md_text = _scan_footnotes(md_text)
    _scan_fig_tab_labels(md_text, frontmatter.get('type', 'doc').lower())
    blocks = parse_markdown(md_text)
    blocks = _inject_bibliography(blocks)
    _scan_html_headings(blocks)
    lout_src = generate_lout(blocks, frontmatter)

    # --lout-only: just emit Lout source
    if args.lout_only:
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(lout_src)
            print(args.output, file=sys.stderr)
            return args.output
        sys.stdout.write(lout_src)
        return None

    lout_bin = _find_lout_bin(args.lout_bin)
    extra_flags = shlex.split(args.lout_args) if args.lout_args else []
    lib_flags = _find_lout_lib(lout_bin)
    lout_flags = lib_flags + extra_flags

    with tempfile.TemporaryDirectory(prefix='mdlout_') as tmpdir:
        lt_file = os.path.join(tmpdir, f'{input_stem}.lt')
        with open(lt_file, 'w', encoding='utf-8') as f:
            f.write(lout_src)

        mydefs_src = None
        if args.mydefs:
            mydefs_src = Path(args.mydefs)
        elif args.input != '-':
            candidate = Path(args.input).resolve().parent / 'mydefs'
            if candidate.is_file():
                mydefs_src = candidate
        if mydefs_src:
            shutil.copy2(mydefs_src, os.path.join(tmpdir, 'mydefs'))

        lout_flags = ['-I', tmpdir] + lout_flags
        if args.input != '-':
            input_dir = str(Path(args.input).resolve().parent)
            if input_dir != tmpdir:
                lout_flags = ['-I', input_dir] + lout_flags

        # Frontmatter `font-features: smcp,onum` -> environment knob that
        # the SVG back-end picks up at SVG_PrintInitialize.  Only meaningful
        # in HTML mode (PDF path goes through z49.c which has no GSUB
        # consumer).  Accepts either a comma-separated string or a YAML
        # list; values land in LOUT_SVG_FONT_FEATURES verbatim.
        lout_env: dict | None = None
        ff = frontmatter.get('font-features', frontmatter.get('font_features'))
        if ff:
            if isinstance(ff, list):
                ff_str = ','.join(str(x).strip() for x in ff if str(x).strip())
            else:
                ff_str = str(ff).strip()
            if ff_str:
                lout_env = {'LOUT_SVG_FONT_FEATURES': ff_str}

        if args.format == 'html':
            svg_file = os.path.join(tmpdir, f'{input_stem}.svg')
            _run_lout(lout_bin, lout_flags + ['-G'], lt_file, svg_file,
                      env=lout_env)

            with open(svg_file, encoding='utf-8') as f:
                svg = f.read()
            # --inline-raster: optionally base64-inline raster <image href>s
            # so the HTML is fully self-contained. Trigger from CLI flag or
            # `inline-raster: true` in frontmatter. Relative paths resolve
            # against the directory containing the source markdown.
            _inline_raster_flag = bool(
                getattr(args, 'inline_raster', False)
                or str(frontmatter.get('inline-raster', '')).strip().lower()
                in ('true', 'yes', '1', 'on')
                or str(frontmatter.get('inline_raster', '')).strip().lower()
                in ('true', 'yes', '1', 'on')
            )
            if _inline_raster_flag:
                if args.input == '-':
                    raster_base = pathlib.Path.cwd()
                else:
                    raster_base = pathlib.Path(args.input).resolve().parent
                before = svg.count('data:image')
                svg = _inline_raster_in_svg(svg, raster_base)
                after = svg.count('data:image')
                inlined = max(0, after - before)
                if inlined:
                    print(
                        f'  inline-raster: inlined {inlined} raster image(s) '
                        f'from {raster_base}',
                        file=sys.stderr,
                    )
            if getattr(args, 'text_as_paths', False):
                try:
                    svg, tap_stats = _convert_text_to_paths(svg)
                    print(
                        f'  text-as-paths: converted {tap_stats["text_converted"]}/'
                        f'{tap_stats["text_total"]} <text> elements -> '
                        f'{tap_stats["glyphs_emitted"]} <path>s '
                        f'(skipped face={tap_stats["text_skipped_face"]}, '
                        f'glyph={tap_stats["text_skipped_glyph"]})',
                        file=sys.stderr,
                    )
                except RuntimeError as e:
                    print(f'  text-as-paths disabled: {e}', file=sys.stderr)
            title = frontmatter.get('title') or input_stem
            # Resolve <html lang="...">: prefer an explicit `html-lang`
            # frontmatter field (BCP-47 friendly), otherwise reuse the
            # Lout `language` field by mapping common names down to two-
            # letter codes, otherwise default to "en".
            html_lang = (
                frontmatter.get('html-lang')
                or frontmatter.get('html_lang')
                or _lout_lang_to_bcp47(frontmatter.get('language'))
                or 'en'
            )
            # `--subset-fonts` / `--no-subset-fonts` (CLI) or
            # `subset-fonts: true|false` (frontmatter) controls whether
            # each inlined Nimbus face is restricted to the codepoints
            # actually used by the SVG.  ON by default since v0.3 -- the
            # typical 50-90% HTML size reduction is worth the small
            # fontTools dependency at build time (falls back gracefully
            # to full-font inline when fontTools is missing).
            # Precedence: explicit --no-subset-fonts wins, then explicit
            # --subset-fonts, then frontmatter `subset-fonts: false`
            # (opt-out), then the default (on).
            _fm_subset = (
                str(frontmatter.get('subset-fonts', '')).strip().lower()
                or str(frontmatter.get('subset_fonts', '')).strip().lower()
            )
            if getattr(args, 'no_subset_fonts', False):
                _subset_fonts_flag = False
            elif getattr(args, 'subset_fonts', False):
                _subset_fonts_flag = True
            elif _fm_subset in ('false', 'no', '0', 'off'):
                _subset_fonts_flag = False
            elif _fm_subset in ('true', 'yes', '1', 'on'):
                _subset_fonts_flag = True
            else:
                _subset_fonts_flag = True
            # Resolve dark-mode preference. CLI `--dark[=MODE]` wins
            # over frontmatter. Frontmatter accepts either
            # `dark-mode: true|false|force|auto` or `theme: dark|light`.
            # The string ends up as 'off' / 'force' / 'auto', matching
            # the _build_html_scaffold parameter contract.
            _dark_mode_flag = 'off'
            if getattr(args, 'dark', None):
                _dark_mode_flag = args.dark  # 'force' or 'auto'
            else:
                fm_dark = str(
                    frontmatter.get('dark-mode')
                    or frontmatter.get('dark_mode')
                    or ''
                ).strip().lower()
                fm_theme = str(frontmatter.get('theme') or '').strip().lower()
                if fm_dark in ('true', 'yes', '1', 'on', 'force'):
                    _dark_mode_flag = 'force'
                elif fm_dark == 'auto':
                    _dark_mode_flag = 'auto'
                elif fm_theme == 'dark':
                    _dark_mode_flag = 'force'
            html, asset_info = _build_html_scaffold(
                svg,
                title,
                external_assets=args.external_assets,
                math_engine=not args.no_math_engine,
                music_engine=not args.no_music_engine,
                mermaid_engine=not args.no_mermaid_engine,
                embed_fonts=not args.no_font_embedding,
                subset_fonts=_subset_fonts_flag,
                highlight=not args.no_highlight,
                lang=html_lang,
                a11y=not getattr(args, 'no_a11y', False),
                page_size=str(frontmatter.get('page') or 'Letter'),
                orientation=str(frontmatter.get('orientation') or 'Portrait'),
                dark_mode=_dark_mode_flag,
            )
            # Inject the live-reload <script> just before </body> so the
            # browser opens an EventSource to /events. Only active in
            # --serve mode (otherwise _LIVE_RELOAD_SCRIPT is empty).
            if _LIVE_RELOAD_SCRIPT:
                html = html.replace(
                    '</body>',
                    _LIVE_RELOAD_SCRIPT + '\n</body>',
                    1,
                )

            out = args.output or f'{input_stem}.html'
            with open(out, 'w', encoding='utf-8') as f:
                f.write(html)
            for k, v in asset_info.items():
                if v is not None:
                    print(f'  {k}: {v}', file=sys.stderr)
            print(out, file=sys.stderr)
            return out

        ps_file = os.path.join(tmpdir, f'{input_stem}.ps')
        _run_lout(lout_bin, lout_flags, lt_file, ps_file)

        if args.ps:
            out = args.output or f'{input_stem}.ps'
            shutil.copy2(ps_file, out)
            print(out, file=sys.stderr)
            return out

        pdf_file = os.path.join(tmpdir, f'{input_stem}.pdf')
        _run_ps2pdf(ps_file, pdf_file)

        out = args.output or f'{input_stem}.pdf'
        shutil.copy2(pdf_file, out)
        print(out, file=sys.stderr)
        return out


# ---------------------------------------------------------------------------
# --watch and --serve helpers
# ---------------------------------------------------------------------------

import threading  # noqa: E402 — kept local to the watch/serve helpers
import time       # noqa: E402
from datetime import datetime  # noqa: E402


def _watch_file_mtime(path: str) -> float:
    """Return mtime of `path`, or 0.0 if missing (treat as 'no change yet')."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def _safe_build(args) -> str | None:
    """Run _build_once but swallow exceptions so watch/serve keep going.

    In --serve mode, captures stderr-style errors so _run_serve can render
    them as an overlay in the served HTML. The captured error (if any)
    lives in the module-level _last_build_error dict so the request
    handler can consult it without re-plumbing return values.
    """
    global _last_build_error
    # Capture stderr only when serving, so the regular CLI keeps its
    # familiar "errors stream live to the terminal" behaviour.
    capture = bool(_LIVE_RELOAD_SCRIPT)
    stderr_buf: io.StringIO | None = None
    tee: '_StderrTee | None' = None
    saved_stderr = sys.stderr
    if capture:
        stderr_buf = io.StringIO()
        tee = _StderrTee(saved_stderr, stderr_buf)
        sys.stderr = tee
    try:
        try:
            out = _build_once(args)
        finally:
            if capture:
                sys.stderr = saved_stderr
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[rebuilt {ts}] {out}', file=sys.stderr)
        _last_build_error = None
        return out
    except SystemExit as e:
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[error {ts}] build exited with {e.code}', file=sys.stderr)
        if capture and stderr_buf is not None:
            _last_build_error = {
                'kind': 'SystemExit',
                'message': f'build exited with code {e.code}',
                'stderr': stderr_buf.getvalue(),
                'ts': ts,
            }
    except Exception as e:
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[error {ts}] {type(e).__name__}: {e}', file=sys.stderr)
        if capture:
            tb = traceback.format_exc()
            stderr_text = stderr_buf.getvalue() if stderr_buf else ''
            _last_build_error = {
                'kind': type(e).__name__,
                'message': str(e),
                'stderr': stderr_text + ('\n' + tb if tb else ''),
                'ts': ts,
            }
    return None


# --serve error overlay state. _safe_build writes the last build error here
# (or clears it on success); the HTTP handler reads it to decide whether to
# wrap the served HTML in a red-bordered error overlay.
_last_build_error: dict | None = None


class _StderrTee:
    """File-like wrapper that writes to two streams. Used in --serve mode
    so build errors still appear in the terminal AND get captured for the
    overlay simultaneously."""

    def __init__(self, primary, secondary):
        self._a = primary
        self._b = secondary

    def write(self, s):
        try:
            self._a.write(s)
        except Exception:
            pass
        try:
            self._b.write(s)
        except Exception:
            pass
        return len(s)

    def flush(self):
        for s in (self._a, self._b):
            try:
                s.flush()
            except Exception:
                pass

    def isatty(self):
        try:
            return self._a.isatty()
        except Exception:
            return False


def _render_error_overlay_html(err: dict, base_html: str | None) -> bytes:
    """Wrap (or replace) base_html with a styled red error overlay.

    The overlay floats over whatever the previous successful build produced,
    so the author still sees their last good render behind it. A "Retry"
    button POSTs to /rebuild which triggers _build_once.
    """
    ts = err.get('ts', '')
    kind = err.get('kind', 'Error')
    message = err.get('message', '')
    stderr = err.get('stderr', '')
    title_text = f'{kind}: {message}' if message else kind

    overlay = (
        '<div id="__mdlout_error_overlay__" '
        'style="position:fixed;left:0;right:0;bottom:0;'
        'max-height:60vh;overflow:auto;'
        'background:#fff;color:#222;'
        'border-top:4px solid #c0392b;'
        'box-shadow:0 -2px 8px rgba(0,0,0,.25);'
        'font:13px/1.4 ui-monospace,Menlo,Consolas,monospace;'
        'padding:.8em 1em;z-index:2147483647">'
        '<div style="display:flex;align-items:center;'
        'justify-content:space-between;gap:1em;margin-bottom:.5em">'
        '<strong style="color:#c0392b;font:600 14px/1.2 system-ui,sans-serif">'
        f'mdlout build error [{_html_escape(ts)}]'
        '</strong>'
        '<span>'
        '<button onclick="fetch(\'/rebuild\',{method:\'POST\'})'
        '.then(function(){setTimeout(function(){location.reload();},300);})" '
        'style="background:#c0392b;color:#fff;border:0;border-radius:3px;'
        'padding:.35em .9em;cursor:pointer;font:600 12px system-ui">Retry</button> '
        '<button onclick="document.getElementById(\'__mdlout_error_overlay__\').remove()" '
        'style="background:#777;color:#fff;border:0;border-radius:3px;'
        'padding:.35em .9em;cursor:pointer;font:600 12px system-ui">Dismiss</button>'
        '</span>'
        '</div>'
        f'<div style="color:#a93226;font-weight:600">{_html_escape(title_text)}</div>'
        f'<pre style="margin:.4em 0 0 0;white-space:pre-wrap;'
        f'word-break:break-word">{_html_escape(stderr)}</pre>'
        '</div>'
    )

    if base_html:
        if '</body>' in base_html:
            wrapped = base_html.replace('</body>', overlay + '\n</body>', 1)
        else:
            wrapped = base_html + overlay
        return wrapped.encode('utf-8')

    # No prior successful build to overlay onto -- produce a minimal page.
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<title>mdlout build error</title>'
        + _LIVE_RELOAD_SCRIPT
        + '</head><body style="margin:0;font-family:system-ui;background:#fafafa">'
        + overlay
        + '</body></html>'
    ).encode('utf-8')


def _run_watch(args) -> None:
    """Loop: rebuild whenever args.input's mtime advances."""
    if args.input == '-':
        print('--watch requires a file argument (cannot watch stdin)', file=sys.stderr)
        sys.exit(2)

    last = _watch_file_mtime(args.input)
    _safe_build(args)  # initial build
    print(f'watching {args.input} (Ctrl-C to exit)', file=sys.stderr)
    try:
        while True:
            time.sleep(0.5)
            cur = _watch_file_mtime(args.input)
            if cur and cur != last:
                last = cur
                _safe_build(args)
    except KeyboardInterrupt:
        print('\nwatch: bye', file=sys.stderr)


# Used by --serve to wake every connected EventSource client.
_serve_lock = threading.Lock()
_serve_condition = threading.Condition(_serve_lock)
_serve_version = 0  # monotonic build counter, bumped after each rebuild


def _bump_serve_version() -> None:
    global _serve_version
    with _serve_condition:
        _serve_version += 1
        _serve_condition.notify_all()


def _run_serve(args, port: int) -> None:
    """Serve the rendered HTML at / with /events SSE live-reload."""
    if args.input == '-':
        print('--serve requires a file argument', file=sys.stderr)
        sys.exit(2)
    if args.format != 'html':
        print('--serve only supports --format=html', file=sys.stderr)
        sys.exit(2)

    global _LIVE_RELOAD_SCRIPT
    _LIVE_RELOAD_SCRIPT = (
        '<script>'
        '(function(){'
        'try{var es=new EventSource("/events");'
        'es.addEventListener("reload",function(){location.reload();});'
        '}catch(e){}'
        '})();'
        '</script>'
    )

    out_path = _safe_build(args)
    if not out_path:
        print('serve: initial build failed; exiting', file=sys.stderr)
        sys.exit(1)
    out_path_abs = os.path.abspath(out_path)

    import http.server  # noqa: E402

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):  # quieter default
            pass

        def do_GET(self):
            if self.path in ('/', '/index.html'):
                try:
                    with open(out_path_abs, 'rb') as f:
                        body = f.read()
                except OSError as e:
                    self.send_error(500, str(e))
                    return
                # If the most recent build failed, drape a red error overlay
                # over the last-known-good HTML so the author sees the error
                # without losing the previous render or having to read the
                # terminal. Retry button POSTs /rebuild.
                if _last_build_error is not None:
                    try:
                        body_str = body.decode('utf-8', errors='replace')
                    except Exception:
                        body_str = None
                    body = _render_error_overlay_html(
                        _last_build_error, body_str
                    )
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == '/events':
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                with _serve_condition:
                    last_ver = _serve_version
                try:
                    while True:
                        with _serve_condition:
                            _serve_condition.wait(timeout=15.0)
                            cur = _serve_version
                        if cur != last_ver:
                            last_ver = cur
                            self.wfile.write(b'event: reload\ndata: 1\n\n')
                        else:
                            # heartbeat keeps the socket alive through proxies
                            self.wfile.write(b': ping\n\n')
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    return
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/rebuild':
                # Force a rebuild on demand. Used by the error-overlay
                # "Retry" button -- author hits it after fixing the input
                # without having to ctrl-S the source.
                if _safe_build(args):
                    _bump_serve_version()
                self.send_response(204)
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                return
            self.send_error(404)

    class ThreadingServer(http.server.ThreadingHTTPServer):
        daemon_threads = True

    httpd = ThreadingServer(('127.0.0.1', port), Handler)
    print(f'serving http://127.0.0.1:{port}/  (Ctrl-C to exit)', file=sys.stderr)

    def _serve_forever():
        try:
            httpd.serve_forever()
        except Exception:
            pass

    t = threading.Thread(target=_serve_forever, daemon=True)
    t.start()

    last = _watch_file_mtime(args.input)
    try:
        while True:
            time.sleep(0.5)
            cur = _watch_file_mtime(args.input)
            if cur and cur != last:
                last = cur
                _safe_build(args)
                # Bump on both success AND failure so the connected
                # EventSource reloads and the overlay (or restored
                # render) shows up immediately.
                _bump_serve_version()
    except KeyboardInterrupt:
        print('\nserve: bye', file=sys.stderr)
        httpd.shutdown()


# ---------------------------------------------------------------------------
# --check and --init helpers
# ---------------------------------------------------------------------------

def _run_check(input_path: str) -> int:
    """Parse-only mode: run md -> Lout pipeline without invoking lout.

    Prints "OK: {path} ({N} blocks)" on success and returns 0.
    Prints "{path}:{line}:{col}: {message}" (line/col elided if not
    recoverable) to stderr on failure and returns 2.
    """
    try:
        if input_path == '-':
            md_text = sys.stdin.read()
        else:
            with open(input_path, encoding='utf-8') as f:
                md_text = f.read()
        _reset_xref_state()
        global _cite_format, _output_format, _highlight_enabled
        frontmatter, md_body = parse_frontmatter(md_text)
        _cite_format = (frontmatter.get('references_format')
                        or frontmatter.get('references-format')
                        or 'numeric').lower()
        if _cite_format not in ('numeric', 'alpha'):
            _cite_format = 'numeric'
        _output_format = 'html'
        _highlight_enabled = True
        md_body = _scan_citations(md_body)
        md_body = _scan_footnotes(md_body)
        _scan_fig_tab_labels(md_body, frontmatter.get('type', 'doc').lower())
        blocks = parse_markdown(md_body)
        blocks = _inject_bibliography(blocks)
        _scan_html_headings(blocks)
        # generate_lout exercises every block's emission path.
        generate_lout(blocks, frontmatter)
    except Exception as e:
        line = getattr(e, 'lineno', None)
        col = getattr(e, 'colno', None) or getattr(e, 'offset', None)
        prefix = input_path
        if line is not None:
            prefix += f':{line}'
            if col is not None:
                prefix += f':{col}'
        print(f'{prefix}: {e}', file=sys.stderr)
        return 2
    print(f'OK: {input_path} ({len(blocks)} blocks)')
    return 0


_INIT_INDEX_MD = '''\
---
title: My mdlout document
author: Your Name
date: 2026-05-22
type: doc
---

# Hello

This is a starter document for **mdlout**.  Edit `index.md` and
rebuild with:

    ./mdlout.py index.md --serve

## Features

- Math: $E = mc^2$
- Lists, tables, links, footnotes -- see `examples/` in the
  mdlout repo for the full feature surface.

## A code block

```python
print("hello, mdlout")
```
'''

_INIT_MYDEFS = '# Add your Lout macro definitions here\n'

_INIT_GITIGNORE = '*.html\n*.pdf\n*.ps\n*.lt\n'

_INIT_README_TMPL = '''\
# {name}

Built with [mdlout](https://github.com/jclements3/mdlout).

## Quick start

    ./mdlout.py index.md           # build HTML
    ./mdlout.py index.md --format=pdf
    ./mdlout.py index.md --serve   # live preview on http://127.0.0.1:8080/
'''


def _run_init(target: str) -> int:
    """Scaffold a new mdlout project under target dir.

    Refuses to clobber a non-empty existing directory.
    """
    path = Path(target)
    if path.exists():
        if not path.is_dir():
            print(f'mdlout --init: {target!s} exists and is not a directory',
                  file=sys.stderr)
            return 1
        if any(path.iterdir()):
            print(f'mdlout --init: {target!s} is not empty; refusing to clobber',
                  file=sys.stderr)
            return 1
    path.mkdir(parents=True, exist_ok=True)

    name = path.resolve().name or 'mdlout-project'
    (path / 'index.md').write_text(_INIT_INDEX_MD, encoding='utf-8')
    (path / 'mydefs').write_text(_INIT_MYDEFS, encoding='utf-8')
    (path / '.gitignore').write_text(_INIT_GITIGNORE, encoding='utf-8')
    (path / 'README.md').write_text(
        _INIT_README_TMPL.format(name=name), encoding='utf-8')

    if target == '.':
        display = '.'
    elif os.path.isabs(target):
        display = target
    else:
        display = f'./{target}'
    cmd_path = 'index.md' if target == '.' else f'{target}/index.md'
    print(f'Initialised mdlout project in {display}')
    print('  index.md       (starter markdown)')
    print('  mydefs         (Lout macro definitions)')
    print('  .gitignore     (build artefacts)')
    print('  README.md')
    print()
    print(f'Next: ./mdlout.py {cmd_path} --serve')
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='mdlout',
        description='Convert Markdown → Lout → HTML (default) or PDF.',
    )
    parser.add_argument(
        '--version', action='version', version=f'mdlout {VERSION}',
    )
    parser.add_argument(
        '--check', action='store_true',
        help='Parse-only: run the md -> Lout pipeline without invoking '
             'the lout binary. Exit 0 on success, 2 on parse failure. '
             'Useful for CI / pre-commit hooks.',
    )
    parser.add_argument(
        '--init', nargs='?', const='.', default=None, metavar='DIR',
        help='Scaffold a new mdlout project (index.md, mydefs, .gitignore, '
             'README.md) in DIR (default: current directory). Refuses to '
             'clobber a non-empty directory.',
    )
    parser.add_argument('input', nargs='?', help='Input Markdown file (- for stdin)')
    parser.add_argument('-o', '--output', help='Output file (default: INPUT.html or INPUT.pdf)')

    parser.add_argument(
        '--format', choices=('html', 'pdf'), default='html',
        help='Output format: html (default, via lout -G SVG back end) or pdf',
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--lout-only', action='store_true',
        help='Only produce Lout source (print to stdout or -o file)',
    )
    mode.add_argument(
        '--ps', action='store_true',
        help='Stop at PostScript (do not convert to PDF); implies --format=pdf',
    )
    mode.add_argument(
        '--pdf', action='store_true',
        help='Legacy alias for --format=pdf',
    )

    parser.add_argument('--lout-bin', default=None, help='Path to lout binary')
    parser.add_argument(
        '--mydefs', default=None,
        help='Path to a Lout mydefs file (default: look for mydefs next to input)',
    )
    parser.add_argument(
        '--lout-args', default='',
        help='Extra arguments to pass to lout',
    )
    parser.add_argument(
        '--external-assets', action='store_true',
        help='Reference KaTeX/abcjs from CDN instead of inlining local copies '
             '(smaller HTML, requires network at view time)',
    )
    parser.add_argument(
        '--no-math-engine', action='store_true',
        help='Omit KaTeX from the generated HTML (smaller output)',
    )
    parser.add_argument(
        '--no-music-engine', action='store_true',
        help='Omit abcjs from the generated HTML (smaller output)',
    )
    parser.add_argument(
        '--no-mermaid-engine', action='store_true',
        help='Omit mermaid.js from the generated HTML (smaller output; '
             '```mermaid blocks will not render in the browser)',
    )
    parser.add_argument(
        '--no-font-embedding', action='store_true',
        help='Do not inline URW++ Nimbus @font-face web fonts into the HTML '
             '(smaller output; SVG text will fall back to system fonts and '
             'may drift slightly from the PS/PDF render)',
    )
    parser.add_argument(
        '--subset-fonts', action='store_true',
        help='Subset the inlined URW Nimbus base-35 fonts to only the '
             'codepoints actually used in the document.  Typical savings: '
             '50-90%% off the embedded font payload (~3.5 MB -> a few '
             'hundred KB).  Requires fontTools (pip install --user '
             'fonttools); falls back to full-font inline if unavailable. '
             'ON by default since v0.3 -- this flag is now a no-op kept '
             'for backwards compatibility.  Use --no-subset-fonts to opt '
             'out, or `subset-fonts: false` in frontmatter.',
    )
    parser.add_argument(
        '--no-subset-fonts', action='store_true',
        help='Disable font subsetting and inline the full URW Nimbus '
             'base-35 outlines (the pre-v0.3 default).  Use this if a '
             'document mutates text content client-side (KaTeX with '
             'runtime macros, abcjsharp dynamic re-render, etc.) and '
             'needs every codepoint available in the inlined fonts.  '
             'Adds ~1 MB to the HTML payload.  Can also be set via '
             '`subset-fonts: false` in frontmatter.',
    )
    parser.add_argument(
        '--no-highlight', action='store_true',
        help='Disable highlight.js syntax highlighting for fenced code '
             'blocks. With highlighting on (default), HTML-mode code blocks '
             'render as a <pre><code class="language-XYZ"> the browser '
             'colourises via the highlight.js CDN.',
    )
    parser.add_argument(
        '--no-a11y', action='store_true',
        help='Omit accessibility scaffolding (semantic landmarks, skip link, '
             'image-alt manifest, focus-ring styles) from the HTML output. '
             'Produces marginally smaller HTML but fails WCAG 2.1 AA on '
             'multiple criteria; only use for diff/regression tooling.',
    )
    parser.add_argument(
        '--dark', nargs='?', const='force', default=None,
        choices=('force', 'auto'), metavar='MODE',
        help='Emit an opt-in dark-mode CSS block. MODE is "force" (default '
             'when --dark is given with no argument) or "auto". '
             '"force" applies the dark theme unconditionally; "auto" wraps '
             'the rules in @media (prefers-color-scheme: dark) so the OS '
             'theme decides. The dark theme re-tints the SVG via a CSS '
             'color: cascade (z53.c emits fill="currentColor" for default '
             'black ink), so text reads light-on-dark while embedded raster '
             'images and authored colours stay unmodified. Also settable '
             'via `dark-mode: true|auto|force` or `theme: dark` in YAML '
             'frontmatter.',
    )
    parser.add_argument(
        '--inline-raster', action='store_true',
        help='Base64-inline raster images (png/jpg/jpeg/gif/webp) that the '
             'SVG references via <image href="...">. Produces a fully self-'
             'contained HTML file at the cost of size. Off by default; can '
             'also be enabled via `inline-raster: true` in frontmatter.',
    )
    parser.add_argument(
        '--text-as-paths', action='store_true',
        help='Replace SVG <text> elements with <path> outlines extracted from '
             'URW++ Nimbus (the Adobe-base-14 substitutes Ghostscript itself '
             'uses).  Eliminates the browser/rsvg text rasteriser from the '
             'pipeline so PS and HTML renderers paint the same vector geometry. '
             'Increases output size noticeably; requires fontTools.',
    )
    parser.add_argument(
        '--watch', action='store_true',
        help='Rebuild whenever the input .md changes on disk (Ctrl-C to exit)',
    )
    parser.add_argument(
        '--serve', nargs='?', const=8080, type=int, default=None, metavar='PORT',
        help='Serve the rendered HTML at http://127.0.0.1:PORT/ with SSE live-reload '
             '(default port 8080; implies --watch and --format=html)',
    )

    args = parser.parse_args()

    # --init: scaffold and exit, no input file required.
    if args.init is not None:
        sys.exit(_run_init(args.init))

    # All remaining modes require an input file.
    if not args.input:
        parser.error('the following arguments are required: input')

    # --check: parse-only, never touches the lout binary.
    if args.check:
        sys.exit(_run_check(args.input))

    # --ps and --pdf are legacy / format-overriding flags
    if args.ps or args.pdf:
        args.format = 'pdf'

    # --serve implies HTML and live-reload
    if args.serve is not None:
        if args.format != 'html':
            print('--serve only supports --format=html (overriding)', file=sys.stderr)
            args.format = 'html'
        _run_serve(args, args.serve)
        return

    if args.watch:
        _run_watch(args)
        return

    _build_once(args)


if __name__ == '__main__':
    main()
