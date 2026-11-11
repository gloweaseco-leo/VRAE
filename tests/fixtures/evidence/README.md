# Independently replayable synthetic EvidencePack

Run `python scripts/verify_ra2a.py` from the repository root. The checked-in file
contains the exact source manifests and base64 objects, so its integrity can be
checked without network/browser execution or the original mutable source objects.
The script also verifies deterministic reconstruction from the synthetic fixtures.
Use `--write-example` only to deliberately regenerate the synthetic fixture.

combined.json contains one HTTP source and one offline BrowserObservation source,
with a synthetic DOM and generated blank PNG matching the viewport dimensions.
These bytes exercise contracts; they do NOT claim real Chromium rendering.
Actual Chromium containment remains covered by the separate existing CI job.

Resolve an evidence_ref with the pinned expected_pack_ref. The returned snapshot,
source_record and content connect to exact source_ref/document_sha256, original
source IDs, JSON pointer, status, timestamp and bytes. Verify the pack first;
never upgrade absence/unknown/blocked states into a business fact.
