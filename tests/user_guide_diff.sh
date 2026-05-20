#!/usr/bin/env bash
# Rebuild the PostScript-vs-SVG comparison for the Lout User's Guide
# end-to-end. This is the "single command to reproduce the artefacts
# in tests/user_guide_diff/" entrypoint.
#
# Wall time is ~15-20 minutes on a recent laptop: dominated by the
# 7-pass SVG build (~6 min) and the per-page ImageMagick compare
# (~4 min). All intermediate files land in /tmp/userguide_compare/;
# only the committed manifests + worst-NN images get rewritten under
# tests/user_guide_diff/.
#
# Requirements (must already be on $PATH):
#   lout (built; the script uses the binary at lout/lout)
#   ps2pdf       (Ghostscript)
#   pdftoppm     (poppler-utils)
#   rsvg-convert (librsvg)
#   compare      (ImageMagick)
#   convert      (ImageMagick)
#   python3      (stdlib only)
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LOUT=$REPO/lout
USER_DIR=$LOUT/doc/user
OUT_DIR=$REPO/tests/user_guide_diff
WORK=/tmp/userguide_compare

if [[ ! -x "$LOUT/lout" ]]; then
    echo "error: $LOUT/lout not built. Run: (cd $LOUT && make all)" >&2
    exit 1
fi

mkdir -p "$WORK"/{ps,svg,diff,svg_split}

# --- Stage 1: build PostScript (7 passes) ------------------------------------
echo "==> building PostScript (7 passes)"
( cd "$USER_DIR" && rm -f ./*.li
  for i in 1 2 3 4 5 6 7; do
      ../../lout -I ../../include -I . all > /tmp/user.ps 2>/tmp/user.ps.err || true
  done )
echo "    PS bytes: $(stat -c%s /tmp/user.ps)"

# --- Stage 2: build SVG (7 passes, accept the largest converged output) ------
echo "==> building SVG (7 passes; alternation between full/partial is expected)"
( cd "$USER_DIR" && rm -f ./*.li
  for i in 1 2 3 4 5 6 7; do
      "$LOUT/lout" -I "$LOUT/include" -I . -G all > "/tmp/user.svg.$i" 2>"/tmp/user.svg.err.$i" || true
  done )
# pick the largest .svg.N as the canonical output
biggest=$(ls -S /tmp/user.svg.[1-7] | head -1)
cp "$biggest" /tmp/user.svg
rm -f /tmp/user.svg.[1-7] /tmp/user.svg.err.[1-7]
echo "    SVG bytes: $(stat -c%s /tmp/user.svg)  (from $biggest)"

# --- Stage 3: rasterise PS pages at 100 dpi ----------------------------------
echo "==> rasterising PS -> PDF -> PNG"
ps2pdf /tmp/user.ps /tmp/user.pdf
rm -f "$WORK"/ps/ps-*.png
( cd "$WORK/ps" && pdftoppm -r 100 -png /tmp/user.pdf ps )
echo "    PS pages: $(ls "$WORK"/ps/ps-*.png | wc -l)"

# --- Stage 4: split SVG and rasterise each page ------------------------------
echo "==> splitting SVG into per-page files"
rm -f "$WORK"/svg_split/*.svg
python3 "$REPO/tests/user_guide_diff_split_svg.py" /tmp/user.svg "$WORK/svg_split"

echo "==> rasterising per-page SVGs at 100 dpi"
rm -f "$WORK"/svg/svg-*.png
for f in "$WORK"/svg_split/page-*.svg; do
    n=$(basename "$f" .svg | sed 's/page-//')
    rsvg-convert -d 100 -p 100 -f png "$f" -o "$WORK/svg/svg-${n}.png" 2>/dev/null || true
done
echo "    SVG pages: $(ls "$WORK"/svg/svg-*.png | wc -l)"

# --- Stage 5: per-page pixel diff via ImageMagick compare --------------------
echo "==> running per-page AE compare (5% fuzz)"
MANIFEST=$WORK/manifest.txt
printf "page\tps_pixels\tsvg_pixels\tdiff_pixels\tdiff_ratio\tverdict\n" > "$MANIFEST"
for psfile in "$WORK"/ps/ps-*.png; do
    n=$(basename "$psfile" .png | sed 's/ps-//')
    svgfile="$WORK/svg/svg-${n}.png"
    difffile="$WORK/diff/diff-${n}.png"
    read w h < <(identify -format "%w %h" "$psfile")
    total=$((w * h))
    if [[ ! -f "$svgfile" ]]; then
        ink=$(convert "$psfile" -threshold 50% -negate -format "%[fx:int(w*h*mean)]" info: 2>/dev/null || echo "$total")
        ratio=$(awk -v a="$ink" -v b="$total" 'BEGIN{printf "%.4f", a/b}')
        printf "%s\t%s\tMISSING\t%s\t%s\tMISSING\n" "$n" "$ink" "$ink" "$ratio" >> "$MANIFEST"
        continue
    fi
    diff_px=$(compare -metric AE -fuzz 5% "$psfile" "$svgfile" "$difffile" 2>&1 | tail -n1)
    [[ "$diff_px" =~ ^[0-9]+$ ]] || diff_px=0
    ratio=$(awk -v a="$diff_px" -v b="$total" 'BEGIN{printf "%.4f", a/b}')
    verdict=$(awk -v r="$ratio" 'BEGIN{
        if (r < 0.05) print "OK";
        else if (r < 0.20) print "DIFF";
        else print "BAD";
    }')
    printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$n" "$total" "$total" "$diff_px" "$ratio" "$verdict" >> "$MANIFEST"
done
cp "$MANIFEST" "$OUT_DIR/manifest.txt"

# --- Stage 6: regenerate JSON manifest + worst-10 side-by-sides --------------
echo "==> regenerating JSON manifest"
python3 "$REPO/tests/user_guide_diff_manifest.py" "$MANIFEST" "$OUT_DIR/manifest.json"

echo "==> rebuilding worst-10 side-by-side images"
python3 "$REPO/tests/user_guide_diff_manifest.py" --print-worst "$MANIFEST" \
    > "$WORK/worst10.txt"
rank=0
while IFS=$'\t' read -r ratio page; do
    rank=$((rank + 1))
    rs=$(printf "%02d" $rank)
    ps="$WORK/ps/ps-${page}.png"
    svg="$WORK/svg/svg-${page}.png"
    diff="$WORK/diff/diff-${page}.png"
    convert "$ps"   -resize 50% -bordercolor white -border 6 \
        -font DejaVu-Sans -pointsize 16 label:"PS  (page ${page})" +swap -append /tmp/_ps_panel.png
    convert "$svg"  -resize 50% -bordercolor white -border 6 \
        -font DejaVu-Sans -pointsize 16 label:"SVG (page ${page})" +swap -append /tmp/_svg_panel.png
    convert "$diff" -resize 50% -bordercolor white -border 6 \
        -font DejaVu-Sans -pointsize 16 label:"DIFF (ratio ${ratio})" +swap -append /tmp/_diff_panel.png
    convert /tmp/_ps_panel.png /tmp/_svg_panel.png /tmp/_diff_panel.png +append \
        -bordercolor white -border 10 "$OUT_DIR/worst-${rs}.png"
done < "$WORK/worst10.txt"
rm -f /tmp/_ps_panel.png /tmp/_svg_panel.png /tmp/_diff_panel.png

echo "==> done. Updated artefacts:"
ls -la "$OUT_DIR"
