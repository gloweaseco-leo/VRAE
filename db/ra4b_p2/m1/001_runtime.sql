-- Owner6895929839 / stage charter: new private synthetic M1 result lane.
-- Never installs the archived S2 001/002 or held legacy graph writer.
BEGIN;
CREATE SCHEMA ra4b_p2 AUTHORIZATION ra4a_owner;
REVOKE ALL ON SCHEMA ra4b_p2 FROM PUBLIC;
SET ROLE ra4a_owner;
CREATE TABLE ra4b_p2.m1_inputs(
 tenant_id text NOT NULL,source_ref text NOT NULL,reference_sha256 text NOT NULL,
 source_record bytea NOT NULL CHECK(octet_length(source_record) BETWEEN 1 AND 8000000),
 source_sha256 text GENERATED ALWAYS AS(encode(sha256(source_record),'hex')) STORED,
 policy_document jsonb NOT NULL,audit_document jsonb NOT NULL,reviewer_role name NOT NULL,
 PRIMARY KEY(tenant_id,source_ref),FOREIGN KEY(tenant_id,source_ref) REFERENCES ra4a.references);
CREATE TABLE ra4b_p2.m1_results(
 tenant_id text NOT NULL,job_id uuid NOT NULL,request_id uuid NOT NULL,run_id uuid NOT NULL,
 worker_role name NOT NULL,lease_seq integer NOT NULL,lease_token_sha256 text NOT NULL,
 lease_until timestamptz NOT NULL,origin_role name NOT NULL,origin_epoch bigint NOT NULL,
 source_ref text NOT NULL,input_sha256 text NOT NULL,reference_sha256 text NOT NULL,
 policy_id text NOT NULL,policy_version integer NOT NULL,
 source_record bytea NOT NULL CHECK(octet_length(source_record) BETWEEN 1 AND 8000000),
 report bytea NOT NULL CHECK(octet_length(report) BETWEEN 1 AND 8000000),
 html bytea NOT NULL CHECK(octet_length(html) BETWEEN 1 AND 8000000),
 binding bytea NOT NULL CHECK(octet_length(binding) BETWEEN 1 AND 8192),
 source_sha256 text GENERATED ALWAYS AS(encode(sha256(source_record),'hex')) STORED,
 report_sha256 text GENERATED ALWAYS AS(encode(sha256(report),'hex')) STORED,
 html_sha256 text GENERATED ALWAYS AS(encode(sha256(html),'hex')) STORED,
 report_id text NOT NULL,report_version integer NOT NULL CHECK(report_version=1),
 finish_event uuid NOT NULL,transaction_id bigint NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,job_id),UNIQUE(tenant_id,report_id,report_version),
 FOREIGN KEY(tenant_id,job_id) REFERENCES ra4a.jobs,
 FOREIGN KEY(tenant_id,run_id) REFERENCES ra4a.runs,
 FOREIGN KEY(tenant_id,request_id) REFERENCES ra4a.requests,
 FOREIGN KEY(tenant_id,source_ref) REFERENCES ra4b_p2.m1_inputs);
CREATE TABLE ra4b_p2.m1_assignments(
 tenant_id text NOT NULL,job_id uuid NOT NULL,db_role name NOT NULL,active boolean NOT NULL DEFAULT true,
 PRIMARY KEY(tenant_id,job_id,db_role),FOREIGN KEY(tenant_id,job_id) REFERENCES ra4b_p2.m1_results);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['m1_inputs','m1_results','m1_assignments'] LOOP
  EXECUTE format('ALTER TABLE ra4b_p2.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE ra4b_p2.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY scoped_m1 ON ra4b_p2.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',tab);
 END LOOP;
END $$;
CREATE FUNCTION ra4b_p2.m1_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M1_IMMUTABLE'; END $$;
CREATE TRIGGER immutable_m1 BEFORE UPDATE OR DELETE ON ra4b_p2.m1_inputs
 FOR EACH ROW EXECUTE FUNCTION ra4b_p2.m1_immutable();
CREATE TRIGGER immutable_m1 BEFORE UPDATE OR DELETE ON ra4b_p2.m1_results
 FOR EACH ROW EXECUTE FUNCTION ra4b_p2.m1_immutable();
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['m1_inputs','m1_results','m1_assignments'] LOOP
  EXECUTE format('CREATE TRIGGER no_truncate_m1 BEFORE TRUNCATE ON ra4b_p2.%I FOR EACH STATEMENT EXECUTE FUNCTION ra4b_p2.m1_immutable()',tab);
 END LOOP;
END $$;
CREATE FUNCTION ra4b_p2.m1_input_guard() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$ BEGIN
 IF SESSION_USER<>'postgres' OR CURRENT_USER<>'postgres' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_PROVISIONED_INPUT_ONLY'; END IF;
 IF NOT EXISTS(SELECT 1 FROM ra4a.references r JOIN ra4a_private.principals reviewer
  ON reviewer.db_role=NEW.reviewer_role AND reviewer.tenant_id=r.tenant_id
  WHERE(r.tenant_id,r.ref_id,r.ref_sha256)=(NEW.tenant_id,NEW.source_ref,NEW.reference_sha256)
  AND r.metadata->>'source_record_sha256'=encode(sha256(NEW.source_record),'hex')
  AND NEW.policy_document->>'tenant_id'=r.tenant_id
  AND NEW.policy_document->>'policy_id'=r.policy_id
  AND (NEW.policy_document->>'policy_version')::integer=r.policy_version
  AND NEW.audit_document->>'tenant_id'=r.tenant_id
  AND NEW.audit_document->>'source_policy_ref'=r.policy_id
  AND (NEW.audit_document->>'source_policy_version')::integer=r.policy_version
  AND reviewer.kind='APP' AND reviewer.enabled AND pg_has_role(reviewer.db_role,'p2b1_review','MEMBER'))
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='M1_INPUT_BINDING'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER provisioned_input BEFORE INSERT ON ra4b_p2.m1_inputs
 FOR EACH ROW EXECUTE FUNCTION ra4b_p2.m1_input_guard();
CREATE FUNCTION ra4b_p2.m1_lease(t text,id uuid,token uuid,seq integer) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE rid uuid; BEGIN
 PERFORM ra4b_test.require_actor(t,'WORKER');
 IF SESSION_USER NOT IN('ra4b_test_a_worker','ra4b_test_b_worker')
 OR pg_has_role(SESSION_USER,'p2a_fixture_writer','MEMBER') THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_WORKER_ONLY'; END IF;
 SELECT run_id INTO rid FROM ra4a.jobs WHERE tenant_id=t AND job_id=id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_LEASE_DENIED'; END IF;
 PERFORM ra4b_test.require_run(t,rid,'WORKER');
 IF NOT EXISTS(SELECT 1 FROM ra4a.jobs WHERE tenant_id=t AND job_id=id
  AND state='LEASED' AND lease_owner=SESSION_USER AND lease_token=token AND lease_seq=seq
  AND lease_until>clock_timestamp()) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_LEASE_DENIED'; END IF;
END $$;
CREATE FUNCTION ra4b_p2.m1_load_source(t text,id uuid,token uuid,seq integer)
 RETURNS TABLE(tenant_id text,request_id uuid,run_id uuid,job_id uuid,worker_role name,
 lease_until timestamptz,origin_epoch bigint,source_ref text,reference_sha256 text,
 raw_source bytea,raw_source_sha256 text,policy_document jsonb,audit_document jsonb,loaded_at timestamptz)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$ BEGIN
 PERFORM ra4b_p2.m1_lease(t,id,token,seq);
 RETURN QUERY SELECT q.tenant_id,q.request_id,j.run_id,j.job_id,SESSION_USER::name,j.lease_until,
 b.epoch,q.source_ref,i.reference_sha256,i.source_record,i.source_sha256,i.policy_document,i.audit_document,clock_timestamp()
 FROM ra4a.jobs j JOIN ra4a.runs s USING(tenant_id,run_id) JOIN ra4a.requests q USING(tenant_id,request_id)
 JOIN ra4b_test.request_origins b USING(tenant_id,request_id)
 JOIN ra4b_p2.m1_inputs i ON(i.tenant_id,i.source_ref)=(q.tenant_id,q.source_ref)
 WHERE j.tenant_id=t AND j.job_id=id;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_INPUT_DENIED'; END IF;
END $$;
CREATE FUNCTION ra4b_p2.m1_commit(t text,id uuid,token uuid,seq integer,
 source_raw bytea,report_raw bytea,html_raw bytea,binding_raw bytea) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE x record; src jsonb; d jsonb; b jsonb; origin name; event uuid; existing ra4b_p2.m1_results%ROWTYPE;
BEGIN
 PERFORM ra4b_test.require_actor(t,'WORKER');
 SELECT * INTO existing FROM ra4b_p2.m1_results WHERE tenant_id=t AND job_id=id;
 IF FOUND THEN
  PERFORM ra4b_test.require_run(t,existing.run_id,'WORKER');
  IF SESSION_USER IS DISTINCT FROM existing.worker_role OR seq IS DISTINCT FROM existing.lease_seq
   OR existing.lease_until<=clock_timestamp()
   OR encode(sha256(convert_to(token::text,'UTF8')),'hex') IS DISTINCT FROM existing.lease_token_sha256
   THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_REPLAY_LEASE_DENIED'; END IF;
  IF (source_raw,report_raw,html_raw,binding_raw) IS DISTINCT FROM
   (existing.source_record,existing.report,existing.html,existing.binding)
   THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='M1_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN jsonb_build_object('tenant_id',t,'job_id',id,'request_id',existing.request_id,'run_id',existing.run_id,
   'report_id',existing.report_id,'report_version',1,'report_sha256',existing.report_sha256,
   'source_sha256',existing.source_sha256,'html_sha256',existing.html_sha256,
   'finish_event',existing.finish_event,'authority','TEST_ONLY_GENERATED_NOT_APPROVED');
 END IF;
 PERFORM ra4b_p2.m1_lease(t,id,token,seq);
 SELECT * INTO STRICT x FROM ra4b_p2.m1_load_source(t,id,token,seq);
 src:=convert_from(source_raw,'UTF8')::jsonb; d:=convert_from(report_raw,'UTF8')::jsonb;
 b:=convert_from(binding_raw,'UTF8')::jsonb;
 IF source_raw IS NULL OR report_raw IS NULL OR html_raw IS NULL OR binding_raw IS NULL
 OR ra4a_bytes.canonical_bytes(src) IS DISTINCT FROM source_raw
 OR ra4a_bytes.canonical_bytes(d) IS DISTINCT FROM report_raw
 OR ra4a_bytes.canonical_bytes(b) IS DISTINCT FROM binding_raw
 OR (b->>'tenant_id',b->>'request_id',b->>'run_id',b->>'job_id',b->>'worker')
 IS DISTINCT FROM(t,x.request_id::text,x.run_id::text,id::text,SESSION_USER::text)
 OR (b->>'lease_seq')::integer IS DISTINCT FROM seq
 OR b->>'lease_token_sha256' IS DISTINCT FROM encode(sha256(convert_to(token::text,'UTF8')),'hex')
 OR (b->>'lease_until')::timestamptz IS DISTINCT FROM x.lease_until
 OR (b->>'origin_epoch')::bigint IS DISTINCT FROM x.origin_epoch
 OR (b->>'source_ref',b->>'reference_sha256') IS DISTINCT FROM(x.source_ref,x.reference_sha256)
 OR b->>'policy_sha256' IS DISTINCT FROM encode(sha256(ra4a_bytes.canonical_bytes(x.policy_document)),'hex')
 OR (b->>'policy_id',(b->>'policy_version')::integer) IS DISTINCT FROM
 (x.audit_document->>'source_policy_ref',(x.audit_document->>'source_policy_version')::integer)
 OR d->'scope' IS DISTINCT FROM jsonb_build_object('tenant_id',t,'run_id',x.run_id::text,
 'policy_id',b->>'policy_id','policy_version',(b->>'policy_version')::integer)
 OR d->'pins'->'expected_scope' IS DISTINCT FROM d->'scope'
 OR d->'metadata'->>'report_id' IS DISTINCT FROM 'job-'||id::text
 OR (d->'metadata'->>'version')::integer IS DISTINCT FROM 1
 OR d->>'approval_status' IS DISTINCT FROM 'NOT_APPROVED' OR d->'shareable' IS DISTINCT FROM 'false'::jsonb
 OR d->'semantic_approval' IS DISTINCT FROM 'false'::jsonb
 OR d->>'reporting_version' IS DISTINCT FROM 'ra3c-disc-1.0.0'
 OR d->>'renderer_version' IS DISTINCT FROM 'ra3c-disc-html-1.0.0'
 OR d->'pins'->>'expected_guard_version' IS DISTINCT FROM 'ra3b-disc-1.0.0'
 OR d->'pins'->>'expected_evaluator_version' IS DISTINCT FROM 'ra2b6-1.0.0'
 OR d->'pins'->>'expected_builder_version' IS DISTINCT FROM 'ra2c3-1.0.0'
 OR d->>'html_sha256' IS DISTINCT FROM encode(sha256(html_raw),'hex')
 OR src->'metadata' IS DISTINCT FROM d->'metadata'
 OR src->'pack'->>'pack_ref' IS DISTINCT FROM d->'pins'->>'expected_pack_ref'
 OR src->'package'->>'package_ref' IS DISTINCT FROM d->'pins'->>'expected_package_ref'
 OR d->>'guard_inputs_sha256' IS DISTINCT FROM encode(sha256(ra4a_bytes.canonical_bytes(jsonb_build_object('bundles',src->'guard_inputs'))),'hex')
 OR jsonb_array_length(src->'guard_inputs') NOT BETWEEN 0 AND 16
 OR d->'pins'->'expected_guard_refs' IS DISTINCT FROM(SELECT coalesce(jsonb_agg(z->'guard'->'guard_ref' ORDER BY ord),'[]'::jsonb) FROM jsonb_array_elements(src->'guard_inputs') WITH ORDINALITY AS bundle(z,ord))
 OR jsonb_array_length(d->'issues') NOT BETWEEN 0 AND 3
 OR jsonb_typeof(src->'guard_inputs') IS DISTINCT FROM 'array'
 OR jsonb_array_length(src->'pack'->'sources') IS DISTINCT FROM 1
 OR src->'pack'->'sources'->0->>'kind' IS DISTINCT FROM 'CaptureManifest'
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(src->'pack'->'sources'->0->'document'->'pages') page
  WHERE NOT EXISTS(SELECT 1 FROM jsonb_array_elements(convert_from(x.raw_source,'UTF8')::jsonb->'pack'->'sources'->0->'document'->'pages') original
   WHERE(original->'snapshot'->>'url',original->>'http_status',original->'snapshot'->>'sha256')
   IS NOT DISTINCT FROM(page->'snapshot'->>'url',page->>'http_status',page->'snapshot'->>'sha256')))
 OR src->'editorial_selection'->'full_evidence_retained' IS DISTINCT FROM 'true'::jsonb
 OR EXISTS(SELECT 1 FROM jsonb_each_text(src->'objects_base64') z
  WHERE z.value IS DISTINCT FROM convert_from(x.raw_source,'UTF8')::jsonb->'objects_base64'->>z.key)
 OR EXISTS(SELECT 1 FROM jsonb_array_elements(src->'guard_inputs') z
  WHERE z->'guard'->>'guard_version' IS DISTINCT FROM 'ra3b-disc-1.0.0')
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='M1_OUTPUT_PIN_DENIED'; END IF;
 SELECT q.principal INTO STRICT origin FROM ra4a.requests q WHERE(q.tenant_id,q.request_id)=(t,x.request_id);
 -- Original finish and output persistence share this one transaction.
 event:=ra4b_test.finish(t,id,token,seq);
 INSERT INTO ra4b_p2.m1_results(tenant_id,job_id,request_id,run_id,worker_role,lease_seq,lease_token_sha256,
  lease_until,origin_role,origin_epoch,source_ref,input_sha256,reference_sha256,policy_id,policy_version,
  source_record,report,html,binding,report_id,report_version,finish_event,transaction_id)
 VALUES(t,id,x.request_id,x.run_id,SESSION_USER,seq,b->>'lease_token_sha256',x.lease_until,origin,x.origin_epoch,
  x.source_ref,x.raw_source_sha256,x.reference_sha256,b->>'policy_id',(b->>'policy_version')::integer,
  source_raw,report_raw,html_raw,binding_raw,'job-'||id::text,1,event,txid_current());
 INSERT INTO ra4b_p2.m1_assignments(tenant_id,job_id,db_role)
 SELECT t,id,i.reviewer_role FROM ra4b_p2.m1_inputs i WHERE(i.tenant_id,i.source_ref)=(t,x.source_ref);
 RETURN jsonb_build_object('tenant_id',t,'job_id',id,'request_id',x.request_id,'run_id',x.run_id,
 'report_id','job-'||id::text,'report_version',1,'report_sha256',encode(sha256(report_raw),'hex'),
 'source_sha256',encode(sha256(source_raw),'hex'),'html_sha256',encode(sha256(html_raw),'hex'),
 'finish_event',event,'authority','TEST_ONLY_GENERATED_NOT_APPROVED');
END $$;
CREATE FUNCTION ra4b_p2.m1_result_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$ BEGIN
 PERFORM ra4b_test.require_run(NEW.tenant_id,NEW.run_id,'WORKER');
 IF SESSION_USER IS DISTINCT FROM NEW.worker_role OR SESSION_USER NOT IN('ra4b_test_a_worker','ra4b_test_b_worker')
 OR NEW.transaction_id<>txid_current() OR NEW.lease_until<=clock_timestamp()
 OR NOT EXISTS(SELECT 1 FROM ra4a.jobs j JOIN ra4a.outbox e USING(tenant_id,run_id)
 JOIN ra4a.audit a USING(tenant_id,run_id)
 WHERE(j.tenant_id,j.job_id,j.run_id,j.lease_owner,j.lease_seq,j.lease_until)=
 (NEW.tenant_id,NEW.job_id,NEW.run_id,NEW.worker_role,NEW.lease_seq,NEW.lease_until)
 AND encode(sha256(convert_to(j.lease_token::text,'UTF8')),'hex')=NEW.lease_token_sha256
 AND j.state='TEST_ONLY_DONE' AND e.event_id=NEW.finish_event AND e.kind='TEST_ONLY_CONSUMED'
 AND a.action='TEST_ONLY_CONSUMED' AND a.db_principal=SESSION_USER AND a.lease_seq=NEW.lease_seq)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_CURRENT_COMMIT_DENIED'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER worker_result_only BEFORE INSERT ON ra4b_p2.m1_results
 FOR EACH ROW EXECUTE FUNCTION ra4b_p2.m1_result_guard();
CREATE CONSTRAINT TRIGGER m1_current_at_commit AFTER INSERT ON ra4b_p2.m1_results
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4b_p2.m1_result_guard();

-- Nonrecursive SECURITY INVOKER witness; no origin table queried here.
CREATE FUNCTION ra4b_p2.current_generated_binding(t text,qid uuid,origin name,epoch_value bigint)
 RETURNS boolean LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE r ra4b_p2.m1_results%ROWTYPE; j ra4a.jobs%ROWTYPE; q ra4a.requests%ROWTYPE;
 p ra4a.policies%ROWTYPE;
BEGIN
 -- Do not plan the Reviewer witness on the original APP/Worker path.
 IF CURRENT_USER<>'ra4a_owner' OR t IS DISTINCT FROM ra4a.scope()
 OR SESSION_USER NOT IN('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 THEN RETURN false; END IF;
 FOR r IN SELECT result.* FROM ra4b_p2.m1_results result
 JOIN ra4b_p2.m1_assignments assignment USING(tenant_id,job_id)
 WHERE result.tenant_id=t AND (qid IS NULL OR result.request_id=qid)
 AND (result.origin_role,result.origin_epoch)=(origin,epoch_value)
 AND assignment.db_role=SESSION_USER AND assignment.active LOOP
  SELECT * INTO j FROM ra4a.jobs WHERE(tenant_id,job_id)=(r.tenant_id,r.job_id);
  IF NOT FOUND OR j.state<>'TEST_ONLY_DONE'
   OR (j.run_id,j.lease_owner,j.lease_seq) IS DISTINCT FROM(r.run_id,r.worker_role,r.lease_seq)
   OR r.created_at>=r.lease_until THEN CONTINUE; END IF;
  SELECT * INTO q FROM ra4a.requests WHERE(tenant_id,request_id)=(r.tenant_id,r.request_id);
  IF NOT FOUND OR (q.principal,q.source_ref,q.policy_id,q.policy_version)
   IS DISTINCT FROM(r.origin_role,r.source_ref,r.policy_id,r.policy_version) THEN CONTINUE; END IF;
  IF NOT EXISTS(SELECT 1 FROM ra4a.runs WHERE(tenant_id,run_id,request_id)=(r.tenant_id,r.run_id,r.request_id))
   OR NOT EXISTS(SELECT 1 FROM ra4a.outbox WHERE(tenant_id,event_id,run_id)=(r.tenant_id,r.finish_event,r.run_id)
      AND kind='TEST_ONLY_CONSUMED')
   OR NOT EXISTS(SELECT 1 FROM ra4a.audit WHERE(tenant_id,run_id,lease_seq,db_principal)=
      (r.tenant_id,r.run_id,r.lease_seq,r.worker_role) AND action='TEST_ONLY_CONSUMED')
   OR NOT EXISTS(SELECT 1 FROM ra4b_p2.m1_inputs WHERE(tenant_id,source_ref,source_sha256,reference_sha256)=
      (r.tenant_id,r.source_ref,r.input_sha256,r.reference_sha256)) THEN CONTINUE; END IF;
  SELECT * INTO p FROM ra4a.policies WHERE(tenant_id,policy_id,version)=(r.tenant_id,r.policy_id,r.policy_version);
  IF FOUND AND p.status='ALLOWED' AND p.expires_at>clock_timestamp()
   AND NOT EXISTS(SELECT 1 FROM ra4a.policies n WHERE(n.tenant_id,n.policy_id)=(p.tenant_id,p.policy_id) AND n.version>p.version)
   THEN RETURN true; END IF;
 END LOOP;
 RETURN false;
END $$;
CREATE POLICY s2_assigned_epoch_select ON ra4b_test.origin_epochs AS PERMISSIVE FOR SELECT TO ra4a_owner
 USING(CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND ra4b_p2.current_generated_binding(tenant_id,NULL::uuid,origin_role,epoch));
CREATE POLICY s2_assigned_request_select ON ra4b_test.request_origins AS PERMISSIVE FOR SELECT TO ra4a_owner
 USING(CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND ra4b_p2.current_generated_binding(tenant_id,request_id,origin_role,epoch));
CREATE POLICY s2_assigned_epoch_lock ON ra4b_test.origin_epochs AS PERMISSIVE FOR UPDATE TO ra4a_owner
 USING(CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND ra4b_p2.current_generated_binding(tenant_id,NULL::uuid,origin_role,epoch)) WITH CHECK(false);
CREATE FUNCTION ra4b_p2.m1_read(t text,id uuid,ver integer,hash text)
 RETURNS TABLE(locator jsonb,source_record bytea,report bytea,html bytea)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE r ra4b_p2.m1_results%ROWTYPE; BEGIN
 IF current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_READ_COMMITTED_REQUIRED'; END IF;
 PERFORM ra4a.require_scope(t,'APP');
 IF NOT pg_has_role(SESSION_USER,'p2b1_review','MEMBER') THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_ASSIGNED_REVIEWER_ONLY'; END IF;
 SELECT * INTO r FROM ra4b_p2.m1_results WHERE(tenant_id,job_id,report_version,report_sha256)=(t,id,ver,hash);
 IF NOT FOUND OR NOT ra4b_p2.current_generated_binding(t,r.request_id,r.origin_role,r.origin_epoch)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_CURRENT_RESULT_DENIED'; END IF;
 PERFORM 1 FROM ra4b_test.origin_epochs e WHERE(e.tenant_id,e.origin_role,e.epoch)=
 (t,r.origin_role,r.origin_epoch) FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_ORIGIN_DENIED'; END IF;
 PERFORM 1 FROM ra4b_p2.m1_assignments a WHERE(a.tenant_id,a.job_id,a.db_role)=(t,id,SESSION_USER) AND a.active FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_ASSIGNMENT_DENIED'; END IF;
 PERFORM 1 FROM ra4a.tenants WHERE tenant_id=t FOR UPDATE;
 IF NOT ra4b_p2.current_generated_binding(t,r.request_id,r.origin_role,r.origin_epoch)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_CURRENT_RESULT_DENIED'; END IF;
 RETURN QUERY SELECT jsonb_build_object('tenant_id',t,'request_id',r.request_id,'run_id',r.run_id,
 'job_id',id,'report_id',r.report_id,'report_version',ver,'report_sha256',r.report_sha256,
 'source_sha256',r.source_sha256,'html_sha256',r.html_sha256,'finish_event',r.finish_event,
 'authority','TEST_ONLY_GENERATED_NOT_APPROVED'),r.source_record,r.report,r.html;
END $$;
CREATE FUNCTION ra4b_p2.m1_read_assigned(t text,id uuid)
 RETURNS TABLE(locator jsonb,source_record bytea,report bytea,html bytea)
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_p2,pg_temp AS $$
DECLARE r ra4b_p2.m1_results%ROWTYPE; BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 IF NOT pg_has_role(SESSION_USER,'p2b1_review','MEMBER') THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_ASSIGNED_REVIEWER_ONLY'; END IF;
 SELECT * INTO r FROM ra4b_p2.m1_results WHERE tenant_id=t AND job_id=id;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M1_CURRENT_RESULT_DENIED'; END IF;
 RETURN QUERY SELECT * FROM ra4b_p2.m1_read(t,id,r.report_version,r.report_sha256);
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA ra4b_p2 FROM PUBLIC,ra4b_app,ra4b_worker,p2b1_review;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ra4b_p2 FROM PUBLIC,ra4b_app,ra4b_worker,p2b1_review;
GRANT USAGE ON SCHEMA ra4b_p2 TO ra4b_worker,p2b1_review;
GRANT EXECUTE ON FUNCTION ra4b_p2.m1_load_source(text,uuid,uuid,integer),
 ra4b_p2.m1_commit(text,uuid,uuid,integer,bytea,bytea,bytea,bytea) TO ra4b_worker;
GRANT EXECUTE ON FUNCTION ra4b_p2.m1_read(text,uuid,integer,text),ra4b_p2.m1_read_assigned(text,uuid) TO p2b1_review;
RESET ROLE;
COMMIT;
