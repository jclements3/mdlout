#!/usr/bin/env bash
# Per-doc sample-10 side-by-side gallery (PS vs SVG via z53.c).
# Reads /tmp/${d}.pdf and /tmp/${d}.svg produced by build.sh and writes
# tests/lout_doc_renders/${d}_diff.html plus tests/lout_doc_renders/${d}_samples/.
#
# DPI (default 100) controls the raster resolution for both pdftoppm
# (PS->PNG) and rsvg-convert (SVG->PNG). 150 lifts mean SSIM by
# shrinking the sub-pixel antialiasing floor; see
# tests/user_guide_diff/README.md "DPI sensitivity" (#172) and the
# 100-vs-150 column in tests/lout_doc_renders/README.md. Override via
# `DPI=150 bash tests/lout_doc_renders/diff.sh`.
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
OUT=$REPO/tests/lout_doc_renders
WORK=/tmp/loutdocs

DOCS=(design expert slides user)
SAMPLE_N=${SAMPLE_N:-10}
DPI=${DPI:-100}

mkdir -p "$WORK"

build_diff_for() {
    local d=$1
    local doc_work=$WORK/$d
    mkdir -p "$doc_work"/{ps,svg,diff,svg_split}

    echo "-- $d: rasterising PDF -> PNG (${DPI}dpi)"
    rm -f "$doc_work"/ps/ps-*.png
    # Force 3-digit zero-padding so our zip-by-page name scheme is
    # uniform across docs of any page count.
    local pdf_pages
    pdf_pages=$(pdfinfo "$OUT/${d}.pdf" | awk '/^Pages:/{print $2}')
    pdftoppm -r "$DPI" -png -forcenum \
        -f 1 -l "$pdf_pages" "$OUT/${d}.pdf" "$doc_work/ps/ps" 2>/dev/null \
        || pdftoppm -r "$DPI" -png "$OUT/${d}.pdf" "$doc_work/ps/ps"
    # Normalise filenames to 3-digit padding regardless of what
    # pdftoppm chose. (pdftoppm picks padding by digit-count of total
    # pages: 2 digits for <100, 3 for >=100. We want 3 across the board
    # so the split-SVG / sample-diff loop can use a single name shape.)
    for f in "$doc_work"/ps/ps-*.png; do
        [[ -f "$f" ]] || continue
        local base
        base=$(basename "$f" .png)
        local num=${base#ps-}
        # Strip leading zeros, then pad to 3 digits.
        local n=$((10#$num))
        local padded
        padded=$(printf "%03d" "$n")
        local newf="$doc_work/ps/ps-${padded}.png"
        if [[ "$f" != "$newf" ]]; then
            mv -f "$f" "$newf"
        fi
    done

    echo "-- $d: splitting SVG"
    rm -f "$doc_work"/svg_split/page-*.svg
    python3 "$REPO/tests/user_guide_diff_split_svg.py" \
        "/tmp/${d}.svg" "$doc_work/svg_split"

    local total
    total=$(ls "$doc_work"/ps/ps-*.png 2>/dev/null | wc -l)
    echo "   $d: $total PostScript pages"

    if [[ "$total" -eq 0 ]]; then
        echo "   $d: no pages, skipping diff" >&2
        return 0
    fi

    # Choose SAMPLE_N evenly-spaced pages.
    local pages
    pages=$(python3 -c "
import sys
n = int(sys.argv[1]); total = int(sys.argv[2])
k = min(n, total)
if k <= 0: sys.exit(0)
step = total / k
out = sorted({max(1, min(total, int((i + 0.5) * step) + 1)) for i in range(k)})
print(' '.join(f'{p:03d}' for p in out))
" "$SAMPLE_N" "$total")
    echo "   $d: sampling pages: $pages"

    # Rasterise just the sampled SVG pages.
    for p in $pages; do
        local svgf="$doc_work/svg_split/page-${p}.svg"
        if [[ -f "$svgf" ]]; then
            rsvg-convert -d "$DPI" -p "$DPI" -f png "$svgf" \
                -o "$doc_work/svg/svg-${p}.png" 2>/dev/null || true
        fi
    done

    # Per-page AE diff + SSIM
    local manifest=$doc_work/sample_manifest.tsv
    : > "$manifest"
    printf "page\twidth\theight\tdiff_pixels\tdiff_ratio\tssim_mean\n" > "$manifest"
    for p in $pages; do
        local ps="$doc_work/ps/ps-${p}.png"
        local svg="$doc_work/svg/svg-${p}.png"
        local diff="$doc_work/diff/diff-${p}.png"
        if [[ ! -f "$ps" ]]; then continue; fi
        local w h total diff_px ratio ssim
        read w h < <(identify -format "%w %h" "$ps") || true
        total=$((w * h))
        if [[ ! -f "$svg" ]]; then
            printf "%s\t%s\t%s\tMISSING\tNA\tNA\n" "$p" "$w" "$h" >> "$manifest"
            continue
        fi
        diff_px=$(compare -metric AE -fuzz 5% "$ps" "$svg" "$diff" 2>&1 | tail -n1 || true)
        [[ "$diff_px" =~ ^[0-9]+$ ]] || diff_px=0
        ratio=$(awk -v a="$diff_px" -v b="$total" 'BEGIN{printf "%.4f", a/b}')
        # SSIM via scikit-image (ImageMagick's DSSIM metric isn't in
        # the Ubuntu/Debian imagemagick build). Match what
        # tests/user_guide_diff_ssim.py does: pad to the smaller
        # intersection, data_range=255.
        ssim=$(python3 "$OUT/ssim.py" "$ps" "$svg" 2>/dev/null || echo "NA")
        printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$p" "$w" "$h" "$diff_px" "$ratio" "$ssim" >> "$manifest"
    done

    # Build side-by-side composite per sampled page in a samples dir.
    local samples="$OUT/${d}_samples"
    rm -rf "$samples"
    mkdir -p "$samples"
    for p in $pages; do
        local ps="$doc_work/ps/ps-${p}.png"
        local svg="$doc_work/svg/svg-${p}.png"
        local diff="$doc_work/diff/diff-${p}.png"
        if [[ ! -f "$ps" ]]; then continue; fi
        if [[ ! -f "$svg" ]]; then
            convert "$ps" -resize 40% -bordercolor white -border 4 \
                -font DejaVu-Sans -pointsize 14 label:"PS (page ${p})" +swap -append \
                "$samples/sample-${p}-ps.png"
            continue
        fi
        convert "$ps"   -resize 40% -bordercolor white -border 4 \
            -font DejaVu-Sans -pointsize 14 label:"PS  (page ${p})" +swap -append /tmp/_ps_panel.png
        convert "$svg"  -resize 40% -bordercolor white -border 4 \
            -font DejaVu-Sans -pointsize 14 label:"SVG (page ${p})" +swap -append /tmp/_svg_panel.png
        if [[ -f "$diff" ]]; then
            convert "$diff" -resize 40% -bordercolor white -border 4 \
                -font DejaVu-Sans -pointsize 14 label:"DIFF (page ${p})" +swap -append /tmp/_diff_panel.png
            convert /tmp/_ps_panel.png /tmp/_svg_panel.png /tmp/_diff_panel.png +append \
                -bordercolor white -border 8 "$samples/sample-${p}.png"
        else
            convert /tmp/_ps_panel.png /tmp/_svg_panel.png +append \
                -bordercolor white -border 8 "$samples/sample-${p}.png"
        fi
    done

    # Per-doc HTML index of the samples.
    python3 "$OUT/build_diff_html.py" \
        --doc "$d" \
        --manifest "$manifest" \
        --samples-dir "$samples" \
        --out "$OUT/${d}_diff.html"
}

for d in "${DOCS[@]}"; do
    build_diff_for "$d"
done

rm -f /tmp/_ps_panel.png /tmp/_svg_panel.png /tmp/_diff_panel.png
echo "done."
