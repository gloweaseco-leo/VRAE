# EvidencePack 1.0

Additive RA-2A contract. Existing Evidence/PageSnapshot, CaptureManifest and
BrowserObservation meanings remain unchanged. A derived snapshot_ref/evidence_ref
is NOT an original RA-0 ID; source_snapshot_id/source_evidence_id preserve the
original IDs (null where BrowserObservation never had one).

Use build_pack with verified source bundles. EvidencePack.load/verify re-runs both
source verifiers, validates blob hashes and rebuilds the entire deterministic
projection. Schema validation alone does not verify graph edges or source bodies.
Resolve with an expected pack identity from a trusted caller; recalculating a
wrapper hash cannot repair a broken source edge, scope, locator or coverage row.

Locators are exact JSON pointers into the embedded source document, not arbitrary
CSS selectors. HTTP_BODY points to the original evidence record whose only
admitted producer locator is http-response-body. Browser pointers select the
original DOM/screenshot reference. No HTML parsing, image OCR, rule or Finding
generation occurs. Browser DOM URL and PNG viewport dimensions are checked before
OBSERVED artifacts are admitted; this is not full PNG validation or proof of rendering.
HTTP capture_mode must remain HTTP; unverified legacy excerpts are rejected because
the current HTTP producer emits excerpt=null and does not verify natural-language text.

OBSERVED means a bounded source observation, never commercial completeness.
UNKNOWN means attempted/incomplete or unverified role, ACCESS_BLOCKED preserves
denials; NOT_VISITED means an identified inventory URL/approved viewport was not
observed. Roles with no discovered URL are UNKNOWN, not invented NOT_VISITED URLs.
NOT_APPLICABLE is explicitly reserved but rejected by v1 assembly/schema: no
applicability decision source exists in this work package. It must not be inferred
from missing pages; future applicability support needs a versioned, grounded contract.

All data remain private, including paths/DOM/screenshots. OBSERVED HTTP metadata
without retained HTML carries RAW_BODY_NOT_RETAINED and resolve returns content=null;
it cannot establish text/link facts from a digest. Incomplete browser artifacts may
be retained for audit with UNKNOWN/ACCESS_BLOCKED, but resolve refuses them.

Hashes establish consistency/content addressing, not remote authenticity or current
authorization. SourcePolicy identity/version is bound; no policy is reauthorized,
no source is fetched, and no identity, DB, storage, retention or signing service exists.
Original source arrays retain order; source bundle input ordering does not affect
the resulting pack. Same-source duplicates or overlapping old/new captures in a
single mode/URL/viewport are rejected rather than silently merged.

Limits: 16 source bundles, 8MB canonical document, 512 blobs/64MB total, with bounded
snapshot/evidence/coverage arrays. Public views are detached copies/read-only bytes.
This is in-process immutability, not protection against a hostile Python process
using reflection or unauthorized rewriting of files. No persistence is performed.
