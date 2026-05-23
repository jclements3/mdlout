#!/usr/bin/env python3
"""Wrap a multi-page Lout SVG file in a minimal HTML5 scaffold.

Inspired by mdlout.py:_build_html_scaffold, but standalone -- this
runs against Lout source (not Markdown), so we can't reuse the mdlout
helper directly. CDN-loaded KaTeX is fine here; this is documentation,
not the regression gallery.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

KATEX_VERSION = "0.16.11"
KATEX_BASE = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist"

CSS = """
html,body{margin:0;padding:0;background:#e8e8e8;
font-family:Times,"Liberation Serif",serif}
body{padding:2em 0}
header.docnav{position:fixed;top:0;left:0;right:0;z-index:10;
background:rgba(40,40,40,0.92);color:#eee;padding:.5em 1em;
font:14px system-ui,sans-serif;display:flex;gap:1em;align-items:center}
header.docnav a{color:#88c0ff;text-decoration:none}
header.docnav a:hover{text-decoration:underline}
header.docnav .spacer{flex:1}
main{padding-top:3.2em}
.lout-page{display:block;margin:1em auto;background:#fff;
box-shadow:0 1px 4px rgba(0,0,0,0.25);max-width:100%}
foreignObject{overflow:visible}
.math{display:inline-block}
@media print{
  html,body{background:#fff!important;margin:0!important;padding:0!important}
  header.docnav{display:none!important}
  main{padding-top:0!important}
  .lout-page{box-shadow:none!important;margin:0!important;padding:0!important;
    page-break-before:always;page-break-after:auto;
    break-before:page;break-after:auto;
    page-break-inside:avoid;break-inside:avoid;max-width:none!important}
  .lout-page:first-of-type,main>article>.lout-page:first-of-type{
    page-break-before:auto;break-before:auto}
  main,article{margin:0!important;padding:0!important;display:block}
}
"""


def build_scaffold(svg_body: str, title: str) -> str:
    # Wrap with a tiny navbar showing siblings + a print-stylesheet
    # that mimics mdlout.py's print rules (page-per-sheet).
    head = (
        '<!DOCTYPE html>'
        '<html lang="en"><head><meta charset="utf-8">'
        f'<title>{title}</title>'
        f'<link rel="stylesheet" href="{KATEX_BASE}/katex.min.css">'
        f'<script defer src="{KATEX_BASE}/katex.min.js"></script>'
        f'<script defer src="{KATEX_BASE}/contrib/auto-render.min.js"'
        ' onload="renderMathInElement(document.body, {throwOnError:false});"></script>'
        f'<style>{CSS}</style>'
        '</head><body>'
    )
    nav = (
        '<header class="docnav">'
        f'<strong>{title}</strong>'
        '<span class="spacer"></span>'
        '<a href="./design.html">design</a>'
        '<a href="./expert.html">expert</a>'
        '<a href="./slides.html">slides</a>'
        '<a href="./user.html">user</a>'
        '<span>|</span>'
        '<a href="./README.md">README</a>'
        '</header>'
    )
    body = f'<main><article>{svg_body}</article></main>'
    foot = '</body></html>'
    return head + nav + body + foot


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--svg", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    svg_text = args.svg.read_text(encoding="utf-8", errors="replace")
    # Strip any leading XML decl (svg back-end output is bare <svg> per page).
    if svg_text.startswith("<?xml"):
        eol = svg_text.find("?>")
        if eol >= 0:
            svg_text = svg_text[eol + 2:]

    html = build_scaffold(svg_text, args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"wrote {args.out} ({len(html)} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
