#!/usr/bin/env bash
# Publish data assets for the evidence prototype viewer (docs/evidence/).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_CAPTURE="${SRC_CAPTURE:-$ROOT/docs/data/qualitative-capture.json}"
EVIDENCE_DATA="$ROOT/docs/evidence/data"
LEARNED_OUT="$EVIDENCE_DATA/learned-url-terms.json"

mkdir -p "$EVIDENCE_DATA"

if [[ ! -f "$SRC_CAPTURE" ]]; then
  echo "Missing capture data at $SRC_CAPTURE" >&2
  echo "Run ./scripts/publish-pilot.sh first or set SRC_CAPTURE=" >&2
  exit 1
fi

cp "$SRC_CAPTURE" "$EVIDENCE_DATA/qualitative-capture.json"
python3 "$ROOT/scripts/build-learned-terms-from-capture.py" \
  "$EVIDENCE_DATA/qualitative-capture.json" \
  --output "$LEARNED_OUT"

echo "Published evidence prototype data to $EVIDENCE_DATA"
