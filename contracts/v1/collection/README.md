# Collection contracts (additive RA-1A)

Six JSON Schema 2020-12 documents extend the offline contract surface without changing
the existing RA-0 documents or deploying an API:

- SafeFetchRequest: normalized URL, GET/HEAD, tenant/policy/run scope. Internal primitive
  requests can have a null run_id; Collector binds the real run before evidence output.
- FetchResponse: status, final URL, peer IP and bounded body hash/size metadata.
- RedirectTrace: reviewed hop, status, location and checked peer.
- PageInventory: candidate roles and discovery provenance; not a completeness assertion.
- CaptureManifest: versioned scope, robots, page snapshots, evidence, limits, errors and
  coverage. Embedded RA-0 shapes retain their original semantics.
- CollectionError: fixed error code and trace, without untrusted remote error text.

Structural validation is followed by CaptureBundle.verify() for cross-object and hash
consistency. Neither establishes semantic truth. FETCHED is transport evidence only.
Raw HTML retention is disabled by default; the manifest makes retained objects explicit.
See docs/03-engineering/RA1A_IMPLEMENTATION_AND_ACCEPTANCE.md for the trusted adapter
boundary and reproducible isolated tests. Do not run a public collection from these examples.
