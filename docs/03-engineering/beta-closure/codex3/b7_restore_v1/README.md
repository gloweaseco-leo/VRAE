# Issue101 deterministic recovery candidate

Accepted starting main: `b9aec4e8379e6978de4177d67d64fde53d1d58ab`.

Run from repository root with a native Python 3.11 or 3.13 environment containing
`requirements-ra4b-p1.lock`:

```
python -B -m integration.beta_review.codex3.b7_restore_v1.run --run-id local-311-v1
```

The runner uses three independent pinned PostgreSQL16 containers, isolated volumes,
`network=none`, and loopback-only authenticated host access. A byte-only local
socket forwards each native psycopg connection through `docker exec busybox nc`
to the real PostgreSQL listener. PostgreSQL performs all SCRAM authentication;
there is no SQL parsing, protocol emulation, identity substitution or external NIC.
Only accepted disposable migration/seed hooks initialize roles and fixtures.
Destination bootstrap databases are dropped before `pg_restore --create --exit-on-error`;
ACLs and owners are restored, never replaced with no-owner/no-acl flags.
A second genuine dump from the verification stage feeds the final target.

Snapshots contain complete row JSON (including full BYTEA hex) privately, table byte
hashes, columns/defaults/PK/constraints/indexes/sequences/functions/triggers,
role attributes/memberships, RLS/FORCE/policies, DB/schema/table/column/default ACLs,
and effective table/column/schema permissions. Raw NULL/empty/explicit ACLs are
retained. Semantic comparisons expand PostgreSQL defaults only for SQL NULL,
retain empty ACLs as empty, and compare grantor/grantee/privilege/grantability.
No restore-time permission, policy, function or old-table repair is attempted.

B3 checks use the accepted native SQL test port with actual Reviewer logins and
original `Receipt` parsing, committed receipt bytes, expired witnesses and a
noncurrent witness epoch. Original B2 cryptographic key-revocation and expired-token
negatives reject before any DB connection; they do not claim positive B2 login. The B3 Python facade and B2 signed HTTP identity are
NOT_TESTED here: their frozen disposable database-name contract differs from B4's
fixed database binding. No database-name spoofing or connection-info wrapper exists.
The source-only authority cycle uses the accepted B4 fixture hook after its sole
old job is already DONE. That completed old-epoch job is never eligible. Only one
current-epoch expired lease is backed up. A fresh unchanged Worker process reclaims
it after restoration; the actual SIGKILL victim's old token cannot finish it.
An independently admitted new current-epoch task is then completed. The sealed
404/200 reports are accepted samples, not newly generated Worker diagnostics.
Dead-letter data is ZERO/NOT_TESTED unless actually present; all empty tables are
listed explicitly in the snapshot evidence.

Predetermined negative cases are a real failing pg_dump, a real failing pg_restore,
a restore omitting a required schema, cross-tenant reads/writes, cross-version B3,
expired/stale authority, and a separately held byte candidate read by Reviewer with
its HTML changed while retaining the original sealed manifest/hash. The latter
uses the original byte verifier and never disables database immutable triggers.

Private logs, dumps, credentials, native JUnit and byte candidates are excluded by
the new directory's `.gitignore`. Public JUnit contains only names/statuses; its
native original hash is retained. Public output is credential-scanned and inventoried
before CI upload. Observe measured lab durations only; no production RTO/RPO SLA.
Resource cleanup requires exact resource membership plus per-environment labels.

This is a TEST_ONLY subpackage candidate, not full B7 EXIT or Beta release. Old
Issue91/93/A1 stays PAUSED, MAX3 0/3 unchanged; no UUID ordering experiment occurs.
Gold remains 0/26, G1-G3 NO-GO, full Beta 2/7. Owner alone may accept or merge.

## Retained initial fixture RED

`local-311-v1`, source `7fd097fcd3e6356f2087a38448e898a8c399c8b9`:
native pytest exit 1 before migrations because this Docker engine does not publish
ports for an internal network. Its sole owned container/volume were destroyed;
no business or permission test ran. This new-container transport problem is L1/L2,
not a permission repair. The corrected revision uses network-none byte forwarding.
The original RED JUnit, process log digest and cleanup record remain alongside it.

`local-311-v2`, source `dfca7cb3c5f63bac34ef314f6199281e27888d5c`:
three independent PG16 clusters and all six-schema original bootstrap hooks ran;
B3 404/200 fixture submissions committed. The new Worker source whitelist omitted
accepted `contracts/` JSON schemas, so the original source verifier refused config
provisioning before spawning Worker. This is a new fixture source-packaging error;
no original permissions or schema were changed. All three clusters were destroyed.
The whitelist correction adds only tracked, accepted contracts from this checkout.

The no-DB source-bundle preflight at `20e09af48f101f05cf96ab90c47ea4c4bd156894`
returned native exit 1 for a second omitted accepted resource,
`industry-packs/rule_catalog.v1.json`. This was not another PG/full recovery run.
The terminal retained its diagnostic tail; a complete raw preflight log was not
saved for that initial check. The runner now records native preflight output and
exit before starting any PostgreSQL resource, with the tracked accepted catalog
included. No same-source full recovery run is retried.
