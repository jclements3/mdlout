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
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


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
    """Replace all placeholder tokens with their stored Lout content."""
    for key, val in _ph_store.items():
        text = text.replace(key, val)
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

    # Images: ![alt](url) — SVG files get routed through @SVGFile (the SVG
    # back-end inlines the file's contents verbatim); everything else falls
    # back to @IncludeGraphic.
    def _image_repl(m: re.Match) -> str:
        url = m.group(2)
        global _needs_svgmacros
        if url.lower().endswith('.svg'):
            _needs_svgmacros = True
            return _ph_put(f'@SVGFile {{ "{url}" }}')
        return _ph_put(f'@IncludeGraphic {{ "{url}" }}')
    result = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _image_repl, result)

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
            blocks.append(_parse_pipe_table(table_lines))
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
    for line in table_lines:
        if _TABLE_SEP_RE.match(line):
            has_header = True
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        rows.append(cells)
    return Block(type=BlockType.TABLE, rows=rows, meta={'has_header': has_header})


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

    # Simple YAML parser — handles key: value pairs (no nesting needed)
    fm: dict[str, str] = {}
    for line in yaml_block.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, _, val = line.partition(':')
            fm[key.strip().lower()] = val.strip().strip('"').strip("'")
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
        entry = '@Report'
        if title:
            entry += f'\n  @Title {{ {title} }}'
        if author:
            entry += f'\n  @Author {{ {author} }}'
        if institution:
            entry += f'\n  @Institution {{ {institution} }}'
        entry += '\n//'
        parts.append(entry)
    elif doc_type == 'book':
        title = frontmatter.get('title', '')
        author = frontmatter.get('author', '')
        entry = '@Book'
        if title:
            entry += f'\n  @Title {{ {title} }}'
        if author:
            entry += f'\n  @Author {{ {author} }}'
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
    match block.type:
        case BlockType.PARAGRAPH:
            return f'@PP\n{convert_inline(block.content)}'
        case BlockType.HEADING:
            level = min(block.level, 6)
            return f'{_HEADING_GAP[level]}\n@Display {_HEADING_FONTS[level]} {{ {convert_inline(block.content)} }}'
        case BlockType.CODE_BLOCK:
            lang = f'# language: {block.language}\n' if block.language else ''
            return f'{lang}@LP\n@IndentedDisplay @F @Verbatim @Begin\n{block.content}\n@End @Verbatim'
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
            global _needs_svgmacros
            _needs_svgmacros = True
            # Pass LaTeX body opaquely through @Math as one Lout string.
            return f'@LP\n@CentredDisplay @Math {{ "{_lout_string_encode(block.content.strip())}" }}'
        case BlockType.ABC:
            _needs_svgmacros = True
            return f'@LP\n@ABC {{ "{_lout_string_encode(block.content)}" }}'
        case BlockType.SVG_RAW:
            _needs_svgmacros = True
            return f'@LP\n@SVG {{ "{_lout_string_encode(block.content)}" }}'
        case BlockType.TOC:
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
    cols = [chr(ord('A') + i) for i in range(min(num_cols, 26))]
    fmt = ' | '.join(f'@Cell {c}' for c in cols[:num_cols])

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


def _run_lout(lout_bin: str, lout_flags: list[str], lt_file: str, ps_file: str) -> None:
    """Run lout up to 3 times to resolve cross-references."""
    cmd = [lout_bin] + lout_flags + [lt_file, '-o', ps_file]
    result = None
    for _ in range(3):
        result = subprocess.run(cmd, capture_output=True, text=True)
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


def _build_font_face_css() -> tuple[str, list[str]]:
    """Build @font-face CSS embedding Nimbus fonts as base64 data URLs.

    Returns (css, used_paths).  If no source files are available the CSS is
    empty and used_paths is [].  Each face is mapped to the Adobe family
    name Lout's SVG back-end references ("Times" / "Helvetica" / "Courier"),
    so an SVG `<text font-family="Times" font-weight="bold">` resolves to
    the embedded Nimbus Roman Bold outlines (Ghostscript's own metric
    source for the Adobe base 14).
    """
    import base64

    pieces: list[str] = []
    used: list[str] = []
    for family, style, weight, candidates in _FONT_EMBED_SPECS:
        path = next((p for p in candidates if os.path.isfile(p)), None)
        if path is None:
            continue
        try:
            with open(path, 'rb') as f:
                raw = f.read()
        except OSError:
            continue
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
    return ''.join(pieces), used


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


def _build_html_scaffold(
    svg: str,
    title: str,
    *,
    external_assets: bool = False,
    math_engine: bool = True,
    music_engine: bool = True,
    embed_fonts: bool = True,
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
        'embedded_fonts': None,
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
        font_css, font_paths = _build_font_face_css()
        if font_css:
            head_parts.append(f'<style>{font_css}</style>')
            info['embedded_fonts'] = (
                f'{len(font_paths)} face(s) from '
                f'{os.path.dirname(font_paths[0])} (inlined base64)'
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
        '@media print{body{background:#fff;padding:0}'
        '.lout-page{box-shadow:none;margin:0;page-break-after:always}}'
        '</style>'
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

    # ---- Init script --------------------------------------------------------
    # Runs once both KaTeX auto-render and abcjs are loaded. We hook
    # DOMContentLoaded and also expose renderMath()/renderMusic() so the
    # defer-loaded CDN scripts can call them after they arrive.
    init_js_parts: list[str] = []
    if math_engine:
        init_js_parts.append(
            "window.renderMath=function(){"
            "if(typeof renderMathInElement!=='function')return;"
            "renderMathInElement(document.body,{delimiters:["
            "{left:'$$',right:'$$',display:true},"
            "{left:'$',right:'$',display:false},"
            "{left:'\\\\(',right:'\\\\)',display:false},"
            "{left:'\\\\[',right:'\\\\]',display:true}"
            "],throwOnError:false});"
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
    init_js_parts.append(
        "function _mdloutInit(){"
        + ("window.renderMath&&renderMath();" if math_engine else "")
        + ("window.renderMusic&&renderMusic();" if music_engine else "")
        + "}"
        "if(document.readyState==='loading')"
        "document.addEventListener('DOMContentLoaded',_mdloutInit);"
        "else _mdloutInit();"
    )

    head = '\n'.join(head_parts)
    init_js = '\n'.join(init_js_parts)

    return (
        '<!DOCTYPE html>\n'
        f'<html lang="en">\n<head>\n{head}\n</head>\n'
        f'<body>\n{svg}\n'
        f'<script>{init_js}</script>\n'
        '</body>\n</html>\n'
    ), info


def _html_escape(s: str) -> str:
    return (
        s.replace('&', '&amp;')
         .replace('<', '&lt;')
         .replace('>', '&gt;')
         .replace('"', '&quot;')
    )


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
    blocks = parse_markdown(md_text)
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

        if args.format == 'html':
            svg_file = os.path.join(tmpdir, f'{input_stem}.svg')
            _run_lout(lout_bin, lout_flags + ['-G'], lt_file, svg_file)

            with open(svg_file, encoding='utf-8') as f:
                svg = f.read()
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
            html, asset_info = _build_html_scaffold(
                svg,
                title,
                external_assets=args.external_assets,
                math_engine=not args.no_math_engine,
                music_engine=not args.no_music_engine,
                embed_fonts=not args.no_font_embedding,
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
    """Run _build_once but swallow exceptions so watch/serve keep going."""
    try:
        out = _build_once(args)
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[rebuilt {ts}] {out}', file=sys.stderr)
        return out
    except SystemExit as e:
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[error {ts}] build exited with {e.code}', file=sys.stderr)
    except Exception as e:
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[error {ts}] {type(e).__name__}: {e}', file=sys.stderr)
    return None


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
                if _safe_build(args):
                    _bump_serve_version()
    except KeyboardInterrupt:
        print('\nserve: bye', file=sys.stderr)
        httpd.shutdown()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='mdlout',
        description='Convert Markdown → Lout → HTML (default) or PDF.',
    )
    parser.add_argument('input', help='Input Markdown file (- for stdin)')
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
        '--no-font-embedding', action='store_true',
        help='Do not inline URW++ Nimbus @font-face web fonts into the HTML '
             '(smaller output; SVG text will fall back to system fonts and '
             'may drift slightly from the PS/PDF render)',
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
