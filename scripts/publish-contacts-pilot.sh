#!/usr/bin/env bash
# Capture school contacts and optionally merge into Comparison-tool index.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPARISON_TOOL="${COMPARISON_TOOL:-/tmp/Comparison-tool}"
LIMIT="${LIMIT:-12}"
LA="${LA:-Hampshire}"
MERGE="${MERGE:-0}"
OUTPUT="$ROOT/output/contact-capture.json"

if [[ ! -f "$COMPARISON_TOOL/public/data/schools-index.json" ]]; then
  echo "Comparison-tool index not found at $COMPARISON_TOOL" >&2
  echo "Clone it or set COMPARISON_TOOL=/path/to/Comparison-tool" >&2
  exit 1
fi

python3 -m school_capture.contact_cli \
  --comparison-tool "$COMPARISON_TOOL" \
  --la "$LA" \
  --require-website \
  --limit "$LIMIT" \
  --output "$OUTPUT"

python3 -c "
import json
p=json.load(open('$OUTPUT'))
s=p.get('stats') or {}
print('Contact capture:', s.get('withPhone',0), 'with phone,', s.get('withHeadteacher',0), 'with head,', s.get('withSenco',0), 'with SENCO')
"

if [[ "$MERGE" == "1" ]]; then
  python3 "$ROOT/scripts/merge-contacts.py" \
    --index "$COMPARISON_TOOL/public/data/schools-index.json" \
    --capture "$OUTPUT"
  echo "Merged contactCapture into $COMPARISON_TOOL/public/data/schools-index.json"
fi

echo "Wrote $OUTPUT"
