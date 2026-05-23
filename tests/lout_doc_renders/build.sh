#!/usr/bin/env bash
# Render lout/doc/{design,expert,slides,user} to PS+PDF and SVG+HTML
# using z53.c. See tests/lout_doc_renders/README.md for context.
#
# Wall-time is ~25-40 min depending on the doc; PostScript pass is fast,
# SVG (z53.c) is currently the bottleneck. Outputs land in
# tests/lout_doc_renders/.

set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
LOUT_BIN=$REPO/lout/lout
INCLUDE=$REPO/lout/include
OUT=$REPO/tests/lout_doc_renders
WORK=/tmp/loutdocs

if [[ ! -x "$LOUT_BIN" ]]; then
    echo "error: $LOUT_BIN not built. Run: (cd $REPO/lout && make all)" >&2
    exit 1
fi

mkdir -p "$WORK" "$OUT"

DOCS=(design expert slides user)
PASSES=${PASSES:-7}

build_doc() {
    local d=$1
    local src_dir=$REPO/lout/doc/$d
    local start_ps end_ps start_svg end_svg

    echo "============================================================"
    echo "==> $d (source: $src_dir)"
    echo "============================================================"

    ( cd "$src_dir" && rm -f ./*.li ./*.ldx ./*.lpc )

    echo "-- $d: PostScript ($PASSES passes)"
    start_ps=$(date +%s)
    ( cd "$src_dir"
      for i in $(seq 1 "$PASSES"); do
        "$LOUT_BIN" -I "$INCLUDE" -I . all \
            > "/tmp/${d}.ps.${i}" 2>"/tmp/${d}.ps.${i}.err" || true
      done )
    cp "/tmp/${d}.ps.${PASSES}" "/tmp/${d}.ps"
    end_ps=$(date +%s)
    echo "   PS bytes: $(stat -c%s /tmp/${d}.ps)  wall=$((end_ps - start_ps))s"

    echo "-- $d: SVG via z53.c ($PASSES passes)"
    ( cd "$src_dir" && rm -f ./*.li ./*.ldx ./*.lpc )
    start_svg=$(date +%s)
    ( cd "$src_dir"
      for i in $(seq 1 "$PASSES"); do
        "$LOUT_BIN" -G -I "$INCLUDE" -I . all \
            > "/tmp/${d}.svg.${i}" 2>"/tmp/${d}.svg.${i}.err" || true
      done )
    # pick the largest .svg.N as the canonical output (matches user_guide_diff.sh)
    biggest=$(ls -S /tmp/${d}.svg.[1-9] 2>/dev/null | head -1)
    if [[ -z "$biggest" ]]; then
        echo "   ERROR: no SVG output produced for $d" >&2
        return 1
    fi
    cp "$biggest" "/tmp/${d}.svg"
    end_svg=$(date +%s)
    echo "   SVG bytes: $(stat -c%s /tmp/${d}.svg)  wall=$((end_svg - start_svg))s  (from $biggest)"

    echo "-- $d: PS -> PDF"
    ps2pdf "/tmp/${d}.ps" "/tmp/${d}.pdf"
    cp "/tmp/${d}.pdf" "$OUT/${d}.pdf"
    echo "   PDF bytes: $(stat -c%s $OUT/${d}.pdf)"

    echo "-- $d: wrap SVG in HTML scaffold"
    python3 "$OUT/wrap_html.py" \
        --title "Lout: $d" \
        --svg "/tmp/${d}.svg" \
        --out "$OUT/${d}.html"
    echo "   HTML bytes: $(stat -c%s $OUT/${d}.html)"

    # record build stats for README aggregation
    {
        echo "doc=${d}"
        echo "ps_bytes=$(stat -c%s /tmp/${d}.ps)"
        echo "svg_bytes=$(stat -c%s /tmp/${d}.svg)"
        echo "pdf_bytes=$(stat -c%s $OUT/${d}.pdf)"
        echo "html_bytes=$(stat -c%s $OUT/${d}.html)"
        echo "ps_wall=$((end_ps - start_ps))"
        echo "svg_wall=$((end_svg - start_svg))"
        echo "biggest_svg_pass=$(basename "$biggest")"
    } > "$WORK/${d}.stats"
}

for d in "${DOCS[@]}"; do
    build_doc "$d"
done

echo
echo "============================================================"
echo "==> all four documents built. Now building diff pages."
echo "============================================================"

bash "$OUT/diff.sh"

echo "============================================================"
echo "==> aggregating README"
echo "============================================================"

python3 "$OUT/aggregate.py"

echo "Done. Outputs in $OUT/"
ls -la "$OUT"
