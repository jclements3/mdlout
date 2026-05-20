#!/usr/bin/env bash
# Variant of user_guide_diff.sh that rasterises the SVG side with Chromium
# headless instead of rsvg-convert, so the @font-face Nimbus base-35 fonts
# that mdlout's HTML wrapper embeds actually get applied. The goal is to
# measure how much the page-level pixel diff vs the Ghostscript-rendered
# PostScript drops when we use the toolchain a real user sees in their
# browser.
#
# Usage:
#   tests/chromium_diff.sh                       # process default 30-page subset
#   tests/chromium_diff.sh 010,019,086,290       # process a custom subset
#
# Prerequisites:
#   * /tmp/userguide_compare/ps/ps-*.png         (from tests/user_guide_diff.sh)
#   * /tmp/userguide_compare/svg_split/page-*.svg
#   * Chromium / Google Chrome reachable from this shell. On WSL the script
#     auto-detects /mnt/c/Program Files/Google/Chrome/Application/chrome.exe
#     and shuttles files through /mnt/c/temp/ to dodge UNC-path quirks.
#
# Pages: defaults to the worst-10 from tests/user_guide_diff/manifest.txt
# plus 20 spread evenly across the document. Anything wider is wall-time
# bound (~3-5s per page in Chromium plus 1s for compare).
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
BASELINE_MANIFEST=$REPO/tests/user_guide_diff/manifest.txt

# Source dirs (produced by user_guide_diff.sh).
SRC_PS=/tmp/userguide_compare/ps
SRC_SVG=/tmp/userguide_compare/svg_split

# Chromium has trouble loading file:// URLs whose paths live on a WSL share
# (\\wsl.localhost\...), so we shuttle everything through a Windows-local
# directory. If you're not on WSL, set WORK to anything you like.
if [[ -d /mnt/c ]]; then
    WORK=${WORK:-/mnt/c/temp/userguide_chromium}
    WIN_WORK=${WIN_WORK:-C:\\temp\\userguide_chromium}
else
    WORK=${WORK:-/tmp/userguide_chromium}
    WIN_WORK=$WORK
fi
OUT_DIR=$REPO/tests/user_guide_diff

# --- locate Chromium ---------------------------------------------------------
CHROME=""
for cand in \
    /usr/bin/chromium \
    /usr/bin/chromium-browser \
    /snap/bin/chromium \
    /usr/bin/google-chrome \
    /usr/bin/chrome \
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe" \
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" ; do
    if [[ -x "$cand" || -L "$cand" ]]; then
        CHROME=$cand; break
    fi
done
if [[ -z "$CHROME" ]]; then
    echo "error: no chromium / chrome binary found." >&2
    echo "fallback: skipping; rerun after installing one of:" >&2
    echo "    sudo apt install chromium-browser" >&2
    echo "    sudo snap install chromium" >&2
    exit 2
fi
echo "==> chrome: $CHROME"

# --- page subset -------------------------------------------------------------
if [[ $# -ge 1 ]]; then
    SELECTED=$(echo "$1" | tr ',' '\n' | awk 'NF' | awk '{ printf "%03d\n", $1 }')
else
    if [[ ! -f "$BASELINE_MANIFEST" ]]; then
        echo "error: baseline manifest $BASELINE_MANIFEST missing." >&2
        echo "       Run tests/user_guide_diff.sh first." >&2
        exit 1
    fi
    SELECTED=$(python3 - "$BASELINE_MANIFEST" << 'PY'
import sys
rows = []
with open(sys.argv[1]) as f:
    next(f)
    for line in f:
        parts = line.rstrip('\n').split('\t')
        if len(parts) >= 5:
            try:
                rows.append((parts[0], float(parts[4])))
            except ValueError:
                pass
worst = {p for p, _ in sorted(rows, key=lambda r: -r[1])[:10]}
n = len(rows)
step = max(1, n // 20)
spread = {rows[i][0] for i in range(0, n, step)}
for p in sorted(worst | spread):
    print(p)
PY
)
fi
NPAGES=$(echo "$SELECTED" | wc -l)
echo "==> processing $NPAGES page(s)"

# --- workdirs ----------------------------------------------------------------
mkdir -p "$WORK"/{html,svg,ps,png,diff}

# --- stage 1: copy inputs into a Chromium-friendly location -----------------
echo "==> staging inputs to $WORK"
for n in $SELECTED; do
    cp -f "$SRC_PS/ps-$n.png"          "$WORK/ps/ps-$n.png"
    cp -f "$SRC_SVG/page-$n.svg"       "$WORK/svg/page-$n.svg"
done

# --- stage 2: wrap each SVG in HTML + write shared CSS ----------------------
echo "==> wrapping SVGs in HTML (@font-face Nimbus base-35 inlined)"
python3 "$REPO/tests/chromium_wrap_svg.py" \
    --pages "$(echo "$SELECTED" | paste -sd,)" \
    "$WORK/svg" "$WORK"

# --- stage 3: screenshot every HTML page with Chromium ----------------------
echo "==> screenshotting via Chromium headless"
PSIZE=0
for n in $SELECTED; do
    PSIZE=$((PSIZE + 1))
    html_url="file:///${WIN_WORK//\\//}/html/page-$n.html"
    # WIN paths in URLs need forward slashes; the substitution above flips
    # the backslashes WIN_WORK still carries.
    # window-size matches chromium_wrap_svg.py's 826 x 1169 CSS-pixel target,
    # which is the same physical extent as pdftoppm -r 100 on A4 (one pixel
    # narrower / shorter than 827 x 1170; the runner crops the PS render
    # before diffing).
    "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
        --window-size=826,1169 \
        --virtual-time-budget=10000 \
        --run-all-compositor-stages-before-draw \
        --screenshot="${WIN_WORK}\\png\\page-$n.png" \
        "$html_url" \
        > /dev/null 2>&1 || true
done
echo "    captured: $(ls "$WORK"/png/page-*.png 2>/dev/null | wc -l) page(s)"

# --- stage 4: per-page AE pixel diff vs the PS render -----------------------
echo "==> running per-page AE compare (5% fuzz)"
MANIFEST=$WORK/chromium_manifest.txt
printf "page\tpixels\tdiff_pixels\tdiff_ratio\tverdict\n" > "$MANIFEST"
# `compare` returns 1 whenever the images differ at all (the normal case
# here) and a few ImageMagick / WSL combinations also emit non-fatal stderr
# warnings on /mnt/c paths. Relax errexit for this loop so neither sinks
# the run; we restore it at the end.
set +e
for n in $SELECTED; do
    psfile=$WORK/ps/ps-$n.png
    cfile=$WORK/png/page-$n.png
    difffile=$WORK/diff/diff-$n.png
    if [[ ! -f "$cfile" ]]; then
        printf "%s\tMISSING\tMISSING\tMISSING\tMISSING\n" "$n" >> "$MANIFEST"
        continue
    fi
    # Chrome -> 826 x 1169 because 842 CSS px * 1.388889 ~= 1169.44 (rounded).
    # The PS pdftoppm render is 827 x 1170. Crop PS down by 1 px to match.
    read w h < <(identify -format "%w %h" "$cfile")
    convert "$psfile" -crop "${w}x${h}+0+0" +repage "$WORK/ps/ps-${n}-c.png"
    total=$((w * h))
    # `compare` exits 1 when images differ (it doesn't mean failure); the AE
    # pixel count is on its last stderr line. Suppress the nonzero exit so
    # `set -e` doesn't terminate the loop on the first page.
    diff_px=$(compare -metric AE -fuzz 5% \
        "$WORK/ps/ps-${n}-c.png" "$cfile" "$difffile" 2>&1 | tail -n1 || true)
    [[ "$diff_px" =~ ^[0-9]+$ ]] || diff_px=0
    ratio=$(awk -v a="$diff_px" -v b="$total" 'BEGIN{printf "%.4f", a/b}')
    verdict=$(awk -v r="$ratio" 'BEGIN{
        if (r < 0.05)      print "OK";
        else if (r < 0.20) print "DIFF";
        else                print "BAD";
    }')
    printf "%s\t%s\t%s\t%s\t%s\n" "$n" "$total" "$diff_px" "$ratio" "$verdict" \
        >> "$MANIFEST"
done
set -e

# --- stage 5: roll up + paired comparison vs baseline rsvg manifest ---------
echo "==> rolling up aggregate stats"
python3 - "$MANIFEST" "$BASELINE_MANIFEST" "$OUT_DIR/chromium_manifest.txt" << 'PY'
import statistics, sys, shutil

chrome_path, base_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

def load(path, ratio_col):
    rows = {}
    with open(path) as f:
        next(f)
        for line in f:
            parts = line.rstrip('\n').split('\t')
            page = parts[0]
            try:
                rows[page] = float(parts[ratio_col])
            except (ValueError, IndexError):
                rows[page] = None
    return rows

chrome = load(chrome_path, 3)
baseline = load(base_path, 4)

paired = [(p, chrome[p], baseline.get(p))
          for p in chrome
          if chrome.get(p) is not None and baseline.get(p) is not None]

def stats(name, values):
    if not values:
        return f"{name}: no data"
    return (f"{name}: n={len(values)} "
            f"mean={statistics.mean(values):.4f} "
            f"median={statistics.median(values):.4f} "
            f"max={max(values):.4f}")

print(stats("chromium (this run)", [c for _, c, _ in paired]))
print(stats("rsvg     (baseline)", [b for _, _, b in paired]))

deltas = [(p, c - b) for p, c, b in paired]
improved = [d for _, d in deltas if d < 0]
worsened = [d for _, d in deltas if d > 0]
print(f"improved (chrome diff < rsvg diff): {len(improved)} of {len(paired)}")
print(f"worsened (chrome diff > rsvg diff): {len(worsened)} of {len(paired)}")
print(f"mean delta (chrome - rsvg)        : {statistics.mean(d for _, d in deltas):+.4f}")

chrome_ok  = [p for p, c, _ in paired if c < 0.05]
chrome_bad = [p for p, c, _ in paired if c >= 0.20]
base_ok    = [p for p, _, b in paired if b < 0.05]
base_bad   = [p for p, _, b in paired if b >= 0.20]
print(f"OK  bucket (<5%):  chrome={len(chrome_ok)}  rsvg={len(base_ok)}")
print(f"BAD bucket (>=20%): chrome={len(chrome_bad)}  rsvg={len(base_bad)}")
if chrome_bad:
    print("  chrome BAD pages: " + ",".join(sorted(chrome_bad)))

shutil.copy(chrome_path, out_path)
print(f"-- wrote {out_path}")
PY

echo "==> done"
