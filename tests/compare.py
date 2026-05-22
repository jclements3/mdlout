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
import subprocess
import sys
import tempfile
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
#
# History: graphics-heavy used to be 20% / 0.75 SSIM back when the
# `@Graphic` PostScript fallback was an XML comment. With the embedded
# PS interpreter in z53.c and the Symbol-font glyph table both in, the
# worst graphics-heavy snippet on the current corpus is colour_mixed at
# 0.49% AE-ratio / 0.9926 SSIM (see tests/out/results.json). The
# tightened bar below leaves a ~1.5% pixel-diff margin and ~0.04 SSIM
# margin above the worst-passing snippet to absorb CI jitter. If/when
# a new snippet exceeds these, prefer fixing the back-end before
# loosening the threshold again.
TEXT_PIXEL_THRESHOLD = 0.05       # AE-ratio < 5%  -> "excellent" gate
GRAPHICS_PIXEL_THRESHOLD = 0.02   # AE-ratio < 2%  -> graphics-heavy passing gate
STRICT_SSIM_THRESHOLD = 0.95      # SSIM >= 0.95 -> "excellent"
TEXT_SSIM_THRESHOLD = 0.85        # SSIM >= 0.85 -> passing
GRAPHICS_SSIM_THRESHOLD = 0.95    # SSIM >= 0.95 -> graphics-heavy passing


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
# Bisect: localize the lines in a snippet responsible for a diff.
# ----------------------------------------------------------------------
# Line prefixes that must always be kept (framing/preamble/postamble).
_FRAMING_PREFIXES = (
    "@SysInclude",
    "@Include",
    "@Use",
)
# Line patterns that open/close the document body; we keep these too.
_FRAMING_SUBSTRINGS = (
    "@Begin",
    "@End",
)


def _line_is_framing(line: str) -> bool:
    ls = line.strip()
    if not ls or ls.startswith("#"):
        return True
    for pref in _FRAMING_PREFIXES:
        if ls.startswith(pref):
            return True
    # @Doc @Text @Begin / @Report ... / @End @Text
    for sub in _FRAMING_SUBSTRINGS:
        if sub in ls and ls.startswith("@"):
            return True
    return False


def _split_into_blocks(text: str) -> list[tuple[int, int, str]]:
    """Split a .lt source into atomic blocks. Coarse-grain when possible
    (blank-line separated paragraphs), fine-grain (line-by-line) when the
    file is dense. Returns [(start_line, end_line, block_text), ...]
    (1-indexed, inclusive). Each block is either entirely framing or
    entirely removable -- never mixed."""
    lines = text.splitlines(keepends=True)
    n = len(lines)
    blocks: list[tuple[int, int, str]] = []
    i = 0
    while i < n:
        # Group consecutive blank lines as a single framing block.
        if lines[i].strip() == "":
            start = i
            while i < n and lines[i].strip() == "":
                i += 1
            blocks.append((start + 1, i, "".join(lines[start:i])))
            continue
        # Group consecutive framing lines as one framing block.
        if _line_is_framing(lines[i]):
            start = i
            while i < n and lines[i].strip() != "" and _line_is_framing(lines[i]):
                i += 1
            blocks.append((start + 1, i, "".join(lines[start:i])))
            continue
        # Group consecutive removable lines as individual single-line blocks
        # so the bisector can excise them at line granularity.
        # (One line per block keeps things simple; the search still
        # binary-searches over the body_idxs list.)
        blocks.append((i + 1, i + 1, lines[i]))
        i += 1
    return blocks


def _is_framing(block_text: str) -> bool:
    stripped = block_text.strip()
    if not stripped:
        return True
    for line in stripped.splitlines():
        if not _line_is_framing(line):
            return False
    return True


def _render_and_diff(
    lt_text: str,
    name: str,
    repo_dir: Path,
    tmp_dir: Path,
    ref_ps_png: Path,
) -> tuple[float | None, float | None]:
    """Render the given .lt source through lout's PS and SVG backends,
    rasterize the first page of each, and compute (pixel_diff_ratio,
    ssim) against the given reference PS PNG. Returns (None, None) on
    rendering failure."""
    lout_dir = repo_dir / "lout"
    lout_bin = lout_dir / "lout"
    if not lout_bin.exists():
        return (None, None)

    lt_path = tmp_dir / f"{name}.lt"
    lt_path.write_text(lt_text, encoding="utf-8")
    ps_path = tmp_dir / f"{name}.ps"
    svg_path = tmp_dir / f"{name}.svg"
    ps_png = tmp_dir / f"{name}.ps.png"
    svg_png = tmp_dir / f"{name}.svg.png"
    svg_norm = tmp_dir / f"{name}.svg.norm.png"
    diff_png = tmp_dir / f"{name}.diff.png"

    def lout(extra: list[str]) -> bool:
        try:
            subprocess.run(
                [str(lout_bin),
                 "-I", str(lout_dir / "include"),
                 "-D", str(lout_dir / "data"),
                 "-F", str(lout_dir / "font"),
                 "-C", str(lout_dir / "maps"),
                 "-H", str(lout_dir / "hyph"),
                 "-s"] + extra + [str(lt_path)],
                cwd=str(tmp_dir),
                check=True, capture_output=True, timeout=60,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError):
            return False

    if not lout(["-o", str(ps_path)]):
        return (None, None)
    if not lout(["-G", "-o", str(svg_path)]):
        return (None, None)

    try:
        subprocess.run(
            ["gs", "-q", "-dSAFER", "-dNOPAUSE", "-dBATCH",
             "-sDEVICE=png16m", "-r150", "-dFirstPage=1", "-dLastPage=1",
             f"-sOutputFile={ps_png}", str(ps_path)],
            check=True, capture_output=True, timeout=60,
        )
    except Exception:
        return (None, None)

    svg_for_rsvg = svg_path
    try:
        svg_text = svg_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        svg_text = ""
    n_svg = svg_text.count("<svg ")
    if n_svg > 1:
        p1 = tmp_dir / f"{name}.svg.p1.svg"
        out_lines: list[str] = []
        in_svg = False
        done = False
        for line in svg_text.splitlines(keepends=True):
            if done:
                break
            if line.startswith("<?xml") and not in_svg:
                out_lines.append(line)
                continue
            if line.startswith("<svg "):
                if not in_svg:
                    in_svg = True
                    out_lines.append(line)
                    continue
                else:
                    break
            if in_svg:
                out_lines.append(line)
                if line.startswith("</svg>"):
                    done = True
        p1.write_text("".join(out_lines), encoding="utf-8")
        svg_for_rsvg = p1

    try:
        subprocess.run(
            ["rsvg-convert", "-d", "150", "-p", "150", "-f", "png",
             "-o", str(svg_png), str(svg_for_rsvg)],
            check=True, capture_output=True, timeout=60,
        )
    except Exception:
        return (None, None)

    try:
        geom = subprocess.run(
            ["identify", "-format", "%wx%h", str(ref_ps_png)],
            check=True, capture_output=True, timeout=30,
        ).stdout.decode().strip()
        subprocess.run(
            ["convert", str(svg_png), "-background", "white",
             "-gravity", "northwest", "-extent", geom, str(svg_norm)],
            check=True, capture_output=True, timeout=30,
        )
    except Exception:
        svg_norm = svg_png

    try:
        proc = subprocess.run(
            ["compare", "-metric", "AE", "-fuzz", "2%",
             str(ref_ps_png), str(svg_norm), str(diff_png)],
            capture_output=True, timeout=60,
        )
        ae_raw = proc.stderr.decode().strip()
        digits = "".join(c for c in ae_raw if c.isdigit())
        ae = int(digits) if digits else None
    except Exception:
        ae = None

    size = png_size(ref_ps_png)
    pixel_diff_ratio = None
    if size and ae is not None:
        w, h = size
        if w * h > 0:
            pixel_diff_ratio = ae / float(w * h)

    ssim_val = compute_ssim(ref_ps_png, svg_norm)
    return (pixel_diff_ratio, ssim_val)


def _is_failing(
    pixel_diff_ratio: float | None,
    ssim_val: float | None,
    is_graphics: bool,
) -> bool:
    if pixel_diff_ratio is None:
        return True
    return classify(pixel_diff_ratio, ssim_val, is_graphics) == "FAIL"


def _fmt_metrics(pr: float | None, sv: float | None) -> str:
    pr_s = f"{pr:.4%}" if isinstance(pr, float) else "?"
    sv_s = f"{sv:.4f}" if isinstance(sv, float) else "?"
    return f"ratio={pr_s}, ssim={sv_s}"


def bisect_snippet(name: str) -> int:
    """Locate the smallest contiguous block range of a snippet that, when
    kept (with the rest of the body removed), still reproduces a FAIL
    verdict. Prints a localized line range and excerpt."""
    script_dir = Path(__file__).resolve().parent
    repo_dir = script_dir.parent
    snip_dir = script_dir / "snippets"
    out_dir = script_dir / "out"
    lt_path = snip_dir / f"{name}.lt"
    if not lt_path.exists():
        print(f"bisect: snippet not found: {lt_path}", file=sys.stderr)
        return 2

    ref_ps_png = out_dir / f"{name}.ps.png"
    if not ref_ps_png.exists():
        print(f"bisect: reference PS PNG missing: {ref_ps_png}\n"
              f"       Run tests/run_all.sh first.", file=sys.stderr)
        return 2

    is_graphics = name in GRAPHICS_HEAVY
    full_text = lt_path.read_text(encoding="utf-8")
    blocks = _split_into_blocks(full_text)
    if not blocks:
        print("bisect: snippet appears to be empty.", file=sys.stderr)
        return 2

    body_idxs = [i for i, (_, _, t) in enumerate(blocks) if not _is_framing(t)]
    if not body_idxs:
        print("bisect: no removable body blocks found "
              "(snippet is all framing).", file=sys.stderr)
        return 2

    def assemble(keep_idxs: set[int]) -> str:
        parts: list[str] = []
        for i, (_, _, t) in enumerate(blocks):
            if _is_framing(t) or i in keep_idxs:
                parts.append(t)
                if not t.endswith("\n"):
                    parts.append("\n")
                parts.append("\n")
        return "".join(parts)

    with tempfile.TemporaryDirectory(prefix=f"bisect_{name}_") as td:
        tmp_dir = Path(td)
        full_keep = set(body_idxs)
        pr, sv = _render_and_diff(assemble(full_keep), name,
                                  repo_dir, tmp_dir, ref_ps_png)
        if not _is_failing(pr, sv, is_graphics):
            print(f"bisect: snippet {name!r} currently PASSES "
                  f"({_fmt_metrics(pr, sv)}). Nothing to localize.")
            return 0
        print(f"bisect: full snippet FAILS ({_fmt_metrics(pr, sv)}); "
              f"searching among {len(body_idxs)} body block(s)...")

        lo = 0
        hi = len(body_idxs)
        steps = 0
        max_steps = 32
        while hi - lo > 1 and steps < max_steps:
            steps += 1
            mid = (lo + hi) // 2
            left_keep = set(body_idxs[lo:mid])
            pr_l, sv_l = _render_and_diff(assemble(left_keep), name,
                                          repo_dir, tmp_dir, ref_ps_png)
            if _is_failing(pr_l, sv_l, is_graphics):
                print(f"  step {steps}: keep blocks [{lo}..{mid - 1}] "
                      f"-> FAIL ({_fmt_metrics(pr_l, sv_l)})")
                hi = mid
                continue
            right_keep = set(body_idxs[mid:hi])
            pr_r, sv_r = _render_and_diff(assemble(right_keep), name,
                                          repo_dir, tmp_dir, ref_ps_png)
            if _is_failing(pr_r, sv_r, is_graphics):
                print(f"  step {steps}: keep blocks [{mid}..{hi - 1}] "
                      f"-> FAIL ({_fmt_metrics(pr_r, sv_r)})")
                lo = mid
                continue
            print(f"  step {steps}: neither half alone fails "
                  f"(left {_fmt_metrics(pr_l, sv_l)}, "
                  f"right {_fmt_metrics(pr_r, sv_r)}); "
                  f"diff is distributed across both halves.")
            break

    final_idxs = body_idxs[lo:hi]
    if not final_idxs:
        print("bisect: could not localize a culprit block.")
        return 1
    start_line = blocks[final_idxs[0]][0]
    end_line = blocks[final_idxs[-1]][1]
    excerpt = "\n".join(blocks[i][2].rstrip("\n") for i in final_idxs)
    print()
    print(f"Diff localized to lines {start_line}-{end_line} "
          f"({len(final_idxs)} block(s)):")
    print("-" * 60)
    print(excerpt)
    print("-" * 60)
    return 0


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
    if len(sys.argv) >= 3 and sys.argv[1] == "--bisect":
        sys.exit(bisect_snippet(sys.argv[2]))
    sys.exit(main())
