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
