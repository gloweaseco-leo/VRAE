# Original Phase0 acceptance mapping (no production PASS claims)

Original Phase0 TEST_PLAN.md is unchanged. The rows below identify actual runnable
D1/D2 synthetic subsets. **Every original real-auth/DB/production/UI case remains
NOT_RUN/BLOCKED in its full production sense.** A passing pytest case validates
only the named offline behavior. This table is not 48 production PASS results.

Test names below are in tests/reviewing; exact node IDs/results are in JUnit and
the read-only CI call receipt. D1 replay is in compatibility.py and D1 JSON.

| A-case | Offline implementation / runnable evidence | Remaining original requirement |
| --- | --- | --- |
| A01 | actor_denied_before_lookup cross-tenant | Real session and zero-byte HTTP response NOT_RUN |
| A02 | native_end_to_end_simulation | Authenticated reviewer prepare NOT_RUN |
| A03 | free_form_actor_not_an_identity, production_port_always_denies | Auth integration BLOCKED |
| A04 | actor_denied_before_lookup model/service/worker; explicit simulation only | Real dual-role operations NOT_RUN |
| A05 | new_version_invalidates_old_and_no_reactivation | Production latest transaction NOT_RUN |
| A06 | pinned_mutations html; forged_target_even_with_recomputed_digest | Real session binding NOT_RUN |
| A07 | cross_tenant_source, cross_pack, forged target fields | Authoritative policy repository BLOCKED |
| A08 | explicit synthetic v2 through public producer, monotonic publication | New collection and production pipeline NOT_RUN |
| A09 | interleaved_first_writer_wins approve/approve | Real concurrent durable CAS NOT_RUN |
| A10 | interleaved_first_writer_wins approve/changes and inverse | DB transaction race NOT_RUN |
| A11 | same receipt object, historical retry effective=false | Durable lost-response recovery NOT_RUN |
| A12 | idempotency_conflict_no_overwrite, round closure | Persistent idempotency NOT_RUN |
| A13 | pinned_mutations html; rehashing_draft_cannot_replace_replayed_original | Immutable object service BLOCKED |
| A14 | css/footer/native/draft/renderer digest mutations | Customer artifact lifecycle NOT_RUN |
| A15 | quote/range/fake evidence and rehashed source native refusal | Production source access NOT_RUN |
| A16 | guard status/missing claim/fact mutations | Current trusted repository BLOCKED |
| A17 | clock_required, clock_high_water_on_observation_and_no_tz_offset | Grant expiry and client clock runtime NOT_RUN |
| A18 | absent/naive/string/offset/backward synthetic clock denied | Persistent trusted high-water BLOCKED |
| A19 | receipt native fields null; production port always denies | Copy/export/recipient runtime NOT_RUN |
| A20 | no_native_approval_or_share_helper_invoked; all receipts unshareable | Owner grant/consent/RA4 NOT_RUN |
| A21 | new version invalidates previous simulation, source context bound | Actual approval invalidation NOT_RUN |
| A22 | version rollback denied; new version required | Persistent monotonic latest BLOCKED |
| A23 | No grant type/API in new package | Expiry/revocation runtime NOT_RUN |
| A24 | No grant or approval produced, no external visibility | Native/full share binding NOT_RUN |
| A25 | original HTML exact bytes; appended script denied | New browser/UI injection runtime NOT_RUN; accepted RA3C tests unchanged |
| A26 | reason bounded/control/bidi denial; prompt injection inert | Future UI safe rendering NOT_RUN |
| A27 | invalid proposals leave simulation_count=0 | Actual partial DB/event failure NOT_RUN |
| A28 | in-memory retry identity and restart-no-recovery test | Durable outbox/restart NOT_RUN |
| A29 | each call rechecks synthetic role and assignment | Current real role revocation BLOCKED |
| A30 | no real session accepted; production port always denies | Session expiry and identity switching NOT_RUN |
| A31 | coverage_cannot_approve_or_erase_unknowns | Genuine authenticated zero-summary workflow NOT_RUN |
| A32 | zero candidate yields SIMULATED_INTERNAL_SCOPE_ACK only | Real human acknowledgement NOT_RUN |
| A33 | no Guard mutation; type-specific disposition ceiling | Actual human review NOT_RUN |
| A34 | missing/duplicate/foreign claims/sections denied; original rejected Guard denied | Production full preview confirmation NOT_RUN |
| A35 | all context fields bound; forged target fails rebuild | Actual engine rollout/reapproval NOT_RUN |
| A36 | synthetic/null model mode retained; forged model native refusal | Live gateway provenance NOT_RUN / NO_GO |
| A37 | No sharing endpoint/subject/token/grant | Real recipient/consent validation NOT_RUN |
| A38 | production port rejects even claimed Owner | Verified issuance authority BLOCKED |
| A39 | no customer cache/access implemented | Cache revocation runtime NOT_RUN |
| A40 | object ref test-only exact scheme; arbitrary URL refused | Protected object delivery NOT_RUN |
| A41 | forged copied receipt has no effective simulation identity | Authenticated durable decision lookup BLOCKED |
| A42 | new engine cannot restore approval from copied receipt | Trusted durable audit integrity/recovery NOT_RUN |
| A43 | changes closes round; competing approval denied | Production native-helper outer adapter NOT_RUN |
| A44 | reject closes round; immutable original receipt | Durable rejection/reopening transaction NOT_RUN |
| A45 | full target required by publish; H0 alone insufficient | Durable native/full sidecar commit NOT_RUN |
| A46 | new sidecar kinds; existing native schemas preserved | Versioned HTTP transport NOT_RUN |
| A47 | immutable simulation receipt explicitly nondurable | Durable commit/lost response UI NOT_RUN |
| A48 | version/target locked in proposed command; synthetic actor scope checked | Desktop/mobile/keyboard/screen-reader new reviewer UI NOT_RUN |
