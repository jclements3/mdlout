#!/usr/bin/env python3
"""history.py -- append one JSON record per regression run and render a
multi-panel dashboard.

Reads:
  tests/out/results.json
  tests/user_guide_diff/manifest.json    (optional, for User's Guide stats)
Writes:
  tests/history.jsonl    (append-only, one JSON object per run)
  tests/history.html     (standalone dashboard, inline SVG + vanilla JS)

Record schema (all User's-Guide / wall-clock fields are optional --
older records render as gaps in the dashboard, not zeros):

{
  "timestamp":         ISO-8601 UTC,
  "commit":            git rev-parse HEAD,
  "pass":              count of PASS verdicts,
  "pass_excellent":    count of PASS-EXCELLENT verdicts,
  "fail":              count of FAIL verdicts,
  "snippets_total":    total snippet count,
  "mean_ae_ratio":     mean of pixel_diff_ratio across snippets,
  "mean_ssim":         best available mean SSIM (UG preferred, else snippet),
  "mean_ssim_source":  "user_guide" | "snippets" | null,
  "ug_ok":             User's Guide pages with diff_ratio < 5%,
  "ug_diff":           User's Guide pages 5% <= diff_ratio < 20%,
  "ug_bad":            User's Guide pages diff_ratio >= 20%,
  "ug_missing":        User's Guide pages with no SVG output,
  "ug_total":          User's Guide total page count,
  "wall_clock_sec":    wall-clock seconds of the most recent UG rebuild,
                       (read from manifest if present, else null),
  "user_guide_wall_time_seconds":  legacy alias of wall_clock_sec
}

Stdlib only.
"""
from __future__ import annotations

import datetime
import html
import json
import subprocess
import sys
import time
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


def safe_mean(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    if not xs:
        return None
    return sum(xs) / len(xs)


def collect_snippet_metrics(results_json: Path) -> dict:
    if not results_json.exists():
        return {
            "pass": 0,
            "pass_excellent": 0,
            "fail": 0,
            "snippets_total": 0,
            "mean_ae_ratio": None,
            "snippet_mean_ssim": None,
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
        "snippet_mean_ssim": safe_mean([s.get("ssim") for s in snippets]),
    }


def collect_user_guide_metrics(manifest_json: Path) -> dict:
    """Read user_guide_diff/manifest.json. Returns a dict with keys
    ug_ok, ug_diff, ug_bad, ug_missing, ug_total, ug_mean_ssim,
    wall_clock_sec. Every value may be None if the manifest is absent
    or doesn't carry the field."""
    out = {
        "ug_ok": None,
        "ug_diff": None,
        "ug_bad": None,
        "ug_missing": None,
        "ug_total": None,
        "ug_mean_ssim": None,
        "wall_clock_sec": None,
    }
    if not manifest_json.exists():
        return out
    try:
        data = json.loads(manifest_json.read_text(encoding="utf-8"))
    except Exception:
        return out
    summary = data.get("summary", {}) or {}
    if "ok_lt_5pct" in summary:
        out["ug_ok"] = int(summary["ok_lt_5pct"])
    if "diff_5_to_20pct" in summary:
        out["ug_diff"] = int(summary["diff_5_to_20pct"])
    if "bad_gt_20pct" in summary:
        out["ug_bad"] = int(summary["bad_gt_20pct"])
    if "missing_svg_pages" in summary:
        out["ug_missing"] = int(summary["missing_svg_pages"])
    if "total_pages" in summary:
        out["ug_total"] = int(summary["total_pages"])

    # SSIM: prefer the summary block, else compute from page rows.
    ssim_summary = data.get("ssim_summary", {}) or {}
    if isinstance(ssim_summary.get("mean_ssim"), (int, float)):
        out["ug_mean_ssim"] = float(ssim_summary["mean_ssim"])
    else:
        pages = data.get("pages", []) or []
        m = safe_mean([p.get("ssim") for p in pages])
        if m is not None:
            out["ug_mean_ssim"] = m

    md = data.get("metadata", {}) or {}
    for key in (
        "wall_clock_sec", "wall_time_seconds", "wall_time",
        "build_seconds", "build_wall_time_seconds", "elapsed_seconds",
    ):
        v = md.get(key)
        if isinstance(v, (int, float)):
            out["wall_clock_sec"] = float(v)
            break
    return out


# ----------------------------------------------------------------------
# HTML scaffold + chart rendering.
# ----------------------------------------------------------------------
HTML_HEAD = """<!doctype html>
<html><head><meta charset="utf-8">
<title>mdlout regression history</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       Helvetica, Arial, sans-serif; margin: 1.5rem; color: #1c1c1c; }
h1 { margin-top: 0; }
h2 { margin: 1.5rem 0 0.5rem 0; }
section.panel { margin: 1.2rem 0; }
.chart { background:#fff; border:1px solid #ddd; display:block; }
.chart-title { font-weight: 600; margin: 0 0 0.4rem 0; }
.chart-subtitle { font-size: 0.8rem; color:#555; margin: 0 0 0.4rem 0; }
table { border-collapse: collapse; margin-top: 1rem; }
th, td { padding: 0.3rem 0.6rem; border-bottom: 1px solid #eee;
         font-size: 0.85rem; font-variant-numeric: tabular-nums; }
th { background:#f3f3f3; text-align: left; }
.muted { color:#777; }
code { font-family: ui-monospace, Menlo, Consolas, monospace;
       font-size: 0.85rem; }
.controls { margin: 0.5rem 0 1rem 0; font-size: 0.9rem; }
.controls label { margin-right: 1rem; cursor: pointer; }
.legend { font-size: 0.8rem; margin: 0.2rem 0 0.5rem 0; }
.legend span { display: inline-block; margin-right: 0.8rem; }
.legend i { display: inline-block; width: 0.8rem; height: 0.8rem;
            margin-right: 0.3rem; vertical-align: middle; border:1px solid #999; }
.chart-by-date { display: none; }
body[data-xaxis="date"] .chart-by-run { display: none; }
body[data-xaxis="date"] .chart-by-date { display: block; }
</style></head><body data-xaxis="run">
<h1>mdlout regression history</h1>
"""


def _fmt_tick(ts_iso: str) -> str:
    """Render an ISO-8601 timestamp as 'MMM DD HH:MM' (UTC)."""
    try:
        dt = datetime.datetime.strptime(ts_iso, "%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ts_iso[:16] if ts_iso else "?"
    return dt.strftime("%b %d %H:%M")


def _iso_to_epoch(ts_iso: str):
    try:
        dt = datetime.datetime.strptime(ts_iso, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _x_positions_by_run(n: int, pad: int, inner_w: int) -> list:
    if n == 0:
        return []
    if n == 1:
        return [pad + inner_w / 2.0]
    return [pad + inner_w * (i / (n - 1)) for i in range(n)]


def _x_positions_by_date(timestamps, pad: int, inner_w: int) -> list:
    """Position points on a real time axis. Records that lack a parsable
    timestamp fall back to evenly-spaced. Returns a list of floats (may
    contain None if the corresponding timestamp is unparsable)."""
    epochs = [_iso_to_epoch(ts) for ts in timestamps]
    valid = [e for e in epochs if e is not None]
    if not valid:
        return _x_positions_by_run(len(timestamps), pad, inner_w)
    lo = min(valid)
    hi = max(valid)
    if hi == lo:
        return [pad + inner_w / 2.0] * len(timestamps)
    out = []
    for e in epochs:
        if e is None:
            out.append(None)
        else:
            out.append(pad + inner_w * (e - lo) / (hi - lo))
    return out


def _date_tick_marks(timestamps, pad: int, inner_w: int, max_ticks: int = 6):
    """Pick up to max_ticks evenly-spaced epochs across the time range
    and return [(x, label), ...]."""
    epochs = [_iso_to_epoch(ts) for ts in timestamps if _iso_to_epoch(ts) is not None]
    if not epochs:
        return []
    lo = min(epochs)
    hi = max(epochs)
    def _epoch_to_iso(e):
        return datetime.datetime.fromtimestamp(
            e, tz=datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    if hi == lo:
        return [(pad + inner_w / 2.0, _fmt_tick(_epoch_to_iso(lo)))]
    n_ticks = min(max_ticks, len(epochs))
    out = []
    for i in range(n_ticks):
        frac = i / (n_ticks - 1) if n_ticks > 1 else 0.5
        e = lo + frac * (hi - lo)
        x = pad + inner_w * frac
        out.append((x, _fmt_tick(_epoch_to_iso(e))))
    return out


def _run_tick_marks(timestamps, pad: int, inner_w: int, max_ticks: int = 6):
    n = len(timestamps)
    if n == 0:
        return []
    if n <= max_ticks:
        idxs = list(range(n))
    else:
        idxs = [int(round(i * (n - 1) / (max_ticks - 1))) for i in range(max_ticks)]
        # de-duplicate
        seen = set()
        idxs2 = []
        for i in idxs:
            if i not in seen:
                seen.add(i)
                idxs2.append(i)
        idxs = idxs2
    out = []
    for i in idxs:
        if n == 1:
            x = pad + inner_w / 2.0
        else:
            x = pad + inner_w * (i / (n - 1))
        out.append((x, _fmt_tick(timestamps[i])))
    return out


def _axes_and_grid(pad: int, inner_w: int, inner_h: int,
                   vmin: float, vmax: float, fmt: str) -> str:
    axis = (
        f"<line x1='{pad}' y1='{pad}' x2='{pad}' "
        f"y2='{pad + inner_h}' stroke='#888' stroke-width='0.8'/>"
        f"<line x1='{pad}' y1='{pad + inner_h}' "
        f"x2='{pad + inner_w}' y2='{pad + inner_h}' "
        f"stroke='#888' stroke-width='0.8'/>"
    )
    # 3 horizontal gridlines: top, middle, bottom (top/bottom are the axes).
    mid_y = pad + inner_h / 2.0
    mid_v = (vmin + vmax) / 2.0
    grid = (
        f"<line x1='{pad}' y1='{mid_y:.1f}' x2='{pad + inner_w}' "
        f"y2='{mid_y:.1f}' stroke='#eee' stroke-width='0.8'/>"
    )
    labels = (
        f"<text x='{pad - 4}' y='{pad + 4}' text-anchor='end' "
        f"font-size='10'>{html.escape(fmt.format(vmax))}</text>"
        f"<text x='{pad - 4}' y='{mid_y + 3:.1f}' text-anchor='end' "
        f"font-size='10'>{html.escape(fmt.format(mid_v))}</text>"
        f"<text x='{pad - 4}' y='{pad + inner_h}' text-anchor='end' "
        f"font-size='10'>{html.escape(fmt.format(vmin))}</text>"
    )
    return axis + grid + labels


def _xaxis_labels(ticks, pad: int, inner_h: int) -> str:
    parts = []
    y_text = pad + inner_h + 14
    y_tick = pad + inner_h
    for x, label in ticks:
        parts.append(
            f"<line x1='{x:.1f}' y1='{y_tick}' x2='{x:.1f}' "
            f"y2='{y_tick + 3}' stroke='#888' stroke-width='0.8'/>"
        )
        parts.append(
            f"<text x='{x:.1f}' y='{y_text}' text-anchor='middle' "
            f"font-size='9' fill='#555'>{html.escape(label)}</text>"
        )
    return "".join(parts)


def render_line_chart(
    series, timestamps, title: str,
    *,
    width: int = 780, height: int = 200, pad_l: int = 50,
    pad_r: int = 20, pad_t: int = 20, pad_b: int = 30,
    fmt: str = "{:.4f}",
    colour: str = "#0a58ca",
    subtitle: str = "",
) -> str:
    n = len(series)
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    if n == 0:
        return f"<section class='panel'><p class='muted'>{html.escape(title)}: no data.</p></section>"

    valid = [v for v in series if isinstance(v, (int, float))]
    if not valid:
        return (
            f"<section class='panel'><p class='chart-title'>{html.escape(title)}</p>"
            f"<p class='muted'>No numeric data yet.</p></section>"
        )
    vmin = min(valid)
    vmax = max(valid)
    if vmin == vmax:
        # give a tiny visual band so the line doesn't disappear
        eps = max(abs(vmin) * 0.01, 1.0)
        vmin -= eps
        vmax += eps

    def build(xs):
        # Build polyline segments + circles. Break the polyline where
        # the series is missing so gaps render as gaps, not lines.
        polylines = []
        circles = []
        current = []
        for i, v in enumerate(series):
            x = xs[i]
            if x is None or not isinstance(v, (int, float)):
                if len(current) >= 2:
                    polylines.append(current)
                elif len(current) == 1:
                    # single point: render as a circle only
                    pass
                current = []
                continue
            y = pad_t + inner_h - inner_h * (v - vmin) / (vmax - vmin)
            current.append((x, y))
            circles.append(
                f"<circle cx='{x:.1f}' cy='{y:.1f}' r='2.5' "
                f"fill='{colour}'><title>"
                f"{html.escape(fmt.format(v))}  @  "
                f"{html.escape(timestamps[i] if i < len(timestamps) else '?')}"
                f"</title></circle>"
            )
        if len(current) >= 2:
            polylines.append(current)

        polylines_svg = "".join(
            f"<polyline fill='none' stroke='{colour}' stroke-width='1.5' "
            f"points='{ ' '.join(f'{x:.1f},{y:.1f}' for x,y in pts) }'/>"
            for pts in polylines
        )
        return polylines_svg + "".join(circles)

    xs_run = _x_positions_by_run(n, pad_l, inner_w)
    xs_date = _x_positions_by_date(timestamps, pad_l, inner_w)
    body_run = build(xs_run)
    body_date = build(xs_date)

    ticks_run = _run_tick_marks(timestamps, pad_l, inner_w)
    ticks_date = _date_tick_marks(timestamps, pad_l, inner_w)

    axes = _axes_and_grid(pad_l, inner_w, inner_h, vmin, vmax, fmt)

    svg_run = (
        f"<svg class='chart chart-by-run' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
        f"{axes}{body_run}{_xaxis_labels(ticks_run, pad_l, inner_h)}"
        f"</svg>"
    )
    svg_date = (
        f"<svg class='chart chart-by-date' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
        f"{axes}{body_date}{_xaxis_labels(ticks_date, pad_l, inner_h)}"
        f"</svg>"
    )

    sub = (
        f"<p class='chart-subtitle'>{html.escape(subtitle)}</p>"
        if subtitle else ""
    )
    return (
        f"<section class='panel'>"
        f"<p class='chart-title'>{html.escape(title)}</p>{sub}"
        f"{svg_run}{svg_date}</section>"
    )


def render_stacked_area_chart(
    layers, timestamps, title: str,
    *,
    width: int = 780, height: int = 220, pad_l: int = 50,
    pad_r: int = 20, pad_t: int = 20, pad_b: int = 30,
    subtitle: str = "",
) -> str:
    """Render a stacked area chart from a list of (label, colour, series).
    Records where ALL layer values are None render as gaps -- the stack
    is broken on either side."""
    n = len(timestamps)
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    if n == 0 or not layers:
        return (
            f"<section class='panel'><p class='chart-title'>"
            f"{html.escape(title)}</p>"
            f"<p class='muted'>No data.</p></section>"
        )

    # Determine which records have at least one layer value.
    present = []
    for i in range(n):
        any_val = False
        for _, _, series in layers:
            v = series[i] if i < len(series) else None
            if isinstance(v, (int, float)):
                any_val = True
                break
        present.append(any_val)
    if not any(present):
        return (
            f"<section class='panel'><p class='chart-title'>"
            f"{html.escape(title)}</p>"
            f"<p class='muted'>No numeric data yet.</p></section>"
        )

    # Determine the maximum stack sum across records (for Y scaling).
    totals = []
    for i in range(n):
        if not present[i]:
            totals.append(0.0)
            continue
        s = 0.0
        for _, _, series in layers:
            v = series[i] if i < len(series) else None
            if isinstance(v, (int, float)):
                s += float(v)
        totals.append(s)
    vmax = max(totals) if totals else 1.0
    if vmax <= 0:
        vmax = 1.0
    vmin = 0.0

    fmt = "{:.0f}"
    axes = _axes_and_grid(pad_l, inner_w, inner_h, vmin, vmax, fmt)

    def build(xs):
        # For each contiguous run of "present" records, render a stack of
        # polygons.
        runs = []
        cur = []
        for i in range(n):
            if present[i] and xs[i] is not None:
                cur.append(i)
            else:
                if cur:
                    runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)

        polys = []
        # baseline lower bound for each record (accumulates as we stack)
        baselines = {idx: 0.0 for idx in range(n)}
        for label, colour, series in layers:
            for run in runs:
                pts_top = []
                pts_bot = []
                for idx in run:
                    v = series[idx] if idx < len(series) else None
                    if not isinstance(v, (int, float)):
                        v = 0.0
                    base = baselines[idx]
                    top = base + float(v)
                    baselines[idx] = top
                    x = xs[idx]
                    y_top = pad_t + inner_h - inner_h * (top - vmin) / (vmax - vmin)
                    y_bot = pad_t + inner_h - inner_h * (base - vmin) / (vmax - vmin)
                    pts_top.append((x, y_top))
                    pts_bot.append((x, y_bot))
                pts = pts_top + list(reversed(pts_bot))
                if len(pts) >= 2:
                    pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
                    polys.append(
                        f"<polygon fill='{colour}' fill-opacity='0.75' "
                        f"stroke='{colour}' stroke-width='0.5' points='{pts_str}'/>"
                    )
        return "".join(polys)

    xs_run = _x_positions_by_run(n, pad_l, inner_w)
    xs_date = _x_positions_by_date(timestamps, pad_l, inner_w)
    body_run = build(xs_run)
    body_date = build(xs_date)

    ticks_run = _run_tick_marks(timestamps, pad_l, inner_w)
    ticks_date = _date_tick_marks(timestamps, pad_l, inner_w)

    legend_html = (
        "<div class='legend'>"
        + "".join(
            f"<span><i style='background:{colour};'></i>"
            f"{html.escape(label)}</span>"
            for label, colour, _ in layers
        )
        + "</div>"
    )

    svg_run = (
        f"<svg class='chart chart-by-run' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
        f"{axes}{body_run}{_xaxis_labels(ticks_run, pad_l, inner_h)}"
        f"</svg>"
    )
    svg_date = (
        f"<svg class='chart chart-by-date' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}'>"
        f"{axes}{body_date}{_xaxis_labels(ticks_date, pad_l, inner_h)}"
        f"</svg>"
    )

    sub = (
        f"<p class='chart-subtitle'>{html.escape(subtitle)}</p>"
        if subtitle else ""
    )
    return (
        f"<section class='panel'>"
        f"<p class='chart-title'>{html.escape(title)}</p>{sub}"
        f"{legend_html}{svg_run}{svg_date}</section>"
    )


def _best_ssim(r: dict):
    """Prefer the User's-Guide mean SSIM; else snippet-level."""
    v = r.get("ug_mean_ssim")
    if isinstance(v, (int, float)):
        return v, "user_guide"
    v = r.get("mean_ssim")
    if isinstance(v, (int, float)):
        # The mean_ssim field used to be snippet-level only; treat it as
        # such unless mean_ssim_source says otherwise.
        src = r.get("mean_ssim_source") or "snippets"
        return v, src
    v = r.get("snippet_mean_ssim")
    if isinstance(v, (int, float)):
        return v, "snippets"
    return None, None


def render_html(jsonl_path: Path, html_path: Path) -> None:
    runs: list = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    parts = [HTML_HEAD]
    if not runs:
        parts.append("<p class='muted'>No history yet. "
                     "Run <code>tests/run_all.sh</code>.</p></body></html>")
        html_path.write_text("".join(parts), encoding="utf-8")
        return

    latest = runs[-1]
    parts.append(
        f"<p class='muted'>{len(runs)} run(s) recorded. "
        f"Latest: <code>{html.escape(latest.get('timestamp', '?'))}"
        f"</code> @ <code>{html.escape(latest.get('commit', '?')[:12])}"
        f"</code>.</p>"
    )

    # X-axis toggle.
    parts.append(
        "<div class='controls'>X-axis: "
        "<label><input type='radio' name='xaxis' value='run' checked> "
        "by run number</label>"
        "<label><input type='radio' name='xaxis' value='date'> "
        "by date</label></div>"
    )

    timestamps = [r.get("timestamp", "") for r in runs]

    # Panel 1: pass-rate (existing).
    pass_rate_series = []
    for r in runs:
        total = r.get("snippets_total") or 0
        passed = (r.get("pass") or 0) + (r.get("pass_excellent") or 0)
        if total > 0:
            pass_rate_series.append(100.0 * passed / total)
        else:
            pass_rate_series.append(None)
    parts.append(render_line_chart(
        pass_rate_series, timestamps,
        "Snippet pass-rate over time",
        fmt="{:.1f}%",
        colour="#0a58ca",
        subtitle="(PASS + PASS-EXCELLENT) / snippets_total, as a percentage.",
    ))

    # Panel 2: pass-excellent COUNT.
    pe_series = [r.get("pass_excellent") for r in runs]
    parts.append(render_line_chart(
        pe_series, timestamps,
        "PASS-EXCELLENT count over time",
        fmt="{:.0f}",
        colour="#198754",
        subtitle="Number of snippets earning the strictest verdict.",
    ))

    # Panel 3: mean SSIM (UG preferred, else snippet-level).
    ssim_series = []
    ssim_sources = []
    for r in runs:
        v, src = _best_ssim(r)
        ssim_series.append(v)
        ssim_sources.append(src)
    used_ug = any(s == "user_guide" for s in ssim_sources)
    sub = (
        "User's-Guide mean SSIM (327 pages) when available; "
        "snippet-level mean SSIM as fallback."
        if used_ug else
        "Snippet-level mean SSIM. "
        "(User's-Guide SSIM will appear here once history.py records it.)"
    )
    parts.append(render_line_chart(
        ssim_series, timestamps,
        "Mean SSIM over time",
        fmt="{:.4f}",
        colour="#6f42c1",
        subtitle=sub,
    ))

    # Panel 4: User's-Guide diff buckets as stacked area.
    ok_series = [r.get("ug_ok") for r in runs]
    diff_series = [r.get("ug_diff") for r in runs]
    bad_series = [r.get("ug_bad") for r in runs]
    miss_series = [r.get("ug_missing") for r in runs]
    parts.append(render_stacked_area_chart(
        [
            ("OK (<5%)",       "#198754", ok_series),
            ("DIFF (5-20%)",   "#fd7e14", diff_series),
            ("BAD (>=20%)",    "#dc3545", bad_series),
            ("MISSING",        "#6c757d", miss_series),
        ],
        timestamps,
        "User's-Guide diff bucket counts (stacked)",
        subtitle="Bucket counts from user_guide_diff/manifest.json. "
                 "Older runs without these fields render as gaps.",
    ))

    # Panel 5: wall-clock UG rebuild duration.
    wall_series = []
    for r in runs:
        v = r.get("wall_clock_sec")
        if v is None:
            # legacy alias
            v = r.get("user_guide_wall_time_seconds")
        if isinstance(v, (int, float)):
            wall_series.append(float(v))
        else:
            wall_series.append(None)
    parts.append(render_line_chart(
        wall_series, timestamps,
        "User's-Guide rebuild wall-clock (seconds)",
        fmt="{:.1f}",
        colour="#0dcaf0",
        subtitle="Either measured by history.py at run time, "
                 "or read from a wall_clock_sec field in the manifest.",
    ))

    # Runs table.
    parts.append("<h2>Runs</h2><table><thead><tr>")
    for h in (
        "Timestamp (UTC)", "Commit", "Pass-Exc", "Pass", "Fail",
        "Mean SSIM", "UG OK", "UG DIFF", "UG BAD", "UG MISS",
        "Wall (s)",
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
        ssim_val, _ = _best_ssim(r)
        wall = r.get("wall_clock_sec")
        if wall is None:
            wall = r.get("user_guide_wall_time_seconds")
        parts.append(
            "<tr>"
            f"<td>{html.escape(r.get('timestamp', '?'))}</td>"
            f"<td><code>{html.escape(r.get('commit', '?')[:12])}</code></td>"
            f"<td>{r.get('pass_excellent', 0)}</td>"
            f"<td>{r.get('pass', 0)}</td>"
            f"<td>{r.get('fail', 0)}</td>"
            f"<td>{fmt(ssim_val)}</td>"
            f"<td>{fmt(r.get('ug_ok'), '{:.0f}')}</td>"
            f"<td>{fmt(r.get('ug_diff'), '{:.0f}')}</td>"
            f"<td>{fmt(r.get('ug_bad'), '{:.0f}')}</td>"
            f"<td>{fmt(r.get('ug_missing'), '{:.0f}')}</td>"
            f"<td>{fmt(wall, '{:.1f}')}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")

    # Vanilla JS toggle for X-axis.
    parts.append("""<script>
(function() {
  var radios = document.querySelectorAll("input[name='xaxis']");
  for (var i = 0; i < radios.length; i++) {
    radios[i].addEventListener("change", function(ev) {
      document.body.setAttribute("data-xaxis", ev.target.value);
    });
  }
})();
</script>""")

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

    t0 = time.monotonic()
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    commit = git_commit(repo_dir)
    snip = collect_snippet_metrics(results_json)
    ug = collect_user_guide_metrics(manifest_json)

    # Pick the best mean_ssim available. Prefer UG over snippets.
    if ug["ug_mean_ssim"] is not None:
        mean_ssim = ug["ug_mean_ssim"]
        mean_ssim_source = "user_guide"
    elif snip["snippet_mean_ssim"] is not None:
        mean_ssim = snip["snippet_mean_ssim"]
        mean_ssim_source = "snippets"
    else:
        mean_ssim = None
        mean_ssim_source = None

    # Wall-clock: a manifest field (if the rebuild script ever starts
    # writing one) wins, otherwise time the runtime of this script as a
    # rough lower bound. The latter is not the UG rebuild time so we
    # only record it if the manifest doesn't have it (so old records
    # with null stay null and new ones get a real value when available).
    elapsed_self = time.monotonic() - t0

    record = {
        "timestamp": timestamp,
        "commit": commit,
        "pass": snip["pass"],
        "pass_excellent": snip["pass_excellent"],
        "fail": snip["fail"],
        "snippets_total": snip["snippets_total"],
        "mean_ae_ratio": snip["mean_ae_ratio"],
        "mean_ssim": mean_ssim,
        "mean_ssim_source": mean_ssim_source,
        "snippet_mean_ssim": snip["snippet_mean_ssim"],
        "ug_ok": ug["ug_ok"],
        "ug_diff": ug["ug_diff"],
        "ug_bad": ug["ug_bad"],
        "ug_missing": ug["ug_missing"],
        "ug_total": ug["ug_total"],
        "ug_mean_ssim": ug["ug_mean_ssim"],
        "wall_clock_sec": ug["wall_clock_sec"],
        # Legacy alias kept for backward-compat with older readers.
        "user_guide_wall_time_seconds": ug["wall_clock_sec"],
        "history_py_elapsed_sec": round(elapsed_self, 3),
    }

    with jsonl_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    render_html(jsonl_path, html_path)

    print(f"history: appended record for {commit[:12]} -> {jsonl_path.name}")
    print(f"history: rendered viewer -> {html_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
