#!/usr/bin/env python3
"""Render tests/snippet_history_sparklines.html.

Reads tests/snippet_history.jsonl (one JSON record per snippet per
regression run) and emits a single HTML page showing a tiny inline-SVG
sparkline of the AE pixel_diff_ratio over the last N runs for every
snippet. CSS grid layout, ~80x20 px per sparkline.

Sort: by most-recent diff_ratio descending (flakier first) so the user
sees the worst offenders first.

Hover: native <title> tooltip on each sparkline with snippet name +
latest AE + latest SSIM.

Click: navigates to snippet_history.html#snippet=<name> for the full
per-snippet view (snippet_history.html honors that hash on load).

Stdlib-only. No external CSS, no JS dependencies. Run from the repo
root or from tests/:

    python3 tests/render_snippet_sparklines.py

Re-running is idempotent. Designed to be invoked alongside or in place
of tests/history.py's render_snippet_history step.
"""
from __future__ import annotations

import html as html_mod
import json
import sys
from pathlib import Path

# Max number of most-recent runs to plot per snippet.
MAX_RUNS = 20

# Sparkline geometry (SVG viewBox units = px).
SPARK_W = 80
SPARK_H = 20
SPARK_PAD = 1.5


def load_records(jsonl_path: Path) -> dict[str, list[dict]]:
    by_name: dict[str, list[dict]] = {}
    if not jsonl_path.exists():
        return by_name
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        nm = rec.get("name")
        if not nm:
            continue
        by_name.setdefault(nm, []).append(rec)
    for nm in by_name:
        by_name[nm].sort(key=lambda r: r.get("timestamp", ""))
    return by_name


def sparkline_svg(values: list[float]) -> str:
    """Return inline SVG markup for the given numeric series.

    Y-axis: min at bottom, max at top. X-axis: evenly spaced indices.
    Single series with no fill, last point marked, baseline at bottom.
    """
    if not values:
        return (f"<svg class='spark' viewBox='0 0 {SPARK_W} {SPARK_H}' "
                f"width='{SPARK_W}' height='{SPARK_H}'></svg>")
    inner_w = SPARK_W - 2 * SPARK_PAD
    inner_h = SPARK_H - 2 * SPARK_PAD
    vmin = min(values)
    vmax = max(values)
    if vmax == vmin:
        vmax = vmin + max(abs(vmin) * 0.01, 1e-9)
    n = len(values)

    def xpos(i: int) -> float:
        if n == 1:
            return SPARK_PAD + inner_w / 2
        return SPARK_PAD + inner_w * (i / (n - 1))

    def ypos(v: float) -> float:
        # Y is inverted: high values plot near top.
        frac = (v - vmin) / (vmax - vmin)
        return SPARK_PAD + inner_h - inner_h * frac

    pts = " ".join(f"{xpos(i):.2f},{ypos(values[i]):.2f}"
                   for i in range(n))
    last_x = xpos(n - 1)
    last_y = ypos(values[-1])
    max_idx = max(range(n), key=lambda i: values[i])
    min_idx = min(range(n), key=lambda i: values[i])
    max_marker = (f"<circle cx='{xpos(max_idx):.2f}' "
                  f"cy='{ypos(values[max_idx]):.2f}' "
                  f"r='1.1' fill='#c12d2d'/>")
    min_marker = (f"<circle cx='{xpos(min_idx):.2f}' "
                  f"cy='{ypos(values[min_idx]):.2f}' "
                  f"r='1.1' fill='#3a8a3a'/>")
    last_marker = (f"<circle cx='{last_x:.2f}' cy='{last_y:.2f}' "
                   f"r='1.4' fill='#0a58ca'/>")
    polyline = (f"<polyline fill='none' stroke='#0a58ca' "
                f"stroke-width='0.9' stroke-linejoin='round' "
                f"stroke-linecap='round' points='{pts}'/>")
    return (f"<svg class='spark' viewBox='0 0 {SPARK_W} {SPARK_H}' "
            f"width='{SPARK_W}' height='{SPARK_H}' "
            f"preserveAspectRatio='none'>"
            f"{polyline}{max_marker}{min_marker}{last_marker}"
            f"</svg>")


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.3f}%"


def fmt_ssim(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:.4f}"


def verdict_class(verdict: str) -> str:
    return {
        "PASS-EXCELLENT": "b-pass-excellent",
        "PASS": "b-pass",
        "FAIL": "b-fail",
    }.get(verdict, "b-skip")


def render(by_name: dict[str, list[dict]]) -> str:
    cards: list[tuple[float, str, str]] = []
    n_runs_total: set[str] = set()
    for nm, rs in by_name.items():
        recent = rs[-MAX_RUNS:]
        ratios = [r.get("pixel_diff_ratio") for r in recent]
        ratios = [v for v in ratios if isinstance(v, (int, float))]
        for r in rs:
            ts = r.get("timestamp")
            if ts:
                n_runs_total.add(ts)
        latest = rs[-1] if rs else {}
        latest_ratio = (latest.get("pixel_diff_ratio")
                        if isinstance(latest.get("pixel_diff_ratio"),
                                      (int, float)) else None)
        latest_ssim = (latest.get("ssim")
                       if isinstance(latest.get("ssim"),
                                     (int, float)) else None)
        latest_ae = latest.get("ae")
        verdict = latest.get("verdict") or "SKIP"
        v_cls = verdict_class(verdict)
        # Sort key: descending diff_ratio (None sorts last).
        sort_key = latest_ratio if latest_ratio is not None else -1.0

        svg = sparkline_svg(ratios) if ratios else (
            "<svg class='spark' viewBox='0 0 "
            f"{SPARK_W} {SPARK_H}' width='{SPARK_W}' "
            f"height='{SPARK_H}'></svg>")
        tooltip = (
            f"{nm}\nlatest AE: {latest_ae if latest_ae is not None else 'n/a'}"
            f"\nlatest diff: {fmt_pct(latest_ratio)}"
            f"\nlatest SSIM: {fmt_ssim(latest_ssim)}"
            f"\nruns shown: {len(ratios)}"
        )
        nm_esc = html_mod.escape(nm)
        tooltip_esc = html_mod.escape(tooltip)
        n_runs = len(ratios)
        ratio_pct = fmt_pct(latest_ratio)
        ssim_str = fmt_ssim(latest_ssim)
        verdict_esc = html_mod.escape(verdict)
        href = f"snippet_history.html#snippet={nm_esc}"
        card = (
            f"<a class='card' href='{href}' title='{tooltip_esc}'>"
            f"<div class='card-head'>"
            f"<span class='nm'>{nm_esc}</span>"
            f"<span class='badge {v_cls}'>{verdict_esc}</span>"
            f"</div>"
            f"<div class='spark-wrap'>{svg}</div>"
            f"<div class='card-foot'>"
            f"<span class='ratio'>{ratio_pct}</span>"
            f"<span class='sep'>&middot;</span>"
            f"<span class='ssim'>SSIM {ssim_str}</span>"
            f"<span class='sep'>&middot;</span>"
            f"<span class='nruns'>{n_runs} run{'s' if n_runs != 1 else ''}</span>"
            f"</div>"
            f"</a>"
        )
        cards.append((sort_key, nm, card))
    # Sort descending diff_ratio; secondary by name ascending for
    # determinism.
    cards.sort(key=lambda t: (-t[0], t[1]))

    n_snip = len(by_name)
    n_runs = len(n_runs_total)
    body_cards = "\n".join(c for _, _, c in cards)

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>mdlout snippet sparklines</title>
<style>
:root {{ color-scheme: light; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
       Helvetica, Arial, sans-serif; margin: 1.2rem; color: #1c1c1c; }}
h1 {{ margin: 0 0 0.3rem 0; font-size: 1.15rem; }}
.muted {{ color: #666; font-size: 0.85rem; margin: 0 0 0.8rem 0; }}
.muted a {{ color: #0a58ca; text-decoration: none; }}
.muted a:hover {{ text-decoration: underline; }}
.toolbar {{ display: flex; gap: 0.6rem; align-items: center;
           margin: 0 0 0.7rem 0; flex-wrap: wrap; font-size: 0.85rem; }}
.toolbar input[type="text"] {{ flex: 0 0 200px; padding: 0.25rem 0.4rem;
                              font-size: 0.85rem; }}
.toolbar label {{ display: inline-flex; align-items: center; gap: 0.25rem;
                 cursor: pointer; }}
.toolbar select {{ font-size: 0.85rem; padding: 0.2rem; }}
.grid {{ display: grid; gap: 0.55rem;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); }}
.card {{ background: #fff; border: 1px solid #ddd; border-radius: 4px;
        padding: 0.45rem 0.55rem; text-decoration: none; color: inherit;
        display: flex; flex-direction: column; gap: 0.25rem; }}
.card:hover {{ background: #f5f8ff; border-color: #b9c8ee; }}
.card-head {{ display: flex; justify-content: space-between;
             align-items: center; gap: 0.3rem; min-width: 0; }}
.card-head .nm {{ font-size: 0.78rem; font-weight: 600;
                 white-space: nowrap; overflow: hidden;
                 text-overflow: ellipsis; min-width: 0; }}
.spark-wrap {{ display: block; line-height: 0; }}
.spark {{ display: block; width: 100%; height: 20px; }}
.card-foot {{ font-size: 0.7rem; color: #555;
             font-variant-numeric: tabular-nums;
             display: flex; gap: 0.25rem; flex-wrap: wrap;
             align-items: center; }}
.card-foot .sep {{ color: #bbb; }}
.badge {{ display: inline-block; padding: 0.02rem 0.3rem;
         border-radius: 0.35rem; font-weight: 600; font-size: 0.62rem;
         line-height: 1.1; flex: 0 0 auto; }}
.b-pass-excellent {{ background: #bff0c8; color: #054d18; }}
.b-pass {{ background: #d6f5dc; color: #0e6620; }}
.b-fail {{ background: #f8d6d6; color: #8a1212; }}
.b-skip {{ background: #eaeaea; color: #555; }}
.card.hidden {{ display: none; }}
</style></head><body>
<h1>mdlout snippet sparklines</h1>
<p class='muted'>{n_snip} snippet(s) across {n_runs} run(s).
Sparklines plot AE pixel_diff_ratio over the most recent
{MAX_RUNS} runs (Y: min=bottom, max=top). Red dot = worst run, green
dot = best run, blue dot = latest. Click a card for the full per-snippet
trend at <a href='snippet_history.html'>snippet_history.html</a>.</p>
<div class='toolbar'>
  <input type='text' id='filter' placeholder='Filter snippets...'>
  <label><input type='checkbox' id='only-graphics'> graphics-heavy only</label>
  <label>Sort:
    <select id='sort'>
      <option value='ratio-desc'>worst diff_ratio first</option>
      <option value='ratio-asc'>best diff_ratio first</option>
      <option value='name'>alphabetical</option>
    </select>
  </label>
</div>
<div class='grid' id='grid'>
{body_cards}
</div>
<script id='spark-meta' type='application/json'>{json.dumps(_build_meta(by_name))}</script>
<script>
(function() {{
  var meta = JSON.parse(document.getElementById('spark-meta').textContent);
  var grid = document.getElementById('grid');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
  var filterEl = document.getElementById('filter');
  var graphicsEl = document.getElementById('only-graphics');
  var sortEl = document.getElementById('sort');

  function apply() {{
    var q = filterEl.value.toLowerCase();
    var gOnly = graphicsEl.checked;
    cards.forEach(function(c) {{
      var nm = (c.getAttribute('href') || '').split('#snippet=')[1] || '';
      nm = decodeURIComponent(nm);
      var m = meta[nm] || {{}};
      var show = nm.toLowerCase().indexOf(q) >= 0;
      if (gOnly && !m.graphics_heavy) show = false;
      c.classList.toggle('hidden', !show);
    }});
    sortCards();
  }}

  function sortCards() {{
    var mode = sortEl.value;
    var visible = cards.filter(function(c) {{
      return !c.classList.contains('hidden');
    }});
    visible.sort(function(a, b) {{
      var na = decodeURIComponent((a.getAttribute('href')||'')
        .split('#snippet=')[1] || '');
      var nb = decodeURIComponent((b.getAttribute('href')||'')
        .split('#snippet=')[1] || '');
      var ma = meta[na] || {{}}, mb = meta[nb] || {{}};
      if (mode === 'name') return na.localeCompare(nb);
      var ra = (typeof ma.ratio === 'number') ? ma.ratio : -1;
      var rb = (typeof mb.ratio === 'number') ? mb.ratio : -1;
      if (mode === 'ratio-asc') return ra - rb;
      return rb - ra;
    }});
    visible.forEach(function(c) {{ grid.appendChild(c); }});
  }}

  filterEl.addEventListener('input', apply);
  graphicsEl.addEventListener('change', apply);
  sortEl.addEventListener('change', sortCards);
}})();
</script>
</body></html>
"""


def _build_meta(by_name: dict[str, list[dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for nm, rs in by_name.items():
        latest = rs[-1] if rs else {}
        out[nm] = {
            "ratio": (latest.get("pixel_diff_ratio")
                      if isinstance(latest.get("pixel_diff_ratio"),
                                    (int, float)) else None),
            "ssim": (latest.get("ssim")
                     if isinstance(latest.get("ssim"), (int, float))
                     else None),
            "graphics_heavy": bool(latest.get("graphics_heavy")),
        }
    return out


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    jsonl = script_dir / "snippet_history.jsonl"
    out = script_dir / "snippet_history_sparklines.html"
    by_name = load_records(jsonl)
    if not by_name:
        out.write_text(
            "<!doctype html><meta charset='utf-8'><title>no data</title>"
            "<p>No snippet history yet. Run <code>tests/run_all.sh</code>"
            " and <code>python3 tests/history.py</code>.</p>",
            encoding="utf-8",
        )
        print(f"sparklines: no data in {jsonl.name}")
        return 0
    out.write_text(render(by_name), encoding="utf-8")
    print(f"sparklines: rendered {len(by_name)} sparkline(s) -> {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
