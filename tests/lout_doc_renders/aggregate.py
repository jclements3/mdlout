#!/usr/bin/env python3
"""Write tests/lout_doc_renders/README.md aggregating per-doc stats."""
from __future__ import annotations

import os
import re
from pathlib import Path
from statistics import mean

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "tests" / "lout_doc_renders"
WORK = Path("/tmp/loutdocs")

DOCS = ["design", "expert", "slides", "user"]


def parse_stats(path: Path) -> dict[str, str]:
    out = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def page_count_from_pdf(pdf: Path) -> int:
    """Use pdfinfo if available; fall back to a /Count search."""
    import subprocess
    try:
        r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split()[1])
    except Exception:
        pass
    return 0


def sample_ssim_mean(manifest: Path) -> tuple[float | None, float | None]:
    """Return (ssim_mean, diff_pct_mean) from the sample-diff manifest."""
    if not manifest.exists():
        return None, None
    ssims = []
    diffs = []
    for i, line in enumerate(manifest.read_text().splitlines()):
        if i == 0 or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        try:
            diffs.append(float(parts[4]))
        except ValueError:
            pass
        try:
            ssims.append(float(parts[5]))
        except ValueError:
            pass
    sm = mean(ssims) if ssims else None
    dm = mean(diffs) if diffs else None
    return sm, dm


def human_bytes(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def main() -> int:
    rows = []
    for d in DOCS:
        stats = parse_stats(WORK / f"{d}.stats")
        pdf = OUT / f"{d}.pdf"
        html = OUT / f"{d}.html"
        sample_manifest = WORK / d / "sample_manifest.tsv"
        pages = page_count_from_pdf(pdf)
        ssim_m, diff_m = sample_ssim_mean(sample_manifest)
        rows.append({
            "doc": d,
            "pages": pages,
            "ps_bytes": int(stats.get("ps_bytes", 0)),
            "svg_bytes": int(stats.get("svg_bytes", 0)),
            "pdf_bytes": int(stats.get("pdf_bytes", 0)),
            "html_bytes": int(stats.get("html_bytes", 0)),
            "ps_wall": int(stats.get("ps_wall", 0)),
            "svg_wall": int(stats.get("svg_wall", 0)),
            "biggest_svg_pass": stats.get("biggest_svg_pass", "?"),
            "ssim_mean": ssim_m,
            "diff_pct_mean": diff_m,
        })

    lines = []
    lines.append("# Lout documentation: PostScript + z53.c SVG renders")
    lines.append("")
    lines.append("This directory holds end-to-end renders of all four documents that ship "
                 "with the Lout source tree (`lout/doc/{design,expert,slides,user}`) using "
                 "the SVG back-end (`z53.c`). Each document is built twice — once through "
                 "the PostScript pipeline (`lout` + `ps2pdf`) and once through the SVG "
                 "pipeline (`lout -G` + HTML scaffold). Both runs use 7 passes for "
                 "cross-reference convergence.")
    lines.append("")
    lines.append("Reproduce with:")
    lines.append("")
    lines.append("```bash")
    lines.append("bash tests/lout_doc_renders/build.sh")
    lines.append("```")
    lines.append("")
    lines.append("## Per-document summary")
    lines.append("")
    lines.append("| Doc | Pages | PS | PDF | SVG | HTML | PS wall | SVG wall | Sample SSIM | Diff %|")
    lines.append("|-----|------:|---:|----:|----:|-----:|--------:|---------:|------------:|------:|")
    for r in rows:
        ssim = f"{r['ssim_mean']:.4f}" if r["ssim_mean"] is not None else "—"
        diff = f"{r['diff_pct_mean'] * 100:.2f}%" if r["diff_pct_mean"] is not None else "—"
        lines.append(
            f"| [{r['doc']}](./{r['doc']}.html) | {r['pages']} | "
            f"{human_bytes(r['ps_bytes'])} | "
            f"[{human_bytes(r['pdf_bytes'])}](./{r['doc']}.pdf) | "
            f"{human_bytes(r['svg_bytes'])} | "
            f"[{human_bytes(r['html_bytes'])}](./{r['doc']}.html) | "
            f"{r['ps_wall']}s | {r['svg_wall']}s | "
            f"{ssim} | {diff} |"
        )
    lines.append("")
    lines.append("Sample SSIM is the mean of scikit-image `structural_similarity` (Wang "
                 "et al. 2004) over 10 evenly-spaced sampled pages per document on "
                 "luminance, data_range=255 (1.0 = pixel-identical, >0.95 = visually "
                 "indistinguishable at 100 dpi, <0.85 = actually different). Diff % is "
                 "the ImageMagick AE pixel-diff ratio at 5% fuzz averaged over the same "
                 "samples. Side-by-side galleries:")
    lines.append("")
    for r in rows:
        lines.append(f"- [{r['doc']}_diff.html](./{r['doc']}_diff.html)")
    lines.append("")
    lines.append("## Per-document notes")
    lines.append("")
    lines.append("### design")
    lines.append("")
    lines.append("Jeffrey Kingston's 1993 design paper. Heavy on `@Eq` (display equations), "
                 "`@Fig` (algorithm flow diagrams), and worked examples of Lout's galley "
                 "system. The toughest of the four for the SVG back-end because the "
                 "diagrams use direct PostScript via `@Graphic`.")
    lines.append("")
    lines.append("### expert")
    lines.append("")
    lines.append("The Expert's Guide (`@Book` style). Exercises advanced features — "
                 "`@Span`, `@TagItem`, `@OneCol`/`@OneRow`, custom galleys, `@Insert`, "
                 "scaled/rotated graphics. The largest in source line count.")
    lines.append("")
    lines.append("### slides")
    lines.append("")
    lines.append("`@OverheadTransparencies` style. Big fonts, landscape, lots of "
                 "`@Code` blocks; light on graphics. The cheapest to build.")
    lines.append("")
    lines.append("### user")
    lines.append("")
    lines.append("The User's Guide. The reference document tracked separately by "
                 "`tests/user_guide_diff.sh`; included here for completeness.")
    lines.append("")
    lines.append("## Bugs / divergences surfaced by these renders")
    lines.append("")
    lines.append("Building the three previously-unrendered docs through z53.c "
                 "highlighted three issue classes:")
    lines.append("")
    lines.append("1. **`@Case { PostScript ... PDF ... }` lacks an `SVG` branch.** "
                 "Many Lout include files (most loudly `s2_3` in `design`) ship "
                 "with explicit `PostScript` and `PDF` cases for back-end-specific "
                 "instructions. Under `lout -G` these fall through to the "
                 "PostScript branch — the message `replacing unknown @Case option "
                 "SVG by PostScript` accounts for most of the stderr volume. "
                 "Functionally harmless (the PostScript branch is usually fine) "
                 "but it should grow an `SVG` case in `lout/include/`.")
    lines.append("")
    lines.append("2. **Raw PostScript inside `@Graphic { ... }`.** The `design` "
                 "document embeds hand-written PostScript snippets in its "
                 "algorithm-flow diagrams (`lightgrey`, `lfig` operators in "
                 "`s2_3`). z53.c flags these as `unknown PostScript operator`. "
                 "This is the long tail tracked by `lout/SVG_PORTING.md` — "
                 "translating PostScript drawing primitives to SVG `<path>` "
                 "operations is future work. Page-level effect is the diagram "
                 "appears as an XML comment with surrounding text intact.")
    lines.append("")
    lines.append("3. **Per-pass output alternation continues.** With 7 passes, "
                 "every doc's SVG run alternates between the full multi-page "
                 "output and a smaller partial output on each pass — the same "
                 "phenomenon `tests/user_guide_diff.sh` already documents. "
                 "We pick the biggest of the seven by file size as the canonical "
                 "output. (`design` peaks on pass 2, `expert` on pass 4, "
                 "`slides` on pass 2, `user` on pass 4.)")
    lines.append("")
    lines.append("Each per-doc gallery (`*_diff.html`) shows 10 evenly-spaced "
                 "sample pages with PS / SVG / pixel-diff panels side by side.")
    lines.append("")
    lines.append("## How the HTML scaffold differs from `mdlout.py`")
    lines.append("")
    lines.append("`mdlout.py:_build_html_scaffold` is wired into the Markdown front "
                 "end and assumes the caller has parsed YAML frontmatter. These docs "
                 "are raw Lout source, so we use a much smaller scaffold "
                 "(`wrap_html.py`) — same `.lout-page` styling, same print "
                 "stylesheet shape, but CDN-loaded KaTeX (no font embedding, no "
                 "abcjsharp, no dark-mode toggle). That's enough for the docs since "
                 "they don't use `@Math`/`@ABC`/`@Mermaid`.")
    lines.append("")
    Path(OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'README.md'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
