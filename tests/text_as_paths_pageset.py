#!/usr/bin/env python3
"""Apply mdlout's _convert_text_to_paths to per-page SVGs and re-run the
PS-vs-SVG pixel diff for a chosen page set.

Usage:
    tests/text_as_paths_pageset.py PAGE [PAGE ...]
    tests/text_as_paths_pageset.py --worst N
        # automatically pick the N worst pages from
        # tests/user_guide_diff/manifest.json

Reads per-page SVGs from /tmp/userguide_compare/svg_split/page-NNN.svg
and PS PNGs from /tmp/userguide_compare/ps/ps-NNN.png. Writes converted
SVGs and rendered PNGs to /tmp/userguide_compare/tap/.  Prints a
side-by-side diff table.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from mdlout import _convert_text_to_paths  # noqa: E402

WORK = Path('/tmp/userguide_compare')
SVG_DIR = WORK / 'svg_split'
PS_PNG_DIR = WORK / 'ps'
TAP_DIR = WORK / 'tap'
TAP_DIR.mkdir(exist_ok=True)


def ae_diff(ps_png: Path, svg_png: Path, diff_png: Path) -> int:
    """Return ImageMagick AE-fuzz-5% pixel diff between two PNGs."""
    p = subprocess.run(
        ['compare', '-metric', 'AE', '-fuzz', '5%',
         str(ps_png), str(svg_png), str(diff_png)],
        capture_output=True, text=True,
    )
    raw = (p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout) else '0'
    digits = ''.join(c for c in raw if c.isdigit())
    return int(digits) if digits else 0


def total_pixels(png: Path) -> int:
    p = subprocess.run(
        ['identify', '-format', '%w %h', str(png)],
        capture_output=True, text=True, check=True,
    )
    w, h = (int(x) for x in p.stdout.split())
    return w * h


def render_svg(svg_path: Path, png_path: Path) -> None:
    subprocess.run(
        ['rsvg-convert', '-d', '100', '-p', '100', '-f', 'png',
         str(svg_path), '-o', str(png_path)],
        check=True, capture_output=True,
    )


def process_page(page: str) -> dict:
    """Process one page; return stats dict."""
    src_svg = SVG_DIR / f'page-{page}.svg'
    ps_png = PS_PNG_DIR / f'ps-{page}.png'
    if not src_svg.is_file() or not ps_png.is_file():
        return {'page': page, 'error': 'missing inputs'}

    # 1) baseline (original SVG)
    baseline_png = TAP_DIR / f'baseline-{page}.png'
    render_svg(src_svg, baseline_png)
    baseline_diff_png = TAP_DIR / f'baseline-diff-{page}.png'
    baseline_ae = ae_diff(ps_png, baseline_png, baseline_diff_png)

    # 2) text-as-paths conversion
    svg_text = src_svg.read_text(encoding='utf-8')
    svg_out, stats = _convert_text_to_paths(svg_text)
    tap_svg = TAP_DIR / f'tap-{page}.svg'
    tap_svg.write_text(svg_out, encoding='utf-8')
    tap_png = TAP_DIR / f'tap-{page}.png'
    render_svg(tap_svg, tap_png)
    tap_diff_png = TAP_DIR / f'tap-diff-{page}.png'
    tap_ae = ae_diff(ps_png, tap_png, tap_diff_png)

    total = total_pixels(ps_png)
    return {
        'page': page,
        'total_px': total,
        'baseline_ae': baseline_ae,
        'baseline_ratio': baseline_ae / total,
        'tap_ae': tap_ae,
        'tap_ratio': tap_ae / total,
        'delta_ae': tap_ae - baseline_ae,
        'delta_ratio': (tap_ae - baseline_ae) / total,
        'text_total': stats['text_total'],
        'text_converted': stats['text_converted'],
        'glyphs_emitted': stats['glyphs_emitted'],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('pages', nargs='*', help='page numbers like 019')
    ap.add_argument('--worst', type=int, default=None,
                    help='process the N worst pages from manifest.json')
    args = ap.parse_args()

    pages: list[str] = list(args.pages)
    if args.worst:
        manifest_path = REPO / 'tests' / 'user_guide_diff' / 'manifest.json'
        with manifest_path.open() as f:
            manifest = json.load(f)
        worst = manifest.get('worst10', [])[: args.worst]
        pages = [w['page'] for w in worst]

    if not pages:
        print('No pages selected', file=sys.stderr)
        return 2

    print(f'{"page":<6}{"baseline":>12}{"tap":>12}{"delta":>12}'
          f'{"base_ratio":>12}{"tap_ratio":>12}'
          f'{"texts":>8}{"glyphs":>8}')
    print('-' * 82)

    totals = {'baseline_ae': 0, 'tap_ae': 0, 'total_px': 0,
              'text_total': 0, 'text_converted': 0, 'glyphs_emitted': 0}
    rows = []
    for page in pages:
        r = process_page(page)
        if 'error' in r:
            print(f'{page:<6}  {r["error"]}')
            continue
        rows.append(r)
        for k in totals:
            totals[k] += r[k]
        print(
            f'{r["page"]:<6}'
            f'{r["baseline_ae"]:>12d}'
            f'{r["tap_ae"]:>12d}'
            f'{r["delta_ae"]:>+12d}'
            f'{r["baseline_ratio"]:>12.4%}'
            f'{r["tap_ratio"]:>12.4%}'
            f'{r["text_total"]:>8d}'
            f'{r["glyphs_emitted"]:>8d}'
        )
    if rows:
        n = len(rows)
        bratio = totals['baseline_ae'] / totals['total_px']
        tratio = totals['tap_ae'] / totals['total_px']
        print('-' * 82)
        print(
            f'TOTAL ({n}):'
            f' baseline {totals["baseline_ae"]} ({bratio:.4%})'
            f' -> tap {totals["tap_ae"]} ({tratio:.4%})'
            f' delta {totals["tap_ae"] - totals["baseline_ae"]:+d}'
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
