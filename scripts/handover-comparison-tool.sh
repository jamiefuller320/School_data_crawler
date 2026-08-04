#!/usr/bin/env bash
# Apply School_data_crawler handover changes into a local Comparison-tool checkout.
#
# Usage:
#   ./scripts/handover-comparison-tool.sh /path/to/Comparison-tool
#   COMPARISON_TOOL=/path/to/Comparison-tool MERGE_CONTACTS=1 ./scripts/handover-comparison-tool.sh
#
# Options (env):
#   COMPARISON_TOOL   — path to Comparison-tool repo (or pass as first argument)
#   SKIP_PATCH        — set to 1 to skip git am (if you already applied the patch)
#   RUN_HARVEST       — set to 1 to re-harvest Hampshire after patch (slow; needs DfE API)
#   CAPTURE_CONTACTS  — set to 1 to run contact capture + merge (default 1)
#   MERGE_CONTACTS    — set to 1 to merge contact-capture into schools-index (default 1 with CAPTURE)
#   LIMIT             — schools for contact pilot (default 12)
#   LA                — local authority filter (default Hampshire)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPARISON_TOOL="${1:-${COMPARISON_TOOL:-}}"
PATCH_DIR="$ROOT/handover/comparison-tool-patches"
PATCH_FILE="$PATCH_DIR/0001-Visit-pack-contacts-and-preserve-telephone-in-harves.patch"

CAPTURE_CONTACTS="${CAPTURE_CONTACTS:-1}"
MERGE_CONTACTS="${MERGE_CONTACTS:-1}"
LIMIT="${LIMIT:-12}"
LA="${LA:-Hampshire}"

if [[ -z "$COMPARISON_TOOL" ]]; then
  echo "Usage: $0 /path/to/Comparison-tool" >&2
  echo "  or:  COMPARISON_TOOL=/path/to/Comparison-tool $0" >&2
  exit 1
fi

if [[ ! -d "$COMPARISON_TOOL/.git" ]]; then
  echo "Not a git repo: $COMPARISON_TOOL" >&2
  exit 1
fi

if [[ ! -f "$PATCH_FILE" ]]; then
  echo "Patch not found: $PATCH_FILE" >&2
  exit 1
fi

echo "==> Comparison-tool handover"
echo "    Repo: $COMPARISON_TOOL"
echo "    Patch: $PATCH_FILE"

cd "$COMPARISON_TOOL"

if [[ "${SKIP_PATCH:-0}" != "1" ]]; then
  if git apply --check "$PATCH_FILE" 2>/dev/null; then
    echo "==> Applying patch (git apply)..."
    git apply "$PATCH_FILE"
  elif git am --3way "$PATCH_FILE" 2>/dev/null; then
    echo "==> Applied patch (git am)"
  else
    echo "Patch failed — you may already have these changes. Try SKIP_PATCH=1" >&2
    git status -sb
    exit 1
  fi
else
  echo "==> Skipping patch (SKIP_PATCH=1)"
fi

echo "==> Running visit pack tests..."
npm run test:visit-pack

if [[ "${RUN_HARVEST:-0}" == "1" ]]; then
  echo "==> Re-harvesting $LA (populates telephone from DfE API)..."
  python3 scripts/harvest-schools.py --la "$LA"
  echo "    Re-run enrich passes if you normally chain them (websites, Ofsted, etc.)."
fi

if [[ "$CAPTURE_CONTACTS" == "1" ]]; then
  echo "==> Capturing contacts from School_data_crawler (limit=$LIMIT, la=$LA)..."
  export COMPARISON_TOOL
  export LIMIT LA
  export MERGE="$MERGE_CONTACTS"
  "$ROOT/scripts/publish-contacts-pilot.sh"
fi

cat <<'EOF'

==> Handover complete.

What changed in Comparison-tool:
  • scripts/harvest-schools.py — telephone kept in LEAN_KEYS
  • src/lib/types.ts — ContactCaptureRecord on SchoolRecord
  • src/lib/visitPack.ts — contact lines for visit pack
  • src/components/VisitPack.tsx — display phone, email, head, SENCO + sources
  • src/app/globals.css — contact list styles

Next steps (manual):
  1. Review: git diff
  2. Commit: git checkout -b feature/visit-pack-contacts && git add -A && git commit
  3. Full LA harvest (optional): RUN_HARVEST=1 ./scripts/handover-comparison-tool.sh ...
  4. Open visit pack in dev server and check a school with contactCapture merged

School_data_crawler PRs (merge first if not on main):
  • #8 contact capture sidecar
  • #9 hub-and-spoke curriculum discovery + learned URL terms
  • #7 phase 3 documents (if not merged)

EOF
