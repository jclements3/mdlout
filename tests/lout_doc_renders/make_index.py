#!/usr/bin/env python3
"""Write tests/lout_doc_renders/index.html: a landing page listing each
of the 4 Lout doc renders with a page-1 thumbnail, page count, file sizes,
and SSIM mean. Vanilla HTML + CSS, no JS framework. Run after build.sh /
diff.sh have produced the renders and /tmp/loutdocs/<doc>/sample_manifest.tsv.

The thumbnails live in tests/lout_doc_renders/thumbs/<doc>_p1.png and are
rasterised from <doc>.pdf via pdftocairo + ImageMagick `convert -resize`.
"""
from __future__ import annotations

import html
import subprocess
import sys
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "tests" / "lout_doc_renders"
WORK = Path("/tmp/loutdocs")
THUMBS = OUT / "thumbs"

DOCS = ["design", "expert", "slides", "user"]

# Maintainer fork; the working branch holding z53.c and svgmacros is svg-backend.
DOC_GH_URL = "https://github.com/jclements3/lout/tree/svg-backend/doc/{doc}"

DOC_BLURB = {
    "design": "Jeffrey Kingston's 1993 design paper on Lout's galley system. "
              "Heavy on @Eq, @Fig, worked examples.",
    "expert": "The Expert's Guide (@Book style). Advanced features: @Span, "
              "@TagItem, custom galleys, @Insert, rotated graphics.",
    "slides": "@OverheadTransparencies style. Big fonts, landscape, lots "
              "of @Code blocks; light on graphics.",
    "user":   "The User's Guide. The reference document also tracked by "
              "tests/user_guide_diff.sh.",
}


def page_count_from_pdf(pdf: Path) -> int:
    try:
        r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return 0


def sample_ssim_mean(manifest: Path) -> tuple[float | None, float | None]:
    if not manifest.exists():
        return None, None
    ssims, diffs = [], []
    for i, line in enumerate(manifest.read_text().splitlines()):
        if i == 0 or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            diffs.append(float(parts[4]))
        except ValueError:
            pass
        try:
            ssims.append(float(parts[5]))
        except ValueError:
            pass
    return (mean(ssims) if ssims else None,
            mean(diffs) if diffs else None)


def human_bytes(n: int) -> str:
    if n == 0:
        return "—"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def ensure_thumb(doc: str) -> str:
    """Generate <doc>_p1.png at ~300px wide from <doc>.pdf via pdftocairo.
    Returns the relative path used in the HTML (or empty string on failure)."""
    THUMBS.mkdir(exist_ok=True)
    out_png = THUMBS / f"{doc}_p1.png"
    pdf = OUT / f"{doc}.pdf"
    if not pdf.exists():
        return ""
    tmp = THUMBS / f"{doc}_p1_tmp"
    try:
        subprocess.run(
            ["pdftocairo", "-png", "-singlefile", "-r", "50",
             "-f", "1", "-l", "1", str(pdf), str(tmp)],
            check=True, capture_output=True)
        subprocess.run(
            ["convert", str(tmp) + ".png", "-resize", "300x", str(out_png)],
            check=True, capture_output=True)
        (THUMBS / (tmp.name + ".png")).unlink(missing_ok=True)
    except Exception as e:
        print(f"thumb {doc}: {e}", file=sys.stderr)
        return ""
    return f"thumbs/{doc}_p1.png"


def ssim_class(s: float | None) -> str:
    if s is None:
        return "ssim-na"
    if s >= 0.95:
        return "ssim-good"
    if s >= 0.85:
        return "ssim-ok"
    return "ssim-diff"


def main() -> int:
    rows = []
    for d in DOCS:
        pdf = OUT / f"{d}.pdf"
        html_p = OUT / f"{d}.html"
        svg_tmp = Path(f"/tmp/{d}.svg")
        sample_manifest = WORK / d / "sample_manifest.tsv"
        ssim_m, diff_m = sample_ssim_mean(sample_manifest)
        thumb_path = ensure_thumb(d)
        rows.append({
            "doc": d,
            "pages": page_count_from_pdf(pdf),
            "pdf_bytes": pdf.stat().st_size if pdf.exists() else 0,
            "html_bytes": html_p.stat().st_size if html_p.exists() else 0,
            "svg_bytes": svg_tmp.stat().st_size if svg_tmp.exists() else 0,
            "ssim_mean": ssim_m,
            "diff_pct_mean": diff_m,
            "thumb": thumb_path,
            "blurb": DOC_BLURB.get(d, ""),
        })

    css = """
:root{--bg:#f4f4f4;--card:#fff;--ink:#222;--mute:#666;--accent:#0066cc;
--good:#0a0;--ok:#c80;--diff:#c00;--na:#888;--border:#ddd}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:1.6em 1.2em 3em}
h1{margin:0 0 .1em;font-size:1.7em}
h1 small{color:var(--mute);font-weight:normal;font-size:.55em}
p.lede{color:var(--mute);margin:.2em 0 1.4em}
.hero{display:grid;grid-template-columns:repeat(4,1fr);gap:.6em;
margin:1.2em 0 1.6em}
.hero a{display:block;background:var(--card);border:1px solid var(--border);
border-radius:6px;padding:.5em;text-align:center;text-decoration:none;
color:var(--ink);box-shadow:0 1px 3px rgba(0,0,0,.06);
transition:transform .15s, box-shadow .15s}
.hero a:hover{transform:translateY(-2px);box-shadow:0 3px 8px rgba(0,0,0,.12)}
.hero img{display:block;width:100%;height:auto;border:1px solid #eee;
background:#fafafa}
.hero .lbl{display:block;margin-top:.4em;font-weight:600;font-size:.95em}

table.docs{border-collapse:collapse;width:100%;background:var(--card);
border:1px solid var(--border);border-radius:6px;overflow:hidden;
box-shadow:0 1px 3px rgba(0,0,0,.06)}
table.docs th,table.docs td{padding:.65em .7em;border-bottom:1px solid var(--border);
vertical-align:top;text-align:left}
table.docs th{background:#eaeaea;font-size:.85em;text-transform:uppercase;
letter-spacing:.04em;color:#555}
table.docs tr:last-child td{border-bottom:none}
table.docs td.num{text-align:right;font-variant-numeric:tabular-nums;
white-space:nowrap}
table.docs td.thumb{width:170px}
table.docs td.thumb img{display:block;width:150px;height:auto;
border:1px solid #ddd;background:#fafafa}
table.docs td.title{min-width:220px}
table.docs td.title .doc-name{font-weight:600;font-size:1.05em}
table.docs td.title .doc-blurb{color:var(--mute);font-size:.88em;
margin-top:.3em;line-height:1.45}
table.docs td.links a{display:inline-block;margin-right:.5em;
margin-bottom:.25em;color:var(--accent);text-decoration:none;
font-size:.88em;white-space:nowrap}
table.docs td.links a:hover{text-decoration:underline}
.ssim-good{color:var(--good);font-weight:600}
.ssim-ok{color:var(--ok);font-weight:600}
.ssim-diff{color:var(--diff);font-weight:600}
.ssim-na{color:var(--na);font-style:italic}
footer{margin-top:2em;color:var(--mute);font-size:.85em;line-height:1.6}
footer code{background:#eee;padding:0 .3em;border-radius:3px}
@media (max-width:760px){
  .hero{grid-template-columns:repeat(2,1fr)}
  table.docs td.thumb{display:none}
}
"""

    # Hero strip
    hero_items = []
    for r in rows:
        thumb = r["thumb"] or ""
        if thumb:
            hero_items.append(
                f'<a href="{r["doc"]}.html"><img src="{html.escape(thumb)}" '
                f'alt="{r["doc"]} page 1"><span class="lbl">{r["doc"]}</span></a>'
            )
        else:
            hero_items.append(
                f'<a href="{r["doc"]}.html"><span class="lbl">{r["doc"]}</span></a>'
            )
    hero = '<section class="hero">' + "".join(hero_items) + "</section>"

    # Doc rows
    body_rows = []
    for r in rows:
        thumb = r["thumb"] or ""
        thumb_cell = (f'<a href="{r["doc"]}.html">'
                      f'<img src="{html.escape(thumb)}" alt="{r["doc"]} page 1"></a>') if thumb else "—"
        ssim_txt = f"{r['ssim_mean']:.4f}" if r["ssim_mean"] is not None else "—"
        diff_txt = (f"{r['diff_pct_mean']*100:.2f}%"
                    if r["diff_pct_mean"] is not None else "—")
        gh_url = DOC_GH_URL.format(doc=r["doc"])
        body_rows.append(
            "<tr>"
            f'<td class="thumb">{thumb_cell}</td>'
            f'<td class="title">'
            f'<span class="doc-name">{r["doc"]}</span>'
            f'<div class="doc-blurb">{html.escape(r["blurb"])}</div>'
            f'</td>'
            f'<td class="num">{r["pages"] or "—"}</td>'
            f'<td class="num">{human_bytes(r["html_bytes"])}</td>'
            f'<td class="num">{human_bytes(r["pdf_bytes"])}</td>'
            f'<td class="num">{human_bytes(r["svg_bytes"])}</td>'
            f'<td class="num {ssim_class(r["ssim_mean"])}">{ssim_txt}</td>'
            f'<td class="num">{diff_txt}</td>'
            f'<td class="links">'
            f'<a href="{r["doc"]}.html">HTML</a>'
            f'<a href="{r["doc"]}.pdf">PDF</a>'
            f'<a href="{r["doc"]}_diff.html">diff gallery</a>'
            f'<a href="{gh_url}" target="_blank" rel="noopener">Lout source</a>'
            f'</td>'
            "</tr>"
        )

    table = (
        '<table class="docs">'
        '<thead><tr>'
        '<th>Page 1</th><th>Document</th><th>Pages</th>'
        '<th>HTML</th><th>PDF</th><th>SVG</th>'
        '<th>SSIM</th><th>Diff %</th><th>Links</th>'
        '</tr></thead>'
        '<tbody>' + "".join(body_rows) + '</tbody>'
        '</table>'
    )

    foot = (
        '<footer>'
        '<p>SSIM is scikit-image <code>structural_similarity</code> '
        '(Wang et al. 2004) mean over 10 evenly-spaced sample pages '
        'comparing the PostScript (ps2pdf + pdftoppm 100&nbsp;dpi) and '
        'SVG (<code>lout&nbsp;-G</code> via <code>z53.c</code> + '
        'rsvg-convert 100&nbsp;dpi) renders. 1.0 = pixel-identical, '
        '&gt;0.95 visually indistinguishable, &lt;0.85 actually '
        'different. Diff&nbsp;% is the ImageMagick AE pixel-diff ratio '
        'at 5% fuzz over the same samples.</p>'
        '<p>Reproduce: '
        '<code>bash tests/lout_doc_renders/build.sh</code>. '
        'See <a href="README.md">README.md</a> for per-doc notes and the '
        'list of known back-end divergences.</p>'
        '</footer>'
    )

    html_doc = (
        '<!DOCTYPE html>'
        '<html lang="en"><head><meta charset="utf-8">'
        '<title>Lout doc renders — PostScript vs z53.c SVG</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<style>{css}</style>'
        '</head><body><div class="wrap">'
        '<h1>Lout doc renders <small>PostScript vs z53.c SVG</small></h1>'
        '<p class="lede">End-to-end renders of the four documents that '
        'ship with the Lout source tree, built via both the legacy '
        'PostScript pipeline and the new SVG back-end (<code>z53.c</code>). '
        'Each HTML page is a standalone Lout document; click a thumbnail '
        'or row for the full render.</p>'
        + hero + table + foot +
        '</div></body></html>'
    )

    out_path = OUT / "index.html"
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"wrote {out_path} ({len(html_doc)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
