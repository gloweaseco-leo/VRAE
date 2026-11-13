-- RA4A P1: disposable synthetic PG16 only. No production identity or approval.
-- Run as isolated migration administrator; runtime must never receive this role.
CREATE ROLE ra4a_owner NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE ra4a_app NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE ra4a_worker NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE ra4a_test_a_app NOLOGIN IN ROLE ra4a_app;
CREATE ROLE ra4a_test_b_app NOLOGIN IN ROLE ra4a_app;
CREATE ROLE ra4a_test_a_worker NOLOGIN IN ROLE ra4a_worker;
CREATE ROLE ra4a_test_b_worker NOLOGIN IN ROLE ra4a_worker;
CREATE ROLE ra4a_test_unassigned NOLOGIN IN ROLE ra4a_app;
REVOKE ALL ON DATABASE vrae_ra4a_p1 FROM PUBLIC;
GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO ra4a_app, ra4a_worker;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA ra4a AUTHORIZATION ra4a_owner;
CREATE SCHEMA ra4a_private AUTHORIZATION ra4a_owner;
SET ROLE ra4a_owner;
ALTER DEFAULT PRIVILEGES REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES REVOKE ALL ON TABLES FROM PUBLIC;

CREATE TABLE ra4a_private.migrations(version integer PRIMARY KEY, sha256 text NOT NULL);
CREATE TABLE ra4a_private.principals(
  db_role name PRIMARY KEY, tenant_id text NOT NULL,
  kind text NOT NULL CHECK(kind IN ('APP','WORKER')), enabled boolean NOT NULL DEFAULT true,
  authority text NOT NULL CHECK(authority='TEST_ONLY'));
CREATE TABLE ra4a_private.assignments(
  db_role name PRIMARY KEY REFERENCES ra4a_private.principals,
  tenant_id text NOT NULL, active boolean NOT NULL DEFAULT true);
ALTER TABLE ra4a_private.principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE ra4a_private.principals FORCE ROW LEVEL SECURITY;
CREATE POLICY principal_session ON ra4a_private.principals
  USING(db_role=SESSION_USER) WITH CHECK(db_role=SESSION_USER);
ALTER TABLE ra4a_private.assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE ra4a_private.assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY assignment_session ON ra4a_private.assignments
  USING(db_role=SESSION_USER) WITH CHECK(db_role=SESSION_USER);

CREATE FUNCTION ra4a.scope() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,ra4a_private,pg_temp AS $$
 SELECT p.tenant_id FROM ra4a_private.principals p
 JOIN ra4a_private.assignments a ON a.db_role=p.db_role AND a.tenant_id=p.tenant_id
 WHERE p.db_role=SESSION_USER AND p.enabled AND p.authority='TEST_ONLY' AND a.active
$$;
CREATE FUNCTION ra4a.require_scope(t text, k text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a_private,pg_temp AS $$
BEGIN
 PERFORM 1 FROM ra4a_private.principals p JOIN ra4a_private.assignments a
 ON p.db_role=a.db_role AND p.tenant_id=a.tenant_id
 WHERE p.db_role=SESSION_USER AND p.tenant_id=t AND p.kind=k AND p.enabled
   AND p.authority='TEST_ONLY' AND a.active FOR SHARE OF p,a;
 IF t IS NULL OR NOT FOUND OR t IS DISTINCT FROM ra4a.scope()
 THEN RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='RA4A_SCOPE_DENIED'; END IF;
END $$;

CREATE TABLE ra4a.tenants(
 tenant_id text PRIMARY KEY CHECK(tenant_id ~ '^tenant-[a-z0-9_-]{2,48}$'),
 authority text NOT NULL DEFAULT 'TEST_ONLY' CHECK(authority='TEST_ONLY'));
CREATE TABLE ra4a.policies(
 tenant_id text REFERENCES ra4a.tenants, policy_id text, version integer CHECK(version>0),
 status text NOT NULL CHECK(status IN ('ALLOWED','REVOKED','UNKNOWN')),
 expires_at timestamptz NOT NULL,
 scope text NOT NULL CHECK(scope='SYNTHETIC_INTERNAL_ONLY'),
 PRIMARY KEY(tenant_id,policy_id,version));
CREATE TABLE ra4a.references(
 tenant_id text REFERENCES ra4a.tenants, ref_id text,
 policy_id text NOT NULL, policy_version integer NOT NULL,
 report_id text NOT NULL, source_run_id text NOT NULL, report_version integer NOT NULL CHECK(report_version>0),
 kind text NOT NULL CHECK(kind IN ('L1_NATIVE','COVERAGE_ONLY')),
 issue_count integer NOT NULL CHECK(issue_count BETWEEN 0 AND 3),
 native_h0 text CHECK(native_h0 ~ '^[0-9a-f]{64}$'),
 native_id text, target_digest text NOT NULL CHECK(target_digest ~ '^[0-9a-f]{64}$'),
 ref_sha256 text NOT NULL CHECK(ref_sha256 ~ '^[0-9a-f]{64}$'),
 metadata jsonb NOT NULL,
 visibility text NOT NULL DEFAULT 'PRIVATE_NOT_APPROVED' CHECK(visibility='PRIVATE_NOT_APPROVED'),
 PRIMARY KEY(tenant_id,ref_id), UNIQUE(tenant_id,report_id,report_version),
 FOREIGN KEY(tenant_id,policy_id,policy_version) REFERENCES ra4a.policies,
 CHECK((kind='COVERAGE_ONLY' AND issue_count=0 AND native_h0 IS NULL AND native_id IS NULL)
    OR (kind='L1_NATIVE' AND issue_count>0 AND native_h0 IS NOT NULL AND native_id IS NOT NULL)),
 CHECK(jsonb_typeof(metadata)='object' AND metadata->>'authority'='TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE'),
 CHECK(metadata ?& ARRAY['tenant_id','report_id','run_id','report_version','kind','policy_id','policy_version',
  'native_content_hash','native_report_version_id','draft_payload_sha256','draft_ref','html_sha256',
  'editorial_content_sha256','renderer_asset_sha256','ordered_guard_refs','guard_inputs_sha256',
  'source_manifest_sha256','evidence_pack_ref','finding_package_ref','execution_ref','model_provenance']),
 CHECK(metadata->>'tenant_id'=tenant_id AND metadata->>'report_id'=report_id
       AND metadata->>'run_id'=source_run_id AND (metadata->>'report_version')::integer=report_version
       AND metadata->>'kind'=kind AND metadata->>'policy_id'=policy_id
       AND (metadata->>'policy_version')::integer=policy_version
       AND metadata->>'native_content_hash' IS NOT DISTINCT FROM native_h0
       AND metadata->>'native_report_version_id' IS NOT DISTINCT FROM native_id));
CREATE TABLE ra4a.requests(
 tenant_id text REFERENCES ra4a.tenants, request_id uuid DEFAULT gen_random_uuid(),
 principal name NOT NULL, idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 8 AND 128),
 payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
 canonical_payload text NOT NULL CHECK(octet_length(canonical_payload)<=8192),
 policy_id text NOT NULL, policy_version integer NOT NULL, source_ref text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,request_id), UNIQUE(tenant_id,principal,idempotency_key),
 FOREIGN KEY(tenant_id,policy_id,policy_version) REFERENCES ra4a.policies,
 FOREIGN KEY(tenant_id,source_ref) REFERENCES ra4a.references);
CREATE TABLE ra4a.runs(
 tenant_id text, run_id uuid DEFAULT gen_random_uuid(), request_id uuid NOT NULL,
 status text NOT NULL CHECK(status IN ('QUEUED','LEASED','TEST_ONLY_CONSUMED','DEAD_LETTER')),
 PRIMARY KEY(tenant_id,run_id), UNIQUE(tenant_id,request_id),
 FOREIGN KEY(tenant_id,request_id) REFERENCES ra4a.requests);
CREATE TABLE ra4a.jobs(
 tenant_id text, job_id uuid DEFAULT gen_random_uuid(), run_id uuid NOT NULL,
 state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','LEASED','TEST_ONLY_DONE','DEAD_LETTER')),
 lease_owner name, lease_token uuid, lease_seq integer NOT NULL DEFAULT 0,
 lease_until timestamptz, attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 3),
 PRIMARY KEY(tenant_id,job_id), UNIQUE(tenant_id,run_id),
 FOREIGN KEY(tenant_id,run_id) REFERENCES ra4a.runs);
CREATE TABLE ra4a.outbox(
 tenant_id text, event_id uuid DEFAULT gen_random_uuid(), run_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('TEST_ONLY_ADMITTED','TEST_ONLY_CONSUMED')),
 undelivered boolean NOT NULL DEFAULT true CHECK(undelivered),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,event_id), UNIQUE(tenant_id,run_id,kind),
 FOREIGN KEY(tenant_id,run_id) REFERENCES ra4a.runs);
CREATE TABLE ra4a.audit(
 tenant_id text, entry_id uuid DEFAULT gen_random_uuid(), run_id uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('ADMITTED','LEASED','TEST_ONLY_CONSUMED','DEAD_LETTER')),
 lease_seq integer NOT NULL DEFAULT 0, db_principal name NOT NULL DEFAULT SESSION_USER,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,entry_id), UNIQUE(tenant_id,run_id,action,lease_seq),
 FOREIGN KEY(tenant_id,run_id) REFERENCES ra4a.runs);

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['tenants','policies','references','requests','runs','jobs','outbox','audit'] LOOP
  EXECUTE format('ALTER TABLE ra4a.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE ra4a.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY tenant_isolation ON ra4a.%I USING (tenant_id=ra4a.scope()) WITH CHECK (tenant_id=ra4a.scope())',t);
 END LOOP;
END $$;
CREATE FUNCTION ra4a_private.immutable() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$ BEGIN
 RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='RA4A_IMMUTABLE_METADATA';
END $$;
CREATE TRIGGER immutable_reference BEFORE UPDATE OR DELETE ON ra4a.references
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable();
CREATE TRIGGER immutable_request BEFORE UPDATE OR DELETE ON ra4a.requests
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable();
CREATE TRIGGER immutable_outbox BEFORE UPDATE OR DELETE ON ra4a.outbox
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable();
CREATE TRIGGER immutable_audit BEFORE UPDATE OR DELETE ON ra4a.audit
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable();

-- Serialize authoritative fixture policy/reference publication with admission.
-- No runtime role has direct policy/reference write privileges.
CREATE FUNCTION ra4a_private.revision_lock() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a,pg_temp AS $$ BEGIN
 PERFORM 1 FROM ra4a.tenants WHERE tenant_id=COALESCE(NEW.tenant_id,OLD.tenant_id) FOR UPDATE;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER policy_revision BEFORE INSERT OR UPDATE OR DELETE ON ra4a.policies
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.revision_lock();
CREATE TRIGGER reference_revision BEFORE INSERT ON ra4a.references
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.revision_lock();

CREATE FUNCTION ra4a.admit(t text, pid text, pv integer, ik text, ph text, payload text)
RETURNS TABLE(request_id uuid, run_id uuid, job_id uuid, event_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a,pg_temp AS $$
DECLARE p jsonb; r ra4a.requests%ROWTYPE; rid uuid; jid uuid; eid uuid; ref text; rs text;
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 PERFORM 1 FROM ra4a.tenants WHERE tenant_id=t FOR UPDATE;
 IF octet_length(payload)>8192 OR length(ik) NOT BETWEEN 8 AND 128
   OR ph IS NULL OR encode(sha256(convert_to(payload,'UTF8')),'hex')<>ph
 THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='RA4A_PAYLOAD_INVALID'; END IF;
 p:=payload::jsonb;
 IF jsonb_typeof(p)<>'object' OR (SELECT array_agg(x ORDER BY x) FROM jsonb_object_keys(p) x)
    IS DISTINCT FROM ARRAY['expected_ref_sha256','mode','source_ref']::text[]
    OR p->>'mode' IS DISTINCT FROM 'SYNTHETIC_INTERNAL_ONLY'
 THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='RA4A_PAYLOAD_INVALID'; END IF;
 PERFORM 1 FROM ra4a.policies q WHERE q.tenant_id=t AND q.policy_id=pid AND q.version=pv
   AND q.status='ALLOWED' AND q.expires_at>clock_timestamp();
 IF NOT FOUND OR EXISTS(SELECT 1 FROM ra4a.policies q WHERE q.tenant_id=t AND q.policy_id=pid AND q.version>pv)
 THEN RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='RA4A_POLICY_DENIED'; END IF;
 ref:=p->>'source_ref'; rs:=p->>'expected_ref_sha256';
 IF ref IS NOT NULL THEN
  PERFORM 1 FROM ra4a.references f WHERE f.tenant_id=t AND f.ref_id=ref AND f.ref_sha256=rs
   AND f.policy_id=pid AND f.policy_version=pv
   AND NOT EXISTS(SELECT 1 FROM ra4a.references newer WHERE newer.tenant_id=t
                  AND newer.report_id=f.report_id AND newer.report_version>f.report_version);
  IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='RA4A_SOURCE_STALE'; END IF;
 ELSIF rs IS NOT NULL THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='RA4A_SOURCE_STALE'; END IF;
 INSERT INTO ra4a.requests(tenant_id,principal,idempotency_key,payload_hash,canonical_payload,policy_id,policy_version,source_ref)
 VALUES(t,SESSION_USER,ik,ph,payload,pid,pv,ref)
 ON CONFLICT(tenant_id,principal,idempotency_key) DO NOTHING RETURNING * INTO r;
 IF NOT FOUND THEN
  SELECT * INTO STRICT r FROM ra4a.requests q WHERE q.tenant_id=t AND q.principal=SESSION_USER AND q.idempotency_key=ik;
  IF r.payload_hash<>ph OR r.canonical_payload<>payload OR r.policy_id<>pid OR r.policy_version<>pv
  THEN RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='RA4A_IDEMPOTENCY_CONFLICT'; END IF;
 ELSE
  INSERT INTO ra4a.runs(tenant_id,request_id,status) VALUES(t,r.request_id,'QUEUED') RETURNING ra4a.runs.run_id INTO rid;
  INSERT INTO ra4a.jobs(tenant_id,run_id) VALUES(t,rid) RETURNING ra4a.jobs.job_id INTO jid;
  INSERT INTO ra4a.outbox(tenant_id,run_id,kind) VALUES(t,rid,'TEST_ONLY_ADMITTED') RETURNING ra4a.outbox.event_id INTO eid;
  INSERT INTO ra4a.audit(tenant_id,run_id,action) VALUES(t,rid,'ADMITTED');
 END IF;
 RETURN QUERY SELECT r.request_id,s.run_id,j.job_id,e.event_id FROM ra4a.runs s
  JOIN ra4a.jobs j USING(tenant_id,run_id) JOIN ra4a.outbox e USING(tenant_id,run_id)
  WHERE s.tenant_id=t AND s.request_id=r.request_id AND e.kind='TEST_ONLY_ADMITTED';
END $$;

CREATE FUNCTION ra4a.claim(t text, seconds integer)
RETURNS TABLE(job_id uuid, run_id uuid, lease_token uuid, lease_seq integer, lease_until timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a,pg_temp AS $$
DECLARE j ra4a.jobs%ROWTYPE;
BEGIN
 PERFORM ra4a.require_scope(t,'WORKER');
 IF seconds IS NULL OR seconds NOT BETWEEN 1 AND 30 THEN
  RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='RA4A_LEASE_BOUNDS'; END IF;
 -- Exhausted jobs are terminal, not silently claimed a fourth time.
 FOR j IN SELECT * FROM ra4a.jobs q WHERE q.tenant_id=t AND q.state='LEASED'
   AND q.lease_until<=clock_timestamp() AND q.attempts>=3 FOR UPDATE SKIP LOCKED LOOP
  UPDATE ra4a.jobs q SET state='DEAD_LETTER' WHERE q.tenant_id=t AND q.job_id=j.job_id;
  UPDATE ra4a.runs s SET status='DEAD_LETTER' WHERE s.tenant_id=t AND s.run_id=j.run_id;
  INSERT INTO ra4a.audit(tenant_id,run_id,action,lease_seq) VALUES(t,j.run_id,'DEAD_LETTER',j.lease_seq);
 END LOOP;
 SELECT q.* INTO j FROM ra4a.jobs q JOIN ra4a.runs s USING(tenant_id,run_id)
 JOIN ra4a.requests r USING(tenant_id,request_id)
 JOIN ra4a.policies p ON (p.tenant_id,p.policy_id,p.version)=(r.tenant_id,r.policy_id,r.policy_version)
 WHERE q.tenant_id=t AND q.attempts<3 AND (q.state='PENDING' OR
   (q.state='LEASED' AND q.lease_until<=clock_timestamp()))
   AND p.status='ALLOWED' AND p.expires_at>clock_timestamp()
 ORDER BY q.job_id FOR UPDATE OF q SKIP LOCKED LIMIT 1;
 IF NOT FOUND THEN RETURN; END IF;
 UPDATE ra4a.jobs q SET state='LEASED',lease_owner=SESSION_USER,lease_token=gen_random_uuid(),
   lease_seq=q.lease_seq+1,lease_until=clock_timestamp()+make_interval(secs=>seconds),attempts=q.attempts+1
 WHERE q.tenant_id=t AND q.job_id=j.job_id RETURNING q.* INTO j;
 UPDATE ra4a.runs s SET status='LEASED' WHERE s.tenant_id=t AND s.run_id=j.run_id;
 INSERT INTO ra4a.audit(tenant_id,run_id,action,lease_seq) VALUES(t,j.run_id,'LEASED',j.lease_seq);
 RETURN QUERY SELECT j.job_id,j.run_id,j.lease_token,j.lease_seq,j.lease_until;
END $$;

CREATE FUNCTION ra4a.finish(t text, id uuid, token uuid, seq integer) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a,pg_temp AS $$
DECLARE j ra4a.jobs%ROWTYPE; eid uuid;
BEGIN
 PERFORM ra4a.require_scope(t,'WORKER');
 SELECT * INTO j FROM ra4a.jobs q WHERE q.tenant_id=t AND q.job_id=id FOR UPDATE;
 IF NOT FOUND OR j.lease_owner IS DISTINCT FROM SESSION_USER OR j.lease_token IS DISTINCT FROM token
   OR j.lease_seq IS DISTINCT FROM seq THEN
  RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='RA4A_LEASE_STALE'; END IF;
 IF j.state='TEST_ONLY_DONE' THEN
  SELECT e.event_id INTO STRICT eid FROM ra4a.outbox e WHERE e.tenant_id=t AND e.run_id=j.run_id AND e.kind='TEST_ONLY_CONSUMED';
  RETURN eid;
 END IF;
 IF j.state<>'LEASED' OR j.lease_until<=clock_timestamp() THEN
  RAISE EXCEPTION USING ERRCODE='55000', MESSAGE='RA4A_LEASE_STALE'; END IF;
 UPDATE ra4a.jobs q SET state='TEST_ONLY_DONE' WHERE q.tenant_id=t AND q.job_id=id;
 UPDATE ra4a.runs s SET status='TEST_ONLY_CONSUMED' WHERE s.tenant_id=t AND s.run_id=j.run_id;
 INSERT INTO ra4a.outbox(tenant_id,run_id,kind) VALUES(t,j.run_id,'TEST_ONLY_CONSUMED') RETURNING event_id INTO eid;
 INSERT INTO ra4a.audit(tenant_id,run_id,action,lease_seq) VALUES(t,j.run_id,'TEST_ONLY_CONSUMED',seq);
 RETURN eid;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA ra4a,ra4a_private FROM PUBLIC,ra4a_app,ra4a_worker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ra4a,ra4a_private FROM PUBLIC;
GRANT USAGE ON SCHEMA ra4a TO ra4a_app,ra4a_worker;
GRANT SELECT ON ALL TABLES IN SCHEMA ra4a TO ra4a_app,ra4a_worker;
GRANT EXECUTE ON FUNCTION ra4a.scope() TO ra4a_app,ra4a_worker;
GRANT EXECUTE ON FUNCTION ra4a.admit(text,text,integer,text,text,text) TO ra4a_app;
GRANT EXECUTE ON FUNCTION ra4a.claim(text,integer),ra4a.finish(text,uuid,uuid,integer) TO ra4a_worker;
RESET ROLE;
