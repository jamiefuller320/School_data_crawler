#!/usr/bin/env bash
# Run a bounded pilot capture and publish results to docs/data for GitHub Pages.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPARISON_TOOL="${COMPARISON_TOOL:-/tmp/Comparison-tool}"
LIMIT="${LIMIT:-12}"
LA="${LA:-Hampshire}"
COPY_ONLY="${COPY_ONLY:-0}"
OUTPUT="$ROOT/output/pilot-qualitative-capture.json"
DOCS_DATA="$ROOT/docs/data/qualitative-capture.json"

mkdir -p "$(dirname "$DOCS_DATA")"

if [[ "$COPY_ONLY" == "1" ]]; then
  if [[ ! -f "$OUTPUT" ]]; then
    echo "No existing output at $OUTPUT" >&2
    exit 1
  fi
else
  if [[ ! -f "$COMPARISON_TOOL/public/data/schools-index.json" ]]; then
    echo "Comparison-tool index not found at $COMPARISON_TOOL" >&2
    echo "Clone it or set COMPARISON_TOOL=/path/to/Comparison-tool" >&2
    exit 1
  fi

  python3 -m school_capture.cli \
    --comparison-tool "$COMPARISON_TOOL" \
    --la "$LA" \
    --require-website \
    --limit "$LIMIT" \
    --no-social \
    --output "$OUTPUT"
fi

cp "$OUTPUT" "$DOCS_DATA"
echo "Published pilot data to $DOCS_DATA"
