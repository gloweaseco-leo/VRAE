# P1 acceptance scope and evidence map

Issue62 is engineering ENTRY GO only. Real PostgreSQL, not SQLite/mocks, is used.
Initial actual Python3.13 runs: 47 PG cases passed; then 52 including real dump/
restore; then 53 including actual Docker restart on an owned persistent volume.
Final source adds the explicit two-connection policy-publication race check and
records all 54 actual PG calls per runtime. Pure no-PG suite has 11 cases. Final
counts/results must be read from actual JUnit/commands and hosted jobs, not inferred.

| Requirement | Executable actual acceptance |
| --- | --- |
| Empty DB additive migration and drift refusal | support.migrate plus version/SHA pg_catalog record |
| Non-super/non-bypass runtime and forced owner RLS | real_version_catalog_and_owner_force_rls |
| Original 404 and 200 source-bound metadata | 404_and_200_references_are_exact_private_metadata |
| Two TEST_ONLY tenants and atomic idempotent admission | two_tenants_admission_is_atomic_and_idempotent |
| Direct SELECT/INSERT/UPDATE/DELETE/TRUNCATE isolation | direct_cross_tenant... for all eight business tables |
| GUC/role/session spoof, row_security=off, private schema/temp attacks | tenant_role_and_guc_spoofs... |
| Missing/foreign tenant, disabled login mapping, revoked assignment | absent_or_revoked_synthetic_scope_denies |
| Fake/revoked/UNKNOWN/expired/stale policy | policy_current_version_and_clock_checked_in_transaction |
| Concurrent current-policy publication | current_policy_publication_waits_for_admission_commit |
| Source/hash mismatch and idempotency collision | admission_links_only_original_bound_reference |
| Extra client authority/HTML/Guard/target fields | client_json_extra_authority_or_forged_source_fields_denied |
| Row overwrite/zero-to-APPROVED denial | immutable_reference... and direct runtime ACL tests |
| Partial outbox failure | partial_sql_failure_rolls_back_every_admission_row |
| Killed connection before commit | connection_termination_before_commit_rolls_back |
| Concurrent real admission retry | real_two_connection_concurrent_idempotency |
| SKIP LOCKED two claimants, stale tokens, no double finish/event | real_skip_locked_claimants_and_lease_recovery |
| Uncommitted worker connection death | uncommitted_worker_disconnect_releases_job |
| Real expiry and maximum attempts | expired_unreclaimed... / attempt_cap... |
| Source v1 invalidated by a legitimate new native synthetic v2 | legitimate_new_synthetic_version... |
| pg_dump/pg_restore data/owner/RLS and idempotency | pg_dump_restore_retains_data_owners_rls_and_idempotency |
| Real restart + committed IDs/lease reclaims, fsync settings | committed_queue_lease...real_container_restart |
| Privileged migration connection not runtime | admin_connection_is_not_a_synthetic_runtime_client |
| Forbidden human approval/ShareGrant | human_approval_and_share_ports... plus pure production_port tests |

Default historical tests/oracles/skip rules/CI/Docker remain unchanged. The four
original hosted jobs must pass on final HEAD + latest main, including actual
127 reviewing and 118 RA3C QA V2 calls. New separate ra4a-pg.yml must pass both
Python3.11/3.13 real PG16 jobs. No original job, QA case or assertion is altered.

## Real initial RED and bounded harness correction

The first harness used a Docker --internal network. Its PostgreSQL process
started and pg_isready succeeded, but docker port returned exit1; no host endpoint
could be discovered. The harness exited nonzero and removed its own container/
network. This was setup RED, not a completed business-test run and not an RLS
bypass. Correction was confined to infra/ra4a: dedicated bridge plus exclusively
127.0.0.1 publication. Do not claim kernel egress denial for that DB network.
Actual subsequent migration, 47/52/53-case JUnit and catalog/dump/restore logs are
preserved separately. The initial temporary tmpfs lab was torn down before the
owned-volume restart proof; no old evidence was relabelled. No fake RED or PASS.

All metadata is synthetic and separately pinned; admin/fixture role remains
trusted and able to reconfigure its disposable cluster. Such authority is never
given to runtime or interpreted as human authority. Real IdP/object store/review/
delivery/production recovery remain NOT_RUN/NO_GO, not skipped passing tests.
Human Gold 0/26. No actual model/site/paid/customer/deploy operations.
