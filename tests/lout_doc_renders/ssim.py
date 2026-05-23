#!/usr/bin/env python3
"""Compute SSIM between two PNG files. Echoes a single float to stdout.

Mirrors tests/user_guide_diff_ssim.py's strategy: pad/crop to the
smaller intersection so SSIM is defined when the two renders differ
slightly in pixel size, then call skimage's structural_similarity with
data_range=255.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
    from skimage.metrics import structural_similarity as _ssim
except ImportError as e:
    print(f"NA", flush=True)
    sys.exit(0)


def main() -> int:
    if len(sys.argv) != 3:
        print("NA")
        return 0
    a = Path(sys.argv[1])
    b = Path(sys.argv[2])
    if not (a.exists() and b.exists()):
        print("NA")
        return 0
    pa = np.asarray(Image.open(a).convert("L"))
    pb = np.asarray(Image.open(b).convert("L"))
    h = min(pa.shape[0], pb.shape[0])
    w = min(pa.shape[1], pb.shape[1])
    pa = pa[:h, :w]
    pb = pb[:h, :w]
    try:
        v = float(_ssim(pa, pb, data_range=255))
    except Exception:
        print("NA")
        return 0
    print(f"{v:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
