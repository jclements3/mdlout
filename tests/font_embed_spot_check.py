#!/usr/bin/env python3
"""Spot-check the metric-alignment fix for a Lout-emitted SVG.

This script compares two rsvg-convert rasters of the same per-page SVG
against the Ghostscript-rendered PostScript page:

  1. baseline    — rsvg-convert with the system's default fontconfig.
                   "Times"/"Helvetica"/"Courier" resolve to whatever
                   system substitute is configured (typically Liberation
                   on Debian-family / Nimbus on some distros).
  2. aliased     — rsvg-convert with a *forced* fontconfig aliasing the
                   three Adobe base-14 family names to URW++ Nimbus,
                   the same outlines Ghostscript uses for its PostScript
                   render.  This is the librsvg-side analogue of the
                   @font-face web fonts mdlout now embeds in the HTML
                   wrapper for browser rendering.
  3. reference   — Ghostscript-rendered PS for the same page.

Pixel diff vs. reference is measured at 5% fuzz with ImageMagick
`compare -metric AE`.  Lower = closer to PS.

NB: librsvg (Cairo+Pango) does NOT honour @font-face — it can't load
fonts from data: URLs.  The fontconfig alias approach is the only way
to test the metric improvement without a real browser, and it exercises
the same Nimbus outlines that mdlout's @font-face block embeds for
browser/HTML rendering.

Usage:
    tests/font_embed_spot_check.py [PAGE [PAGE ...]]

Requires:
    /tmp/userguide_compare/ from `tests/user_guide_diff.sh` (any recent run)
    rsvg-convert, compare (ImageMagick), fc-cache
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORK = Path('/tmp/userguide_compare')
PS_DIR = WORK / 'ps'
SVG_DIR = WORK / 'svg_split'

sys.path.insert(0, str(REPO))
import mdlout  # noqa: E402 — re-uses _build_font_face_css

# Fontconfig snippet that forces "Times" / "Helvetica" / "Courier" to
# resolve to URW++ Nimbus — the same outlines Ghostscript uses for the
# Adobe base 14, and the same outlines mdlout's @font-face block embeds.
NIMBUS_FC = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>/usr/share/fonts/opentype/urw-base35</dir>
  <alias binding="strong"><family>Times</family>
    <prefer><family>Nimbus Roman</family></prefer></alias>
  <alias binding="strong"><family>Helvetica</family>
    <prefer><family>Nimbus Sans</family></prefer></alias>
  <alias binding="strong"><family>Courier</family>
    <prefer><family>Nimbus Mono PS</family></prefer></alias>
</fontconfig>
"""


def render(svg_text: str, png_path: Path, *, fontconfig: str | None = None) -> None:
    env = os.environ.copy()
    with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
        f.write(svg_text)
        tmp = f.name
    fc_file = None
    try:
        if fontconfig is not None:
            with tempfile.NamedTemporaryFile(
                'w', suffix='.conf', delete=False,
            ) as fc:
                fc.write(fontconfig)
                fc_file = fc.name
            env['FONTCONFIG_FILE'] = fc_file
        subprocess.run(
            ['rsvg-convert', '-d', '100', '-p', '100', '-f', 'png',
             tmp, '-o', str(png_path)],
            check=True, stderr=subprocess.DEVNULL, env=env,
        )
    finally:
        os.unlink(tmp)
        if fc_file is not None:
            try:
                os.unlink(fc_file)
            except OSError:
                pass


def diff_ae(a: Path, b: Path) -> int:
    """ImageMagick AE pixel-difference count with 5% fuzz."""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        diff_png = f.name
    try:
        r = subprocess.run(
            ['compare', '-metric', 'AE', '-fuzz', '5%',
             str(a), str(b), diff_png],
            capture_output=True, text=True,
        )
        out = (r.stderr or r.stdout).strip().split()[-1]
        return int(out) if out.isdigit() else -1
    finally:
        try:
            os.unlink(diff_png)
        except OSError:
            pass


def inject_font_css(svg: str, css: str) -> str:
    """Insert a <style> block holding the @font-face CSS at the top of <defs>."""
    style = f'<defs><style type="text/css"><![CDATA[{css}]]></style></defs>'
    # put it right after the root <svg ...> open tag
    return re.sub(r'(<svg[^>]*>)', r'\1\n' + style, svg, count=1)


def main(argv: list[str]) -> int:
    if shutil.which('rsvg-convert') is None or shutil.which('compare') is None:
        print('error: need rsvg-convert and ImageMagick compare on PATH',
              file=sys.stderr)
        return 2
    if not WORK.is_dir():
        print(f'error: {WORK} missing — run tests/user_guide_diff.sh first',
              file=sys.stderr)
        return 2

    css, used_paths = mdlout._build_font_face_css()
    if not css:
        print('error: no Nimbus fonts found at the expected paths',
              file=sys.stderr)
        return 2

    pages = argv[1:] or ['002', '010', '030', '050']
    print(f'mdlout @font-face: {len(used_paths)} faces; CSS = {len(css)} bytes')
    print(f'(rsvg-convert proxy: fontconfig alias to the same Nimbus outlines)')
    print(f'{"page":>5} {"baseline":>10} {"aliased":>10}  delta  '
          f'ratio_baseline  ratio_aliased')

    sum_base = sum_alias = sum_total = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        for n in pages:
            svg_path = SVG_DIR / f'page-{n}.svg'
            ps_png = PS_DIR / f'ps-{n}.png'
            if not svg_path.is_file() or not ps_png.is_file():
                print(f'  page {n}: missing inputs, skipping')
                continue
            raw = svg_path.read_text(encoding='utf-8')

            base_png = td / f'base-{n}.png'
            alias_png = td / f'alias-{n}.png'
            render(raw, base_png, fontconfig=None)
            render(raw, alias_png, fontconfig=NIMBUS_FC)

            base_diff = diff_ae(ps_png, base_png)
            alias_diff = diff_ae(ps_png, alias_png)

            wh = subprocess.run(
                ['identify', '-format', '%w %h', str(ps_png)],
                capture_output=True, text=True, check=True,
            ).stdout.split()
            total = int(wh[0]) * int(wh[1])
            sum_base += max(base_diff, 0)
            sum_alias += max(alias_diff, 0)
            sum_total += total
            print(f'  {n:>3}  {base_diff:>10}  {alias_diff:>10}  '
                  f'{alias_diff - base_diff:+7d}  '
                  f'{base_diff / total:>13.4f}  '
                  f'{alias_diff / total:>13.4f}')

    if sum_total:
        print(f'  {"sum":>3}  {sum_base:>10}  {sum_alias:>10}  '
              f'{sum_alias - sum_base:+7d}  '
              f'{sum_base / sum_total:>13.4f}  '
              f'{sum_alias / sum_total:>13.4f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
