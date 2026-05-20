#!/usr/bin/env bash
# run_compare.sh -- per-snippet PS vs SVG rendering and diff.
#
# For each .lt in tests/snippets/, this script:
#   1. Runs lout to produce PostScript (out/<name>.ps).
#   2. Runs lout -G to produce SVG (out/<name>.svg).
#   3. Rasterizes both to PNG at 150dpi.
#   4. Runs ImageMagick `compare` to emit a diff PNG and an AE pixel count.
#   5. Appends a status line to out/results.txt.
#
# Designed to be tolerant of per-snippet failures: missing/incomplete SVG
# support in z53.c should not abort the whole run.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOUT_DIR="${REPO_DIR}/lout"
LOUT_BIN="${LOUT_DIR}/lout"
SNIP_DIR="${SCRIPT_DIR}/snippets"
OUT_DIR="${SCRIPT_DIR}/out"
RESULTS="${OUT_DIR}/results.txt"

DPI=150
FUZZ=2%

mkdir -p "${OUT_DIR}"
: > "${RESULTS}"

# Tool availability check (don't abort if some missing -- record gaps).
have() { command -v "$1" >/dev/null 2>&1; }
MISSING=""
for t in gs rsvg-convert compare; do
   have "$t" || MISSING="${MISSING} ${t}"
done
if [[ -n "${MISSING}" ]]; then
   echo "WARNING: missing tools:${MISSING}" | tee -a "${RESULTS}"
fi

if [[ ! -x "${LOUT_BIN}" ]]; then
   echo "FATAL: lout binary not found at ${LOUT_BIN}" | tee -a "${RESULTS}"
   echo "Run \`cd ${LOUT_DIR} && make lout\` first." | tee -a "${RESULTS}"
   exit 2
fi

# Run lout with the in-tree library paths so we don't need `make install`.
run_lout() {
   "${LOUT_BIN}" \
      -I "${LOUT_DIR}/include" \
      -D "${LOUT_DIR}/data" \
      -F "${LOUT_DIR}/font" \
      -C "${LOUT_DIR}/maps" \
      -H "${LOUT_DIR}/hyph" \
      "$@"
}

# Format: name<TAB>status<TAB>ae<TAB>ps_bytes<TAB>svg_bytes<TAB>note
printf 'snippet\tstatus\tae\tps_bytes\tsvg_bytes\tnote\n' > "${RESULTS}"

shopt -s nullglob
SNIPPETS=( "${SNIP_DIR}"/*.lt )
if [[ ${#SNIPPETS[@]} -eq 0 ]]; then
   echo "No snippets found in ${SNIP_DIR}" | tee -a "${RESULTS}"
   exit 1
fi

TOTAL=0
COMPLETED=0
for lt in "${SNIPPETS[@]}"; do
   name="$(basename "${lt}" .lt)"
   TOTAL=$((TOTAL + 1))
   ps="${OUT_DIR}/${name}.ps"
   svg="${OUT_DIR}/${name}.svg"
   ps_png="${OUT_DIR}/${name}.ps.png"
   svg_png="${OUT_DIR}/${name}.svg.png"
   diff_png="${OUT_DIR}/${name}.diff.png"
   ps_err="${OUT_DIR}/${name}.ps.err"
   svg_err="${OUT_DIR}/${name}.svg.err"

   note=""
   ae="-"
   status="OK"

   # 1) PostScript output (suppress crossref database side files via -s).
   if ! ( cd "${OUT_DIR}" && run_lout -s -o "${ps}" "${lt}" ) 2> "${ps_err}"; then
      status="PS_FAIL"
      note="lout PS failed"
   fi

   # 2) SVG output.
   if [[ "${status}" == "OK" ]]; then
      if ! ( cd "${OUT_DIR}" && run_lout -s -G -o "${svg}" "${lt}" ) 2> "${svg_err}"; then
         status="SVG_FAIL"
         note="lout SVG failed"
      fi
   fi

   ps_bytes=0; svg_bytes=0
   [[ -f "${ps}"  ]] && ps_bytes=$(stat -c%s "${ps}")
   [[ -f "${svg}" ]] && svg_bytes=$(stat -c%s "${svg}")

   # 3) Rasterize PS -> PNG (first page).
   if [[ "${status}" == "OK" && -s "${ps}" ]]; then
      if ! gs -q -dSAFER -dNOPAUSE -dBATCH \
              -sDEVICE=png16m -r${DPI} \
              -dFirstPage=1 -dLastPage=1 \
              -sOutputFile="${ps_png}" "${ps}" \
              > "${OUT_DIR}/${name}.gs.err" 2>&1; then
         status="GS_FAIL"
         note="gs rasterize failed"
      fi
   fi

   # 4) Rasterize SVG -> PNG.
   if [[ "${status}" == "OK" && -s "${svg}" ]]; then
      if ! rsvg-convert -d ${DPI} -p ${DPI} -f png \
                       -o "${svg_png}" "${svg}" \
                       2> "${OUT_DIR}/${name}.rsvg.err"; then
         status="RSVG_FAIL"
         note="rsvg-convert failed"
      fi
   fi

   # 5) Compare. Force same canvas size by extent-padding via convert if
   #    necessary; ImageMagick handles mismatched sizes by reporting fail,
   #    so we resize the SVG render to the PS render's geometry.
   if [[ "${status}" == "OK" && -s "${ps_png}" && -s "${svg_png}" ]]; then
      # Get PS canvas size.
      geom=$(identify -format '%wx%h' "${ps_png}" 2>/dev/null || echo "")
      svg_resized="${OUT_DIR}/${name}.svg.norm.png"
      if [[ -n "${geom}" ]]; then
         convert "${svg_png}" -background white -gravity northwest \
                 -extent "${geom}" "${svg_resized}" \
                 2> "${OUT_DIR}/${name}.convert.err" || cp "${svg_png}" "${svg_resized}"
      else
         cp "${svg_png}" "${svg_resized}"
      fi
      ae=$(compare -metric AE -fuzz ${FUZZ} \
             "${ps_png}" "${svg_resized}" "${diff_png}" 2>&1 || true)
      # `compare` prints the AE pixel count to stderr; clean it.
      ae="${ae//[^0-9]/}"
      [[ -z "${ae}" ]] && ae="-"
      COMPLETED=$((COMPLETED + 1))
   fi

   printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "${name}" "${status}" "${ae}" "${ps_bytes}" "${svg_bytes}" "${note}" \
      >> "${RESULTS}"
   printf '  %-22s  %-9s  AE=%s\n' "${name}" "${status}" "${ae}"
done

echo ""
echo "Snippets total:     ${TOTAL}"
echo "Reached compare:    ${COMPLETED}"
echo "Results table:      ${RESULTS}"
