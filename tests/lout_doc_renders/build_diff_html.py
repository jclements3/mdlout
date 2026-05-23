#!/usr/bin/env python3
"""Build a per-doc HTML index of sampled side-by-side PS-vs-SVG composites."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

HTML_HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<style>
body{{font:14px/1.4 system-ui,sans-serif;background:#f4f4f4;color:#222;
     margin:0;padding:1.5em}}
h1{{margin:0 0 .3em}}
nav a{{margin-right:.8em;color:#0066cc;text-decoration:none}}
nav a:hover{{text-decoration:underline}}
table.summary{{border-collapse:collapse;margin:1em 0;font-size:13px}}
table.summary th,table.summary td{{
  border:1px solid #ccc;padding:.3em .6em;text-align:right}}
table.summary th{{background:#eaeaea}}
table.summary td:first-child{{text-align:left;font-family:monospace}}
.sample{{background:#fff;border:1px solid #ddd;border-radius:4px;
  padding:.8em;margin:.8em 0;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.sample h3{{margin:0 0 .4em;font-size:14px}}
.sample img{{display:block;max-width:100%;height:auto;border:1px solid #eee}}
.verdict-OK{{color:#0a0;font-weight:bold}}
.verdict-DIFF{{color:#c80;font-weight:bold}}
.verdict-BAD{{color:#c00;font-weight:bold}}
.verdict-MISSING{{color:#888;font-style:italic}}
</style>
</head><body>
<nav>
  <a href="./README.md">README</a>
  <a href="./design_diff.html">design</a>
  <a href="./expert_diff.html">expert</a>
  <a href="./slides_diff.html">slides</a>
  <a href="./user_diff.html">user</a>
  <span>|</span>
  <a href="./design.html">design HTML</a>
  <a href="./expert.html">expert HTML</a>
  <a href="./slides.html">slides HTML</a>
  <a href="./user.html">user HTML</a>
</nav>
<h1>{title}</h1>
"""


def verdict(ratio_str: str) -> str:
    try:
        r = float(ratio_str)
    except ValueError:
        return "MISSING"
    if r < 0.05:
        return "OK"
    if r < 0.20:
        return "DIFF"
    return "BAD"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--samples-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    rows = []
    with args.manifest.open() as fh:
        for i, line in enumerate(fh):
            parts = line.rstrip("\n").split("\t")
            if i == 0:
                continue
            rows.append(parts)

    title = f"Lout doc/{args.doc} — PostScript vs z53.c SVG sample diff"

    html = [HTML_HEAD.format(title=title)]
    html.append('<p>Sampled pages, rendered via both the PostScript pipeline '
                f'(<code>lout</code> + ps2pdf + pdftoppm) and the SVG pipeline '
                f'(<code>lout&nbsp;-G</code> via z53.c + rsvg-convert). '
                'AE = ImageMagick absolute-error pixel count at 5% fuzz; '
                'SSIM is scikit-image structural_similarity on luminance '
                '(1.0 = identical).</p>')

    html.append('<table class="summary"><thead><tr>'
                '<th>Page</th><th>W</th><th>H</th>'
                '<th>Diff px</th><th>Diff %</th><th>SSIM</th><th>Verdict</th>'
                '</tr></thead><tbody>')
    for r in rows:
        if len(r) < 6:
            continue
        page, w, h, diff_px, ratio, ssim = r[0], r[1], r[2], r[3], r[4], r[5]
        v = verdict(ratio)
        try:
            ratio_pct = f"{float(ratio) * 100:.2f}"
        except ValueError:
            ratio_pct = ratio
        html.append(
            f'<tr><td><a href="#p{page}">{page}</a></td>'
            f'<td>{w}</td><td>{h}</td>'
            f'<td>{diff_px}</td><td>{ratio_pct}</td><td>{ssim}</td>'
            f'<td class="verdict-{v}">{v}</td></tr>'
        )
    html.append('</tbody></table>')

    # Per-page side-by-sides
    samples_rel = args.samples_dir.name
    for r in rows:
        if len(r) < 6:
            continue
        page = r[0]
        img = args.samples_dir / f"sample-{page}.png"
        rel = f"{samples_rel}/{img.name}"
        if not img.exists():
            continue
        ratio = r[4]
        v = verdict(ratio)
        try:
            ratio_pct = f"{float(ratio) * 100:.2f}%"
        except ValueError:
            ratio_pct = ratio
        html.append(
            f'<section class="sample" id="p{page}">'
            f'<h3>Page {page} — verdict <span class="verdict-{v}">{v}</span> '
            f'(diff {ratio_pct}, SSIM {r[5]})</h3>'
            f'<img src="{rel}" alt="PS vs SVG vs DIFF for page {page}">'
            f'</section>'
        )

    html.append('</body></html>')
    args.out.write_text("".join(html), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
