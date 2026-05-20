#!/usr/bin/env python3
"""Wrap per-page Lout SVG files in minimal HTML so a headless browser can
rasterise them with the @font-face Nimbus base-35 fonts that mdlout itself
embeds in its HTML wrapper.

This is the SVG-rendering half of the chromium_diff pipeline that lives in
tests/chromium_diff.sh. The PS-rendering half (Ghostscript -> pdftoppm) is
unchanged.

Two outputs:
  * <out_dir>/nimbus_fonts.css   -- shared @font-face declarations (base64).
  * <out_dir>/html/page-NNN.html -- one HTML per input SVG that links the CSS
                                   and forces the SVG to render at exactly
                                   595 x 842 CSS pixels (A4 in CSS pixels).

Usage:
    chromium_wrap_svg.py <svg_dir> <out_dir>           # wrap every page-*.svg
    chromium_wrap_svg.py --pages 001,010 <svg_dir> <out_dir>

Stdlib only. The Nimbus paths match the canonical Debian/Ubuntu locations
that mdlout._FONT_EMBED_SPECS targets.
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

# Mirror mdlout._FONT_EMBED_SPECS exactly: same family names, same style /
# weight pairs, same font files. If mdlout changes its embedded faces this
# script must be updated in lockstep (the whole point is to mimic what the
# user sees in a browser).
_FONT_EMBED_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ('Times',     'normal', 'normal', '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Regular.otf'),
    ('Times',     'normal', 'bold',   '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Bold.otf'),
    ('Times',     'italic', 'normal', '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Italic.otf'),
    ('Times',     'italic', 'bold',   '/usr/share/fonts/opentype/urw-base35/NimbusRoman-BoldItalic.otf'),
    ('Helvetica', 'normal', 'normal', '/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf'),
    ('Helvetica', 'normal', 'bold',   '/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf'),
    ('Helvetica', 'italic', 'normal', '/usr/share/fonts/opentype/urw-base35/NimbusSans-Italic.otf'),
    ('Helvetica', 'italic', 'bold',   '/usr/share/fonts/opentype/urw-base35/NimbusSans-BoldItalic.otf'),
    ('Courier',   'normal', 'normal', '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Regular.otf'),
    ('Courier',   'normal', 'bold',   '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Bold.otf'),
    ('Courier',   'italic', 'normal', '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-Italic.otf'),
    ('Courier',   'italic', 'bold',   '/usr/share/fonts/opentype/urw-base35/NimbusMonoPS-BoldItalic.otf'),
)


def build_font_face_css() -> tuple[str, list[str]]:
    pieces: list[str] = []
    used: list[str] = []
    for family, style, weight, path in _FONT_EMBED_SPECS:
        p = Path(path)
        if not p.is_file():
            continue
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode('ascii')
        fmt = 'opentype' if p.suffix == '.otf' else 'truetype'
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


# A4 in PostScript points is 595 x 842, which is also what Lout writes into
# every <svg width="595pt" height="842pt"> element. Chrome's default
# pt-to-CSS-px conversion (1pt = 1/72in, 1px = 1/96in) would render that as
# 793 x 1123 CSS px -- wider than the screenshot we want. The matching
# pdftoppm PS render is 100 dpi (= 826 x 1169 px for A4), so we explicitly
# force the SVG to fill 826 x 1169 CSS pixels and pair this template with
# a Chromium --window-size=826,1169 (no device-scale-factor needed). One
# pixel narrower / shorter than ps2pdf+pdftoppm's 827 x 1170 because the
# 842pt * 100/72 = 1169.44 rounds down in Chromium; the runner crops PS
# down to 826 x 1169 before diffing.
_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="stylesheet" href="{css_href}">
<style>
html,body{{margin:0;padding:0;background:#fff;font-family:Times,"Liberation Serif",serif}}
svg.lout-page{{display:block;margin:0;background:#fff;width:826px;height:1169px}}
</style>
</head>
<body>
{svg}
</body>
</html>
"""


def wrap_one(svg_path: Path, html_path: Path, css_href: str) -> None:
    svg = svg_path.read_text(encoding='utf-8')
    # Strip the XML prolog (`<?xml ?>`) -- HTML parsers ignore it but it
    # confuses some sanitizers and is redundant inline inside HTML5.
    if svg.startswith('<?xml'):
        svg = svg.split('?>', 1)[1].lstrip()
    html_path.write_text(
        _HTML_TEMPLATE.format(
            title=svg_path.stem,
            css_href=css_href,
            svg=svg,
        ),
        encoding='utf-8',
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('svg_dir', type=Path, help='dir of page-NNN.svg files')
    ap.add_argument('out_dir', type=Path, help='destination dir')
    ap.add_argument('--pages', default='',
                    help='comma-separated page numbers (zero-padded ok); '
                         'default = all page-*.svg in svg_dir')
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    html_dir = args.out_dir / 'html'
    html_dir.mkdir(parents=True, exist_ok=True)

    css, used = build_font_face_css()
    if not css:
        print('error: no Nimbus fonts found on the system; install '
              'fonts-urw-base35 or adjust _FONT_EMBED_SPECS', file=sys.stderr)
        return 1
    css_path = args.out_dir / 'nimbus_fonts.css'
    css_path.write_text(css, encoding='utf-8')
    print(f'wrote {css_path} ({len(css)} bytes from {len(used)} face(s))')

    if args.pages:
        wanted = {p.strip().zfill(3) for p in args.pages.split(',') if p.strip()}
        svgs = sorted(args.svg_dir.glob('page-*.svg'))
        svgs = [s for s in svgs if s.stem.split('-')[1] in wanted]
    else:
        svgs = sorted(args.svg_dir.glob('page-*.svg'))

    count = 0
    for svg_path in svgs:
        out = html_dir / f'{svg_path.stem}.html'
        wrap_one(svg_path, out, css_href='../nimbus_fonts.css')
        count += 1

    print(f'wrapped {count} page(s) into {html_dir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
