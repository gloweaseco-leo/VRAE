## Codex1 — one L3 STOP / complete source and SQL review delta

Owner6894393962; base67acff97689514fdede01f2aab81dd5a7a96b9cd. Independent S2 worktree. All source below is unpublished review material, not S2 PASS.

Real Linux Python3.11 + disposable PG16: **39 PASS / 1 FAIL of40**. accepted-200 has17 catalog facts (INFO5/SEO2/TRUST10); my new producer creates17 Guard bundles, exceeding protected report limit16: **REPORT_GUARD_PINS**. STOP; no limit change, fact dropping, native rerun, 3.13 native run, push/PR/CI/merge/deploy. Worker404 genuinely generated and committed only UNSEALED_CANDIDATE. Trusted result rows0. Full JUnit SHA `0bac0fe168b107ba9c1bd192dfe58b9f219a21592f67edba2589927c2c22030d`. All RED retained; four owned resources absent. Old250+145 hash-exact.

Actual revoke waits on Worker transaction, then42501; epoch rollover and private table/origin DML negatives passed. Catalog unchanged except exact3 policies. Positive trusted FOR SHARE remains UNPROVED (no seeding). Pure311 checkpoint21 PASS is not final-source dual-minor proof. CI Ruff selection/mypy PASS; broad Ruff22 additional findings.

First write blocker: actual Worker original register42501/P2A_FIXTURE_WRITER_ONLY. New authority fails original references_metadata_check23514 on NEW-table exact constraint copy only. No protected write attempted. Below003 is FULL HELD transaction SQL, never staged/executed. It proposes explicit new authority + guarded reference/graph seal + original finish + audit/outbox + COMMIT guards. Original0001–0004 files/ACL/roles intact. Final witness joins/target field alignment are static post-STOP review, not rerun.

B3 SQL generic typed-byte layout is only structurally assessed, not positive-proved. Old Python build_target rejects new trust label D_TRUST_INPUT_REQUIRED and uses legacy report replay. B2/B5A DB prefix also differs from actual B4 DB; neither validator changed/faked. No authentic signed generated read claim. Beta2/7; Gold0/26; G1–G3NO-GO.

One exact remaining storage delta follows (current files, then held additions); native approval remains HOLD. No extra broad redesign.

`db/ra4b_p2/001_isolated_interfaces.sql` SHA256 `08119de966aac3c3582e277ec9a9e1ab937dab743756534c34a011814a4c5fd0`
```
-- Owner6894393962: additive disposable TEST_ONLY experiment only.
-- No INSERT/UPDATE/DELETE of legacy references/graphs/objects/events.
BEGIN;
CREATE SCHEMA ra4b_p2 AUTHORIZATION ra4a_owner;
REVOKE ALL ON SCHEMA ra4b_p2 FROM PUBLIC;
SET ROLE ra4a_owner;
CREATE TABLE ra4b_p2.raw_inputs(
 tenant_id text NOT NULL, source_ref text NOT NULL,
 reference_sha256 text NOT NULL CHECK(reference_sha256 ~ '^[a-f0-9]{64}$'),
 source_record bytea NOT NULL CHECK(octet_length(source_record) BETWEEN 1 AND 8000000),
 source_sha256 text GENERATED ALWAYS AS(encode(sha256(source_record),'hex')) STORED,
 policy_document jsonb NOT NULL, audit_document jsonb NOT NULL,
 PRIMARY KEY(tenant_id,source_ref),
 FOREIGN KEY(tenant_id,source_ref) REFERENCES ra4a.references);
CREATE TABLE ra4b_p2.candidate_bindings(
 tenant_id text NOT NULL, request_id uuid NOT NULL, run_id uuid NOT NULL, job_id uuid NOT NULL,
 worker_role name NOT NULL, lease_seq integer NOT NULL, lease_token_sha256 text NOT NULL,
 lease_until timestamptz NOT NULL, origin_role name NOT NULL, origin_epoch bigint NOT NULL,
 source_ref text NOT NULL, source_sha256 text NOT NULL, reference_sha256 text NOT NULL,
 policy_id text NOT NULL, policy_version integer NOT NULL,
 candidate bytea NOT NULL CHECK(octet_length(candidate) BETWEEN 1 AND 8000000),
 source_record bytea NOT NULL CHECK(octet_length(source_record) BETWEEN 1 AND 8000000),
 html bytea NOT NULL CHECK(octet_length(html) BETWEEN 1 AND 8000000),
 candidate_sha256 text GENERATED ALWAYS AS(encode(sha256(candidate),'hex')) STORED,
 source_record_sha256 text GENERATED ALWAYS AS(encode(sha256(source_record),'hex')) STORED,
 html_sha256 text GENERATED ALWAYS AS(encode(sha256(html),'hex')) STORED,
 stage text NOT NULL DEFAULT 'UNSEALED_CANDIDATE' CHECK(stage='UNSEALED_CANDIDATE'),
 staged_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,job_id,lease_seq),
 FOREIGN KEY(tenant_id,job_id) REFERENCES ra4a.jobs,
 FOREIGN KEY(tenant_id,run_id) REFERENCES ra4a.runs,
 FOREIGN KEY(tenant_id,request_id) REFERENCES ra4a.requests);
-- No live INSERT endpoint populates this table while legacy sealing is HOLD.
-- Both its insert guard and predicate independently demand the actual legacy
-- immutable graph/event/reference plus real DONE/finish transaction evidence.
CREATE TABLE ra4b_p2.sealed_bindings(
 tenant_id text NOT NULL, job_id uuid NOT NULL, lease_seq integer NOT NULL,
 generated_ref text NOT NULL, report_id text NOT NULL, report_version integer NOT NULL,
 target_digest text NOT NULL, manifest_sha256 text NOT NULL,
 finish_event uuid NOT NULL, transaction_id bigint NOT NULL,
 sealed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,job_id), UNIQUE(tenant_id,generated_ref),
 FOREIGN KEY(tenant_id,job_id,lease_seq) REFERENCES ra4b_p2.candidate_bindings);
CREATE TABLE ra4b_p2.result_audit(
 tenant_id text NOT NULL,job_id uuid NOT NULL,lease_seq integer NOT NULL,
 event_id uuid NOT NULL,transaction_id bigint NOT NULL,target_digest text NOT NULL,
 PRIMARY KEY(tenant_id,job_id),
 FOREIGN KEY(tenant_id,job_id) REFERENCES ra4b_p2.sealed_bindings);
CREATE TABLE ra4b_p2.result_outbox(LIKE ra4b_p2.result_audit INCLUDING ALL);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['raw_inputs','candidate_bindings','sealed_bindings','result_audit','result_outbox'] LOOP
  EXECUTE format('ALTER TABLE ra4b_p2.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE ra4b_p2.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY tenant_scope ON ra4b_p2.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',tab);
  EXECUTE format('CREATE TRIGGER immutable_s2 BEFORE UPDATE OR DELETE ON ra4b_p2.%I FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable()',tab);
 END LOOP;
END $$;
CREATE FUNCTION ra4b_p2.no_truncate() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$ BEGIN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='S2_IMMUTABLE_LEDGER'; END $$;
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['raw_inputs','candidate_bindings','sealed_bindings','result_audit','result_outbox'] LOOP
  EXECUTE format('CREATE TRIGGER no_truncate_s2 BEFORE TRUNCATE ON ra4b_p2.%I FOR EACH STATEMENT EXECUTE FUNCTION ra4b_p2.no_truncate()',tab);
 END LOOP;
END $$;
CREATE FUNCTION ra4b_p2.input_guard() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$ BEGIN
 IF SESSION_USER<>'postgres' OR CURRENT_USER<>'postgres' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_TRUSTED_RAW_INPUT_BOOTSTRAP_ONLY'; END IF;
 IF NOT EXISTS(SELECT 1 FROM ra4a.references r WHERE
  (r.tenant_id,r.ref_id,r.ref_sha256)=(NEW.tenant_id,NEW.source_ref,NEW.reference_sha256)
  AND r.metadata->>'source_record_sha256'=encode(sha256(NEW.source_record),'hex')
  AND NEW.policy_document->>'tenant_id'=r.tenant_id
  AND NEW.policy_document->>'policy_id'=r.policy_id
  AND (NEW.policy_document->>'policy_version')::integer=r.policy_version
  AND NEW.audit_document->>'tenant_id'=r.tenant_id
  AND NEW.audit_document->>'source_policy_ref'=r.policy_id
  AND (NEW.audit_document->>'source_policy_version')::integer=r.policy_version)
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_RAW_INPUT_REFERENCE_MISMATCH'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER validate_input BEFORE INSERT ON ra4b_p2.raw_inputs
FOR EACH ROW EXECUTE FUNCTION ra4b_p2.input_guard();

CREATE FUNCTION ra4b_p2.require_lease(t text,id uuid,token uuid,seq integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE rid uuid; BEGIN
 PERFORM ra4b_test.require_actor(t,'WORKER');
 IF SESSION_USER NOT IN('ra4b_test_a_worker','ra4b_test_b_worker')
 OR pg_has_role(SESSION_USER,'p2a_fixture_writer','MEMBER') THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_EXACT_WORKER_REQUIRED'; END IF;
 SELECT j.run_id INTO rid FROM ra4a.jobs j WHERE j.tenant_id=t AND j.job_id=id FOR UPDATE;
 IF rid IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_CURRENT_LEASE_DENIED'; END IF;
 PERFORM ra4b_test.require_run(t,rid,'WORKER');
 IF NOT EXISTS(SELECT 1 FROM ra4a.jobs j WHERE (j.tenant_id,j.job_id)=(t,id)
 AND j.state='LEASED' AND j.lease_owner=SESSION_USER AND j.lease_token=token
 AND j.lease_seq=seq AND j.lease_until>clock_timestamp()) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_CURRENT_LEASE_DENIED'; END IF;
END $$;
CREATE FUNCTION ra4b_p2.load_leased_source(t text,id uuid,token uuid,seq integer)
RETURNS TABLE(tenant_id text,request_id uuid,run_id uuid,job_id uuid,worker_role name,
 lease_until timestamptz,origin_role name,origin_epoch bigint,source_ref text,
 reference_sha256 text,raw_source bytea,raw_source_sha256 text,policy_document jsonb,
 audit_document jsonb,loaded_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$ BEGIN
 PERFORM ra4b_p2.require_lease(t,id,token,seq);
 RETURN QUERY SELECT q.tenant_id,q.request_id,j.run_id,j.job_id,SESSION_USER::name,
 j.lease_until,b.origin_role,b.epoch,q.source_ref,r.ref_sha256,i.source_record,
 i.source_sha256,i.policy_document,i.audit_document,clock_timestamp()
 FROM ra4a.jobs j JOIN ra4a.runs s USING(tenant_id,run_id)
 JOIN ra4a.requests q USING(tenant_id,request_id)
 JOIN ra4b_test.request_origins b USING(tenant_id,request_id)
 JOIN ra4b_test.origin_epochs e ON(e.tenant_id,e.origin_role,e.epoch)=(b.tenant_id,b.origin_role,b.epoch)
 JOIN ra4a.references r ON(r.tenant_id,r.ref_id)=(q.tenant_id,q.source_ref)
 JOIN ra4b_p2.raw_inputs i ON(i.tenant_id,i.source_ref,i.reference_sha256)=(q.tenant_id,q.source_ref,r.ref_sha256)
 WHERE j.tenant_id=t AND j.job_id=id AND i.source_sha256=r.metadata->>'source_record_sha256';
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_AUTHORIZED_INPUT_UNAVAILABLE'; END IF;
END $$;
CREATE FUNCTION ra4b_p2.candidate_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE j ra4a.jobs%ROWTYPE; BEGIN
 PERFORM ra4b_test.require_run(NEW.tenant_id,NEW.run_id,'WORKER');
 SELECT * INTO STRICT j FROM ra4a.jobs WHERE tenant_id=NEW.tenant_id AND job_id=NEW.job_id;
 IF SESSION_USER<>NEW.worker_role OR j.lease_owner<>SESSION_USER OR j.state<>'LEASED'
 OR j.lease_seq<>NEW.lease_seq OR j.lease_until<>NEW.lease_until OR j.lease_until<=clock_timestamp()
 OR encode(sha256(convert_to(j.lease_token::text,'UTF8')),'hex')<>NEW.lease_token_sha256
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_CURRENT_AT_COMMIT_DENIED'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER current_candidate_at_commit AFTER INSERT ON ra4b_p2.candidate_bindings
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4b_p2.candidate_guard();
CREATE FUNCTION ra4b_p2.commit_generated_result(t text,id uuid,token uuid,seq integer,
 candidate_raw bytea,source_raw bytea,html_raw bytea) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE x record; d jsonb; src jsonb; b jsonb; old ra4b_p2.candidate_bindings%ROWTYPE; BEGIN
 PERFORM ra4b_p2.require_lease(t,id,token,seq);
 SELECT * INTO STRICT x FROM ra4b_p2.load_leased_source(t,id,token,seq);
 IF candidate_raw IS NULL OR source_raw IS NULL OR html_raw IS NULL
 OR octet_length(candidate_raw) NOT BETWEEN 1 AND 8000000
 OR octet_length(source_raw) NOT BETWEEN 1 AND 8000000 OR octet_length(html_raw) NOT BETWEEN 1 AND 8000000
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_CANDIDATE_BOUND'; END IF;
 d:=convert_from(candidate_raw,'UTF8')::jsonb; src:=convert_from(source_raw,'UTF8')::jsonb; b:=d->'binding';
 IF jsonb_typeof(d) IS DISTINCT FROM 'object' OR NOT(d ?& ARRAY[
 'contract_version','authority','committed','commit_receipt','reviewer_assignment','native_approval','share_grant',
 'binding','scope','versions','evidence_pack_ref','evidence_sha256','rule_execution_ref','execution_sha256',
 'finding_package_ref','finding_sha256','guard_refs','guard_sha256','draft_ref','report','report_sha256','html_sha256'])
 OR (SELECT count(*) FROM jsonb_object_keys(d))<>22
 OR ra4a_bytes.canonical_bytes(d)<>candidate_raw OR ra4a_bytes.canonical_bytes(src)<>source_raw
 OR d->>'contract_version'<>'ra4b-p2-generated-candidate-v1'
 OR d->>'authority'<>'CONSISTENCY_CANDIDATE_NOT_COMMITTED_NOT_APPROVED'
 OR d->'committed'<>'false'::jsonb OR d->'commit_receipt'<>'null'::jsonb
 OR d->'reviewer_assignment'<>'null'::jsonb OR d->'native_approval'<>'null'::jsonb OR d->'share_grant'<>'null'::jsonb
 OR d->'versions'<>jsonb_build_object('evaluator','ra2b6-1.0.0','builder','ra2c3-1.0.0',
 'guard','ra3b-disc-1.0.0','report','ra3c-disc-1.0.0','renderer','ra3c-disc-html-1.0.0')
 OR (b->>'tenant_id',b->>'request_id',b->>'run_id',b->>'job_id',b->>'worker') IS DISTINCT FROM
 (t,x.request_id::text,x.run_id::text,id::text,SESSION_USER::text)
 OR (b->>'lease_seq')::integer IS DISTINCT FROM seq
 OR b->>'lease_token_sha256' IS DISTINCT FROM encode(sha256(convert_to(token::text,'UTF8')),'hex')
 OR (b->>'lease_until')::timestamptz IS DISTINCT FROM x.lease_until
 OR (b->>'origin_epoch')::bigint IS DISTINCT FROM x.origin_epoch
 OR b->>'source_ref' IS DISTINCT FROM x.source_ref OR b->>'reference_sha256' IS DISTINCT FROM x.reference_sha256
 OR (b->>'policy_id',(b->>'policy_version')::integer) IS DISTINCT FROM
 (x.audit_document->>'source_policy_ref',(x.audit_document->>'source_policy_version')::integer)
 OR b->>'policy_sha256' IS DISTINCT FROM encode(sha256(ra4a_bytes.canonical_bytes(x.policy_document)),'hex')
 OR d->>'html_sha256' IS DISTINCT FROM encode(sha256(html_raw),'hex')
 OR d->>'report_sha256' IS DISTINCT FROM encode(sha256(ra4a_bytes.canonical_bytes(d->'report')),'hex')
 OR d->'report'->'pins'->>'expected_guard_version' IS DISTINCT FROM 'ra3b-disc-1.0.0'
 OR d->'report'->>'reporting_version' IS DISTINCT FROM 'ra3c-disc-1.0.0'
 OR d->'report'->'metadata'->>'report_id' IS DISTINCT FROM 'job-'||id::text
 OR d->'report'->'scope' IS DISTINCT FROM jsonb_build_object('tenant_id',t,'run_id',x.run_id::text,
 'policy_id',x.audit_document->>'source_policy_ref','policy_version',(x.audit_document->>'source_policy_version')::integer)
 OR src->'pack'->>'pack_ref' IS DISTINCT FROM d->>'evidence_pack_ref'
 OR encode(sha256(ra4a_bytes.canonical_bytes(src->'pack')),'hex') IS DISTINCT FROM d->>'evidence_sha256'
 OR encode(sha256(ra4a_bytes.canonical_bytes(src->'package')),'hex') IS DISTINCT FROM d->>'finding_sha256'
 OR src->'metadata' IS DISTINCT FROM d->'report'->'metadata'
 OR src->'objects_base64' IS DISTINCT FROM (convert_from(x.raw_source,'UTF8')::jsonb)->'objects_base64'
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_EXACT_CANDIDATE_BINDING_DENIED'; END IF;
 SELECT * INTO old FROM ra4b_p2.candidate_bindings WHERE tenant_id=t AND job_id=id AND lease_seq=seq;
 IF FOUND THEN
  IF (old.candidate,old.source_record,old.html) IS DISTINCT FROM(candidate_raw,source_raw,html_raw) THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_IMMUTABLE_CANDIDATE_CONFLICT'; END IF;
 ELSE
  INSERT INTO ra4b_p2.candidate_bindings(tenant_id,request_id,run_id,job_id,worker_role,lease_seq,
   lease_token_sha256,lease_until,origin_role,origin_epoch,source_ref,source_sha256,reference_sha256,
   policy_id,policy_version,candidate,source_record,html)
  VALUES(t,x.request_id,x.run_id,id,SESSION_USER,seq,b->>'lease_token_sha256',x.lease_until,
   x.origin_role,x.origin_epoch,x.source_ref,x.raw_source_sha256,x.reference_sha256,
   x.audit_document->>'source_policy_ref',(x.audit_document->>'source_policy_version')::integer,
   candidate_raw,source_raw,html_raw);
 END IF;
 -- Operative draft stops here. No old graph writes and no native finish.
 RETURN jsonb_build_object('status','S2_REGISTRATION_HOLD','committed_generated_result',false,
  'job_id',id,'lease_seq',seq,'candidate_sha256',encode(sha256(candidate_raw),'hex'));
END $$;

CREATE FUNCTION ra4b_p2.current_generated_binding(t text,qid uuid,origin name,epoch_value bigint)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
 SELECT CURRENT_USER='ra4a_owner' AND SESSION_USER IN
 ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer') AND t=ra4a.scope()
 AND EXISTS(SELECT 1 FROM ra4b_p2.sealed_bindings z
 JOIN ra4b_p2.candidate_bindings c USING(tenant_id,job_id,lease_seq)
 JOIN ra4a.jobs j USING(tenant_id,job_id)
 JOIN ra4a.runs s ON(s.tenant_id,s.run_id)=(c.tenant_id,c.run_id)
 JOIN ra4a.requests q ON(q.tenant_id,q.request_id)=(c.tenant_id,c.request_id)
 JOIN ra4a.references r ON(r.tenant_id,r.ref_id)=(z.tenant_id,z.generated_ref)
 JOIN ra4a_bytes.graphs g ON(g.tenant_id,g.ref_id)=(z.tenant_id,z.generated_ref)
 JOIN ra4a_bytes.events ge ON(ge.tenant_id,ge.source_run_id,ge.report_id,ge.report_version)=
 (g.tenant_id,g.source_run_id,g.report_id,g.report_version)
 JOIN ra4a_review_test.assignments a ON(a.tenant_id,a.report_id)=(z.tenant_id,z.report_id)
 JOIN ra4a.policies p ON(p.tenant_id,p.policy_id,p.version)=(q.tenant_id,q.policy_id,q.policy_version)
 JOIN ra4b_p2.result_audit au ON(au.tenant_id,au.job_id)=(z.tenant_id,z.job_id)
 JOIN ra4b_p2.result_outbox ob ON(ob.tenant_id,ob.job_id)=(z.tenant_id,z.job_id)
 JOIN ra4a.outbox native_outbox ON(native_outbox.tenant_id,native_outbox.event_id)=(z.tenant_id,z.finish_event)
 JOIN ra4a.audit native_audit ON(native_audit.tenant_id,native_audit.run_id,native_audit.lease_seq)=
 (c.tenant_id,c.run_id,c.lease_seq)
 WHERE z.tenant_id=t AND (qid IS NULL OR q.request_id=qid)
 AND (c.origin_role,c.origin_epoch)=(origin,epoch_value) AND q.principal=c.origin_role
 AND q.source_ref=c.source_ref AND s.request_id=q.request_id AND j.run_id=s.run_id
 AND j.state='TEST_ONLY_DONE' AND j.lease_owner=c.worker_role AND j.lease_seq=c.lease_seq
 AND ge.db_principal=c.worker_role AND z.sealed_at<c.lease_until
 AND native_outbox.run_id=c.run_id AND native_outbox.kind='TEST_ONLY_CONSUMED'
 AND native_audit.action='TEST_ONLY_CONSUMED' AND native_audit.db_principal=c.worker_role
 AND a.db_role=SESSION_USER AND a.active AND a.authority='TEST_ONLY'
 AND p.status='ALLOWED' AND p.expires_at>clock_timestamp()
 AND NOT EXISTS(SELECT 1 FROM ra4a.policies n WHERE(n.tenant_id,n.policy_id)=(p.tenant_id,p.policy_id) AND n.version>p.version)
 AND r.metadata->>'authority'='TEST_ONLY_WORKER_GENERATED_SOURCE'
 AND r.metadata->>'contract_version'='ra4b-p2-generated-target-v1'
 AND r.metadata->>'guard_version'='ra3b-disc-1.0.0'
 AND r.metadata->>'reporting_version'='ra3c-disc-1.0.0'
 AND (r.source_run_id,r.report_id,r.report_version)=(c.run_id::text,z.report_id,z.report_version)
 AND r.metadata=convert_from(g.target_payload,'UTF8')::jsonb AND r.ref_sha256=g.target_sha256
 AND g.target_digest=z.target_digest AND g.manifest_sha256=z.manifest_sha256
 AND (au.event_id,au.transaction_id,au.target_digest)=(z.finish_event,z.transaction_id,z.target_digest)
 AND (ob.event_id,ob.transaction_id,ob.target_digest)=(au.event_id,au.transaction_id,au.target_digest)
 AND NOT EXISTS(SELECT 1 FROM ra4a.references n WHERE(n.tenant_id,n.report_id)=(r.tenant_id,r.report_id) AND n.report_version>r.report_version)
 );
$$;
CREATE FUNCTION ra4b_p2.sealed_insert_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$ BEGIN
 IF SESSION_USER NOT IN('ra4b_test_a_worker','ra4b_test_b_worker') OR CURRENT_USER<>'ra4a_owner'
 OR NOT EXISTS(SELECT 1 FROM ra4a.jobs j JOIN ra4a_bytes.graphs g ON g.tenant_id=j.tenant_id AND g.ref_id=NEW.generated_ref
 JOIN ra4a_bytes.events e ON(e.tenant_id,e.source_run_id,e.report_id,e.report_version)=
 (g.tenant_id,g.source_run_id,g.report_id,g.report_version)
 JOIN ra4a.references r ON(r.tenant_id,r.ref_id)=(g.tenant_id,g.ref_id)
 WHERE(j.tenant_id,j.job_id)=(NEW.tenant_id,NEW.job_id) AND j.state='TEST_ONLY_DONE'
 AND j.lease_owner=SESSION_USER AND e.db_principal=SESSION_USER
 AND r.metadata->>'authority'='TEST_ONLY_WORKER_GENERATED_SOURCE')
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_TRUSTED_GENERATED_SEAL_REQUIRED'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER real_seal_required BEFORE INSERT ON ra4b_p2.sealed_bindings
FOR EACH ROW EXECUTE FUNCTION ra4b_p2.sealed_insert_guard();
CREATE FUNCTION ra4b_p2.read_assigned_generated_result(t text,id uuid,report text,ver integer,digest text)
RETURNS TABLE(source_run_id text,report_id text,report_version integer,target_digest text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE b record; BEGIN
 IF SESSION_USER NOT IN('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_REVIEWER_REQUIRED'; END IF;
 PERFORM ra4a_review_test.require_reviewer(t,report);
 SELECT c.*,z.generated_ref,z.target_digest,z.report_id,z.report_version INTO b
 FROM ra4b_p2.candidate_bindings c JOIN ra4b_p2.sealed_bindings z USING(tenant_id,job_id,lease_seq)
 WHERE(c.tenant_id,c.job_id,z.report_id,z.report_version,z.target_digest)=(t,id,report,ver,digest);
 IF NOT FOUND OR NOT ra4b_p2.current_generated_binding(t,b.request_id,b.origin_role,b.origin_epoch)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_COMMITTED_GENERATED_BINDING_REQUIRED'; END IF;
 PERFORM 1 FROM ra4a_review_test.load_target(t,b.generated_ref,b.run_id::text,report,ver,digest);
 PERFORM 1 FROM ra4b_test.origin_epochs e WHERE(e.tenant_id,e.origin_role,e.epoch)=
 (t,b.origin_role,b.origin_epoch) FOR SHARE;
 IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM ra4b_test.request_origins r WHERE
 (r.tenant_id,r.request_id,r.origin_role,r.epoch)=(t,b.request_id,b.origin_role,b.origin_epoch))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_CURRENT_ORIGIN_REQUIRED'; END IF;
 RETURN QUERY SELECT b.run_id::text,report,ver,digest;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA ra4b_p2 FROM PUBLIC,ra4b_worker,p2b1_review;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ra4b_p2 FROM PUBLIC,ra4b_worker,p2b1_review;
GRANT USAGE ON SCHEMA ra4b_p2 TO ra4b_worker,p2b1_review;
GRANT EXECUTE ON FUNCTION ra4b_p2.load_leased_source(text,uuid,uuid,integer),
 ra4b_p2.commit_generated_result(text,uuid,uuid,integer,bytea,bytea,bytea) TO ra4b_worker;
GRANT EXECUTE ON FUNCTION ra4b_p2.read_assigned_generated_result(text,uuid,text,integer,text) TO p2b1_review;
RESET ROLE;
COMMIT;
```

`db/ra4b_p2/002_conditional_origin_policies.sql` SHA256 `22dc4b9e76ea5eda1d6284679a366f50768c9b43b80d1fd873b8f43bbfc22499`
```
-- Owner6894393962 conditional experiment. Private nonrecursive predicate must
-- exist and be reviewed first. No positive trusted seal can be seeded.
BEGIN;
SET ROLE ra4a_owner;
CREATE POLICY s2_assigned_epoch_select ON ra4b_test.origin_epochs
 AS PERMISSIVE FOR SELECT TO ra4a_owner USING (
 CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND SESSION_USER IN ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 AND ra4b_p2.current_generated_binding(tenant_id,NULL::uuid,origin_role,epoch));
CREATE POLICY s2_assigned_request_select ON ra4b_test.request_origins
 AS PERMISSIVE FOR SELECT TO ra4a_owner USING (
 CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND SESSION_USER IN ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 AND ra4b_p2.current_generated_binding(tenant_id,request_id,origin_role,epoch));
CREATE POLICY s2_assigned_epoch_lock ON ra4b_test.origin_epochs
 AS PERMISSIVE FOR UPDATE TO ra4a_owner USING (
 CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND SESSION_USER IN ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 AND ra4b_p2.current_generated_binding(tenant_id,NULL::uuid,origin_role,epoch))
 WITH CHECK(false);
RESET ROLE;
COMMIT;
```

`vrae/application/ra4b_p2/producer.py` SHA256 `bd468f111ce84d6e6093ca4924c409b1643a3a7ef89dffd845b3862820ce6ccf`
```
"""Replay fresh authorized capture input through the accepted DISC chain.

These are consistency candidates, never DB COMMIT receipts or authorization.
The missing low-role source/commit/read ports must be independently approved;
neither this module nor a caller-provided lease can replace those checks.
"""

from dataclasses import asdict, dataclass, field
import base64
from datetime import datetime
import hashlib
import json
import re
from uuid import UUID

from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.collection.policy import SourceAccess
from vrae.evidence import build_pack
from vrae.findings import build_findings
from vrae.interpretation.disc_report_v1 import binding, catalog, validate
from vrae.reporting.common import digest
from vrae.reporting.disc_report_v1 import ReportDraft, build_draft
from vrae.reporting.disc_report_v1.policy import proposals_for
from vrae.rules import execute

VERSION = "ra4b-p2-generated-candidate-v1"
AUTHORITY = "CONSISTENCY_CANDIDATE_NOT_COMMITTED_NOT_APPROVED"


class CandidateDenied(ValueError):
    """Closed error vocabulary, never raw pages or lease tokens."""


def encode(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def require(condition):
    if not condition:
        raise CandidateDenied("S2_LEASE_CONTEXT_DENIED")


def capture_digest(capture):
    capture.verify()
    return document_hash(
        {
            "manifest": capture.manifest,
            "objects": {
                k: hashlib.sha256(v).hexdigest() for k, v in sorted(capture.objects.items())
            },
        }
    )


@dataclass(frozen=True)
class LeaseContext:
    tenant_id: str
    request_id: str
    run_id: str
    job_id: str
    worker: str
    lease_token: str = field(repr=False)
    lease_seq: int
    lease_until: str
    origin_epoch: int
    source_ref: str
    reference_sha256: str
    input_sha256: str
    policy_id: str
    policy_version: int
    policy_sha256: str
    created_at: str

    def check(self, now):
        try:
            expected = {"ra4b_test_a_worker": "tenant-test", "ra4b_test_b_worker": "tenant-beta"}
            require(expected.get(self.worker) == self.tenant_id)
            for value in (self.request_id, self.run_id, self.job_id, self.lease_token):
                require(type(value) is str and str(UUID(value)) == value)
            require(len({self.request_id, self.run_id, self.job_id}) == 3)
            require(type(self.lease_seq) is int and 1 <= self.lease_seq <= 3)
            require(type(self.origin_epoch) is int and 0 < self.origin_epoch < 2**63)
            require(type(self.policy_version) is int and self.policy_version > 0)
            require(now.tzinfo is not None)
            until = datetime.fromisoformat(self.lease_until.replace("Z", "+00:00"))
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            require(until.tzinfo is not None and created.tzinfo is not None)
            require(created <= now < until and (until - created).total_seconds() <= 30)
            require(re.fullmatch(r"[A-Za-z0-9_.-]{3,128}", self.source_ref))
            require(re.fullmatch(r"[A-Za-z0-9_.-]{3,128}", self.policy_id))
            for value in (self.reference_sha256, self.input_sha256, self.policy_sha256):
                require(type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value))
        except Exception:
            raise CandidateDenied("S2_LEASE_CONTEXT_DENIED") from None

    def private_binding(self):
        result = asdict(self)
        token = result.pop("lease_token")
        result["lease_token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
        return result


@dataclass(frozen=True)
class GeneratedCandidate:
    _payload: bytes = field(repr=False)
    _html: bytes = field(repr=False)
    _source: bytes = field(default=b"", repr=False)

    @property
    def private_document(self):
        return json.loads(self._payload)

    @property
    def ref(self):
        return "s2c-" + hashlib.sha256(self._payload).hexdigest()

    def verify(self, capture, access, context, *, now):
        rebuilt = generate(capture, access, context, now=now)
        if (
            self._payload != rebuilt._payload
            or self._html != rebuilt._html
            or self._source != rebuilt._source
        ):
            raise CandidateDenied("S2_CANDIDATE_REPLAY_MISMATCH")
        return rebuilt


def generate(capture: CaptureBundle, access: SourceAccess, context: LeaseContext, *, now: datetime):
    context.check(now)
    if type(capture) is not CaptureBundle or type(access) is not SourceAccess:
        raise CandidateDenied("S2_CAPTURE_POLICY_REQUIRED")
    # Detach the mutable caller-owned bundle before any replay or hashing.
    capture = CaptureBundle(json.loads(encode(capture.manifest)), dict(capture.objects))
    scope = {k: capture.manifest[k] for k in ("tenant_id", "run_id", "policy_id", "policy_version")}
    expected = {k: getattr(context, k) for k in scope}
    if scope != expected or capture_digest(capture) != context.input_sha256:
        raise CandidateDenied("S2_AUTHORIZED_INPUT_MISMATCH")
    access.check(access.start_url)
    if document_hash(access.provider()) != context.policy_sha256:
        raise CandidateDenied("S2_POLICY_VERSION_MISMATCH")
    if (
        access.audit["tenant_id"] != context.tenant_id
        or access.audit["source_policy_ref"] != context.policy_id
        or access.audit["source_policy_version"] != context.policy_version
    ):
        raise CandidateDenied("S2_POLICY_SCOPE_MISMATCH")
    for page in capture.manifest["pages"]:
        access.check(page["snapshot"]["url"])
    pack = build_pack([capture])
    execution = execute(pack, expected_pack_ref=pack.ref, evaluator_version="ra2b6-1.0.0")
    base = {
        "expected_pack_ref": pack.ref,
        "expected_execution_ref": execution["execution_ref"],
        "expected_builder_version": "ra2c3-1.0.0",
        "expected_evaluator_version": "ra2b6-1.0.0",
    }
    package = build_findings(pack, execution, **base)
    source_pins = {
        **base,
        "expected_package_ref": package.ref,
        "expected_guard_version": "ra3b-disc-1.0.0",
        "expected_scope": scope,
    }
    bundles = []
    source_catalog = catalog(pack, package, **source_pins)
    for index, fact in enumerate(source_catalog["facts"]):
        interpretation: dict = {
            "schema_version": "1.0",
            "tenant_id": context.tenant_id,
            "run_id": context.run_id,
            "interpretation_id": "s2-generated-" + str(index),
            "observation_ids": [fact["observation_id"]],
            "evidence_ids": [fact["source"]["citation"]["evidence_ref"]],
            "hypotheses": [fact["statement"]],
            "recommendations": [],
            "missing_information": [],
            "model_id": None,
            "input_tokens": None,
            "output_tokens": None,
            "status": "VALIDATED",
        }
        bindings = [
            binding(
                pointer="/hypotheses/0",
                text=fact["statement"],
                claim_type="OBJECTIVE_SOURCE_FACT",
                fact=fact,
                context=source_catalog["context"],
            )
        ]
        if fact["proof_kind"] in ("CAPTURED_CTA_HTTP_FAILURE", "CAPTURED_DISC_HTTP_FAILURE"):
            for kind, text in proposals_for(fact["rule_id"]).values():
                key = "recommendations" if kind == "RECOMMENDATION" else "hypotheses"
                pointer = "/" + key + "/" + str(len(interpretation[key]))
                interpretation[key].append(text)
                bindings.append(
                    binding(
                        pointer=pointer,
                        text=text,
                        claim_type=kind,
                        fact=fact,
                        context=source_catalog["context"],
                    )
                )
        guard = validate(interpretation, bindings, pack, package, **source_pins)
        bundles.append(
            {"interpretation": interpretation, "bindings": bindings, "guard": guard.document}
        )
    metadata = {
        "report_id": "job-" + context.job_id,
        "version": 1,
        "created_at": context.created_at,
        "created_by": context.worker,
        "mode": "SYNTHETIC_PRIVATE_PREVIEW",
        "finding_selection": None,
    }
    pins = {
        **source_pins,
        "expected_guard_refs": [b["guard"]["guard_ref"] for b in bundles],
        "expected_metadata_sha256": digest(metadata),
        "expected_reporting_version": "ra3c-disc-1.0.0",
        "expected_renderer_version": "ra3c-disc-html-1.0.0",
    }
    draft = build_draft(pack, package, bundles, metadata, **pins)
    ReportDraft.load(
        draft.document,
        draft.html_bytes,
        pack,
        package,
        bundles,
        metadata,
        expected_draft_ref=draft.ref,
        **pins,
    )
    result = {
        "contract_version": VERSION,
        "authority": AUTHORITY,
        "committed": False,
        "commit_receipt": None,
        "reviewer_assignment": None,
        "native_approval": None,
        "share_grant": None,
        "binding": context.private_binding(),
        "scope": scope,
        "versions": {
            "evaluator": "ra2b6-1.0.0",
            "builder": "ra2c3-1.0.0",
            "guard": "ra3b-disc-1.0.0",
            "report": "ra3c-disc-1.0.0",
            "renderer": "ra3c-disc-html-1.0.0",
        },
        "evidence_pack_ref": pack.ref,
        "evidence_sha256": document_hash(pack.document),
        "rule_execution_ref": execution["execution_ref"],
        "execution_sha256": document_hash(execution),
        "finding_package_ref": package.ref,
        "finding_sha256": document_hash(package.document),
        "guard_refs": pins["expected_guard_refs"],
        "guard_sha256": [document_hash(b["guard"]) for b in bundles],
        "draft_ref": draft.ref,
        "report": draft.document,
        "report_sha256": document_hash(draft.document),
        "html_sha256": hashlib.sha256(draft.html_bytes).hexdigest(),
    }
    source = {
        "pack": pack.document,
        "objects_base64": {k: base64.b64encode(v).decode() for k, v in pack.objects.items()},
        "package": package.document,
        "guard_inputs": bundles,
        "metadata": metadata,
    }
    return GeneratedCandidate(encode(result), draft.html_bytes, encode(source))
```

`vrae/application/ra4b_p2/source_adapter.py` SHA256 `b2da710541ef9baa171de98d86242328b91e3afc309dac32f427872b5c08686c`
```
"""Import an authorized recorded CaptureManifest into a distinct job scope.

Raw bytes/status/timestamps are preserved. This is declared offline input replay,
not a claim that an HTTP request was made again or that an old report is output.
"""

import base64
from datetime import datetime, timezone
import json

from vrae.collection.manifest import CaptureBundle, document_hash
from vrae.collection.policy import SourceAccess
from vrae.evidence import EvidencePack
from .producer import CandidateDenied, LeaseContext, capture_digest


def load(c, tenant, lease):
    cur = c.execute(
        "SELECT * FROM ra4b_p2.load_leased_source(%s,%s,%s,%s)",
        (tenant, lease[0], lease[2], lease[3]),
    )
    row = cur.fetchone()
    if row is None:
        raise CandidateDenied("S2_AUTHORIZED_INPUT_UNAVAILABLE")
    return dict(zip([v.name for v in cur.description], row))


def materialize(row, lease):
    source = json.loads(bytes(row["raw_source"]))
    objects = {k: base64.b64decode(v, validate=True) for k, v in source["objects_base64"].items()}
    pack = EvidencePack.load(source["pack"], objects, expected_ref=source["pack"]["pack_ref"])
    entries = pack.document["sources"]
    if len(entries) != 1 or entries[0]["kind"] != "CaptureManifest":
        raise CandidateDenied("S2_SINGLE_OFFLINE_CAPTURE_REQUIRED")
    origin = entries[0]
    capture = CaptureBundle(
        json.loads(json.dumps(origin["document"])),
        {k: objects[v] for k, v in origin["object_refs"].items()},
    )
    capture.verify()
    audit = dict(row["audit_document"])
    audit["audit_id"] = str(row["request_id"])
    policy = dict(row["policy_document"])
    scope = {
        "tenant_id": row["tenant_id"],
        "run_id": str(row["run_id"]),
        "policy_id": audit["source_policy_ref"],
        "policy_version": audit["source_policy_version"],
    }
    capture.manifest.update(scope)
    capture.manifest["audit_id"] = audit["audit_id"]
    for page in capture.manifest["pages"]:
        snap = page["snapshot"]
        snap.update(scope)
        identity = document_hash(
            {"tenant": scope["tenant_id"], "run": scope["run_id"], "url": snap["url"]}
        )
        snap["snapshot_id"] = "snap-" + identity
        if page["evidence"] is not None:
            page["evidence"].update(
                tenant_id=scope["tenant_id"],
                run_id=scope["run_id"],
                snapshot_id=snap["snapshot_id"],
                evidence_id="ev-" + identity,
            )
    capture.manifest["manifest_sha256"] = document_hash(
        {k: v for k, v in capture.manifest.items() if k != "manifest_sha256"}
    )
    capture.verify()
    access = SourceAccess(
        audit, lambda: policy, terms_reference=capture.manifest["terms_reference"]
    )
    context = LeaseContext(
        scope["tenant_id"],
        str(row["request_id"]),
        scope["run_id"],
        str(row["job_id"]),
        row["worker_role"],
        str(lease[2]),
        lease[3],
        row["lease_until"].isoformat(),
        row["origin_epoch"],
        row["source_ref"],
        row["reference_sha256"],
        capture_digest(capture),
        scope["policy_id"],
        scope["policy_version"],
        document_hash(policy),
        row["loaded_at"].isoformat(),
    )
    return capture, access, context


def build(c, tenant, lease):
    from .producer import generate

    with c.transaction():
        row = load(c, tenant, lease)
    capture, access, context = materialize(row, lease)
    return generate(capture, access, context, now=datetime.now(timezone.utc)), context


def stage(c, tenant, lease, candidate):
    with c.transaction():
        return c.execute(
            "SELECT ra4b_p2.commit_generated_result(%s,%s,%s,%s,%s,%s,%s)",
            (
                tenant,
                lease[0],
                lease[2],
                lease[3],
                candidate._payload,
                candidate._source,
                candidate._html,
            ),
        ).fetchone()[0]
```

`vrae/application/ra4b_p2/worker.py` SHA256 `fafaf56cea8f0cb0d3ec82c97cf18b6148a8d7108f72c196ee70cc80cd676690`
```
"""Low-UID draft producer using original claim; final graph seal/finish is HOLD."""

import time

import argparse
import base64
import json
import os
from pathlib import Path

IMPORT_START = time.monotonic()


def main():
    from vrae.application.ra4b import store
    from .source_adapter import build, stage

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--private-receipt")
    args = parser.parse_args()
    config = store.load_config(args.config, "WORKER")
    print(
        json.dumps({"stage": "WORKER_READY", "startup_seconds": time.monotonic() - IMPORT_START}),
        flush=True,
    )
    with store.connect(config) as c:
        lease = store.claim(c, config, 30)
        if lease is None:
            return
        started = time.monotonic()
        candidate, _ = build(c, config["tenant"], lease)
        receipt = stage(c, config["tenant"], lease, candidate)
        receipt["generation_and_draft_commit_seconds"] = time.monotonic() - started
        if args.private_receipt:
            path = Path(args.private_receipt)
            directory = Path(args.config).resolve().parent
            if (
                path.resolve().parent != directory
                or directory.stat().st_uid != getattr(os, "geteuid", lambda: -1)()
                or directory.stat().st_mode & 0o077
            ):
                raise ValueError("S2_PRIVATE_WORKER_IPC_REQUIRED")
            record = {
                "lease": [str(v) if i != 3 else v for i, v in enumerate(lease)],
                "candidate": base64.b64encode(candidate._payload).decode(),
                "source": base64.b64encode(candidate._source).decode(),
                "html": base64.b64encode(candidate._html).decode(),
            }
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(record, stream)
        print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
```

`vrae/application/ra4b_p2/generated_graph.py` SHA256 `680c28a2fe337047a37c12a82b993a4a2f645debd4d3a3d571a8833f3aba2256`
```
"""Versioned graph bytes for the HELD registration delta, never a live writer.

The object is untrusted until a genuine DB seal/finish/commit receipt exists.
This adapter independently replays the DISC draft; it never relabels it as an
old accepted-fixture target or changes the original B3/private-byte validators.
"""

import base64
from dataclasses import dataclass
import json

from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.persistence.private_bytes import Artifact, descriptors
from vrae.reporting.disc_report_v1 import ReportDraft
from vrae.reporting.disc_report_v1.renderer import CSS, RENDERER_VERSION, asset_hash
from vrae.reviewing.canonical import canonical, digest, SOURCE_LIMIT, sha
from vrae.reviewing.target import _claim_manifest, SECTIONS
from .producer import CandidateDenied, GeneratedCandidate, encode

AUTHORITY = "TEST_ONLY_WORKER_GENERATED_SOURCE"
VERSION = "ra4b-p2-generated-target-v1"


@dataclass(frozen=True)
class GeneratedGraph:
    target: bytes
    manifest: bytes
    artifacts: tuple[Artifact, ...]

    @property
    def target_digest(self):
        return digest("target", json.loads(self.target))


def assemble(candidate: GeneratedCandidate):
    doc = candidate.private_document
    d = doc["report"]
    s = json.loads(candidate._source)
    p = d["pins"]
    if doc["committed"] or doc["commit_receipt"] is not None:
        raise CandidateDenied("S2_NOT_AN_AUTHORIZED_COMMIT_RECEIPT")
    objects = {k: base64.b64decode(v, validate=True) for k, v in s["objects_base64"].items()}
    pack = EvidencePack.load(s["pack"], objects, expected_ref=p["expected_pack_ref"])
    finding_keys = (
        "expected_pack_ref",
        "expected_execution_ref",
        "expected_package_ref",
        "expected_evaluator_version",
        "expected_builder_version",
    )
    package = FindingPackage.load(s["package"], pack, **{k: p[k] for k in finding_keys})
    draft = ReportDraft.load(
        d,
        candidate._html,
        pack,
        package,
        s["guard_inputs"],
        s["metadata"],
        expected_draft_ref=doc["draft_ref"],
        **p,
    )
    if sha(encode(d)) != doc["report_sha256"] or sha(candidate._html) != doc["html_sha256"]:
        raise CandidateDenied("S2_GRAPH_HASH_MISMATCH")
    native = d["native_report_version"]
    binding = doc["binding"]
    target = {
        "contract_version": VERSION,
        "authority": AUTHORITY,
        "kind": "L1_NATIVE" if native else "COVERAGE_ONLY",
        **d["scope"],
        "report_id": d["metadata"]["report_id"],
        "report_version": d["metadata"]["version"],
        "native_content_hash": native["content_hash"] if native else None,
        "native_report_version_id": native["report_version_id"] if native else None,
        "draft_ref": draft.ref,
        "draft_payload_sha256": sha(encode(d)),
        "editorial_content_sha256": d["editorial_content_sha256"],
        "html_sha256": sha(candidate._html),
        "renderer_asset_sha256": asset_hash(),
        "evidence_pack_ref": pack.ref,
        "execution_ref": p["expected_execution_ref"],
        "finding_package_ref": package.ref,
        "ordered_guard_refs": p["expected_guard_refs"],
        "source_manifest_sha256": sha(
            canonical(
                {
                    "pack_ref": pack.ref,
                    "document": pack.document,
                    "objects": [
                        {"object_key": k, "content_sha256": sha(v), "length_bytes": len(v)}
                        for k, v in sorted(objects.items())
                    ],
                },
                limit=SOURCE_LIMIT,
            )
        ),
        "source_record_sha256": sha(candidate._source),
        "guard_inputs_sha256": d["guard_inputs_sha256"],
        "builder_version": p["expected_builder_version"],
        "evaluator_version": p["expected_evaluator_version"],
        "guard_version": p["expected_guard_version"],
        "reporting_version": d["reporting_version"],
        "editorial_version": d["editorial_version"],
        "renderer_version": d["renderer_version"],
        "model_provenance": [
            {
                "guard_ref": b["guard"]["guard_ref"],
                "mode": "SYNTHETIC_NO_MODEL_NOT_RUN",
                "model_id": None,
                "interpretation_sha256": sha(encode(b["interpretation"])),
            }
            for b in s["guard_inputs"]
        ],
        "artifact_ref": "private-generated://"
        + binding["tenant_id"]
        + "/"
        + d["metadata"]["report_id"]
        + "/v1/"
        + sha(candidate._html),
        "claims": _claim_manifest(d, pack, s),
        "required_sections": list(SECTIONS),
        "scope_digest": digest(
            "coverage",
            {
                "pages": d["examined_pages"],
                "recorded_coverage": d["recorded_coverage"],
                "journey": d["buyer_journey"],
            },
        ),
        "limitations_digest": digest("limitations", d["limitations"]),
        "generated_binding": binding,
        "candidate_sha256": sha(candidate._payload),
    }
    raw = canonical(target)
    artifacts = [
        Artifact("DRAFT", "draft", encode(d)),
        Artifact("HTML", "html", candidate._html),
        Artifact("SOURCE", "source", candidate._source),
        Artifact("PACK", "pack", canonical(s["pack"], limit=SOURCE_LIMIT)),
        Artifact("PACKAGE", "package", canonical(s["package"], limit=SOURCE_LIMIT)),
        Artifact("GUARD", "guard", canonical(s["guard_inputs"], limit=SOURCE_LIMIT)),
        Artifact("METADATA", "metadata", canonical(s["metadata"], limit=SOURCE_LIMIT)),
        Artifact("CSS", "css", (RENDERER_VERSION + "\n" + CSS).encode()),
        Artifact("TARGET", "target", raw),
    ]
    artifacts.extend(Artifact("SOURCE_OBJECT", k, v) for k, v in objects.items())
    artifacts = sorted(artifacts, key=lambda a: (a.kind, a.key))
    if (
        len(artifacts) > 137
        or sum(len(a.raw) for a in artifacts) > 64000000
        or any(len(a.raw) > 8000000 for a in artifacts)
    ):
        raise CandidateDenied("S2_GRAPH_BOUND")
    return GeneratedGraph(
        raw, canonical(descriptors(artifacts), limit=SOURCE_LIMIT), tuple(artifacts)
    )
```

`docs/03-engineering/ra4b-p2/held/003_generated_seal.sql.proposed` SHA256 `71fa390fd0059001a7712012ddbd2d781eb6369f11df0e9424f90429d4da0923`
```
-- REVIEW ARTIFACT ONLY. NOT A MIGRATION. NOT INSTALLED BY ANY HARNESS.
-- Requires separate Owner L3 approval. Native positive/rollback proof is HOLD.
-- Prerequisite: experimental ra4b_p2/001 + exact three conditional policies.
BEGIN;
SET ROLE ra4a_owner;

-- First incompatible original contract: references_metadata_check (23514).
-- The accepted authority branch is retained; a distinct generated authority
-- requires the additional genuine-Worker trigger below, never fixture identity.
ALTER TABLE ra4a.references DROP CONSTRAINT references_metadata_check;
ALTER TABLE ra4a.references ADD CONSTRAINT references_metadata_check CHECK (
 jsonb_typeof(metadata)='object' AND
 (metadata->>'authority'='TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE' OR
  (metadata->>'authority'='TEST_ONLY_WORKER_GENERATED_SOURCE' AND
   metadata->>'contract_version'='ra4b-p2-generated-target-v1')));

CREATE FUNCTION ra4b_p2.generated_reference_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE c ra4b_p2.candidate_bindings%ROWTYPE; b jsonb; d jsonb; BEGIN
 IF NEW.metadata->>'authority'<>'TEST_ONLY_WORKER_GENERATED_SOURCE' THEN RETURN NEW; END IF;
 b:=NEW.metadata->'generated_binding';
 SELECT * INTO STRICT c FROM ra4b_p2.candidate_bindings
 WHERE tenant_id=NEW.tenant_id AND job_id=(b->>'job_id')::uuid AND lease_seq=(b->>'lease_seq')::integer;
 PERFORM ra4b_test.require_run(c.tenant_id,c.run_id,'WORKER');
 IF SESSION_USER<>c.worker_role OR SESSION_USER NOT IN('ra4b_test_a_worker','ra4b_test_b_worker')
 OR pg_has_role(SESSION_USER,'p2a_fixture_writer','MEMBER') OR c.lease_until<=clock_timestamp()
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_GENERATED_REFERENCE_WORKER_ONLY'; END IF;
 d:=convert_from(c.candidate,'UTF8')::jsonb;
 IF b IS DISTINCT FROM d->'binding'
 OR NEW.metadata->>'candidate_sha256' IS DISTINCT FROM c.candidate_sha256
 OR (NEW.source_run_id,NEW.report_id,NEW.report_version,NEW.policy_id,NEW.policy_version)
 IS DISTINCT FROM(c.run_id::text,'job-'||c.job_id::text,1,c.policy_id,c.policy_version)
 OR NEW.metadata->>'source_record_sha256' IS DISTINCT FROM c.source_record_sha256
 OR NEW.metadata->>'draft_payload_sha256' IS DISTINCT FROM d->>'report_sha256'
 OR NEW.metadata->>'html_sha256' IS DISTINCT FROM c.html_sha256
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_GENERATED_REFERENCE_BINDING'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER s2_generated_reference BEFORE INSERT ON ra4a.references
 FOR EACH ROW EXECUTE FUNCTION ra4b_p2.generated_reference_guard();

-- Private storage seam, called only inside the 12-argument commit below.
-- Original fixture-only register is unchanged and still rejects real Worker.
CREATE FUNCTION ra4b_p2.register_generated_graph(t text,id uuid,token uuid,seq integer,
 target_raw bytea,manifest_raw bytea,kinds text[],keys text[],payloads bytea[])
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE c ra4b_p2.candidate_bindings%ROWTYPE; d jsonb; v jsonb; src jsonb;
 ref text; n integer; i integer; total bigint:=0; expected bytea; descriptors jsonb;
BEGIN
 PERFORM ra4b_p2.require_lease(t,id,token,seq);
 SELECT * INTO STRICT c FROM ra4b_p2.candidate_bindings WHERE tenant_id=t AND job_id=id AND lease_seq=seq;
 d:=convert_from(c.candidate,'UTF8')::jsonb;
 src:=convert_from(c.source_record,'UTF8')::jsonb;
 v:=convert_from(target_raw,'UTF8')::jsonb;
 n:=cardinality(payloads);
 IF target_raw IS NULL OR manifest_raw IS NULL OR n IS NULL OR n NOT BETWEEN 9 AND 137
 OR array_ndims(payloads)<>1 OR array_ndims(kinds)<>1 OR array_ndims(keys)<>1
 OR array_lower(payloads,1)<>1 OR array_lower(kinds,1)<>1 OR array_lower(keys,1)<>1
 OR cardinality(kinds)<>n OR cardinality(keys)<>n
 OR octet_length(target_raw) NOT BETWEEN 1 AND 65536
 OR octet_length(manifest_raw) NOT BETWEEN 1 AND 8000000
 OR target_raw IS DISTINCT FROM ra4a_bytes.canonical_bytes(v)
 OR v->>'authority' IS DISTINCT FROM 'TEST_ONLY_WORKER_GENERATED_SOURCE'
 OR v->>'contract_version' IS DISTINCT FROM 'ra4b-p2-generated-target-v1'
 OR v->'generated_binding' IS DISTINCT FROM d->'binding'
 OR v->>'candidate_sha256' IS DISTINCT FROM c.candidate_sha256
 OR (v->>'tenant_id',v->>'run_id',v->>'report_id',(v->>'report_version')::integer)
 IS DISTINCT FROM(t,c.run_id::text,'job-'||id::text,1)
 OR v->>'policy_id' IS DISTINCT FROM c.policy_id
 OR (v->>'policy_version')::integer IS DISTINCT FROM c.policy_version
 OR v->>'source_record_sha256' IS DISTINCT FROM c.source_record_sha256
 OR v->>'html_sha256' IS DISTINCT FROM c.html_sha256
 OR v->>'draft_payload_sha256' IS DISTINCT FROM d->>'report_sha256'
 OR v->>'draft_ref' IS DISTINCT FROM d->>'draft_ref'
 OR v->>'evidence_pack_ref' IS DISTINCT FROM d->>'evidence_pack_ref'
 OR v->>'execution_ref' IS DISTINCT FROM d->>'rule_execution_ref'
 OR v->>'finding_package_ref' IS DISTINCT FROM d->>'finding_package_ref'
 OR v->'ordered_guard_refs' IS DISTINCT FROM d->'guard_refs'
 OR v->>'guard_inputs_sha256' IS DISTINCT FROM d->'report'->>'guard_inputs_sha256'
 OR v->>'guard_version' IS DISTINCT FROM 'ra3b-disc-1.0.0'
 OR v->>'reporting_version' IS DISTINCT FROM 'ra3c-disc-1.0.0'
 OR v->>'renderer_version' IS DISTINCT FROM 'ra3c-disc-html-1.0.0'
 OR v->>'evaluator_version' IS DISTINCT FROM 'ra2b6-1.0.0'
 OR v->>'builder_version' IS DISTINCT FROM 'ra2c3-1.0.0'
 OR v->'required_sections' IS DISTINCT FROM '["coverage.v1","limitations.v1","full_preview.v1","business_boundaries.v1"]'::jsonb
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_GENERATED_GRAPH_BINDING'; END IF;
 -- Never accept arbitrary source bytes even when a caller recomputes hashes.
 IF src->'objects_base64' IS DISTINCT FROM (
  SELECT convert_from(raw_source,'UTF8')::jsonb->'objects_base64'
  FROM ra4b_p2.load_leased_source(t,id,token,seq))
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_GENERATED_SOURCE_BYTES'; END IF;
 FOR i IN 1..n LOOP
  IF kinds[i] IS NULL OR keys[i] IS NULL OR payloads[i] IS NULL
  OR length(keys[i]) NOT BETWEEN 1 AND 128 OR octet_length(payloads[i])>8000000
  OR kinds[i] NOT IN('DRAFT','HTML','SOURCE','PACK','PACKAGE','GUARD','METADATA','CSS','TARGET','SOURCE_OBJECT')
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_GENERATED_ARTIFACT_BOUND'; END IF;
  total:=total+octet_length(payloads[i]);
  expected:=CASE kinds[i]
   WHEN 'DRAFT' THEN ra4a_bytes.canonical_bytes(d->'report')
   WHEN 'HTML' THEN c.html WHEN 'SOURCE' THEN c.source_record WHEN 'TARGET' THEN target_raw
   WHEN 'PACK' THEN ra4a_bytes.canonical_bytes(src->'pack')
   WHEN 'PACKAGE' THEN ra4a_bytes.canonical_bytes(src->'package')
   WHEN 'GUARD' THEN ra4a_bytes.canonical_bytes(src->'guard_inputs')
   WHEN 'METADATA' THEN ra4a_bytes.canonical_bytes(src->'metadata')
   WHEN 'SOURCE_OBJECT' THEN decode(src->'objects_base64'->>keys[i],'base64')
   ELSE payloads[i] END;
  IF payloads[i] IS DISTINCT FROM expected THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_GENERATED_ARTIFACT_BYTES'; END IF;
 END LOOP;
 SELECT jsonb_agg(jsonb_build_object('key',keys[k],'kind',kinds[k],
  'sha256',encode(sha256(payloads[k]),'hex'),'length',octet_length(payloads[k]))
  ORDER BY kinds[k] COLLATE "C",keys[k] COLLATE "C") INTO descriptors FROM generate_series(1,n) k;
 IF total>64000000 OR manifest_raw IS DISTINCT FROM ra4a_bytes.canonical_bytes(descriptors)
 OR (SELECT count(DISTINCT (kinds[k],keys[k])) FROM generate_series(1,n) k)<>n
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='S2_GENERATED_MANIFEST'; END IF;
 ref:='generated-'||id::text||'-'||seq::text;
 INSERT INTO ra4a.references(tenant_id,ref_id,policy_id,policy_version,report_id,source_run_id,
  report_version,kind,issue_count,native_h0,native_id,target_digest,ref_sha256,metadata)
 VALUES(t,ref,c.policy_id,c.policy_version,'job-'||id::text,c.run_id::text,1,v->>'kind',
  jsonb_array_length(d->'report'->'issues'),v->>'native_content_hash',v->>'native_report_version_id',
  encode(sha256(convert_to('vrae.ra3d.target.offline-v1'||chr(10),'UTF8')||target_raw),'hex'),
  encode(sha256(target_raw),'hex'),v);
 INSERT INTO ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version,ref_id,target_payload,manifest)
 VALUES(t,c.run_id::text,'job-'||id::text,1,ref,target_raw,manifest_raw);
 INSERT INTO ra4a_bytes.objects(tenant_id,source_run_id,report_id,report_version,kind,object_key,raw)
 SELECT t,c.run_id::text,'job-'||id::text,1,kinds[k],keys[k],payloads[k] FROM generate_series(1,n) k;
 INSERT INTO ra4a_bytes.events(tenant_id,source_run_id,report_id,report_version,db_principal)
 VALUES(t,c.run_id::text,'job-'||id::text,1,SESSION_USER);
 -- Original deferred complete_graph/check_binding/no_append remain installed.
 RETURN ref;
END $$;

-- Draft-only seven-argument endpoint is retained. This new overload is held.
CREATE FUNCTION ra4b_p2.commit_generated_result(t text,id uuid,token uuid,seq integer,
 candidate_raw bytea,source_raw bytea,html_raw bytea,target_raw bytea,manifest_raw bytea,
 kinds text[],keys text[],payloads bytea[]) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE ref text; event uuid; g ra4a_bytes.graphs%ROWTYPE; BEGIN
 PERFORM ra4b_p2.commit_generated_result(t,id,token,seq,candidate_raw,source_raw,html_raw);
 ref:=ra4b_p2.register_generated_graph(t,id,token,seq,target_raw,manifest_raw,kinds,keys,payloads);
 event:=ra4b_test.finish(t,id,token,seq);
 SELECT * INTO STRICT g FROM ra4a_bytes.graphs WHERE tenant_id=t AND ref_id=ref;
 INSERT INTO ra4b_p2.sealed_bindings(tenant_id,job_id,lease_seq,generated_ref,report_id,report_version,
  target_digest,manifest_sha256,finish_event,transaction_id)
 VALUES(t,id,seq,ref,g.report_id,g.report_version,g.target_digest,g.manifest_sha256,event,txid_current());
 INSERT INTO ra4b_p2.result_audit VALUES(t,id,seq,event,txid_current(),g.target_digest);
 INSERT INTO ra4b_p2.result_outbox VALUES(t,id,seq,event,txid_current(),g.target_digest);
 RETURN jsonb_build_object('status','SEALED_TEST_ONLY_NOT_APPROVED','job_id',id,'lease_seq',seq,
  'generated_ref',ref,'target_digest',g.target_digest,'manifest_sha256',g.manifest_sha256,'finish_event',event);
END $$;

-- Replace only the NEW candidate guard. Original 0004 commit_guard is intact.
CREATE OR REPLACE FUNCTION ra4b_p2.candidate_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE j ra4a.jobs%ROWTYPE; BEGIN
 PERFORM ra4b_test.require_run(NEW.tenant_id,NEW.run_id,'WORKER');
 SELECT * INTO STRICT j FROM ra4a.jobs WHERE tenant_id=NEW.tenant_id AND job_id=NEW.job_id;
 IF SESSION_USER IS DISTINCT FROM NEW.worker_role OR j.lease_owner IS DISTINCT FROM SESSION_USER
 OR j.lease_seq IS DISTINCT FROM NEW.lease_seq OR j.lease_until IS DISTINCT FROM NEW.lease_until
 OR j.lease_until<=clock_timestamp()
 OR encode(sha256(convert_to(j.lease_token::text,'UTF8')),'hex') IS DISTINCT FROM NEW.lease_token_sha256
 OR NOT(j.state='LEASED' OR (j.state='TEST_ONLY_DONE' AND EXISTS(
  SELECT 1 FROM ra4b_p2.sealed_bindings z JOIN ra4b_p2.result_audit a USING(tenant_id,job_id,lease_seq)
  JOIN ra4b_p2.result_outbox o USING(tenant_id,job_id,lease_seq)
  JOIN ra4a.outbox e ON(e.tenant_id,e.event_id)=(z.tenant_id,z.finish_event)
  JOIN ra4a.audit au ON(au.tenant_id,au.run_id,au.lease_seq)=(NEW.tenant_id,NEW.run_id,NEW.lease_seq)
  WHERE(z.tenant_id,z.job_id,z.lease_seq)=(NEW.tenant_id,NEW.job_id,NEW.lease_seq)
  AND z.transaction_id=txid_current() AND z.sealed_at<NEW.lease_until
  AND e.run_id=NEW.run_id AND e.kind='TEST_ONLY_CONSUMED'
  AND au.action='TEST_ONLY_CONSUMED' AND au.db_principal=SESSION_USER
  AND (a.event_id,a.transaction_id,a.target_digest)=(z.finish_event,z.transaction_id,z.target_digest)
  AND (o.event_id,o.transaction_id,o.target_digest)=(a.event_id,a.transaction_id,a.target_digest))))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_CURRENT_AT_COMMIT_DENIED'; END IF;
 RETURN NULL;
END $$;
-- Ensure an already-staged candidate also rechecks at final seal COMMIT.
CREATE FUNCTION ra4b_p2.sealed_commit_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE c ra4b_p2.candidate_bindings%ROWTYPE; j ra4a.jobs%ROWTYPE; BEGIN
 SELECT * INTO STRICT c FROM ra4b_p2.candidate_bindings
 WHERE(tenant_id,job_id,lease_seq)=(NEW.tenant_id,NEW.job_id,NEW.lease_seq);
 PERFORM ra4b_test.require_run(c.tenant_id,c.run_id,'WORKER');
 SELECT * INTO STRICT j FROM ra4a.jobs WHERE(tenant_id,job_id)=(c.tenant_id,c.job_id);
 IF SESSION_USER IS DISTINCT FROM c.worker_role OR j.state<>'TEST_ONLY_DONE'
 OR j.lease_owner IS DISTINCT FROM SESSION_USER OR j.lease_seq IS DISTINCT FROM c.lease_seq
 OR j.lease_until IS DISTINCT FROM c.lease_until OR j.lease_until<=clock_timestamp()
 OR encode(sha256(convert_to(j.lease_token::text,'UTF8')),'hex') IS DISTINCT FROM c.lease_token_sha256
 OR NEW.transaction_id<>txid_current() OR NEW.sealed_at>=c.lease_until
 OR NOT EXISTS(SELECT 1 FROM ra4a.outbox e JOIN ra4a.audit a USING(tenant_id,run_id)
 JOIN ra4a_bytes.graphs g ON(g.tenant_id,g.ref_id)=(NEW.tenant_id,NEW.generated_ref)
 JOIN ra4a_bytes.events ge ON(ge.tenant_id,ge.source_run_id,ge.report_id,ge.report_version)=
 (g.tenant_id,g.source_run_id,g.report_id,g.report_version)
 JOIN ra4b_p2.result_audit au ON(au.tenant_id,au.job_id)=(NEW.tenant_id,NEW.job_id)
 JOIN ra4b_p2.result_outbox ob ON(ob.tenant_id,ob.job_id)=(NEW.tenant_id,NEW.job_id)
 WHERE(e.tenant_id,e.run_id,e.event_id)=(c.tenant_id,c.run_id,NEW.finish_event)
 AND e.kind='TEST_ONLY_CONSUMED' AND a.action='TEST_ONLY_CONSUMED'
 AND a.db_principal=SESSION_USER AND a.lease_seq=c.lease_seq AND ge.db_principal=SESSION_USER
 AND (g.source_run_id,g.report_id,g.report_version,g.target_digest,g.manifest_sha256)=
 (c.run_id::text,NEW.report_id,NEW.report_version,NEW.target_digest,NEW.manifest_sha256)
 AND (au.event_id,au.transaction_id,au.target_digest)=(NEW.finish_event,NEW.transaction_id,NEW.target_digest)
 AND (ob.event_id,ob.transaction_id,ob.target_digest)=(au.event_id,au.transaction_id,au.target_digest))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='S2_SEAL_CURRENT_AT_COMMIT_DENIED'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER sealed_current_at_commit AFTER INSERT ON ra4b_p2.sealed_bindings
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4b_p2.sealed_commit_guard();
REVOKE ALL ON FUNCTION ra4b_p2.generated_reference_guard(),
 ra4b_p2.sealed_commit_guard(),
 ra4b_p2.register_generated_graph(text,uuid,uuid,integer,bytea,bytea,text[],text[],bytea[]),
 ra4b_p2.commit_generated_result(text,uuid,uuid,integer,bytea,bytea,bytea,bytea,bytea,text[],text[],bytea[])
 FROM PUBLIC,ra4b_worker,p2b1_review;
GRANT EXECUTE ON FUNCTION ra4b_p2.commit_generated_result(text,uuid,uuid,integer,bytea,bytea,bytea,bytea,bytea,text[],text[],bytea[]) TO ra4b_worker;
RESET ROLE;
COMMIT;
```

`docs/03-engineering/ra4b-p2/held/source_adapter.py.proposed` SHA256 `379aed6af5b3ab9a9edf0cb4b859c3613fe6967f6fb4a4027762c21ee2ec24fb`
```
"""REVIEW ONLY: proposed addition to the new source_adapter, never imported.

Requires Owner approval of 003_generated_seal.sql.proposed and a new native
transaction/rollback gate. A SQL return inside the transaction is not evidence
of durable success. No Reviewer assignment/approval is created here.
"""

from psycopg.pq import TransactionStatus
from vrae.application.ra4b_p2.generated_graph import assemble
from vrae.application.ra4b_p2.producer import CandidateDenied


def commit_sealed(c, tenant, lease, candidate):
    if not c.autocommit or c.info.transaction_status != TransactionStatus.IDLE:
        raise CandidateDenied("S2_TOP_LEVEL_COMMIT_REQUIRED")
    graph = assemble(candidate)  # Full versioned DISC replay before SQL.
    artifacts = graph.artifacts
    with c.transaction():
        receipt = c.execute(
            "SELECT ra4b_p2.commit_generated_result(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                tenant, lease[0], lease[2], lease[3],
                candidate._payload, candidate._source, candidate._html,
                graph.target, graph.manifest,
                [a.kind for a in artifacts], [a.key for a in artifacts],
                [a.raw for a in artifacts],
            ),
        ).fetchone()[0]
    # Only after the actual outer COMMIT and all original deferred checks.
    return receipt
```

`docs/03-engineering/ra4b-p2/held/worker.py.diff.proposed` SHA256 `cebe77a3fc16a2a72ac6fb9d6f1071ed973984c3e012158145dbfe3de1b13494`
```
--- a/vrae/application/ra4b_p2/worker.py
+++ b/vrae/application/ra4b_p2/worker.py
@@ -13,7 +13,7 @@
 
 def main():
     from vrae.application.ra4b import store
-    from .source_adapter import build, stage
+    from .source_adapter import build, commit_sealed
 
     parser = argparse.ArgumentParser()
     parser.add_argument("--config", required=True)
@@ -30,7 +30,7 @@
             return
         started = time.monotonic()
         candidate, _ = build(c, config["tenant"], lease)
-        receipt = stage(c, config["tenant"], lease, candidate)
+        receipt = commit_sealed(c, config["tenant"], lease, candidate)
         receipt["generation_and_draft_commit_seconds"] = time.monotonic() - started
         if args.private_receipt:
             path = Path(args.private_receipt)
```
