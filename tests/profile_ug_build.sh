#!/usr/bin/env bash
# tests/profile_ug_build.sh -- profile the User's Guide SVG build with gprof.
#
# What it does:
#   1. Saves the current optimised lout binary (if any) as lout.baseline.
#   2. Rebuilds lout with -pg and -fno-omit-frame-pointer (under -O3, -no-pie
#      at link time so gprof can resolve symbols on this Ubuntu host).
#   3. Runs doc/user/all under the instrumented lout, exactly the same
#      invocation as tests/user_guide_diff.sh stage 2 (the heavy SVG pass).
#   4. Runs gprof against the resulting gmon.out and writes two reports
#      under tests/profile/.
#   5. Restores the optimised binary so the regression suite stays clean.
#
# Output (committed):
#   tests/profile/gprof_full.txt     - full flat + call-graph report
#   tests/profile/gprof_brief.txt    - flat-only report (gprof -b)
#   tests/profile/gprof_z53_hot.txt  - just the z53.c rows from the flat
#                                      profile, sorted by self-time
#
# Notes:
#   * Wall time roughly 90 s (rebuild ~30 s + instrumented run ~36 s +
#     restore link ~3 s).
#   * Subsequent lout passes after the first one converge quickly and
#     write essentially empty SVGs (because the heavy galley work is
#     amortised once cross-references settle), so the single gmon.out
#     captured here represents the full SVG emission cost.
#   * Only pass-1 of the 7-pass cycle from user_guide_diff.sh is
#     profiled; that pass is the one that actually exercises every
#     z53.c emission path.
#   * Set MDLOUT_PROFILE_KEEP_PG=1 in the environment to leave the
#     instrumented binary in place after the script exits (handy when
#     iterating on gprof options).
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LOUT=$REPO/lout
USER_DIR=$LOUT/doc/user
OUT_DIR=$REPO/tests/profile

mkdir -p "$OUT_DIR"

if [[ ! -d "$LOUT" ]]; then
    echo "error: lout submodule not present at $LOUT" >&2
    exit 1
fi

cd "$LOUT"

# Stage 0: snapshot the current optimised binary, if any, so we can
# put it back at the end.
if [[ -x ./lout && ! -e ./lout.baseline ]]; then
    cp ./lout ./lout.baseline
fi

echo "==> rebuilding lout with -pg (this takes ~30 s)"
make clean > /dev/null
# Pass -pg via TRACING so the makefile's CFLAGS template (with all the
# -D defines) is preserved. The link step needs -pg too, plus -no-pie
# to dodge "DT_TEXTREL in a PIE" warnings/errors on modern toolchains.
make -j1 lout TRACING="-pg -fno-omit-frame-pointer" LDFLAGS="-pg -no-pie" \
    > "$OUT_DIR/build.log" 2>&1 || {
    echo "    initial link with -pg failed; retrying manual link with -no-pie..."
    gcc -pg -no-pie -O3 -o lout \
        z01.o z02.o z03.o z04.o z05.o z06.o z07.o z08.o z09.o z10.o \
        z11.o z12.o z13.o z14.o z15.o z16.o z17.o z18.o z19.o z20.o \
        z21.o z22.o z23.o z24.o z25.o z26.o z27.o z28.o z29.o z30.o \
        z31.o z32.o z33.o z34.o z35.o z36.o z37.o z38.o z39.o z40.o \
        z41.o z42.o z43.o z44.o z45.o z46.o z47.o z48.o z49.o z50.o \
        z51.o z52.o z53.o z53_glyph.o -lm
}

# Stage 1: clean the doc/user tree and run a single SVG pass under
# the instrumented binary. gmon.out lands in CWD = doc/user.
echo "==> running instrumented SVG build of doc/user/all"
cd "$USER_DIR"
rm -f ./*.li ./*.ldx gmon.out
START=$(date +%s)
"$LOUT/lout" -I "$LOUT/include" -I . -G all \
    > /tmp/mdlout_profile.svg 2> /tmp/mdlout_profile.err || true
END=$(date +%s)
echo "    wall: $((END - START))s, SVG bytes: $(stat -c%s /tmp/mdlout_profile.svg)"

if [[ ! -f gmon.out ]]; then
    echo "error: gmon.out not produced; profiling failed" >&2
    exit 1
fi

# Stage 2: gprof reports.
echo "==> running gprof"
gprof    "$LOUT/lout" gmon.out > "$OUT_DIR/gprof_full.txt"
gprof -b "$LOUT/lout" gmon.out > "$OUT_DIR/gprof_brief.txt"

# Stage 3: extract just the z53.c functions (everything starting with
# SVG_ or svg_) from the flat profile, sorted by self-time descending.
# The flat profile lives between "Flat profile:" and the call graph
# (separator "Call graph (explanation follows)"); awk handles both.
awk '
    /^Flat profile:/ { in_flat = 1; next }
    /^Call graph/    { in_flat = 0 }
    in_flat && NF >= 4 && $1 ~ /^[0-9]/ \
            && ($NF ~ /^SVG_/ || $NF ~ /^svg_/) { print }
' "$OUT_DIR/gprof_full.txt" \
    | sort -k3,3 -gr > "$OUT_DIR/gprof_z53_hot.txt"

# Restore the optimised binary so tests/run_all.sh stays at the
# regression-suite-passing baseline.
if [[ -z "${MDLOUT_PROFILE_KEEP_PG:-}" && -x "$LOUT/lout.baseline" ]]; then
    echo "==> restoring optimised lout binary"
    cp "$LOUT/lout.baseline" "$LOUT/lout"
fi

# Tidy: gmon.out + transient SVG/error tarpits.
rm -f "$USER_DIR/gmon.out" /tmp/mdlout_profile.svg /tmp/mdlout_profile.err

echo "==> done. Reports under $OUT_DIR/"
ls -la "$OUT_DIR"
echo
echo "Top z53.c functions:"
head -10 "$OUT_DIR/gprof_z53_hot.txt"
