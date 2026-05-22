#!/usr/bin/env bash
# bench.sh -- thin shell wrapper around tests/bench.py.
#
# Run on demand or via `bash tests/run_all.sh --bench`. Forwards all
# extra args (e.g. --strict, --snippets foo,bar) through to bench.py.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Optional tool warnings; bench.py itself records None for missing tools.
have() { command -v "$1" >/dev/null 2>&1; }
MISSING=""
for t in ps2pdf rsvg-convert; do
   have "$t" || MISSING="${MISSING} ${t}"
done
if [[ -n "${MISSING}" ]]; then
   echo "bench.sh: WARNING missing optional tool(s):${MISSING}" >&2
fi

exec python3 "${SCRIPT_DIR}/bench.py" "$@"
