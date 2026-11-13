# B7-P0 disposable PostgreSQL recovery

Entry: accepted main `4fd1ce15f4bc2e596111aa2e8fe86a2a46ba640d`.
Authority: Owner Issue #81 comment 6853193972, TEST_ONLY restore precursor.

Two independently labelled PG16 containers, volumes and dedicated loopback-published
networks are provisioned. Existing migrations 0001–0003 and public synthetic
fixture helpers are reused without changing their source. No B4/0004 is used.
Dedicated bridges are not a proof of kernel egress isolation; no external site,
issuer, model, API/Worker/SSR service or production credential is used.

Full custom-format `pg_dump` archives stay in ignored `integration/ra4e/.runtime/`
only and must never be committed or uploaded. Public evidence contains hashes,
counts, SQLSTATEs, catalog metadata and sanitized command results, never raw
evidence bytes, tokens, database passwords or private signing keys.

Expected manifests are captured before backup from independent accepted source
fixtures plus live source SQL data/catalog/sequence fingerprints. A restore cannot
publish a success receipt until import, independent source verification and exact
manifest checks pass. Partial/unverified destinations are not runtime-ready.

Destination roles are freshly provisioned through unchanged accepted migrations;
runtime credentials are independently generated. Cluster credentials are not in a
database dump. B2's persisted principal/assignment rows are recoverable; issuer
private keys, trust provisioning and process-local replay storage are not. A new
test issuer/trust boundary must reject the old token and verify a fresh one.

The legacy 0001 raw SELECT grants to ra4a_app/ra4a_worker remain acknowledged
security debt. Restoring their original ACL/RLS is compatibility evidence, not
production least-privilege approval. No native human approval or ShareGrant exists.

No results are predeclared. Local/hosted receipts must identify the actual source,
ordered merge parents, expected roots, every executed negative and owned teardown.
Full B7, G1/G2/G3, deployment, cloud provisioning and real backups remain blocked.
