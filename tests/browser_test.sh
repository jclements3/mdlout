#!/usr/bin/env bash
# browser_test.sh -- thin wrapper around browser_test.py.
#
# Exits 0 on all-pass, 1 on any failure, 77 when no Chromium binary is
# available (autotools "skipped" convention -- friendly for CI).
#
# Forwards CLI args verbatim, so:
#   tests/browser_test.sh                            # all examples in examples/out/
#   tests/browser_test.sh --only 04_math.html,05_music.html
#   tests/browser_test.sh --html-dir /tmp/foo --out /tmp/manifest.json
#
# Environment:
#   MDLOUT_CHROME=/path/to/chrome      # override auto-detection

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${SCRIPT_DIR}/browser_test_manifest.json"

echo "==> tests/browser_test.sh"
python3 "${SCRIPT_DIR}/browser_test.py" "$@"
rc=$?

if [[ ${rc} -eq 77 ]]; then
   echo "==> SKIP (no chromium); manifest at ${MANIFEST}"
   exit 77
fi

if [[ -f "${MANIFEST}" ]]; then
   # Print compact summary from the manifest.
   python3 - "${MANIFEST}" << 'PY' || true
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)
if data.get("status") == "skipped":
    print(f"==> skipped: {data.get('reason')}")
    sys.exit(0)
print(f"==> summary: pass={data['pass']} fail={data['fail']} total={data['total']}")
fails = [e for e in data['examples'] if not e['ok']]
if fails:
    print("==> failures:")
    for e in fails:
        bad = [c for c in e['checks'] if not c['ok']]
        names = ",".join(c['name'] for c in bad) if bad else "(driver error)"
        print(f"     {e['name']:32s}  failed: {names}")
        if e.get('error'):
            print(f"        error: {e['error']}")
        for c in bad:
            if c.get('detail'):
                print(f"        {c['name']}: {c['detail']}")
PY
fi

exit ${rc}
