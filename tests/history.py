#!/usr/bin/env python3
"""history.py -- append one JSON record per regression run.

Reads:
  tests/out/results.json
  tests/user_guide_diff/manifest.json  (optional, for last user-guide build)
Writes:
  tests/history.jsonl   (append-only, one JSON object per run)
  tests/history.html    (small static viewer; SVG line charts, stdlib only)

Schema for each JSONL line:
{
  "timestamp":         ISO-8601 UTC,
  "commit":            git rev-parse HEAD (short or full),
  "pass":              count of PASS verdicts,
  "pass_excellent":    count of PASS-EXCELLENT verdicts,
  "fail":              count of FAIL verdicts,
  "snippets_total":    total snippet count,
  "mean_ae_ratio":     mean of pixel_diff_ratio across snippets with a value,
  "mean_ssim":         mean of ssim across snippets with a value,
  "user_guide_wall_time_seconds":  if available in user_guide_diff/manifest.json
}

Stdlib only.
"""
from __future__ import annotations

import datetime
import html
import json
import subprocess
import sys
from pathlib import Path


# ----------------------------------------------------------------------
# Helpers.
# ----------------------------------------------------------------------
def git_commit(repo_dir: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return out.decode("ascii", "replace").strip()
    except Exception:
        return "unknown"


def safe_mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if isinstance(x, (int, float))]
    if not xs:
        return None
    return sum(xs) / len(xs)


def collect_metrics(results_json: Path) -> dict:
    if not results_json.exists():
        return {
            "pass": 0,
            "pass_excellent": 0,
            "fail": 0,
            "snippets_total": 0,
            "mean_ae_ratio": None,
            "mean_ssim": None,
        }
    data = json.loads(results_json.read_text(encoding="utf-8"))
    counts = data.get("counts", {}) or {}
    snippets = data.get("snippets", []) or []
    return {
        "pass": int(counts.get("pass", 0)),
        "pass_excellent": int(counts.get("pass_excellent", 0)),
        "fail": int(counts.get("fail", 0)),
        "snippets_total": int(data.get("snippets_total", len(snippets))),
        "mean_ae_ratio": safe_mean(
            [s.get("pixel_diff_ratio") for s in snippets]
        ),
        "mean_ssim": safe_mean([s.get("ssim") for s in snippets]),
    }


def user_guide_wall_time(manifest_json: Path) -> float | None:
    """Look for an optional wall-time field in the user-guide manifest.

    The field is not part of the original schema, so we look for a few
    likely names. Returns seconds (float) or None if absent.
    """
    if not manifest_json.exists():
        return None
    try:
        data = json.loads(manifest_json.read_text(encoding="utf-8"))
    except Exception:
        return None
    md = data.get("metadata", {}) or {}
    for key in (
        "wall_time_seconds", "wall_time", "build_seconds",
        "build_wall_time_seconds", "elapsed_seconds",
    ):
        v = md.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


# ----------------------------------------------------------------------
# HTML viewer with inline SVG line charts.
# ----------------------------------------------------------------------
HTML_HEAD = """<!doctype html>
<html><head><meta charset="utf-8">
<title>mdlout regression history</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       Helvetica, Arial, sans-serif; margin: 1.5rem; color: #1c1c1c; }
h1 { margin-top: 0; }
section { margin: 1.5rem 0; }
.chart { background:#fff; border:1px solid #ddd; }
.chart-title { font-weight: 600; margin: 0 0 0.4rem 0; }
table { border-collapse: collapse; margin-top: 1rem; }
th, td { padding: 0.3rem 0.6rem; border-bottom: 1px solid #eee;
         font-size: 0.85rem; font-variant-numeric: tabular-nums; }
th { background:#f3f3f3; text-align: left; }
.muted { color:#777; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.85rem; }
</style></head><body>
<h1>mdlout regression history</h1>
"""


def _scale(values: list[float], lo: float, hi: float) -> list[float]:
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def render_svg_chart(
    series: list[float | None],
    title: str,
    *,
    width: int = 720,
    height: int = 160,
    pad: int = 30,
    fmt: str = "{:.4f}",
) -> str:
    """Render a hand-rolled SVG line chart from a list of values.

    Missing data points are skipped from the polyline but kept in the
    x-axis position sequence so commits align across charts.
    """
    n = len(series)
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    if n == 0:
        return f"<p class='muted'>{html.escape(title)}: no data.</p>"

    valid = [v for v in series if isinstance(v, (int, float))]
    if not valid:
        return f"<p class='muted'>{html.escape(title)}: no numeric data.</p>"
    vmin = min(valid)
    vmax = max(valid)
    if vmin == vmax:
        vmin -= 1.0
        vmax += 1.0

    pts: list[str] = []
    circles: list[str] = []
    for i, v in enumerate(series):
        x = pad + (inner_w * (i / max(1, n - 1)))
        if isinstance(v, (int, float)):
            y = pad + inner_h - inner_h * (v - vmin) / (vmax - vmin)
            pts.append(f"{x:.1f},{y:.1f}")
            circles.append(
                f"<circle cx='{x:.1f}' cy='{y:.1f}' r='2.5' fill='#0a58ca'/>"
            )

    polyline = (
        f"<polyline fill='none' stroke='#0a58ca' stroke-width='1.5' "
        f"points='{' '.join(pts)}'/>"
        if pts else ""
    )

    axis = (
        f"<line x1='{pad}' y1='{pad}' x2='{pad}' "
        f"y2='{pad + inner_h}' stroke='#888' stroke-width='0.8'/>"
        f"<line x1='{pad}' y1='{pad + inner_h}' "
        f"x2='{pad + inner_w}' y2='{pad + inner_h}' "
        f"stroke='#888' stroke-width='0.8'/>"
    )

    labels = (
        f"<text x='{pad - 4}' y='{pad + 4}' text-anchor='end' "
        f"font-size='10'>{html.escape(fmt.format(vmax))}</text>"
        f"<text x='{pad - 4}' y='{pad + inner_h}' text-anchor='end' "
        f"font-size='10'>{html.escape(fmt.format(vmin))}</text>"
    )

    return (
        f"<section>"
        f"<p class='chart-title'>{html.escape(title)}</p>"
        f"<svg class='chart' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
        f"{axis}{polyline}{''.join(circles)}{labels}"
        f"</svg></section>"
    )


def render_html(jsonl_path: Path, html_path: Path) -> None:
    runs: list[dict] = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    parts: list[str] = [HTML_HEAD]
    if not runs:
        parts.append("<p class='muted'>No history yet. "
                     "Run <code>tests/run_all.sh</code>.</p></body></html>")
        html_path.write_text("".join(parts), encoding="utf-8")
        return

    parts.append(
        f"<p class='muted'>{len(runs)} run(s) recorded. "
        f"Latest: <code>{html.escape(runs[-1].get('timestamp', '?'))}"
        f"</code> @ <code>{html.escape(runs[-1].get('commit', '?')[:12])}"
        f"</code>.</p>"
    )

    pass_series = [r.get("pass", 0) + r.get("pass_excellent", 0) for r in runs]
    fail_series = [r.get("fail", 0) for r in runs]
    ssim_series = [r.get("mean_ssim") for r in runs]
    ae_series = [r.get("mean_ae_ratio") for r in runs]
    wall_series = [r.get("user_guide_wall_time_seconds") for r in runs]

    parts.append(render_svg_chart(
        pass_series, "Total Pass (PASS + PASS-EXCELLENT)",
        fmt="{:.0f}",
    ))
    parts.append(render_svg_chart(
        fail_series, "Fail count", fmt="{:.0f}",
    ))
    parts.append(render_svg_chart(
        ssim_series, "Mean SSIM",
    ))
    parts.append(render_svg_chart(
        ae_series, "Mean AE ratio", fmt="{:.4f}",
    ))
    parts.append(render_svg_chart(
        wall_series,
        "User-guide build wall time (seconds)",
        fmt="{:.1f}",
    ))

    parts.append("<h2>Runs</h2><table><thead><tr>")
    for h in (
        "Timestamp (UTC)", "Commit", "Pass-Exc", "Pass",
        "Fail", "Mean AE", "Mean SSIM", "UG wall (s)",
    ):
        parts.append(f"<th>{h}</th>")
    parts.append("</tr></thead><tbody>")
    for r in reversed(runs):
        def fmt(v, spec="{:.4f}"):
            if v is None:
                return "&mdash;"
            try:
                return html.escape(spec.format(v))
            except Exception:
                return html.escape(str(v))
        parts.append(
            "<tr>"
            f"<td>{html.escape(r.get('timestamp', '?'))}</td>"
            f"<td><code>{html.escape(r.get('commit', '?')[:12])}</code></td>"
            f"<td>{r.get('pass_excellent', 0)}</td>"
            f"<td>{r.get('pass', 0)}</td>"
            f"<td>{r.get('fail', 0)}</td>"
            f"<td>{fmt(r.get('mean_ae_ratio'))}</td>"
            f"<td>{fmt(r.get('mean_ssim'))}</td>"
            f"<td>{fmt(r.get('user_guide_wall_time_seconds'), '{:.1f}')}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")
    parts.append("</body></html>")
    html_path.write_text("".join(parts), encoding="utf-8")


# ----------------------------------------------------------------------
# Main.
# ----------------------------------------------------------------------
def main() -> int:
    script_dir = Path(__file__).resolve().parent
    repo_dir = script_dir.parent
    results_json = script_dir / "out" / "results.json"
    manifest_json = script_dir / "user_guide_diff" / "manifest.json"
    jsonl_path = script_dir / "history.jsonl"
    html_path = script_dir / "history.html"

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    commit = git_commit(repo_dir)
    metrics = collect_metrics(results_json)
    wall_seconds = user_guide_wall_time(manifest_json)

    record = {
        "timestamp": timestamp,
        "commit": commit,
        **metrics,
        "user_guide_wall_time_seconds": wall_seconds,
    }

    with jsonl_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    render_html(jsonl_path, html_path)

    print(f"history: appended record for {commit[:12]} -> {jsonl_path.name}")
    print(f"history: rendered viewer -> {html_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
