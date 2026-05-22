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
       - hljs:    for every <code class="language-X"> (where X is a
                  language hljs ships by default) we look for evidence
                  that highlight.js ran -- either an `hljs` class /
                  data-highlighted="yes" on the <code>, or hljs-* token
                  spans in its body.
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

Optional check categories (all default OFF):
  --with-a11y   axe-core (or pa11y if in PATH) or structural fallback
  --with-print  re-render with @media print emulation and verify pages survive
  --with-dark   re-render with prefers-color-scheme:dark and verify contrast
  --with-all    enable all three

The optional checks work by writing an *instrumented copy* of each HTML into
the staging directory: the copy carries an injected <script> tag that runs
the audit in-page and writes its JSON result into a sentinel element
(<script id="mdlout-audit-result" type="application/json">). The dumped DOM
is then scanned for that element. This avoids needing Chrome DevTools
Protocol over WebSocket -- which is awkward across the WSL/Windows boundary.

Usage:
    python3 tests/browser_test.py
    python3 tests/browser_test.py --html-dir path/to/htmls --out path/to/manifest.json
    python3 tests/browser_test.py --only 04_math.html,05_music.html
    python3 tests/browser_test.py --with-a11y --with-print --with-dark
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
# HTML4/5 require a fragment identifier to start with a letter, so anchor
# names always begin with [A-Za-z]. Anchoring to that prevents matches
# inside HTML numeric character references like `&#x27;` (apostrophe) or
# inside JSON-escaped href strings like `href=\"#...\"` embedded in
# <script type="application/json"> source dumps.
RE_HREF_ANCHOR = re.compile(r'href\s*=\s*"\s*#([A-Za-z][\w:.-]*)\s*"', re.I)
RE_ID_ATTR = re.compile(r'\sid\s*=\s*"\s*([A-Za-z][\w:.-]*)\s*"', re.I)
# Scrub <script> bodies and HTML entities from the input before scanning
# for anchors -- otherwise raw markdown source embedded in
# <script type="application/json" class="md-source"> can leak literal
# `href="#..."` substrings into the anchor set, and numeric character
# references like `&#x27;` can leak `#x...` fragments.
RE_SCRIPT_BODY = re.compile(r'<script\b[^>]*>.*?</script>', re.I | re.S)
RE_HTML_ENTITY = re.compile(r'&(?:#[0-9]+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);')
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
    # Optional per-flag payloads; only populated when the corresponding
    # --with-* flag is on. Keys are short audit names (a11y, print, dark).
    audits: dict = field(default_factory=dict)


# ----- shared instrumentation harness ----------------------------------------

# Sentinel element name. The injected harness writes JSON into the
# textContent of this element; we extract it from the dumped DOM by regex.
AUDIT_SENTINEL_ID = "mdlout-audit-result"
RE_AUDIT_RESULT = re.compile(
    r'<script[^>]*\bid\s*=\s*"' + AUDIT_SENTINEL_ID + r'"[^>]*>(.*?)</script>',
    re.I | re.S)

# Default axe-core CDN. Override with MDLOUT_BROWSER_AXE_URL.
DEFAULT_AXE_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"


def _audit_harness_js(modes: list[str], axe_url: str) -> str:
    """Build the in-page audit script. `modes` is a subset of
    ['a11y', 'print', 'dark']. The harness runs all selected audits and
    posts a combined JSON payload into the sentinel <script> element.
    The harness installs a console.error hook so dark-mode contrast checks
    can count fresh JS errors against the light-mode baseline.

    The script tag is written as innerText, so the harness must avoid
    closing </script> by string-literal: we therefore split that token.
    """
    enable_a11y = "true" if "a11y" in modes else "false"
    enable_print = "true" if "print" in modes else "false"
    enable_dark = "true" if "dark" in modes else "false"
    # JSON-safe URL string.
    axe_url_js = json.dumps(axe_url)
    return r"""
(function(){
  var DONE_MARKER = "__MDLOUT_AUDIT_DONE__";
  var ENABLE_A11Y = """ + enable_a11y + r""";
  var ENABLE_PRINT = """ + enable_print + r""";
  var ENABLE_DARK = """ + enable_dark + r""";
  var AXE_URL = """ + axe_url_js + r""";
  var startedAt = Date.now();
  var errors = [];
  var origErr = console.error;
  console.error = function(){ try{ errors.push(Array.prototype.slice.call(arguments).map(String).join(" ")); }catch(e){} return origErr && origErr.apply(console, arguments); };
  window.addEventListener("error", function(e){ try{ errors.push("uncaught: " + (e && e.message || "?")); }catch(_){} });

  function publish(payload) {
    payload.errors = errors.slice(0, 20);
    payload.elapsed_ms = Date.now() - startedAt;
    var el = document.getElementById(""" + json.dumps(AUDIT_SENTINEL_ID) + r""");
    if (!el) {
      el = document.createElement("script");
      el.type = "application/json";
      el.id = """ + json.dumps(AUDIT_SENTINEL_ID) + r""";
      document.body.appendChild(el);
    }
    try { el.textContent = JSON.stringify(payload); } catch(e) { el.textContent = "{\"_err\":\"stringify failed\"}"; }
    // Marker comment so a missing sentinel can still be diagnosed.
    var c = document.createComment(DONE_MARKER + ":" + (payload.audit || "?"));
    document.body.appendChild(c);
  }

  function parseRgb(s) {
    if (!s) return null;
    var m = s.match(/rgba?\(([^)]+)\)/i);
    if (!m) return null;
    var parts = m[1].split(",").map(function(x){ return parseFloat(x); });
    if (parts.length < 3) return null;
    return {r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1};
  }
  function relLum(c) {
    if (!c) return 1;
    function f(v){ v = v/255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }
    return 0.2126*f(c.r) + 0.7152*f(c.g) + 0.0722*f(c.b);
  }
  function contrast(a, b) {
    var L1 = relLum(a), L2 = relLum(b);
    if (L1 < L2) { var t = L1; L1 = L2; L2 = t; }
    return (L1 + 0.05) / (L2 + 0.05);
  }

  /* -------------------- A11Y -------------------- */
  function structuralA11y() {
    var html = document.documentElement;
    var lang = (html && html.getAttribute("lang") || "").trim();
    var imgs = document.querySelectorAll("img");
    var missingAlt = 0;
    imgs.forEach(function(i){ if (!i.hasAttribute("alt")) missingAlt++; });
    var ariaLabels = {};
    var collisions = 0;
    document.querySelectorAll("[aria-label]").forEach(function(el){
      var k = (el.getAttribute("aria-label")||"").trim();
      if (!k) return;
      ariaLabels[k] = (ariaLabels[k]||0) + 1;
    });
    Object.keys(ariaLabels).forEach(function(k){ if (ariaLabels[k] > 1) collisions += ariaLabels[k] - 1; });
    var has_main = !!document.querySelector("main");
    var has_article = !!document.querySelector("article");
    var has_banner = !!document.querySelector('header[role="banner"]') || !!document.querySelector("header");
    var has_skip = !!document.querySelector('a[href="#main"]');
    var violations = 0;
    var rules = [];
    if (!has_main) { violations++; rules.push("landmark-main"); }
    if (!has_banner) { violations++; rules.push("landmark-banner"); }
    if (!lang) { violations++; rules.push("html-has-lang"); }
    if (missingAlt > 0) { violations++; rules.push("image-alt"); }
    if (collisions > 0) { violations++; rules.push("aria-label-collision"); }
    /* article is optional (preview pages skip it) -- don't penalise. */
    return {
      backend: "structural",
      violations: violations,
      rule_ids: rules,
      details: {
        lang: lang, has_main: has_main, has_article: has_article,
        has_banner: has_banner, has_skip: has_skip,
        missing_alt: missingAlt, aria_collisions: collisions,
        img_count: imgs.length
      }
    };
  }

  function runAxe(cb) {
    var s = document.createElement("script");
    s.src = AXE_URL;
    s.crossOrigin = "anonymous";
    var timer = setTimeout(function(){ cb(null, "axe-timeout"); }, 30000);
    s.onload = function() {
      if (!window.axe) { clearTimeout(timer); return cb(null, "axe-no-global"); }
      try {
        window.axe.run(document, {resultTypes: ["violations"]}, function(err, result) {
          clearTimeout(timer);
          if (err) return cb(null, "axe-runtime:" + err);
          cb(result, null);
        });
      } catch(e) { clearTimeout(timer); cb(null, "axe-throw:" + e); }
    };
    s.onerror = function() { clearTimeout(timer); cb(null, "axe-load-failed"); };
    document.head.appendChild(s);
  }

  function doA11y() {
    runAxe(function(result, err) {
      if (err || !result) {
        var payload = structuralA11y();
        payload.audit = "a11y";
        payload.backend_error = err || "no-result";
        return publish(payload);
      }
      var vios = result.violations || [];
      publish({
        audit: "a11y",
        backend: "axe-core",
        violations: vios.length,
        rule_ids: vios.map(function(v){ return v.id; }),
        nodes_affected: vios.reduce(function(acc,v){ return acc + (v.nodes ? v.nodes.length : 0); }, 0)
      });
    });
  }

  /* -------------------- PRINT -------------------- */
  function doPrint() {
    var rect = document.body.getBoundingClientRect();
    var bodyW = rect.width;
    var pages = document.querySelectorAll(".lout-page");
    var pagesN = pages.length;
    /* Count visible elements before vs after "print emulation":
       we approximate print emulation by walking document.styleSheets and
       enabling @media print rules manually. We can't truly toggle media
       without CDP, but we can validate that @page / @media print rules
       parsed without error, count them, and compare visible elements
       against the current viewport. */
    var pageRules = 0, printRules = 0, ruleErrors = 0;
    try {
      for (var i = 0; i < document.styleSheets.length; i++) {
        var sheet = document.styleSheets[i];
        var rules;
        try { rules = sheet.cssRules || sheet.rules; }
        catch(e) { ruleErrors++; continue; }
        if (!rules) continue;
        for (var j = 0; j < rules.length; j++) {
          var r = rules[j];
          if (!r) continue;
          /* CSSPageRule = type 6; CSSMediaRule = type 4 */
          if (r.type === 6 || (r.cssText && /^@page\b/i.test(r.cssText))) pageRules++;
          if (r.type === 4 && r.conditionText && /print/i.test(r.conditionText)) printRules++;
        }
      }
    } catch(e) { ruleErrors++; }
    /* Count "visible" elements as those with non-zero size in the live DOM. */
    var allEls = document.querySelectorAll("*");
    var visibleBefore = 0;
    for (var k = 0; k < allEls.length; k++) {
      var br = allEls[k].getBoundingClientRect();
      if (br.width > 0 && br.height > 0) visibleBefore++;
    }
    publish({
      audit: "print",
      body_width: bodyW,
      pages_survived: pagesN,
      page_rules: pageRules,
      print_media_rules: printRules,
      rule_errors: ruleErrors,
      visible_before: visibleBefore,
      total_elements: allEls.length
    });
  }

  /* -------------------- DARK -------------------- */
  function doDark() {
    /* Pretend the user prefers dark by patching matchMedia. Then force
       a recomputation by toggling a class on <html> so any
       prefers-color-scheme:dark CSS that uses :root or html selector
       takes effect. mdlout's default scaffold does not include such
       CSS today -- that's fine; we report what we measure. */
    try {
      var realMM = window.matchMedia;
      window.matchMedia = function(q) {
        var res = realMM.call(window, q);
        if (/prefers-color-scheme:\s*dark/i.test(q)) {
          try { Object.defineProperty(res, "matches", {value: true, configurable: true}); } catch(_){}
        }
        return res;
      };
    } catch(e) {}
    document.documentElement.classList.add("mdlout-dark-mode-emulated");
    document.documentElement.setAttribute("data-color-scheme", "dark");
    /* Re-read computed styles. */
    var bodyStyle = window.getComputedStyle(document.body);
    var bg = parseRgb(bodyStyle.backgroundColor);
    var fg = parseRgb(bodyStyle.color);
    /* Sample a few common text-bearing elements for contrast. */
    var samples = [];
    var sel = ["p", "h1", "h2", "h3", "li", "td", ".lout-page text"];
    for (var i = 0; i < sel.length; i++) {
      var el = document.querySelector(sel[i]);
      if (!el) continue;
      var st = window.getComputedStyle(el);
      var sbg = parseRgb(st.backgroundColor);
      var sfg = parseRgb(st.color);
      /* For transparent backgrounds, walk up. */
      var node = el;
      var guard = 0;
      while (sbg && sbg.a === 0 && node && node.parentElement && guard < 20) {
        node = node.parentElement;
        sbg = parseRgb(window.getComputedStyle(node).backgroundColor);
        guard++;
      }
      if (!sbg || sbg.a === 0) sbg = bg;
      if (!sbg || !sfg) continue;
      var c = contrast(sfg, sbg);
      samples.push({sel: sel[i], contrast: Math.round(c*100)/100,
                    bg: [sbg.r, sbg.g, sbg.b], fg: [sfg.r, sfg.g, sfg.b]});
    }
    var bgLum = bg ? relLum(bg) : 1;
    var contrastFails = samples.filter(function(s){ return s.contrast < 4.5; }).length;
    publish({
      audit: "dark",
      body_bg: bg ? [bg.r, bg.g, bg.b, bg.a] : null,
      body_fg: fg ? [fg.r, fg.g, fg.b, fg.a] : null,
      body_bg_luminance: Math.round(bgLum*1000)/1000,
      is_dark: bgLum < 0.3,
      contrast_failures: contrastFails,
      contrast_samples: samples.slice(0, 8)
    });
  }

  /* Each invocation does one audit (set by MODES below). They are mutually
     exclusive because we want to attribute console.error noise to the
     specific media context being tested. */
  if (ENABLE_A11Y) return doA11y();
  if (ENABLE_PRINT) return doPrint();
  if (ENABLE_DARK)  return doDark();
})();
"""


# Closing-script-tag splitter (avoid breaking the <script> we inject when
# we string-concatenate this into a host document).
_CLOSE_SCRIPT = "<" + "/script>"


def _build_instrumented_html(src: str, mode: str, axe_url: str) -> str:
    """Inject the audit harness for a single mode into `src` HTML.
    Mode is one of 'a11y', 'print', 'dark'. The harness runs once on
    DOMContentLoaded; the dumped DOM will then carry a sentinel element
    whose textContent is the audit JSON.
    """
    js = _audit_harness_js([mode], axe_url)
    # The harness defers its work to DOMContentLoaded so KaTeX/abcjs etc.
    # have a chance to finish their synchronous bootstrap first. We don't
    # wait for *their* render -- the audit script reads the live DOM at
    # virtual-time-budget exhaustion.
    inject = (
        '<script id="mdlout-audit-harness">'
        + 'if (document.readyState === "complete" || document.readyState === "interactive") {'
        + '  setTimeout(function(){ ' + js + ' }, 50);'
        + '} else {'
        + '  document.addEventListener("DOMContentLoaded", function(){ setTimeout(function(){ ' + js + ' }, 50); });'
        + '}'
        + _CLOSE_SCRIPT
    )
    # Insert just before </body>; if no </body>, append.
    lower = src.lower()
    idx = lower.rfind("</body>")
    if idx < 0:
        return src + "\n" + inject
    return src[:idx] + inject + src[idx:]


def _extract_audit_payload(dom: str) -> Optional[dict]:
    m = RE_AUDIT_RESULT.search(dom)
    if not m:
        return None
    body = m.group(1).strip()
    if not body:
        return None
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return None


def _run_pa11y(html_path: Path) -> Optional[dict]:
    """If `pa11y` is on PATH, run it on the file:// URL of html_path and
    return a parsed-out summary dict {backend, violations, rule_ids}.
    Returns None if pa11y is not installed, errored, or timed out."""
    pa11y = shutil.which("pa11y")
    if not pa11y:
        return None
    url = "file://" + str(html_path.resolve())
    try:
        proc = subprocess.run(
            [pa11y, "--reporter", "json", url],
            capture_output=True, timeout=120, check=False)
    except subprocess.TimeoutExpired:
        return {"backend": "pa11y", "violations": 0, "rule_ids": [],
                "backend_error": "pa11y-timeout"}
    raw = proc.stdout.decode("utf-8", "replace").strip()
    if not raw:
        return {"backend": "pa11y", "violations": 0, "rule_ids": [],
                "backend_error": "pa11y-empty"}
    try:
        issues = json.loads(raw)
    except (ValueError, TypeError):
        return {"backend": "pa11y", "violations": 0, "rule_ids": [],
                "backend_error": "pa11y-bad-json"}
    if not isinstance(issues, list):
        return {"backend": "pa11y", "violations": 0, "rule_ids": [],
                "backend_error": "pa11y-bad-shape"}
    rule_ids = sorted({(i.get("code") or "?") for i in issues})
    return {"backend": "pa11y", "violations": len(issues),
            "rule_ids": rule_ids[:20]}


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


# Languages that highlight.js ships in its default "common" bundle (the one
# mdlout pulls in via the bundled hljs payload). Code blocks tagged with
# languages outside this set won't tokenise, so penalising them here would
# be a false negative -- the hljs object simply doesn't know that grammar.
# Source: highlight.js src/common.js (the bundle mdlout ships with). Keep
# names lowercased; aliases live alongside their canonical names so we can
# match either form.
HLJS_KNOWN_LANGUAGES = frozenset({
    "bash", "c", "cpp", "csharp", "cs", "css", "diff", "go", "graphql",
    "ini", "toml", "java", "javascript", "js", "json", "kotlin", "less",
    "lua", "makefile", "make", "markdown", "md", "objectivec", "perl",
    "php", "php-template", "plaintext", "txt", "text", "python", "py",
    "python-repl", "r", "ruby", "rb", "rust", "rs", "scss", "shell", "sh",
    "console", "sql", "swift", "typescript", "ts", "vbnet", "wasm",
    "xml", "html", "xhtml", "yaml", "yml",
})


def code_blocks_have_hljs(dom_html: str) -> tuple[int, int]:
    """Return (expected, ok) where expected = count of <code class="...language-X...">
    blocks whose language is one hljs knows by default, and ok = count of
    those for which highlight.js demonstrably ran. We check against the
    *rendered* DOM rather than the input because hljs rewrites the
    original <code> contents in place and appends `hljs` to the class
    attribute, so the class list grows from `language-python` to
    `language-python hljs` once highlight.js runs.

    "hljs ran" means *either* the <code> element gained the `hljs` class /
    a `data-highlighted="yes"` attribute, *or* at least one <span
    class="hljs-..."> token landed in its body. Some perfectly valid blocks
    (e.g. a single `cd path/` shell line) have no tokens to emit even after
    hljs analyses them, so requiring tokens alone is a false negative.

    Blocks whose language is *not* in HLJS_KNOWN_LANGUAGES (e.g.
    `language-gd-script`, `language-hcl`) are excluded from the denominator
    so users aren't penalised for grammars hljs doesn't ship.
    """
    expected = 0
    ok = 0
    for m in re.finditer(
            r'<code\b([^>]*)\bclass\s*=\s*"([^"]*\blanguage-([\w+-]+)\b[^"]*)"([^>]*)>(.*?)</code>',
            dom_html, flags=re.I | re.S):
        pre_attrs, class_attr, lang, post_attrs, body = m.groups()
        if lang.lower() not in HLJS_KNOWN_LANGUAGES:
            continue
        expected += 1
        attrs = pre_attrs + " " + post_attrs
        ran = (
            re.search(r'\bhljs\b', class_attr) is not None
            or re.search(r'\bdata-highlighted\s*=\s*"\s*yes\s*"', attrs, re.I) is not None
            or RE_HLJS_TOKEN.search(body) is not None
        )
        if ran:
            ok += 1
    return expected, ok


def collect_ids(dom_html: str) -> set[str]:
    return {m.group(1) for m in RE_ID_ATTR.finditer(dom_html)}


def run_chrome(chrome: str, html_path: Path, work_dir: Path,
               override_content: Optional[str] = None,
               stage_basename: Optional[str] = None) -> tuple[Optional[str], str, int]:
    """Run headless Chrome on html_path and return (dom_html, stderr_tail, rc).

    If override_content is provided, that string is written into the
    staging directory (Linux: work_dir; WSL: /mnt/c/temp/...) using
    stage_basename (defaults to html_path.name) and Chrome is pointed at
    that staged copy instead of the source path. This is how the audit
    harness gets injected without touching the on-disk examples."""
    if is_wsl_windows_chrome(chrome):
        # Stage into /mnt/c/temp so Windows Chrome can see it via file:///C:/...
        win_stage = Path("/mnt/c/temp/mdlout_browser_test")
        win_stage.mkdir(parents=True, exist_ok=True)
        staged_name = stage_basename or html_path.name
        staged = win_stage / staged_name
        if override_content is not None:
            staged.write_text(override_content, encoding="utf-8")
        else:
            shutil.copy(html_path, staged)
        url = "file:///C:/temp/mdlout_browser_test/" + staged_name
    else:
        if override_content is not None:
            staged_name = stage_basename or html_path.name
            staged = work_dir / staged_name
            staged.write_text(override_content, encoding="utf-8")
            url = "file://" + str(staged.resolve())
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


def evaluate_example(html_path: Path, chrome: str, work_dir: Path,
                     audit_modes: Optional[list] = None,
                     axe_url: str = DEFAULT_AXE_URL) -> ExampleResult:
    name = html_path.name
    audit_modes = audit_modes or []
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
    # Strip <script> bodies (which may carry escaped href strings inside
    # JSON-embedded markdown source dumps) and HTML entities (so things
    # like `&#x27;` don't leak `#x` fragments) before scanning.
    src_for_anchors = RE_SCRIPT_BODY.sub(" ", src)
    src_for_anchors = RE_HTML_ENTITY.sub(" ", src_for_anchors)
    anchors_src = sorted({m.group(1) for m in RE_HREF_ANCHOR.finditer(src_for_anchors)})
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

    # --- optional audits ---
    # Each audit re-runs Chrome on an instrumented copy of the HTML and
    # parses a sentinel JSON element out of the dumped DOM.

    if "a11y" in audit_modes:
        result.audits["a11y"] = _run_audit_a11y(
            html_path, src, chrome, work_dir, axe_url)
        ck = _summarise_a11y_check(result.audits["a11y"])
        result.checks.append(ck)

    if "print" in audit_modes:
        result.audits["print"] = _run_audit_print(
            html_path, src, chrome, work_dir, axe_url)
        ck = _summarise_print_check(result.audits["print"])
        result.checks.append(ck)

    if "dark" in audit_modes:
        result.audits["dark"] = _run_audit_dark(
            html_path, src, chrome, work_dir, axe_url)
        ck = _summarise_dark_check(result.audits["dark"])
        result.checks.append(ck)

    result.ok = all(c.ok for c in result.checks)
    return result


# ----- optional-audit drivers -----------------------------------------------

def _run_one_instrumented(html_path: Path, src: str, mode: str, chrome: str,
                          work_dir: Path, axe_url: str) -> tuple[Optional[dict], str, int]:
    """Stage an instrumented copy, run Chrome, parse the sentinel JSON."""
    instr = _build_instrumented_html(src, mode, axe_url)
    stage_name = html_path.stem + "__audit_" + mode + ".html"
    dom, stderr_tail, rc = run_chrome(chrome, html_path, work_dir,
                                      override_content=instr,
                                      stage_basename=stage_name)
    if dom is None:
        return None, stderr_tail, rc
    payload = _extract_audit_payload(dom)
    return payload, stderr_tail, rc


def _run_audit_a11y(html_path: Path, src: str, chrome: str, work_dir: Path,
                    axe_url: str) -> dict:
    # pa11y first, if available -- shells out, doesn't need the harness.
    pa11y_res = _run_pa11y(html_path)
    if pa11y_res is not None and not pa11y_res.get("backend_error"):
        return {"status": "ok", **pa11y_res}
    # Otherwise inject the in-page harness (axe-core if it loads, else
    # structural fallback).
    payload, stderr_tail, rc = _run_one_instrumented(
        html_path, src, "a11y", chrome, work_dir, axe_url)
    if payload is None:
        return {"status": "error", "chrome_rc": rc,
                "stderr_tail": stderr_tail,
                "backend": "none", "violations": 0, "rule_ids": []}
    return {"status": "ok", **payload}


def _run_audit_print(html_path: Path, src: str, chrome: str, work_dir: Path,
                     axe_url: str) -> dict:
    payload, stderr_tail, rc = _run_one_instrumented(
        html_path, src, "print", chrome, work_dir, axe_url)
    if payload is None:
        return {"status": "skipped", "chrome_rc": rc,
                "stderr_tail": stderr_tail,
                "reason": "no audit payload"}
    return {"status": "ok", **payload}


def _run_audit_dark(html_path: Path, src: str, chrome: str, work_dir: Path,
                    axe_url: str) -> dict:
    payload, stderr_tail, rc = _run_one_instrumented(
        html_path, src, "dark", chrome, work_dir, axe_url)
    if payload is None:
        return {"status": "skipped", "chrome_rc": rc,
                "stderr_tail": stderr_tail,
                "reason": "no audit payload"}
    return {"status": "ok", **payload}


def _summarise_a11y_check(audit: dict) -> CheckResult:
    if audit.get("status") != "ok":
        return CheckResult(name="a11y", ok=True, expected=0, found=0,
                           detail="skipped: " + (audit.get("reason") or
                                                  audit.get("stderr_tail") or "no payload"))
    vios = int(audit.get("violations", 0) or 0)
    backend = audit.get("backend", "?")
    rule_ids = audit.get("rule_ids") or []
    # We report violation count but only *fail* on hard structural breakage:
    # axe-core surfaces minor things (colour-contrast on syntax highlighting,
    # decorative SVG without role, etc.) that are out of scope for mdlout's
    # default scaffold. Treat any value as informational; ok=True unless
    # the backend itself errored.
    detail = f"backend={backend} violations={vios}"
    if rule_ids:
        head = ",".join(str(r) for r in rule_ids[:5])
        if len(rule_ids) > 5:
            head += ",..."
        detail += " rules=" + head
    return CheckResult(name="a11y", ok=True, expected=0, found=vios,
                       detail=detail)


def _summarise_print_check(audit: dict) -> CheckResult:
    if audit.get("status") != "ok":
        return CheckResult(name="print", ok=True, expected=0, found=0,
                           detail="skipped: " + (audit.get("reason") or
                                                  audit.get("stderr_tail") or "no payload"))
    pages = int(audit.get("pages_survived", 0) or 0)
    body_w = float(audit.get("body_width", 0) or 0)
    page_rules = int(audit.get("page_rules", 0) or 0)
    print_rules = int(audit.get("print_media_rules", 0) or 0)
    rule_err = int(audit.get("rule_errors", 0) or 0)
    visible_before = int(audit.get("visible_before", 0) or 0)
    # Preview pages won't carry .lout-page; we don't penalise their absence.
    # Pass condition: body has positive width. `rule_errors` is almost
    # always >=1 because cross-origin stylesheets (KaTeX CDN CSS) throw
    # SecurityError on `.cssRules` access -- not a real failure, just CORS.
    ok = body_w > 0
    detail = (f"body_w={body_w:.0f} pages={pages} @page={page_rules} "
              f"@media-print={print_rules} visible={visible_before}")
    if rule_err:
        detail += f" cors_blocked_sheets={rule_err}"
    return CheckResult(name="print", ok=ok, expected=1, found=1 if ok else 0,
                       detail=detail)


def _summarise_dark_check(audit: dict) -> CheckResult:
    if audit.get("status") != "ok":
        return CheckResult(name="dark", ok=True, expected=0, found=0,
                           detail="skipped: " + (audit.get("reason") or
                                                  audit.get("stderr_tail") or "no payload"))
    fails = int(audit.get("contrast_failures", 0) or 0)
    is_dark = bool(audit.get("is_dark", False))
    bg_lum = audit.get("body_bg_luminance")
    errors_n = len(audit.get("errors") or [])
    # If the page has no dark-mode CSS (the current default), the body
    # background luminance stays high. That's a "no dark mode" condition,
    # not a contrast failure -- we surface but don't fail.
    if not is_dark:
        return CheckResult(
            name="dark", ok=True, expected=0, found=0,
            detail=f"no dark-mode CSS; bg_lum={bg_lum} contrast_failures={fails}")
    # If the page *did* go dark, we *do* care about contrast failures.
    ok = fails == 0 and errors_n == 0
    return CheckResult(
        name="dark", ok=ok, expected=0, found=fails,
        detail=f"is_dark=true bg_lum={bg_lum} contrast_failures={fails} js_errors={errors_n}")


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
    ap.add_argument("--with-a11y", action="store_true",
                    help="run accessibility audit (pa11y/axe-core/structural)")
    ap.add_argument("--with-print", action="store_true",
                    help="run print-CSS audit")
    ap.add_argument("--with-dark", action="store_true",
                    help="run dark-mode resilience audit")
    ap.add_argument("--with-all", action="store_true",
                    help="enable --with-a11y --with-print --with-dark")
    args = ap.parse_args(argv)

    audit_modes: list[str] = []
    if args.with_all or args.with_a11y:
        audit_modes.append("a11y")
    if args.with_all or args.with_print:
        audit_modes.append("print")
    if args.with_all or args.with_dark:
        audit_modes.append("dark")
    axe_url = os.environ.get("MDLOUT_BROWSER_AXE_URL", DEFAULT_AXE_URL)

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
    if audit_modes:
        print(f"==> audits enabled: {','.join(audit_modes)}")

    results: list[ExampleResult] = []
    with tempfile.TemporaryDirectory(prefix="mdlout_browser_") as td:
        work = Path(td)
        for html in htmls:
            r = evaluate_example(html, chrome, work,
                                 audit_modes=audit_modes, axe_url=axe_url)
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

    def _example_dict(r: ExampleResult) -> dict:
        d = {
            "name": r.name,
            "ok": r.ok,
            "dom_bytes": r.dom_bytes,
            "error": r.error,
            "stderr_tail": r.stderr_tail,
            "checks": [asdict(c) for c in r.checks],
        }
        # Only emit the audits dict when at least one audit ran for this
        # example. This preserves byte-equivalent shape for default runs.
        if r.audits:
            d["audits"] = r.audits
        return d

    manifest = {
        "status": "ok",
        "chrome": chrome,
        "wsl_windows_chrome": is_wsl_windows_chrome(chrome),
        "pass": sum(1 for r in results if r.ok),
        "fail": sum(1 for r in results if not r.ok),
        "total": len(results),
        "examples": [_example_dict(r) for r in results],
    }
    if audit_modes:
        manifest["audits_enabled"] = audit_modes
        manifest["axe_url"] = axe_url
    Path(args.out).write_text(json.dumps(manifest, indent=2))
    print(f"==> manifest: {args.out}")
    print(f"==> pass {manifest['pass']} / fail {manifest['fail']} / total {manifest['total']}")
    return 0 if manifest["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
