#!/usr/bin/env bash
# run_all.sh -- orchestrate the full regression run:
#   1. run_compare.sh  produces PS, SVG, rasters, diffs, results.txt
#   2. compare.py      adds SSIM/pixel ratios, emits results.json + report.html
#
# Does not launch a browser; just prints the path of the report.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> running run_compare.sh"
bash "${SCRIPT_DIR}/run_compare.sh"
rc=$?
if [[ ${rc} -ne 0 ]]; then
   echo "run_compare.sh exited with ${rc}; continuing to compare.py anyway"
fi

echo ""
echo "==> running compare.py"
python3 "${SCRIPT_DIR}/compare.py"

REPORT="${SCRIPT_DIR}/report.html"
echo ""
if [[ -f "${REPORT}" ]]; then
   echo "Report written to: ${REPORT}"
   echo "Open with:  xdg-open \"${REPORT}\""
fi

# Append a record to tests/history.jsonl and regenerate tests/history.html.
echo ""
echo "==> running history.py"
python3 "${SCRIPT_DIR}/history.py"
