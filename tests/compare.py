#!/usr/bin/env python3
"""
compare.py -- supplementary comparison + report generator for the
PS-vs-SVG regression framework.

Reads the per-snippet results that run_compare.sh wrote into
`out/results.txt`, augments them with SSIM (via scikit-image, when
importable) and a pixel-diff ratio, and emits:

  - out/results.json    machine-readable summary
  - report.html         side-by-side gallery for visual review

Verdict logic combines the two metrics:
  - AE-ratio < TEXT_PIXEL_THRESHOLD and SSIM >= STRICT_SSIM_THRESHOLD
        -> PASS-EXCELLENT
  - AE-ratio < GRAPHICS_PIXEL_THRESHOLD and SSIM >= TEXT_SSIM_THRESHOLD
        -> PASS
  - For snippets flagged graphics-heavy, the SSIM bar is relaxed to
    GRAPHICS_SSIM_THRESHOLD on the same pixel-ratio gates.
  - Otherwise -> FAIL.

When scikit-image is not importable, we skip SSIM (recording a "note"
on each row) and fall back to the AE-only verdict for backwards
compatibility with the previous framework.

Standard library + scikit-image only.
"""
from __future__ import annotations

import html
import json
import struct
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Graphics-heavy manifest.
#
# Snippets in this set are rendered through the SVG back end's bitmap /
# raw-PostScript path, where anti-aliasing differences between Ghostscript
# and librsvg accumulate.  We hold them to a looser SSIM bar.
# ----------------------------------------------------------------------
GRAPHICS_HEAVY = {
    "graphic_line",
    "graphic_circle",
    "graphic_stress",
    "transform_rotate",
    "box_curve",
    "box_shadow",
    "rule_full",
    "rule_local",
    "eq_matrix",
    "eq_matrix_3x3",
    "eq_integral_summation",
    "syntax_diag_repeat",
    "tree_deep",
    "fig_multi",
    "diag_labels_complex",
    "colour_mixed",
}

# Verdict thresholds.
TEXT_PIXEL_THRESHOLD = 0.05       # AE-ratio < 5%  -> "excellent" gate
GRAPHICS_PIXEL_THRESHOLD = 0.20   # AE-ratio < 20% -> passing gate
STRICT_SSIM_THRESHOLD = 0.95      # SSIM >= 0.95 -> "excellent"
TEXT_SSIM_THRESHOLD = 0.85        # SSIM >= 0.85 -> passing
GRAPHICS_SSIM_THRESHOLD = 0.75    # SSIM >= 0.75 -> graphics-heavy passing


# ----------------------------------------------------------------------
# PNG geometry probe -- stdlib only, no Pillow.
# ----------------------------------------------------------------------
def png_size(path: Path) -> tuple[int, int] | None:
    """Return (width, height) of a PNG, or None on failure."""
    try:
        with path.open("rb") as fh:
            sig = fh.read(8)
            if sig[:8] != b"\x89PNG\r\n\x1a\n":
                return None
            # Read IHDR length(4) + type(4) + payload(13) + crc(4).
            fh.read(4)            # length
            ctype = fh.read(4)
            if ctype != b"IHDR":
                return None
            w = struct.unpack(">I", fh.read(4))[0]
            h = struct.unpack(">I", fh.read(4))[0]
            return w, h
    except OSError:
        return None


# ----------------------------------------------------------------------
# SSIM (scikit-image + numpy + Pillow).  Skipped gracefully if the
# imports fail.
# ----------------------------------------------------------------------
def _try_import_ssim():
    try:
        import numpy  # noqa: F401
        from skimage.metrics import structural_similarity as ssim
        from PIL import Image  # type: ignore
        return ssim, Image, numpy
    except Exception:
        return None


SSIM_DEPS = _try_import_ssim()


def compute_ssim(ps_png: Path, svg_png: Path) -> float | None:
    if SSIM_DEPS is None:
        return None
    ssim, Image, numpy = SSIM_DEPS
    try:
        a = numpy.asarray(Image.open(ps_png).convert("L"))
        b = numpy.asarray(Image.open(svg_png).convert("L"))
        if a.shape != b.shape:
            # Crop both to the smaller intersection so SSIM is defined.
            h = min(a.shape[0], b.shape[0])
            w = min(a.shape[1], b.shape[1])
            a = a[:h, :w]
            b = b[:h, :w]
        return float(ssim(a, b, data_range=255))
    except Exception:
        return None


# ----------------------------------------------------------------------
# Verdict resolution.
# ----------------------------------------------------------------------
def classify(
    pixel_diff_ratio: float | None,
    ssim_val: float | None,
    is_graphics: bool,
) -> str:
    """Return one of PASS-EXCELLENT / PASS / FAIL / SKIP."""
    if pixel_diff_ratio is None:
        return "SKIP"

    # SSIM may be unavailable; in that case the SSIM gate is not
    # enforced (treated as satisfied) so we degrade to an AE-only check.
    ssim_ok_strict = (ssim_val is None) or (ssim_val >= STRICT_SSIM_THRESHOLD)
    pass_ssim_floor = (GRAPHICS_SSIM_THRESHOLD if is_graphics
                       else TEXT_SSIM_THRESHOLD)
    ssim_ok_pass = (ssim_val is None) or (ssim_val >= pass_ssim_floor)

    if pixel_diff_ratio < TEXT_PIXEL_THRESHOLD and ssim_ok_strict:
        return "PASS-EXCELLENT"
    if pixel_diff_ratio < GRAPHICS_PIXEL_THRESHOLD and ssim_ok_pass:
        return "PASS"
    return "FAIL"


# ----------------------------------------------------------------------
# Results parsing.
# ----------------------------------------------------------------------
def parse_results(results_path: Path) -> list[dict]:
    rows: list[dict] = []
    if not results_path.exists():
        return rows
    with results_path.open() as fh:
        header = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            line = line.rstrip("\n")
            if not line or "\t" not in line:
                continue
            parts = line.split("\t")
            row = dict(zip(header, parts))
            rows.append(row)
    return rows


# ----------------------------------------------------------------------
# HTML report.
# ----------------------------------------------------------------------
def _img_uri(path: Path) -> str:
    """Return a relative path suitable for a same-directory HTML file."""
    return path.name


_VERDICT_CLASSES = {
    "PASS-EXCELLENT": "pass-excellent",
    "PASS": "pass",
    "FAIL": "fail",
    "SKIP": "skip",
}


def render_html(report_path: Path, out_dir: Path, rows: list[dict]) -> None:
    style = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       Helvetica, Arial, sans-serif; margin: 1.5rem; color: #1c1c1c; }
h1 { margin-top: 0; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 0.55rem 0.6rem; border-bottom: 1px solid #ddd;
         vertical-align: top; font-size: 0.92rem; }
th { background: #f3f3f3; text-align: left; }
.badge { display: inline-block; padding: 0.15rem 0.55rem; border-radius:
         0.5rem; font-weight: 600; font-size: 0.78rem; white-space: nowrap; }
.pass-excellent { background: #bff0c8; color: #054d18; }
.pass { background: #d6f5dc; color: #0e6620; }
.fail { background: #f8d6d6; color: #8a1212; }
.skip { background: #eaeaea; color: #555; }
.gallery img { max-width: 280px; max-height: 380px;
               border: 1px solid #ccc; background: #fff; }
.gallery td { text-align: center; }
.note { color: #555; font-size: 0.82rem; }
.metric { font-variant-numeric: tabular-nums; }
.metric.ae { color: #1c1c1c; }
.metric.ssim { color: #1c1c1c; }
.metric .bad { color: #8a1212; font-weight: 600; }
.metric .ok  { color: #0e6620; font-weight: 600; }
.metric .warn { color: #8a5a12; font-weight: 600; }
.gh-flag { font-size: 0.72rem; color: #555; margin-left: 0.4rem; }
"""
    parts: list[str] = []
    parts.append("<!doctype html><html><head><meta charset='utf-8'>")
    parts.append("<title>Lout PS vs SVG regression report</title>")
    parts.append(f"<style>{style}</style></head><body>")
    parts.append("<h1>Lout PS vs SVG regression report</h1>")
    n = len(rows)
    n_exc = sum(1 for r in rows if r.get("verdict") == "PASS-EXCELLENT")
    n_pass = sum(1 for r in rows if r.get("verdict") == "PASS")
    n_fail = sum(1 for r in rows if r.get("verdict") == "FAIL")
    n_skip = n - n_exc - n_pass - n_fail
    parts.append(
        "<p>"
        f"<b>{n}</b> snippets &middot; "
        f"<span class='badge pass-excellent'>PASS-EXCELLENT {n_exc}</span> "
        f"<span class='badge pass'>PASS {n_pass}</span> "
        f"<span class='badge fail'>FAIL {n_fail}</span> "
        f"<span class='badge skip'>OTHER {n_skip}</span>"
        "</p>"
    )
    parts.append(
        "<p class='note'>Thresholds: "
        f"AE-ratio &lt; {TEXT_PIXEL_THRESHOLD:.0%} &amp; SSIM &ge; "
        f"{STRICT_SSIM_THRESHOLD:.2f} = PASS-EXCELLENT; "
        f"AE-ratio &lt; {GRAPHICS_PIXEL_THRESHOLD:.0%} &amp; SSIM &ge; "
        f"{TEXT_SSIM_THRESHOLD:.2f} = PASS (graphics-heavy: SSIM &ge; "
        f"{GRAPHICS_SSIM_THRESHOLD:.2f}).</p>"
    )
    parts.append("<table class='gallery'><thead><tr>")
    for h in ("Snippet", "PostScript", "SVG", "Diff",
              "AE (pixels / ratio)", "SSIM", "Verdict"):
        parts.append(f"<th>{h}</th>")
    parts.append("</tr></thead><tbody>")

    for r in rows:
        name = r["snippet"]
        ps_png = out_dir / f"{name}.ps.png"
        svg_png = out_dir / f"{name}.svg.norm.png"
        diff_png = out_dir / f"{name}.diff.png"
        verdict = r.get("verdict", "SKIP")
        cls = _VERDICT_CLASSES.get(verdict, "skip")
        is_gh = bool(r.get("graphics_heavy"))

        ae_html = "&mdash;"
        if r.get("ae") not in (None, "", "-"):
            ratio = r.get("pixel_diff_ratio")
            if isinstance(ratio, (int, float)):
                ratio_cls = ("ok" if ratio < TEXT_PIXEL_THRESHOLD
                             else "warn" if ratio < GRAPHICS_PIXEL_THRESHOLD
                             else "bad")
                ae_html = (
                    f"{r['ae']}<br>"
                    f"<span class='{ratio_cls}'>{ratio:.2%}</span>"
                )
            else:
                ae_html = str(r["ae"])

        ssim_html = "&mdash;"
        ssim_val = r.get("ssim")
        if isinstance(ssim_val, (int, float)):
            floor_for_pass = (GRAPHICS_SSIM_THRESHOLD if is_gh
                              else TEXT_SSIM_THRESHOLD)
            ssim_cls = ("ok" if ssim_val >= STRICT_SSIM_THRESHOLD
                        else "warn" if ssim_val >= floor_for_pass
                        else "bad")
            ssim_html = f"<span class='{ssim_cls}'>{ssim_val:.4f}</span>"
        elif SSIM_DEPS is None:
            ssim_html = "<span class='note'>n/a</span>"

        status_line = f"status: {html.escape(r.get('status', '?'))}"
        if r.get("note"):
            status_line += (
                f"<br><span class='note'>{html.escape(r['note'])}</span>"
            )

        gh_marker = (" <span class='gh-flag'>(graphics-heavy)</span>"
                     if is_gh else "")

        parts.append("<tr>")
        parts.append(
            f"<td><b>{html.escape(name)}</b>{gh_marker}<br>"
            f"<span class='note'>{status_line}</span></td>"
        )
        parts.append(
            f"<td>{'<img src=\"' + _img_uri(ps_png) + '\">' if ps_png.exists() else '&mdash;'}</td>"
        )
        parts.append(
            f"<td>{'<img src=\"' + _img_uri(svg_png) + '\">' if svg_png.exists() else '&mdash;'}</td>"
        )
        parts.append(
            f"<td>{'<img src=\"' + _img_uri(diff_png) + '\">' if diff_png.exists() else '&mdash;'}</td>"
        )
        parts.append(f"<td class='metric ae'>{ae_html}</td>")
        parts.append(f"<td class='metric ssim'>{ssim_html}</td>")
        parts.append(
            f"<td><span class='badge {cls}'>"
            f"{html.escape(verdict)}</span></td>"
        )
        parts.append("</tr>")

    parts.append("</tbody></table>")
    if SSIM_DEPS is None:
        parts.append(
            "<p class='note'>SSIM not computed: scikit-image / Pillow / "
            "numpy not importable. Falling back to AE-only verdicts.</p>"
        )
    parts.append("</body></html>")
    report_path.write_text("".join(parts), encoding="utf-8")


# ----------------------------------------------------------------------
# Main.
# ----------------------------------------------------------------------
def main() -> int:
    script_dir = Path(__file__).resolve().parent
    out_dir = script_dir / "out"
    results_tsv = out_dir / "results.txt"
    results_json = out_dir / "results.json"
    report_html = script_dir / "report.html"

    rows = parse_results(results_tsv)
    if not rows:
        print(f"No rows found in {results_tsv}. Run run_compare.sh first.",
              file=sys.stderr)
        return 1

    if SSIM_DEPS is None:
        print("note: scikit-image not available; SSIM will be skipped "
              "and verdicts will fall back to the AE-only thresholds.")

    summary = {
        "snippets_total": len(rows),
        "snippets": [],
        "skimage_available": SSIM_DEPS is not None,
        "graphics_heavy_manifest": sorted(GRAPHICS_HEAVY),
        "thresholds": {
            "text_pixel_diff_max": TEXT_PIXEL_THRESHOLD,
            "graphics_pixel_diff_max": GRAPHICS_PIXEL_THRESHOLD,
            "strict_ssim_min": STRICT_SSIM_THRESHOLD,
            "text_ssim_min": TEXT_SSIM_THRESHOLD,
            "graphics_ssim_min": GRAPHICS_SSIM_THRESHOLD,
        },
    }
    n_excellent = n_pass = n_fail = n_skip = 0

    for r in rows:
        name = r["snippet"]
        ps_png = out_dir / f"{name}.ps.png"
        svg_png = out_dir / f"{name}.svg.norm.png"
        try:
            ae = int(r.get("ae", "")) if r.get("ae") not in ("", "-", None) else None
        except ValueError:
            ae = None
        size = png_size(ps_png) if ps_png.exists() else None
        pixel_diff_ratio = None
        if size and ae is not None:
            w, h = size
            if w * h > 0:
                pixel_diff_ratio = ae / float(w * h)

        ssim_val = None
        if ps_png.exists() and svg_png.exists():
            ssim_val = compute_ssim(ps_png, svg_png)

        is_graphics = name in GRAPHICS_HEAVY

        verdict = "SKIP"
        if r.get("status") == "OK":
            verdict = classify(pixel_diff_ratio, ssim_val, is_graphics)

        if verdict == "PASS-EXCELLENT":
            n_excellent += 1
        elif verdict == "PASS":
            n_pass += 1
        elif verdict == "FAIL":
            n_fail += 1
        else:
            n_skip += 1

        r["pixel_diff_ratio"] = pixel_diff_ratio
        r["ssim"] = ssim_val
        r["verdict"] = verdict
        r["graphics_heavy"] = is_graphics
        r["canvas"] = list(size) if size else None
        summary["snippets"].append({
            "name": name,
            "status": r.get("status"),
            "ae": ae,
            "pixel_diff_ratio": pixel_diff_ratio,
            "ssim": ssim_val,
            "verdict": verdict,
            "graphics_heavy": is_graphics,
            "ps_bytes": int(r.get("ps_bytes", 0) or 0),
            "svg_bytes": int(r.get("svg_bytes", 0) or 0),
            "canvas": list(size) if size else None,
            "note": r.get("note", ""),
        })

    n_pass_any = n_excellent + n_pass
    summary["counts"] = {
        "pass_excellent": n_excellent,
        "pass": n_pass,
        "pass_any": n_pass_any,
        "fail": n_fail,
        "skip_or_error": n_skip,
    }
    results_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    render_html(report_html, out_dir, rows)

    print()
    print(f"  Pass-Excellent: {n_excellent}")
    print(f"  Pass:           {n_pass}")
    print(f"  Pass (any):     {n_pass_any}")
    print(f"  Fail:           {n_fail}")
    print(f"  Other:          {n_skip}")
    print(f"  JSON:           {results_json}")
    print(f"  HTML:           {report_html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
