#!/usr/bin/env python3
"""mdlout - Markdown to Lout converter.

Converts Markdown to Lout, runs lout to produce PostScript, and converts to PDF.

Usage:
    ./mdlout input.md              # produces input.pdf
    ./mdlout input.md -o out.pdf   # produces out.pdf
    ./mdlout input.md --lout-only  # print Lout source to stdout
    ./mdlout input.md --ps         # stop at PostScript (input.ps)
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
    Double-quote itself becomes '"\\""'.
    """
    def _repl(m: re.Match) -> str:
        ch = m.group(1)
        if ch == '"':
            return '"\\""'
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

    # Backslash escapes: \@ \* \_ \` \\ etc.
    result = re.sub(
        r'\\([\\`*_{}[\]()#+\-.!~@|>])',
        lambda m: _ph_put(lout_escape(m.group(1))),
        result,
    )

    # Images: ![alt](url)
    result = re.sub(
        r'!\[([^\]]*)\]\(([^)]+)\)',
        lambda m: _ph_put(f'@IncludeGraphic {{ "{m.group(2)}" }}'),
        result,
    )

    # Links: [text](url)
    def _link_repl(m: re.Match) -> str:
        link_text = _convert_inline_inner(m.group(1))
        url = m.group(2)
        return _ph_put(f'{link_text} @FootNote {{ @F {{ {lout_escape(url)} }} }}')
    result = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link_repl, result)

    # Inline code: `code`
    result = re.sub(
        r'`([^`]+)`',
        lambda m: _ph_put('@F { ' + lout_escape(m.group(1)) + ' }'),
        result,
    )

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

        # Fenced code block
        m = _FENCED_START_RE.match(stripped)
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
            if _HEADING_RE.match(cs) or _HR_RE.match(cs) or _FENCED_START_RE.match(cs):
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
    needs_eq = any(b.type == BlockType.MATH_BLOCK for b in blocks)

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
        parts.append(f'@SysInclude {{ {pkg} }}')
    else:
        # Generate a custom setup: include base packages, mydefs, then @Use blocks
        parts.append('@SysInclude { langdefs }')
        parts.append('@SysInclude { bsf }')
        parts.append('@SysInclude { dsf }')
        if needs_tbl:
            parts.append('@SysInclude { tbl }')
        if needs_eq:
            parts.append('@SysInclude { eq }')

        # Package-specific setup include
        type_include = {'doc': 'docf', 'report': 'reportf', 'book': 'bookf', 'slides': 'slidesf'}
        parts.append(f'@SysInclude {{ {type_include[doc_type]} }}')
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
    parts: list[str] = _generate_preamble(fm, blocks)

    if doc_type in ('report', 'book'):
        parts.extend(_generate_sectioned_body(blocks, doc_type))
    elif doc_type == 'slides':
        parts.extend(_generate_slides_body(blocks))
    else:
        for block in blocks:
            lout = _block_to_lout(block)
            if lout:
                parts.append(lout)
                parts.append('')

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
            return f'@LP\n@CentredDisplay @Eq {{ {block.content} }}'
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
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='mdlout',
        description='Convert Markdown → Lout → PostScript → PDF.',
    )
    parser.add_argument('input', help='Input Markdown file (- for stdin)')
    parser.add_argument('-o', '--output', help='Output file (default: INPUT.pdf)')

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        '--lout-only', action='store_true',
        help='Only produce Lout source (print to stdout or -o file)',
    )
    mode.add_argument(
        '--ps', action='store_true',
        help='Stop at PostScript (do not convert to PDF)',
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

    args = parser.parse_args()

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
        else:
            sys.stdout.write(lout_src)
        return

    # Full pipeline: md → .lt → .ps → .pdf
    lout_bin = _find_lout_bin(args.lout_bin)
    extra_flags = shlex.split(args.lout_args) if args.lout_args else []
    lib_flags = _find_lout_lib(lout_bin)

    lout_flags = lib_flags + extra_flags

    with tempfile.TemporaryDirectory(prefix='mdlout_') as tmpdir:
        lt_file = os.path.join(tmpdir, f'{input_stem}.lt')
        ps_file = os.path.join(tmpdir, f'{input_stem}.ps')

        with open(lt_file, 'w', encoding='utf-8') as f:
            f.write(lout_src)

        # Copy mydefs into the temp dir so Lout's @Include { mydefs } finds it.
        # Priority: --mydefs flag > mydefs next to input file > (none, use library default)
        mydefs_src = None
        if args.mydefs:
            mydefs_src = Path(args.mydefs)
        elif args.input != '-':
            candidate = Path(args.input).resolve().parent / 'mydefs'
            if candidate.is_file():
                mydefs_src = candidate
        if mydefs_src:
            shutil.copy2(mydefs_src, os.path.join(tmpdir, 'mydefs'))

        # Add temp dir as an include path so Lout finds the mydefs there first,
        # and add the input file's directory for any user @Include files
        lout_flags = ['-I', tmpdir] + lout_flags
        if args.input != '-':
            input_dir = str(Path(args.input).resolve().parent)
            if input_dir != tmpdir:
                lout_flags = ['-I', input_dir] + lout_flags

        _run_lout(lout_bin, lout_flags, lt_file, ps_file)

        if args.ps:
            # --ps: copy PS to final destination
            out = args.output or f'{input_stem}.ps'
            shutil.copy2(ps_file, out)
            print(out, file=sys.stderr)
            return

        # Convert PS → PDF
        pdf_file = os.path.join(tmpdir, f'{input_stem}.pdf')
        _run_ps2pdf(ps_file, pdf_file)

        out = args.output or f'{input_stem}.pdf'
        shutil.copy2(pdf_file, out)
        print(out, file=sys.stderr)


if __name__ == '__main__':
    main()
