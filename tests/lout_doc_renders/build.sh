#!/usr/bin/env bash
# Render lout/doc/{design,expert,slides,user} to PS+PDF and SVG+HTML
# using z53.c. See tests/lout_doc_renders/README.md for context.
#
# Wall-time is ~25-40 min depending on the doc; PostScript pass is fast,
# SVG (z53.c) is currently the bottleneck. Outputs land in
# tests/lout_doc_renders/.
#
# DPI (default 100) controls the raster resolution for the sample
# pixel-diff stage (passed through to diff.sh -> pdftoppm + rsvg-convert).
# 150 lifts mean SSIM by shrinking the sub-pixel antialiasing floor;
# see tests/user_guide_diff/README.md "DPI sensitivity" (#172) and the
# 100-vs-150 column in tests/lout_doc_renders/README.md. Override via
# `DPI=150 bash tests/lout_doc_renders/build.sh`.
#
# SKIP_DOC_BUILD=1 reuses the existing /tmp/{design,expert,slides,user}.{ps,svg}
# artifacts (and the published per-doc PDFs/HTMLs) and only re-runs the
# diff stage. Handy when iterating on diff-stage parameters (e.g. DPI)
# without paying the ~25-40 min PS/SVG rebuild cost.

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
DPI=${DPI:-100}
SKIP_DOC_BUILD=${SKIP_DOC_BUILD:-0}
export DPI

build_doc() {
    local d=$1
    local orig_dir=$REPO/lout/doc/$d
    local src_dir=$WORK/src/$d
    local start_ps end_ps start_svg end_svg

    echo "============================================================"
    echo "==> $d (source: $orig_dir -> scratch $src_dir)"
    echo "============================================================"

    # Copy doc sources to a per-run scratch dir before invoking lout.
    # Lout writes *.li / *.ldx / lout.lix to the cwd as it resolves
    # cross-references; concurrent agents running lout against the
    # shared lout/doc/$d/ would race on those files, causing symptoms
    # like "assert failed in Parse: *token!", "rename failed", or
    # "line too long" (diagnosed by agent #142 on 2026-05-23).
    rm -rf "$src_dir"
    mkdir -p "$src_dir"
    cp -r "$orig_dir"/. "$src_dir"/

    ( cd "$src_dir" && rm -f ./*.li ./*.ldx ./*.lpc )

    echo "-- $d: PostScript ($PASSES passes)"
    start_ps=$(date +%s)
    ( cd "$src_dir"
      for i in $(seq 1 "$PASSES"); do
        "$LOUT_BIN" -I "$INCLUDE" -I . all \
            > "/tmp/${d}.ps.${i}" 2>"/tmp/${d}.ps.${i}.err" || true
      done )
    # Pick the latest "converged" PS pass (where two consecutive passes
    # produce the same file size, i.e. cross-refs are resolved) among
    # the non-crashed passes. At lout HEAD the expert doc starts
    # asserting in Parse() from pass 4 onward, producing a 45 KB stub
    # -- the earlier passes still emit a valid multi-hundred-KB
    # PostScript file. Filter passes whose stderr contains
    # "internal error" before considering them.
    biggest_ps=""
    prev_size=-1
    for i in $(seq 1 "$PASSES"); do
        f="/tmp/${d}.ps.${i}"
        e="/tmp/${d}.ps.${i}.err"
        [[ -s "$f" ]] || continue
        if grep -q "internal error" "$e" 2>/dev/null; then
            continue
        fi
        sz=$(stat -c%s "$f")
        # Remember the last pass that matched the previous size.
        if [[ "$sz" -eq "$prev_size" ]]; then
            biggest_ps=$f
        fi
        prev_size=$sz
    done
    if [[ -z "$biggest_ps" ]]; then
        # No convergence: fall back to largest non-crashed pass.
        biggest_size=0
        for i in $(seq 1 "$PASSES"); do
            f="/tmp/${d}.ps.${i}"
            e="/tmp/${d}.ps.${i}.err"
            [[ -s "$f" ]] || continue
            if grep -q "internal error" "$e" 2>/dev/null; then continue; fi
            sz=$(stat -c%s "$f")
            if [[ "$sz" -gt "$biggest_size" ]]; then
                biggest_size=$sz
                biggest_ps=$f
            fi
        done
    fi
    if [[ -z "$biggest_ps" ]]; then
        biggest_ps=$(ls -S /tmp/${d}.ps.[1-9] 2>/dev/null | head -1)
    fi
    if [[ -z "$biggest_ps" ]]; then
        echo "   ERROR: no PS output produced for $d" >&2
        return 1
    fi
    cp "$biggest_ps" "/tmp/${d}.ps"
    end_ps=$(date +%s)
    echo "   PS bytes: $(stat -c%s /tmp/${d}.ps)  wall=$((end_ps - start_ps))s  (from $biggest_ps)"

    echo "-- $d: SVG via z53.c ($PASSES passes)"
    ( cd "$src_dir" && rm -f ./*.li ./*.ldx ./*.lpc )
    start_svg=$(date +%s)
    ( cd "$src_dir"
      for i in $(seq 1 "$PASSES"); do
        "$LOUT_BIN" -G -I "$INCLUDE" -I . all \
            > "/tmp/${d}.svg.${i}" 2>"/tmp/${d}.svg.${i}.err" || true
      done )
    # Same convergence rule as for PS: pick the latest pass whose size
    # matches the previous pass (xref-converged). Fall back to the
    # largest pass if no two consecutive passes agree.
    biggest=""
    prev_size=-1
    for i in $(seq 1 "$PASSES"); do
        f="/tmp/${d}.svg.${i}"
        [[ -s "$f" ]] || continue
        sz=$(stat -c%s "$f")
        if [[ "$sz" -eq "$prev_size" ]]; then
            biggest=$f
        fi
        prev_size=$sz
    done
    if [[ -z "$biggest" ]]; then
        biggest=$(ls -S /tmp/${d}.svg.[1-9] 2>/dev/null | head -1)
    fi
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
        echo "biggest_ps_pass=$(basename "$biggest_ps")"
    } > "$WORK/${d}.stats"
}

if [[ "$SKIP_DOC_BUILD" == "1" ]]; then
    echo "==> SKIP_DOC_BUILD=1: reusing /tmp/{design,expert,slides,user}.{ps,svg}"
    for d in "${DOCS[@]}"; do
        for ext in ps svg; do
            if [[ ! -s "/tmp/${d}.${ext}" ]]; then
                echo "error: SKIP_DOC_BUILD=1 but /tmp/${d}.${ext} missing." >&2
                echo "       Run without SKIP_DOC_BUILD to rebuild." >&2
                exit 1
            fi
        done
    done
else
    for d in "${DOCS[@]}"; do
        build_doc "$d"
    done
fi

echo
echo "============================================================"
echo "==> all four documents built. Now building diff pages (DPI=$DPI)."
echo "============================================================"

DPI="$DPI" bash "$OUT/diff.sh"

echo "============================================================"
echo "==> aggregating README"
echo "============================================================"

python3 "$OUT/aggregate.py"

echo "============================================================"
echo "==> building index.html landing page"
echo "============================================================"

python3 "$OUT/make_index.py"

echo "Done. Outputs in $OUT/"
ls -la "$OUT"
