#!/usr/bin/env python3
"""Generate the JSON manifest (and optionally the worst-10 list) for
the PS-vs-SVG User's Guide comparison. Stdlib only.

Usage:
    user_guide_diff_manifest.py <manifest.txt> <out.json>
    user_guide_diff_manifest.py --print-worst <manifest.txt>

The second form prints the 10 worst pages (highest diff_ratio among
pages whose SVG exists) as "<ratio>\\t<page>" lines, ready to be piped
into the side-by-side compositor in tests/user_guide_diff.sh.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def load(manifest_txt: Path) -> list[dict]:
    pages: list[dict] = []
    with manifest_txt.open() as fh:
        fh.readline()  # header
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 6:
                continue
            page, ps_pixels, svg_pixels, diff_pixels, ratio, verdict = parts
            pages.append({
                "page": page,
                "ps_pixels": int(ps_pixels) if ps_pixels.isdigit() else ps_pixels,
                "svg_pixels": int(svg_pixels) if svg_pixels.isdigit() else svg_pixels,
                "diff_pixels": int(diff_pixels) if diff_pixels.isdigit() else diff_pixels,
                "diff_ratio": float(ratio),
                "verdict": verdict,
            })
    return pages


def submodule_sha() -> str:
    repo = Path(__file__).resolve().parent.parent
    return subprocess.check_output(
        ["git", "-C", str(repo / "lout"), "rev-parse", "HEAD"], text=True
    ).strip()


def build_json(pages: list[dict]) -> dict:
    present = [p for p in pages if p["verdict"] != "MISSING"]
    worst10 = sorted(present, key=lambda p: p["diff_ratio"], reverse=True)[:10]
    return {
        "metadata": {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lout_submodule_sha": submodule_sha(),
            "render_dpi": 100,
            "fuzz_percent": 5,
            "compare_metric": "AE",
            "ps_passes": 7,
            "svg_passes": 7,
            "ps_source": "lout/doc/user/all -> /tmp/user.ps",
            "svg_source": "lout/doc/user/all -> /tmp/user.svg (largest converged pass)",
        },
        "summary": {
            "total_pages": len(pages),
            "ok_lt_5pct": sum(1 for p in pages if p["verdict"] == "OK"),
            "diff_5_to_20pct": sum(1 for p in pages if p["verdict"] == "DIFF"),
            "bad_gt_20pct": sum(1 for p in pages if p["verdict"] == "BAD"),
            "missing_svg_pages": sum(1 for p in pages if p["verdict"] == "MISSING"),
        },
        "worst10": [
            {"page": p["page"], "diff_ratio": p["diff_ratio"]} for p in worst10
        ],
        "pages": pages,
    }


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--print-worst":
        pages = load(Path(argv[2]))
        present = [p for p in pages if p["verdict"] != "MISSING"]
        worst10 = sorted(present, key=lambda p: p["diff_ratio"], reverse=True)[:10]
        for p in worst10:
            print(f"{p['diff_ratio']:.4f}\t{p['page']}")
        return 0
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    pages = load(Path(argv[1]))
    out = Path(argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_json(pages), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
