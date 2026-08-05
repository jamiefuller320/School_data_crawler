# Comparison-tool handover

School contact capture and visit-pack UI live in **two repos**. This repo (`School_data_crawler`) produces the `contactCapture` sidecar; **Comparison-tool** displays it and should preserve `telephone` from the DfE harvest.

## Comparison-tool handover

School contact capture, qualitative website evidence, and visit-pack UI integrate into **Comparison-tool**. This repo produces sidecars; Comparison-tool displays them.

### Monorepo migration (v0.6.0)

Apply the latest patch (school capture + LLM synthesis + Website evidence UI):

```bash
cd /path/to/Comparison-tool
git checkout -b cursor/school-capture-monorepo-f652
git apply /path/to/School_data_crawler/handover/comparison-tool-patches/0001-Add-school-capture-monorepo*.patch
pip install -r requirements-data.txt
npm run test:qualitative-evidence
```

Or cherry-pick / push branch `cursor/school-capture-monorepo-f652` if already created locally.

Enrichment from Comparison-tool root:

```bash
python3 scripts/enrich-qualitative.py --la Hampshire --require-website --limit 12
python3 scripts/enrich-qualitative.py --la Hampshire --limit 12 --synthesize  # OPENAI_API_KEY
python3 scripts/enrich-contacts.py --la Hampshire --require-website --limit 12
```

## Quick apply (visit-pack contacts — already on Comparison-tool main)

```bash
# From School_data_crawler root, with Comparison-tool cloned alongside or anywhere:
./scripts/handover-comparison-tool.sh ../Comparison-tool

# Skip patch if you already applied it; only capture + merge:
SKIP_PATCH=1 COMPARISON_TOOL=../Comparison-tool ./scripts/handover-comparison-tool.sh

# Also re-harvest Hampshire so telephone flows from DfE API (slow):
RUN_HARVEST=1 ./scripts/handover-comparison-tool.sh ../Comparison-tool
```

## What the patch contains

| File | Change |
|------|--------|
| `scripts/harvest-schools.py` | Add `telephone` to `LEAN_KEYS` |
| `src/lib/types.ts` | `ContactEntry`, `ContactCaptureRecord`, `SchoolRecord.contactCapture` |
| `src/lib/visitPack.ts` | `contactLinesForRecord()`, extended `VisitContactRow` |
| `src/components/VisitPack.tsx` | Show contacts with source links (screen + print) |
| `src/app/globals.css` | `.visit-contact-lines` styles |
| `scripts/test-visit-pack.mjs` | Test contact merge on visit row |

Patch file: `handover/comparison-tool-patches/0001-Visit-pack-contacts-and-preserve-telephone-in-harves.patch`

Manual apply:

```bash
cd /path/to/Comparison-tool
git apply /path/to/School_data_crawler/handover/comparison-tool-patches/0001-*.patch
npm run test:visit-pack
```

## End-to-end workflow

```bash
# 1. Capture contacts (this repo)
python3 -m school_capture.contact_cli \
  --comparison-tool ../Comparison-tool \
  --la Hampshire --require-website --limit 12

# 2. Merge into schools-index
python3 scripts/merge-contacts.py \
  --index ../Comparison-tool/public/data/schools-index.json \
  --capture output/contact-capture.json

# 3. (Comparison-tool) Re-harvest to populate telephone from DfE
cd ../Comparison-tool && python3 scripts/harvest-schools.py --la Hampshire

# 4. Verify visit pack in Comparison-tool dev server
```

Or use the all-in-one helper:

```bash
./scripts/publish-contacts-pilot.sh          # capture only
MERGE=1 ./scripts/publish-contacts-pilot.sh  # capture + merge into index
```

## Qualitative + documents (same pattern)

| Sidecar | Merge script | Comparison-tool field (planned) |
|---------|--------------|----------------------------------|
| `output/qualitative-capture.json` | `scripts/merge-qualitative.py` | `qualitativeCapture` |
| `output/contact-capture.json` | `scripts/merge-contacts.py` | `contactCapture` |

## Dependency on School_data_crawler PRs

Merge these into `School_data_crawler` `main` before relying on production capture:

- **PR #8** — contact capture engine (`contact_cli`, GIAS + website scrape)
- **PR #9** — hub-and-spoke curriculum discovery, learned URL terms
- **PR #7** — site document scan (optional; separate from contacts)
