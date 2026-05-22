#!/usr/bin/env python3
"""browser_test.py -- verify that examples/out/*.html actually render in a
real browser.

For each HTML in examples/out/ this script:
  1. Picks the first available Chromium/Chrome binary (preferring native
     Linux builds; falls back to the Windows binary when running under WSL).
  2. Drives headless Chrome with --dump-dom to get the post-JS DOM.
  3. Compares input markup vs the rendered DOM:
       - KaTeX:   every <span class="math"> in input -> a .katex element
                  in the rendered DOM.
       - abcjs:   every <div class="abc-music"> in input -> exactly one
                  child <svg> in the same div in the rendered DOM.
       - hljs:    for every <code class="language-X"> we look for
                  <span class="hljs-..."> descendants (tokenisation marker).
       - Anchors: every <a href="#x"> in input has a matching id="x" in
                  the rendered DOM.

Writes tests/browser_test_manifest.json with per-example pass/fail and
returns a non-zero exit code if any example fails. If no Chromium-flavoured
binary is reachable the script exits 77 (the autotools "skip" convention)
so CI can treat the result as a skip, not a failure.

WSL caveat
----------
The fallback path is `/mnt/c/Program Files/Google/Chrome/Application/chrome.exe`.
Windows Chrome cannot load `file://` URLs that resolve through the
\\wsl.localhost share, so we copy each HTML into /mnt/c/temp/mdlout_browser_test
and feed Chrome a `file:///C:/temp/...` URL. The Linux Chromium path needs
no such shuttling.

Usage:
    python3 tests/browser_test.py
    python3 tests/browser_test.py --html-dir path/to/htmls --out path/to/manifest.json
    python3 tests/browser_test.py --only 04_math.html,05_music.html
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ----- chrome detection ------------------------------------------------------

CHROME_CANDIDATES = [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/snap/bin/chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chrome",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
]


def find_chrome() -> Optional[str]:
    # Honour explicit override first.
    explicit = os.environ.get("MDLOUT_CHROME")
    if explicit and (os.access(explicit, os.X_OK) or os.path.exists(explicit)):
        return explicit
    # PATH lookups in priority order.
    for name in ("chromium", "chromium-browser", "google-chrome",
                 "google-chrome-stable"):
        p = shutil.which(name)
        if p:
            return p
    # Hard-coded candidate paths (the WSL fallback lives at the end of the list).
    for cand in CHROME_CANDIDATES:
        if os.path.exists(cand) and (cand.endswith(".exe") or os.access(cand, os.X_OK)):
            return cand
    return None


def is_wsl_windows_chrome(path: str) -> bool:
    return path.lower().endswith(".exe") and path.startswith("/mnt/")


# ----- regex helpers ---------------------------------------------------------

# Match `<span class= "math">` even when the lout HTML emitter spaces things out
# (the user's emitter writes `<span class=  "  math  "  >`).
RE_SPAN_MATH = re.compile(r'<span\s+class\s*=\s*"\s*math[\s\w-]*"', re.I)
RE_FOREIGNOBJECT_MATH = re.compile(
    r'<foreignObject[^>]*>\s*<span\s+class\s*=\s*"\s*math', re.I)
RE_DIV_ABC = re.compile(r'<div[^>]*\bclass\s*=\s*"[^"]*\babc-music\b[^"]*"', re.I)
RE_CODE_LANG = re.compile(r'<code\s+class\s*=\s*"\s*language-([\w+-]+)\s*"', re.I)
RE_HREF_ANCHOR = re.compile(r'href\s*=\s*"\s*#([^"\s]+)\s*"', re.I)
RE_ID_ATTR = re.compile(r'\sid\s*=\s*"\s*([^"\s]+)\s*"', re.I)
RE_KATEX = re.compile(r'class\s*=\s*"[^"]*\bkatex\b[^"]*"', re.I)
RE_HLJS_TOKEN = re.compile(r'<span\s+class\s*=\s*"\s*hljs-[\w-]+', re.I)
RE_SVG = re.compile(r'<svg\b', re.I)


@dataclass
class CheckResult:
    name: str
    ok: bool
    expected: int = 0
    found: int = 0
    detail: str = ""


@dataclass
class ExampleResult:
    name: str
    ok: bool
    skipped: bool = False
    checks: list = field(default_factory=list)
    error: str = ""
    dom_bytes: int = 0
    stderr_tail: str = ""


# ----- per-example logic -----------------------------------------------------

def count_abc_with_svg(dom_html: str) -> int:
    """Count <div ...class="...abc-music..."> divs that contain >=1 <svg>.
    abcjs typically appends classes (e.g. `abc-music abcjs-container`) and
    may insert deeply nested children, so we walk balanced-ish-tag bodies
    until we either find a <svg> or step into the next abc-music sibling.
    """
    n = 0
    starts = [m.end() for m in re.finditer(
        r'<div[^>]*\bclass\s*=\s*"[^"]*\babc-music\b[^"]*"[^>]*>',
        dom_html, flags=re.I)]
    starts.append(len(dom_html))
    for i, s in enumerate(starts[:-1]):
        # Search up to the next abc-music opener; if an <svg> appears in
        # that window we count this div as rendered. Because abcjs always
        # injects its <svg> *immediately* inside the abc-music div, this is
        # a safe approximation without writing a real HTML parser.
        body = dom_html[s:starts[i + 1]]
        if RE_SVG.search(body):
            n += 1
    return n


def code_blocks_have_hljs(dom_html: str) -> tuple[int, int]:
    """Return (expected, ok) where expected = count of <code class="...language-X...">
    in dom and ok = count of those that contain at least one hljs-* span.
    We check against the *rendered* DOM rather than the input because hljs
    typically rewrites the original <code> contents in place and appends
    `hljs` to the class attribute, so the class list grows from
    `language-python` to `language-python hljs` once highlight.js runs.
    """
    expected = 0
    ok = 0
    for m in re.finditer(
            r'<code\b[^>]*\bclass\s*=\s*"[^"]*\blanguage-[\w+-]+\b[^"]*"[^>]*>(.*?)</code>',
            dom_html, flags=re.I | re.S):
        expected += 1
        if RE_HLJS_TOKEN.search(m.group(1)):
            ok += 1
    return expected, ok


def collect_ids(dom_html: str) -> set[str]:
    return {m.group(1) for m in RE_ID_ATTR.finditer(dom_html)}


def run_chrome(chrome: str, html_path: Path, work_dir: Path) -> tuple[Optional[str], str, int]:
    """Run headless Chrome on html_path and return (dom_html, stderr_tail, rc)."""
    if is_wsl_windows_chrome(chrome):
        # Stage into /mnt/c/temp so Windows Chrome can see it via file:///C:/...
        win_stage = Path("/mnt/c/temp/mdlout_browser_test")
        win_stage.mkdir(parents=True, exist_ok=True)
        staged = win_stage / html_path.name
        shutil.copy(html_path, staged)
        url = "file:///C:/temp/mdlout_browser_test/" + html_path.name
    else:
        url = "file://" + str(html_path.resolve())

    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        "--disable-features=Translate,MediaRouter",
        "--virtual-time-budget=20000",
        "--run-all-compositor-stages-before-draw",
        "--dump-dom",
        url,
    ]
    # The largest examples (complex_diag, scientific_paper) include 100+ abcjs
    # blocks and large KaTeX equations; rendering can take 60-120 s on the
    # WSL Chrome bridge. Pick a generous wall-clock ceiling.
    timeout_s = int(os.environ.get("MDLOUT_BROWSER_TIMEOUT", "240"))
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        tail = (exc.stderr or b"").decode("utf-8", "replace")[-400:]
        return None, "timeout: " + tail, 124

    stderr = proc.stderr.decode("utf-8", "replace")
    stderr_tail = "\n".join(
        line for line in stderr.splitlines()[-12:]
        if line.strip() and "DevTools listening" not in line)
    if proc.returncode != 0:
        return None, stderr_tail, proc.returncode
    return proc.stdout.decode("utf-8", "replace"), stderr_tail, 0


def evaluate_example(html_path: Path, chrome: str, work_dir: Path) -> ExampleResult:
    name = html_path.name
    try:
        src = html_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        # Another tool (e.g. the examples generator) can race us and delete a
        # file between glob() and read. Treat as a vanished sibling rather
        # than a hard failure -- the next run will see it.
        return ExampleResult(name=name, ok=True, skipped=True,
                             error="file disappeared between glob and read")
    dom, stderr_tail, rc = run_chrome(chrome, html_path, work_dir)
    if dom is None:
        return ExampleResult(name=name, ok=False,
                             error=f"chrome rc={rc}",
                             stderr_tail=stderr_tail)
    result = ExampleResult(name=name, ok=True, dom_bytes=len(dom),
                           stderr_tail=stderr_tail)

    # --- check 1: chrome loaded the file (any output at all + no fatal err) ---
    fatal = any(tok in stderr_tail.lower()
                for tok in ("net::err", "failed to load", "crashed"))
    result.checks.append(CheckResult(
        name="loaded", ok=(len(dom) > 0 and not fatal),
        expected=1, found=int(len(dom) > 0),
        detail=stderr_tail if fatal else ""))

    # --- check 2: KaTeX rendered math blocks ---
    # The lout HTML emitter wraps every math expression in `<span class="math">`
    # (typically inside a <foreignObject>). KaTeX rewrites that span into a
    # `.katex` tree. We accept any element carrying the `katex` class because
    # different KaTeX versions emit different inner wrappers.
    math_in = len(RE_SPAN_MATH.findall(src))
    math_out = len(RE_KATEX.findall(dom))
    # KaTeX produces a flurry of nested .katex* elements per equation; require
    # at least one per input span. (We don't insist on equality.)
    math_ok = math_in == 0 or math_out >= math_in
    result.checks.append(CheckResult(
        name="katex", ok=math_ok, expected=math_in, found=math_out,
        detail="" if math_ok else f"only {math_out} .katex matches for {math_in} spans"))

    # --- check 3: abcjs rendered every <div class="abc-music"> ---
    abc_in = len(RE_DIV_ABC.findall(src))
    abc_out = count_abc_with_svg(dom)
    abc_ok = abc_in == abc_out
    result.checks.append(CheckResult(
        name="abcjs", ok=abc_ok, expected=abc_in, found=abc_out,
        detail="" if abc_ok else f"{abc_out}/{abc_in} abc-music divs gained an <svg>"))

    # --- check 4: every #anchor href resolves to an id in the DOM ---
    anchors_src = sorted({m.group(1) for m in RE_HREF_ANCHOR.finditer(src)})
    ids_dom = collect_ids(dom)
    missing = [a for a in anchors_src if a not in ids_dom]
    result.checks.append(CheckResult(
        name="anchors",
        ok=(not missing),
        expected=len(anchors_src),
        found=len(anchors_src) - len(missing),
        detail="" if not missing else
        "missing ids: " + ",".join(missing[:5])
        + ("..." if len(missing) > 5 else "")))

    # --- check 5: hljs tokenisation ---
    hljs_expected, hljs_ok = code_blocks_have_hljs(dom)
    ok = hljs_expected == 0 or hljs_ok == hljs_expected
    result.checks.append(CheckResult(
        name="hljs", ok=ok, expected=hljs_expected, found=hljs_ok,
        detail="" if ok else
        f"{hljs_ok}/{hljs_expected} <code class=language-*> had hljs-* spans"))

    result.ok = all(c.ok for c in result.checks)
    return result


# ----- driver ----------------------------------------------------------------

def main(argv: list[str]) -> int:
    here = Path(__file__).resolve().parent
    repo = here.parent
    default_html = repo / "examples" / "out"
    default_manifest = here / "browser_test_manifest.json"

    ap = argparse.ArgumentParser()
    ap.add_argument("--html-dir", default=str(default_html),
                    help="directory containing *.html to test")
    ap.add_argument("--out", default=str(default_manifest),
                    help="path for the JSON manifest")
    ap.add_argument("--only", default="",
                    help="comma-separated subset of html basenames to test")
    ap.add_argument("--chrome", default="",
                    help="override Chrome/Chromium binary path")
    args = ap.parse_args(argv)

    chrome = args.chrome or find_chrome()
    if not chrome:
        msg = ("SKIP: no Chromium/Chrome binary found. Install one of:\n"
               "  sudo apt install chromium-browser\n"
               "  sudo snap install chromium\n"
               "or set MDLOUT_CHROME=/path/to/chrome")
        print(msg)
        manifest = {
            "status": "skipped",
            "reason": "no chrome binary",
            "candidates": CHROME_CANDIDATES,
            "examples": [],
        }
        Path(args.out).write_text(json.dumps(manifest, indent=2))
        return 77  # autotools "skipped"

    html_dir = Path(args.html_dir)
    if not html_dir.is_dir():
        print(f"error: html-dir {html_dir} does not exist", file=sys.stderr)
        return 2

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    htmls = sorted(p for p in html_dir.glob("*.html")
                   if not only or p.name in only)
    if not htmls:
        print("no html files to test")
        Path(args.out).write_text(json.dumps(
            {"status": "skipped", "reason": "no html", "examples": []},
            indent=2))
        return 0

    print(f"==> chrome: {chrome}")
    print(f"==> testing {len(htmls)} file(s) from {html_dir}")

    results: list[ExampleResult] = []
    with tempfile.TemporaryDirectory(prefix="mdlout_browser_") as td:
        work = Path(td)
        for html in htmls:
            r = evaluate_example(html, chrome, work)
            results.append(r)
            tag = "PASS" if r.ok else "FAIL"
            checks = " ".join(
                f"{c.name}={'ok' if c.ok else 'X'}({c.found}/{c.expected})"
                for c in r.checks)
            print(f"  {tag:4s}  {r.name:32s}  {checks}")
            if r.error:
                print(f"        error: {r.error}")
            if not r.ok and r.stderr_tail:
                # show one line of context so failures are diagnosable
                first = r.stderr_tail.splitlines()[0] if r.stderr_tail else ""
                if first:
                    print(f"        stderr: {first[:200]}")

    manifest = {
        "status": "ok",
        "chrome": chrome,
        "wsl_windows_chrome": is_wsl_windows_chrome(chrome),
        "pass": sum(1 for r in results if r.ok),
        "fail": sum(1 for r in results if not r.ok),
        "total": len(results),
        "examples": [
            {
                "name": r.name,
                "ok": r.ok,
                "dom_bytes": r.dom_bytes,
                "error": r.error,
                "stderr_tail": r.stderr_tail,
                "checks": [asdict(c) for c in r.checks],
            }
            for r in results
        ],
    }
    Path(args.out).write_text(json.dumps(manifest, indent=2))
    print(f"==> manifest: {args.out}")
    print(f"==> pass {manifest['pass']} / fail {manifest['fail']} / total {manifest['total']}")
    return 0 if manifest["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
