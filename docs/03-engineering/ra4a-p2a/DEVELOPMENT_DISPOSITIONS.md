# Original RED / correction dispositions

All named stages retain raw command stdout/stderr, JUnit where generated, actual
call logs, migration snapshots and source fingerprints. No historical result was
edited into GREEN. This file classifies observed evidence, not skipped assertions.

* initial-migration: new v2 generated expression used convert_to, which PG rejects
  as non-immutable. Whole v2 transaction rolled back. Original SQL snapshot retained;
  fixed generated target prefix to constant decoded bytes and built-in immutable
  SHA/encode. Canonical JSON helper is STABLE, not a fake immutable workaround.
* dev-p2a-01: first actual call failed at deferred COMMIT because invoker-trigger
  execution lacked private graph SELECT after SECURITY DEFINER register returned.
  Fixed only new complete-graph trigger to fixed-search-path non-BYPASSRLS owner;
  runtime table privileges remained absent, FORCE RLS and SESSION_USER scope held.
* dev-p2a-02: 64 PASS /1 FAIL, then -x stopped further calls. The failed disconnect
  harness implicitly COMMITted a backend it had deliberately terminated. Now it
  explicitly observes OperationalError/connection termination, closes without a
  second COMMIT, and still asserts zero committed graphs and valid recovery.
* dev-p2a-03: 74 PASS /1 failed call plus1 teardown error in original JUnit (76 XML
  test entries). After real restart, held loopback port57880 differed from actual
  Docker port64628; reconnect and session-finish timed out. The process naturally
  failed before a planned own-PID abort (Stop-Process reported not found). Fixed
  only the new restart harness to refresh actual loopback binding as original P1
  already does, with a monotonic readiness deadline. No recovery PASS claimed here.
* local311-full: ineligible as fresh migration. Caller supplied an output path
  outside scan_stop's authorized docs tree; the guard refused. Ungated following
  PowerShell commands safely refused existing STATE startup but then reused v2.
  P1 catalog proves both mislabeled phases were v2; they do not certify fresh v1.
  The requested exact p1-v2 child stop found none after it had finished; subsequent
  owned-lab teardown interrupted the newly started P2A phase. Those errors are
  explicit lifecycle interruption, not alleged production defects. All original
  outputs retained; the separate local311-fresh run starts only after both old
  runner and verified cleanup completed, with each step checked independently.

The independent review also added a no-append-after-event seal and a deferred
requirement for the private registration event; normal fixture-admin SQL cannot
append to a committed graph. Privileged corruption probes deliberately disable
triggers only in disposable isolated test clones and prove external original-byte
verification rejects changed content despite regenerated stored hashes. These
probes do not claim that a cluster superuser lacks DDL/break-glass capability.

dev-full-04 is the first complete Python3.13 execution: original P1-v1 54,
unchanged P1-v2 54, original11+new14 pure and P2A86 all pass; all runtime source
fingerprints must match committed final functional sources. Its start Git HEAD
was e9ec1bd with uncommitted P2A source; later source commit and accepted-main
merge did not change these runtime source bytes. Final hosted tests must prove
the exact final merge-ref on both runtimes. local311-fresh is separately verified.
