#!/usr/bin/env python3
"""bench.py -- microbenchmark suite for the lout build pipeline.

For each snippet in tests/snippets/*.lt this script times four stages
(median of three runs each):

    1. PS  build via `lout` (the FROZEN PostScript back-end).
    2. SVG build via `lout -G` (the new z53.c back-end).
    3. PS -> PDF via `ps2pdf`.
    4. SVG -> PNG via `rsvg-convert`.

Per-snippet records have the shape:

    {"snippet": "name",
     "ps_sec": float, "svg_sec": float,
     "ps2pdf_sec": float, "rsvg_sec": float}

A per-run record is appended to tests/bench.jsonl with the same
top-level shape as tests/history.jsonl:

    {"iso_ts": "...", "commit": "...",
     "snippets": [<per-snippet records>],
     "totals": {"ps": ..., "svg": ..., "ps2pdf": ..., "rsvg": ...}}

Regression detection: for each (snippet, stage) the latest measurement
is compared against the median of that stage across the last 5 runs.
If we have N >= 3 historical samples and `new > 1.5 * median` a
WARNING is printed. Exit code is 0 by default; with --strict any
regression yields exit 1.

Stdlib + subprocess + time only. No third-party deps.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


# ----------------------------------------------------------------------
# Configuration.
# ----------------------------------------------------------------------
RUNS_PER_STAGE = 3      # median of 3
HISTORY_WINDOW = 5      # last N runs for regression baseline
HISTORY_MIN = 3         # minimum historical samples to warn
REGRESSION_FACTOR = 1.5

STAGES = ("ps", "svg", "ps2pdf", "rsvg")


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


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def time_cmd(cmd, cwd: Optional[Path] = None) -> float:
    """Run cmd, return wall-clock seconds. Stdout/stderr are discarded.
    On non-zero exit we still return the elapsed time but mark the run
    by raising. Caller decides what to do."""
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(map(str, cmd))}")
    return elapsed


def median_of(cmd, runs: int, cwd: Optional[Path] = None) -> Optional[float]:
    """Run cmd `runs` times, return the median wall-clock. Returns None
    if any run fails."""
    samples = []
    for _ in range(runs):
        try:
            samples.append(time_cmd(cmd, cwd=cwd))
        except RuntimeError:
            return None
    return statistics.median(samples)


# ----------------------------------------------------------------------
# Per-snippet pipeline.
# ----------------------------------------------------------------------
def bench_snippet(
    name: str,
    lt_path: Path,
    out_dir: Path,
    lout_bin: Path,
    lout_dir: Path,
) -> dict:
    """Time the four stages for one snippet. Each stage that succeeds
    gets a float; any stage that fails (missing tool, lout error,
    rsvg error...) is recorded as None."""
    ps = out_dir / f"{name}.bench.ps"
    svg = out_dir / f"{name}.bench.svg"
    pdf = out_dir / f"{name}.bench.pdf"
    png = out_dir / f"{name}.bench.png"

    lout_base = [
        str(lout_bin),
        "-I", str(lout_dir / "include"),
        "-D", str(lout_dir / "data"),
        "-F", str(lout_dir / "font"),
        "-C", str(lout_dir / "maps"),
        "-H", str(lout_dir / "hyph"),
        "-s",
    ]

    rec = {"snippet": name, "ps_sec": None, "svg_sec": None,
           "ps2pdf_sec": None, "rsvg_sec": None}

    # 1) PS build (frozen back-end, default).
    rec["ps_sec"] = median_of(
        lout_base + ["-o", str(ps), str(lt_path)],
        RUNS_PER_STAGE, cwd=out_dir,
    )

    # 2) SVG build (z53.c, -G).
    rec["svg_sec"] = median_of(
        lout_base + ["-G", "-o", str(svg), str(lt_path)],
        RUNS_PER_STAGE, cwd=out_dir,
    )

    # 3) PS -> PDF (only if PS exists).
    if ps.exists() and ps.stat().st_size > 0 and have("ps2pdf"):
        rec["ps2pdf_sec"] = median_of(
            ["ps2pdf", str(ps), str(pdf)],
            RUNS_PER_STAGE,
        )

    # 4) SVG -> PNG via rsvg-convert. Lout emits multiple <svg> roots
    # for multi-page; we don't pre-split here -- rsvg-convert may
    # accept only the first page or fail. Failure is recorded as None
    # rather than aborting.
    if svg.exists() and svg.stat().st_size > 0 and have("rsvg-convert"):
        rec["rsvg_sec"] = median_of(
            ["rsvg-convert", "-d", "150", "-p", "150",
             "-f", "png", "-o", str(png), str(svg)],
            RUNS_PER_STAGE,
        )

    # Clean up the intermediate artifacts so bench runs don't pollute
    # the regression compare output dir.
    for p in (ps, svg, pdf, png):
        try:
            p.unlink()
        except FileNotFoundError:
            pass

    return rec


# ----------------------------------------------------------------------
# Regression detection.
# ----------------------------------------------------------------------
def load_history(jsonl_path: Path) -> list:
    if not jsonl_path.exists():
        return []
    runs = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return runs


def historical_medians(
    history: list, window: int = HISTORY_WINDOW
) -> dict:
    """Return {snippet: {stage: median_over_window_or_None}} from the
    last `window` historical runs."""
    recent = history[-window:] if len(history) > window else history
    out: dict = {}
    for run in recent:
        for s in run.get("snippets", []):
            name = s.get("snippet")
            if not name:
                continue
            d = out.setdefault(name, {st: [] for st in STAGES})
            for st in STAGES:
                v = s.get(f"{st}_sec")
                if isinstance(v, (int, float)):
                    d[st].append(float(v))
    medians: dict = {}
    for name, by_stage in out.items():
        medians[name] = {
            st: (statistics.median(vs) if len(vs) >= HISTORY_MIN else None)
            for st, vs in by_stage.items()
        }
    return medians


def check_regressions(latest_snips: list, baseline: dict) -> list:
    """Return a list of warning strings. Empty if no regressions."""
    warnings = []
    for s in latest_snips:
        name = s.get("snippet")
        if not name or name not in baseline:
            continue
        for st in STAGES:
            new = s.get(f"{st}_sec")
            old = baseline[name].get(st)
            if not isinstance(new, (int, float)):
                continue
            if not isinstance(old, (int, float)) or old <= 0:
                continue
            if new > REGRESSION_FACTOR * old:
                warnings.append(
                    f"WARNING: {name} {st} regressed: "
                    f"{new:.3f}s vs median {old:.3f}s"
                )
    return warnings


# ----------------------------------------------------------------------
# Main.
# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--strict", action="store_true",
        help="Exit 1 if any regression is detected.",
    )
    ap.add_argument(
        "--snippets", default=None,
        help="Comma-separated subset of snippet base names "
             "(default: all *.lt in tests/snippets/).",
    )
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_dir = script_dir.parent
    lout_dir = repo_dir / "lout"
    lout_bin = lout_dir / "lout"
    snip_dir = script_dir / "snippets"
    out_dir = script_dir / "out"
    jsonl_path = script_dir / "bench.jsonl"
    html_path = script_dir / "bench.html"

    out_dir.mkdir(parents=True, exist_ok=True)

    if not lout_bin.exists() or not os.access(lout_bin, os.X_OK):
        print(f"FATAL: lout binary not found at {lout_bin}",
              file=sys.stderr)
        print(f"Run `cd {lout_dir} && make lout` first.",
              file=sys.stderr)
        return 2

    all_lts = sorted(snip_dir.glob("*.lt"))
    if args.snippets:
        wanted = set(s.strip() for s in args.snippets.split(",") if s.strip())
        all_lts = [p for p in all_lts if p.stem in wanted]
    if not all_lts:
        print(f"No snippets found in {snip_dir}", file=sys.stderr)
        return 1

    print(f"bench: {len(all_lts)} snippet(s), "
          f"{RUNS_PER_STAGE} runs/stage, "
          f"4 stages = {len(all_lts) * 4 * RUNS_PER_STAGE} timed processes")
    t_start = time.monotonic()

    snippets = []
    for i, lt in enumerate(all_lts, 1):
        name = lt.stem
        rec = bench_snippet(name, lt, out_dir, lout_bin, lout_dir)
        snippets.append(rec)

        def f(v):
            return "----" if v is None else f"{v:.3f}"
        print(
            f"  [{i:3d}/{len(all_lts)}] {name:<32}  "
            f"ps={f(rec['ps_sec'])}  svg={f(rec['svg_sec'])}  "
            f"ps2pdf={f(rec['ps2pdf_sec'])}  rsvg={f(rec['rsvg_sec'])}"
        )

    elapsed = time.monotonic() - t_start

    totals = {st: 0.0 for st in STAGES}
    for s in snippets:
        for st in STAGES:
            v = s.get(f"{st}_sec")
            if isinstance(v, (int, float)):
                totals[st] += v

    iso_ts = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    commit = git_commit(repo_dir)

    record = {
        "iso_ts": iso_ts,
        "commit": commit,
        "snippets": snippets,
        "totals": {st: round(totals[st], 4) for st in STAGES},
        "elapsed_sec": round(elapsed, 3),
        "snippet_count": len(snippets),
    }

    # Regression detection BEFORE we append the new record (so the
    # baseline doesn't include the just-measured run).
    history = load_history(jsonl_path)
    baseline = historical_medians(history, HISTORY_WINDOW)
    warnings = check_regressions(snippets, baseline)

    # Append new record.
    with jsonl_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    # Re-render the viewer if the HTML scaffold is available next to
    # this script. (Static HTML; reads bench.jsonl client-side, so we
    # only need to copy/write it once. We re-write each run so updates
    # propagate even if a user edits bench.html accidentally.)
    try:
        render_html(jsonl_path, html_path)
    except Exception as exc:
        print(f"bench: warning -- could not render {html_path.name}: {exc}",
              file=sys.stderr)

    print("")
    print(f"bench: totals (sec)  "
          + "  ".join(f"{st}={totals[st]:.2f}" for st in STAGES))
    print(f"bench: elapsed = {elapsed:.1f}s  "
          f"appended -> {jsonl_path.name}")

    if warnings:
        for w in warnings:
            print(w)
        if args.strict:
            return 1
    elif history:
        print(f"bench: no regressions vs last {min(len(history), HISTORY_WINDOW)} run(s)")
    else:
        print("bench: no history yet -- baseline established")

    return 0


# ----------------------------------------------------------------------
# HTML viewer.
#
# A standalone, dependency-free page that reads bench.jsonl via
# fetch("./bench.jsonl") and renders two charts in inline SVG using
# vanilla JS:
#
#   - Top: stacked-bar chart of total time per back-end (ps / svg /
#     ps2pdf / rsvg), one bar per run, last 30 runs.
#   - Below: per-snippet line chart. A sortable list of all snippets
#     on the left; clicking a snippet renders four series (one per
#     stage) on the right.
#
# Inline SVG only, no external CSS or JS.
# ----------------------------------------------------------------------
VIEWER_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8">
<title>mdlout bench history</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       Helvetica, Arial, sans-serif; margin: 1.2rem; color: #1c1c1c; }
h1 { margin-top: 0; }
h2 { margin: 1.4rem 0 0.4rem 0; }
.muted { color: #777; font-size: 0.9rem; }
.chart { background: #fff; border: 1px solid #ddd; display: block; }
.chart-title { font-weight: 600; margin: 0 0 0.3rem 0; }
.legend { font-size: 0.8rem; margin: 0.2rem 0 0.4rem 0; }
.legend span { display: inline-block; margin-right: 0.8rem; }
.legend i { display: inline-block; width: 0.8rem; height: 0.8rem;
            margin-right: 0.3rem; vertical-align: middle;
            border: 1px solid #999; }
.row { display: flex; gap: 1rem; align-items: flex-start; }
.snip-list { width: 260px; max-height: 360px; overflow-y: auto;
             border: 1px solid #ddd; padding: 0.3rem; font-size: 0.85rem;
             font-variant-numeric: tabular-nums; }
.snip-list .item { cursor: pointer; padding: 0.15rem 0.3rem;
                   border-radius: 3px; }
.snip-list .item:hover { background: #eef; }
.snip-list .item.sel { background: #cfe2ff; font-weight: 600; }
.snip-list .item .total { color: #555; float: right; font-size: 0.8rem; }
.controls { font-size: 0.85rem; margin: 0.2rem 0; }
.controls label { margin-right: 0.8rem; cursor: pointer; }
code { font-family: ui-monospace, Menlo, Consolas, monospace;
       font-size: 0.82rem; }
.err { color: #b00; }
</style></head><body>
<h1>mdlout bench history</h1>
<p class="muted" id="meta">Loading bench.jsonl...</p>

<h2>Total time per back-end (last 30 runs)</h2>
<p class="muted">Wall-clock seconds summed across all snippets, stacked per stage.</p>
<div class="legend" id="totals-legend"></div>
<div id="totals-chart"></div>

<h2>Per-snippet timing</h2>
<p class="muted">Click a snippet to plot its four stages over history.</p>
<div class="controls">
  Sort by:
  <label><input type="radio" name="sort" value="name" checked> name</label>
  <label><input type="radio" name="sort" value="total"> total time (latest)</label>
  <label><input type="radio" name="sort" value="ps"> ps</label>
  <label><input type="radio" name="sort" value="svg"> svg</label>
  <label><input type="radio" name="sort" value="ps2pdf"> ps2pdf</label>
  <label><input type="radio" name="sort" value="rsvg"> rsvg</label>
</div>
<div class="row">
  <div class="snip-list" id="snip-list"></div>
  <div style="flex: 1;">
    <div class="legend" id="snip-legend"></div>
    <div id="snip-chart"></div>
  </div>
</div>

<script>
(function() {
  var STAGES = ["ps", "svg", "ps2pdf", "rsvg"];
  var COLOURS = {ps:"#0a58ca", svg:"#198754", ps2pdf:"#fd7e14", rsvg:"#6f42c1"};
  var runs = [];

  function el(tag, attrs, kids) {
    var ns = "http://www.w3.org/2000/svg";
    var n = (tag === "svg" || tag === "g" || tag === "rect" ||
             tag === "line" || tag === "text" || tag === "polyline" ||
             tag === "circle" || tag === "title")
      ? document.createElementNS(ns, tag)
      : document.createElement(tag);
    attrs = attrs || {};
    for (var k in attrs) {
      if (attrs.hasOwnProperty(k)) n.setAttribute(k, attrs[k]);
    }
    if (kids) {
      for (var i = 0; i < kids.length; i++) {
        n.appendChild(typeof kids[i] === "string"
          ? document.createTextNode(kids[i]) : kids[i]);
      }
    }
    return n;
  }

  function fmtTick(iso) {
    if (!iso) return "?";
    var m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
    if (!m) return iso.slice(0, 16);
    var mon = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"][parseInt(m[2],10)-1];
    return mon + " " + m[3] + " " + m[4] + ":" + m[5];
  }

  function isoToEpoch(iso) {
    var t = Date.parse(iso);
    return isNaN(t) ? null : t / 1000;
  }

  function renderLegend(target, items) {
    target.innerHTML = "";
    items.forEach(function(it) {
      var sp = document.createElement("span");
      var i = document.createElement("i");
      i.style.background = it.colour;
      sp.appendChild(i);
      sp.appendChild(document.createTextNode(it.label));
      target.appendChild(sp);
    });
  }

  function axisAndGrid(svg, padL, padT, innerW, innerH, vmin, vmax, fmt) {
    svg.appendChild(el("line", {x1:padL, y1:padT, x2:padL, y2:padT+innerH,
                                stroke:"#888", "stroke-width":"0.8"}));
    svg.appendChild(el("line", {x1:padL, y1:padT+innerH, x2:padL+innerW,
                                y2:padT+innerH, stroke:"#888",
                                "stroke-width":"0.8"}));
    var midY = padT + innerH/2;
    svg.appendChild(el("line", {x1:padL, y1:midY, x2:padL+innerW, y2:midY,
                                stroke:"#eee", "stroke-width":"0.8"}));
    svg.appendChild(el("text", {x:padL-4, y:padT+4, "text-anchor":"end",
                                "font-size":"10"}, [fmt(vmax)]));
    svg.appendChild(el("text", {x:padL-4, y:midY+3, "text-anchor":"end",
                                "font-size":"10"}, [fmt((vmin+vmax)/2)]));
    svg.appendChild(el("text", {x:padL-4, y:padT+innerH, "text-anchor":"end",
                                "font-size":"10"}, [fmt(vmin)]));
  }

  function xAxisLabels(svg, ticks, padT, innerH) {
    var yText = padT + innerH + 14;
    var yTick = padT + innerH;
    ticks.forEach(function(t) {
      svg.appendChild(el("line", {x1:t.x, y1:yTick, x2:t.x, y2:yTick+3,
                                  stroke:"#888", "stroke-width":"0.8"}));
      svg.appendChild(el("text", {x:t.x, y:yText, "text-anchor":"middle",
                                  "font-size":"9", fill:"#555"}, [t.label]));
    });
  }

  function pickTicks(n, maxTicks, timestamps) {
    if (!n) return [];
    var idxs = [];
    if (n <= maxTicks) {
      for (var i = 0; i < n; i++) idxs.push(i);
    } else {
      var seen = {};
      for (var i = 0; i < maxTicks; i++) {
        var idx = Math.round(i * (n - 1) / (maxTicks - 1));
        if (!seen[idx]) { seen[idx] = 1; idxs.push(idx); }
      }
    }
    return idxs.map(function(i) { return {i:i, ts:timestamps[i]}; });
  }

  function renderTotalsChart(container, runs) {
    var W = 780, H = 240, padL = 60, padR = 20, padT = 20, padB = 40;
    var innerW = W - padL - padR;
    var innerH = H - padT - padB;
    var slice = runs.slice(-30);
    var n = slice.length;
    if (!n) {
      container.innerHTML = "<p class='muted'>No runs yet.</p>";
      return;
    }
    var sums = slice.map(function(r) {
      var s = 0;
      STAGES.forEach(function(st) {
        var v = r.totals && r.totals[st];
        if (typeof v === "number") s += v;
      });
      return s;
    });
    var vmax = Math.max.apply(null, sums);
    if (!isFinite(vmax) || vmax <= 0) vmax = 1;
    var vmin = 0;

    var svg = el("svg", {"class":"chart", width:W, height:H,
                         viewBox:"0 0 " + W + " " + H});
    axisAndGrid(svg, padL, padT, innerW, innerH, vmin, vmax,
                function(v){return v.toFixed(0);});

    // bar width
    var bw = Math.max(2, Math.floor(innerW / Math.max(n, 1)) - 2);
    slice.forEach(function(r, i) {
      var x = padL + (n === 1 ? innerW/2 - bw/2
                               : (innerW * i / Math.max(n-1, 1)) - bw/2);
      var yBase = padT + innerH;
      var acc = 0;
      STAGES.forEach(function(st) {
        var v = r.totals && r.totals[st];
        if (typeof v !== "number") return;
        var h = innerH * (v / vmax);
        var yTop = yBase - h;
        var rect = el("rect", {
          x: x, y: yTop, width: bw, height: h,
          fill: COLOURS[st], "fill-opacity":"0.85"
        });
        rect.appendChild(el("title", {}, [
          st + ": " + v.toFixed(2) + "s @ " + (r.iso_ts || "?")
        ]));
        svg.appendChild(rect);
        yBase = yTop;
        acc += v;
      });
    });

    var tickIdxs = pickTicks(n, 6, slice.map(function(r){return r.iso_ts;}));
    var ticks = tickIdxs.map(function(t) {
      var x = padL + (n === 1 ? innerW/2 : innerW * t.i / Math.max(n-1, 1));
      return {x:x, label:fmtTick(t.ts)};
    });
    xAxisLabels(svg, ticks, padT, innerH);
    container.innerHTML = "";
    container.appendChild(svg);
  }

  function renderSnippetChart(container, runs, snippet) {
    var W = 600, H = 280, padL = 50, padR = 20, padT = 20, padB = 40;
    var innerW = W - padL - padR;
    var innerH = H - padT - padB;
    var series = {};
    STAGES.forEach(function(st){ series[st] = []; });
    var timestamps = [];
    runs.forEach(function(r) {
      timestamps.push(r.iso_ts || "");
      var s = (r.snippets || []).find(function(x){return x.snippet === snippet;});
      STAGES.forEach(function(st){
        series[st].push(s && typeof s[st+"_sec"] === "number" ? s[st+"_sec"] : null);
      });
    });
    var allVals = [];
    STAGES.forEach(function(st){
      series[st].forEach(function(v){
        if (typeof v === "number") allVals.push(v);
      });
    });
    if (!allVals.length) {
      container.innerHTML = "<p class='muted'>No data for "
        + snippet + ".</p>";
      return;
    }
    var vmin = 0;
    var vmax = Math.max.apply(null, allVals);
    if (vmax <= vmin) vmax = vmin + 0.01;
    var svg = el("svg", {"class":"chart", width:W, height:H,
                         viewBox:"0 0 " + W + " " + H});
    axisAndGrid(svg, padL, padT, innerW, innerH, vmin, vmax,
                function(v){return v.toFixed(3);});

    var n = runs.length;
    STAGES.forEach(function(st) {
      var pts = [];
      for (var i = 0; i < n; i++) {
        var v = series[st][i];
        if (typeof v !== "number") {
          if (pts.length >= 2) {
            svg.appendChild(el("polyline", {fill:"none", stroke:COLOURS[st],
              "stroke-width":"1.5", points: pts.join(" ")}));
          }
          pts = [];
          continue;
        }
        var x = padL + (n === 1 ? innerW/2 : innerW * i / Math.max(n-1, 1));
        var y = padT + innerH - innerH * (v - vmin) / (vmax - vmin);
        pts.push(x.toFixed(1) + "," + y.toFixed(1));
        var c = el("circle", {cx:x.toFixed(1), cy:y.toFixed(1), r:"2.5",
                              fill: COLOURS[st]});
        c.appendChild(el("title", {}, [st + ": " + v.toFixed(3)
          + "s @ " + (timestamps[i] || "?")]));
        svg.appendChild(c);
      }
      if (pts.length >= 2) {
        svg.appendChild(el("polyline", {fill:"none", stroke:COLOURS[st],
          "stroke-width":"1.5", points: pts.join(" ")}));
      }
    });

    var tickIdxs = pickTicks(n, 6, timestamps);
    var ticks = tickIdxs.map(function(t) {
      var x = padL + (n === 1 ? innerW/2 : innerW * t.i / Math.max(n-1, 1));
      return {x:x, label:fmtTick(t.ts)};
    });
    xAxisLabels(svg, ticks, padT, innerH);
    container.innerHTML = "";
    container.appendChild(svg);
  }

  function buildSnippetList(runs) {
    if (!runs.length) return [];
    var latest = runs[runs.length - 1];
    var byName = {};
    (latest.snippets || []).forEach(function(s) {
      var total = 0, ok = false;
      STAGES.forEach(function(st){
        var v = s[st+"_sec"];
        if (typeof v === "number") { total += v; ok = true; }
      });
      byName[s.snippet] = {
        name: s.snippet, total: ok ? total : null,
        ps: s.ps_sec, svg: s.svg_sec,
        ps2pdf: s.ps2pdf_sec, rsvg: s.rsvg_sec
      };
    });
    return Object.keys(byName).map(function(k){return byName[k];});
  }

  function paintSnipList(items, sortKey, sel) {
    var list = items.slice();
    list.sort(function(a, b) {
      if (sortKey === "name") return a.name.localeCompare(b.name);
      var av = a[sortKey], bv = b[sortKey];
      if (av == null && bv == null) return a.name.localeCompare(b.name);
      if (av == null) return 1;
      if (bv == null) return -1;
      return bv - av;  // descending for time-based sorts
    });
    var host = document.getElementById("snip-list");
    host.innerHTML = "";
    list.forEach(function(it) {
      var div = document.createElement("div");
      div.className = "item" + (it.name === sel ? " sel" : "");
      var label = document.createElement("span");
      label.textContent = it.name;
      var total = document.createElement("span");
      total.className = "total";
      total.textContent = it.total == null ? "----" : it.total.toFixed(3) + "s";
      div.appendChild(label);
      div.appendChild(total);
      div.onclick = function() { selectSnippet(it.name); };
      host.appendChild(div);
    });
  }

  var _items = [];
  var _sortKey = "name";
  var _selected = null;
  function selectSnippet(name) {
    _selected = name;
    paintSnipList(_items, _sortKey, _selected);
    renderSnippetChart(document.getElementById("snip-chart"), runs, name);
  }

  function setSort(key) {
    _sortKey = key;
    paintSnipList(_items, _sortKey, _selected);
  }

  function load() {
    fetch("./bench.jsonl", {cache: "no-store"})
      .then(function(r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function(text) {
        runs = text.split(/\r?\n/).filter(function(l){return l.trim();})
          .map(function(l){
            try { return JSON.parse(l); } catch (e) { return null; }
          }).filter(function(x){return x;});
        var meta = document.getElementById("meta");
        if (!runs.length) {
          meta.textContent = "bench.jsonl is empty.";
          return;
        }
        var latest = runs[runs.length - 1];
        meta.innerHTML = runs.length + " run(s) recorded. Latest: <code>"
          + (latest.iso_ts || "?") + "</code> @ <code>"
          + ((latest.commit || "?").slice(0, 12)) + "</code> ("
          + (latest.snippet_count || (latest.snippets||[]).length)
          + " snippets, " + (latest.elapsed_sec || 0).toFixed(1) + "s).";

        renderLegend(document.getElementById("totals-legend"),
          STAGES.map(function(st){return {label:st, colour:COLOURS[st]};}));
        renderLegend(document.getElementById("snip-legend"),
          STAGES.map(function(st){return {label:st, colour:COLOURS[st]};}));
        renderTotalsChart(document.getElementById("totals-chart"), runs);

        _items = buildSnippetList(runs);
        _selected = _items.length ? _items[0].name : null;
        paintSnipList(_items, _sortKey, _selected);
        if (_selected)
          renderSnippetChart(document.getElementById("snip-chart"),
                             runs, _selected);
      })
      .catch(function(err) {
        document.getElementById("meta").innerHTML =
          "<span class='err'>Could not load bench.jsonl: "
          + err.message + "</span>";
      });

    var radios = document.querySelectorAll("input[name='sort']");
    for (var i = 0; i < radios.length; i++) {
      radios[i].addEventListener("change", function(ev){
        setSort(ev.target.value);
      });
    }
  }
  load();
})();
</script>
</body></html>
"""


def render_html(jsonl_path: Path, html_path: Path) -> None:
    """Write the static viewer HTML. It reads bench.jsonl client-side
    via fetch(), so we only need to (re)write the scaffold once per
    run -- but doing it every run keeps the file in sync if anyone
    edits it inadvertently."""
    html_path.write_text(VIEWER_HTML, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
