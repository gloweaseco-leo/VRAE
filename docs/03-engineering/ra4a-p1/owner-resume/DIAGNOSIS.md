# Bounded startup diagnosis and repair

Owner authority: https://github.com/gloweaseco-leo/VRAE/pull/63#issuecomment-6827379191

The original hosted HEAD 469ccb6 remains preserved. Its six logs/security ZIP
and blocked receipts are also copied byte-for-byte into the previous-head archive;
SHA256 19dfdbdb18e7ab1675a0e1e9f5cc911cc607d9b2db7e954173724ba4bbbc50fa.

Before changing readiness behavior, the diagnostics-only lab snapshot
(SHA256 72310872c886941802246f83466586f33ae893f78e4e804a2c402beec6f176bf)
reproduced the same psql exit 2 locally in diagnose-original-gate-02/startup.jsonl.
Actual stderr: server closed the connection unexpectedly. The same container's
bounded logs show temporary PID85 listening on Unix socket, accepting connections,
FATAL target database does not exist, CREATE DATABASE, fast shutdown and a new
PID1 PostgreSQL server starting with TCP listeners. This establishes the temporary
initialization server/readiness race for the local reproduction. Original hosted
jobs lacked stderr/init logs, so their exact initiating error remains unproven;
the identical call/exit and this reproduction support the same mechanism, not proof
of the specific original hosted stderr. No auth/runner outage is inferred.

Repair is confined to infra/ra4a lab/negative harness and the new PG workflow.
Readiness requires authenticated TCP SQL against vrae_ra4a_p1, exact dbname and
PG16 version, pinned image digest, loopback publication, a maximum 60s deadline,
bounded command timeouts and fail-closed non-transient errors. The temporary
initialization server has no TCP listener. SCRAM init setting, SQL, RLS, business
contracts, all 54 PG cases and original 11 pure tests are unchanged.

Non-secret ownership receipt exists before resource creation. Each actual cleanup
checks exact random own names and TEST_ONLY labels, records rm return codes and
daemon-confirmed absence; permission/daemon errors cannot stand for absence.
The always workflow teardown reads ownership even without password STATE. Startup
diagnostics and failure proof are always uploaded separately from test outputs.
Passwords only travel in temporary env file/ignored STATE/stdin; neither Env nor
unrestricted inspect/DB contents are exported. Output is bounded and secrets are
redacted. Dedicated bridge is not an egress sandbox.

Negative harness deliberately uses a zero startup deadline after actual Docker
resource creation. This is labeled a harness failure, zero business tests.
failure-cleanup-probe retained an actual RED: Docker network inspect says
"network <name> not found", whereas container/volume say "No such ...". The strict
absence classifier was corrected to accept either daemon message only with the
exact own name. failure-cleanup-probe-v2 proves removal and two subsequent
idempotent cleanup checks, with no STATE ever published. The first cleanup proof
is hash-pinned and not overwritten. fixed-start-smoke proves PG160015 target SQL
readiness, followed by verified own-resource teardown.

diagnose-original-gate-01 is a distinct local sandbox Docker pipe permission RED,
not a PostgreSQL business failure. The escalated diagnostic run 02 captured the
actual initialization race. Full dual Python regression and six exact-head CI
gates remain required after ordinary main integration.
