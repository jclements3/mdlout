#!/usr/bin/env python3
"""Augment tests/user_guide_diff/manifest.json (and manifest.txt) with a
per-page SSIM column.

Rationale
---------
The existing AE metric counts every pixel whose RGB differs by more than
5% between the PostScript and SVG renders. That number includes every
subpixel anti-aliasing difference between Ghostscript and librsvg, so
content-identical pages routinely score 7-15% AE.

SSIM (structural similarity index, Wang et al. 2004) is a perceptual
metric in [0, 1]: 1.0 means pixel-identical, >0.95 means visually
indistinguishable at this DPI, <0.85 means actually different.

This script does NOT recompute AE. It only adds an ``ssim`` field to
each page record and an ``ssim_summary`` block to the JSON.

Inputs
------
- /tmp/userguide_compare/ps/ps-NNN.png
- /tmp/userguide_compare/svg/svg-NNN.png
- tests/user_guide_diff/manifest.json   (existing AE manifest, in place)

Outputs (overwrites in place)
-----------------------------
- tests/user_guide_diff/manifest.json   (now with ssim fields + summary)
- tests/user_guide_diff/manifest.txt    (now with trailing ssim column)
- tests/user_guide_diff/ssim_summary.txt (human-readable aggregate)
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

PS_DIR = Path("/tmp/userguide_compare/ps")
SVG_DIR = Path("/tmp/userguide_compare/svg")
MANIFEST_JSON = Path(
    "/home/clementsj/projects/mdlout/tests/user_guide_diff/manifest.json"
)
MANIFEST_TXT = Path(
    "/home/clementsj/projects/mdlout/tests/user_guide_diff/manifest.txt"
)
SUMMARY_TXT = Path(
    "/home/clementsj/projects/mdlout/tests/user_guide_diff/ssim_summary.txt"
)


def compute_ssim(ps_path: Path, svg_path: Path) -> float:
    ps = np.asarray(Image.open(ps_path).convert("L"))
    svg = np.asarray(Image.open(svg_path).convert("L"))
    if ps.shape != svg.shape:
        # Pad / crop to the smaller intersection so SSIM is defined.
        h = min(ps.shape[0], svg.shape[0])
        w = min(ps.shape[1], svg.shape[1])
        ps = ps[:h, :w]
        svg = svg[:h, :w]
    return float(ssim(ps, svg, data_range=255))


def main() -> int:
    doc = json.loads(MANIFEST_JSON.read_text())
    pages = doc["pages"]

    ssim_values: list[float] = []
    for rec in pages:
        page = rec["page"]
        ps_path = PS_DIR / f"ps-{page}.png"
        svg_path = SVG_DIR / f"svg-{page}.png"
        if not ps_path.exists() or not svg_path.exists():
            rec["ssim"] = None
            continue
        v = compute_ssim(ps_path, svg_path)
        rec["ssim"] = round(v, 4)
        ssim_values.append(v)

    # Aggregate stats
    n = len(ssim_values)
    if n:
        mean_ssim = statistics.fmean(ssim_values)
        median_ssim = statistics.median(ssim_values)
        ge_99 = sum(1 for v in ssim_values if v >= 0.99)
        ge_95 = sum(1 for v in ssim_values if v >= 0.95)
        ge_85 = sum(1 for v in ssim_values if v >= 0.85)
        lt_85 = sum(1 for v in ssim_values if v < 0.85)
        min_v = min(ssim_values)
        max_v = max(ssim_values)
    else:
        mean_ssim = median_ssim = min_v = max_v = float("nan")
        ge_99 = ge_95 = ge_85 = lt_85 = 0

    doc.setdefault("metadata", {})["ssim_metric"] = (
        "skimage.metrics.structural_similarity (grayscale, data_range=255)"
    )
    doc["ssim_summary"] = {
        "pages_with_ssim": n,
        "mean_ssim": round(mean_ssim, 4),
        "median_ssim": round(median_ssim, 4),
        "min_ssim": round(min_v, 4),
        "max_ssim": round(max_v, 4),
        "count_ge_0_99": ge_99,
        "count_ge_0_95": ge_95,
        "count_ge_0_85": ge_85,
        "count_lt_0_85": lt_85,
    }

    # Worst10 enrichment: attach ssim where available.
    if "worst10" in doc:
        page_to_ssim = {p["page"]: p.get("ssim") for p in pages}
        for w in doc["worst10"]:
            w["ssim"] = page_to_ssim.get(w["page"])

    MANIFEST_JSON.write_text(json.dumps(doc, indent=2) + "\n")

    # Rewrite manifest.txt with appended ssim column.
    lines = MANIFEST_TXT.read_text().splitlines()
    if not lines:
        return 1
    out_lines = [lines[0].rstrip() + "\tssim"]
    page_to_ssim_str: dict[str, str] = {}
    for rec in pages:
        v = rec.get("ssim")
        page_to_ssim_str[rec["page"]] = "" if v is None else f"{v:.4f}"
    for line in lines[1:]:
        parts = line.split("\t")
        if not parts:
            continue
        page = parts[0]
        out_lines.append(line.rstrip() + "\t" + page_to_ssim_str.get(page, ""))
    MANIFEST_TXT.write_text("\n".join(out_lines) + "\n")

    summary = (
        f"SSIM summary (skimage.metrics.structural_similarity, grayscale, data_range=255)\n"
        f"Pages compared:        {n}\n"
        f"Mean SSIM:             {mean_ssim:.4f}\n"
        f"Median SSIM:           {median_ssim:.4f}\n"
        f"Min SSIM:              {min_v:.4f}\n"
        f"Max SSIM:              {max_v:.4f}\n"
        f"Pages SSIM >= 0.99:    {ge_99}\n"
        f"Pages SSIM >= 0.95:    {ge_95}  (visually indistinguishable)\n"
        f"Pages SSIM >= 0.85:    {ge_85}  (close)\n"
        f"Pages SSIM <  0.85:    {lt_85}  (visibly different)\n"
    )
    SUMMARY_TXT.write_text(summary)
    sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
