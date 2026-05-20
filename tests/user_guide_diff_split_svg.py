#!/usr/bin/env python3
"""Split a multi-page Lout SVG document (one `<svg>` per page) into
individual per-page SVG files.

Called by tests/user_guide_diff.sh. Stdlib only.

Usage:
    user_guide_diff_split_svg.py <input.svg> <output_dir>
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: user_guide_diff_split_svg.py <input.svg> <output_dir>", file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    prolog = '<?xml version="1.0" encoding="UTF-8"?>\n'
    current: list[str] = []
    in_page = False
    page_idx = 0

    with src.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("<svg "):
                in_page = True
                current = [prolog, line]
            elif in_page:
                current.append(line)
                if line.startswith("</svg>"):
                    page_idx += 1
                    (out_dir / f"page-{page_idx:03d}.svg").write_text(
                        "".join(current), encoding="utf-8"
                    )
                    in_page = False
                    current = []

    print(f"wrote {page_idx} pages to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
