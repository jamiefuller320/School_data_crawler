# Remaining steps after PR #10 (School_data_crawler)

`main` now includes Phase 3, contact capture, hub-and-spoke discovery, and the Comparison-tool handover assets.

## Done automatically

- [x] [PR #10](https://github.com/jamiefuller320/School_data_crawler/pull/10) merged to `main`
- [x] GitHub Pages deploy triggered (pilot viewer)
- [x] `pytest` passing on `main` (33 tests)

## Comparison-tool (manual — agent cannot push to that repo)

Run on your machine where you have write access to `jamiefuller320/Comparison-tool`:

```bash
# 1. Clone/update Comparison-tool
git clone https://github.com/jamiefuller320/Comparison-tool.git
cd Comparison-tool
git checkout main && git pull

# 2. Apply handover from School_data_crawler (after pulling latest main)
/path/to/School_data_crawler/scripts/handover-comparison-tool.sh "$(pwd)"

# Or manually:
git checkout -b cursor/visit-pack-contacts-f652
git apply /path/to/School_data_crawler/handover/comparison-tool-patches/0001-*.patch
npm run test:visit-pack
git add -A && git commit -m "Visit pack school contacts and preserve telephone in harvest"
git push -u origin cursor/visit-pack-contacts-f652
gh pr create --title "Visit pack school contacts and preserve telephone in harvest" \
  --body "Shows contactCapture in visit packs. Keeps telephone in LEAN_KEYS. Handover from School_data_crawler PR #10."
gh pr merge --merge
```

## Populate contact data in schools-index

After the Comparison-tool UI PR is merged (or on a branch):

```bash
cd /path/to/School_data_crawler
MERGE=1 LIMIT=12 LA=Hampshire COMPARISON_TOOL=/path/to/Comparison-tool \
  ./scripts/publish-contacts-pilot.sh

# Full LA (slow — downloads GIAS Edubase once):
MERGE=1 LIMIT=607 LA=Hampshire COMPARISON_TOOL=/path/to/Comparison-tool \
  ./scripts/publish-contacts-pilot.sh
```

Commit the updated `public/data/schools-index.json` in Comparison-tool when ready.

## Optional: DfE telephone on next harvest

After the `LEAN_KEYS` patch is in Comparison-tool:

```bash
cd Comparison-tool
python3 scripts/harvest-schools.py --la Hampshire
# then your usual enrich chain (websites, Ofsted, etc.)
```

## Optional: re-run qualitative pilot with new discovery

```bash
cd School_data_crawler
LIMIT=12 COMPARISON_TOOL=/path/to/Comparison-tool ./scripts/publish-pilot.sh
git add docs/data/qualitative-capture.json && git commit -m "Refresh Hampshire pilot with hub-and-spoke discovery"
git push origin main
```
