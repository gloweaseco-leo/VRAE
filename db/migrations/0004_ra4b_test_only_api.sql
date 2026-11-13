-- Owner #78 bounded correction: additive B4-only TEST_ONLY runtime seam.
-- Old migrations/functions/grants remain unchanged; legacy raw SELECT is debt.
CREATE ROLE ra4b_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE ra4b_worker NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE ra4b_test_a_app NOLOGIN IN ROLE ra4b_app;
CREATE ROLE ra4b_test_b_app NOLOGIN IN ROLE ra4b_app;
CREATE ROLE ra4b_test_a_worker NOLOGIN IN ROLE ra4b_worker;
CREATE ROLE ra4b_test_b_worker NOLOGIN IN ROLE ra4b_worker;
GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO ra4b_app,ra4b_worker;
CREATE SCHEMA ra4b_test AUTHORIZATION ra4a_owner;
-- Fresh B4 roles cannot have pre-existing unverified private authority. Never
-- seed an epoch from an administrator's cross-actor SELECT or a claimed name.
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM ra4a_private.principals WHERE db_role IN ('ra4b_test_a_app','ra4b_test_b_app'))
 OR EXISTS(SELECT 1 FROM ra4a_private.assignments WHERE db_role IN ('ra4b_test_a_app','ra4b_test_b_app'))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_FRESH_AUTHORITY_BOOTSTRAP_REQUIRED'; END IF;
END $$;
SET ROLE ra4a_owner;

-- Owner RA4B_P1_RLS_POLICY_COMPAT_GO: reuse all ten original policies.
-- Keep FORCE RLS and every origin/current-authority guard intact. Actual B4
-- execution must prove visibility; no role/GUC impersonation or extra policy.

CREATE TABLE ra4b_test.origin_epochs(
 tenant_id text NOT NULL,origin_role name NOT NULL,epoch bigint NOT NULL CHECK(epoch>0),
 PRIMARY KEY(tenant_id,origin_role),
 CHECK((tenant_id='tenant-test' AND origin_role='ra4b_test_a_app') OR
       (tenant_id='tenant-beta' AND origin_role='ra4b_test_b_app')));
CREATE TABLE ra4b_test.request_origins(
 tenant_id text NOT NULL,request_id uuid NOT NULL,origin_role name NOT NULL,
 epoch bigint NOT NULL CHECK(epoch>0),PRIMARY KEY(tenant_id,request_id),
 FOREIGN KEY(tenant_id,request_id) REFERENCES ra4a.requests,
 CHECK((tenant_id='tenant-test' AND origin_role='ra4b_test_a_app') OR
       (tenant_id='tenant-beta' AND origin_role='ra4b_test_b_app')));
ALTER TABLE ra4b_test.origin_epochs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ra4b_test.origin_epochs FORCE ROW LEVEL SECURITY;
ALTER TABLE ra4b_test.request_origins ENABLE ROW LEVEL SECURITY;
ALTER TABLE ra4b_test.request_origins FORCE ROW LEVEL SECURITY;
-- Actual postgres is the disposable trusted source-authority mutator, never a
-- runtime credential. FORCE RLS also applies to the definer. Runtime projection
-- reads are restricted by its genuine source-derived tenant scope.
CREATE POLICY epoch_scope ON ra4b_test.origin_epochs USING (
 SESSION_USER='postgres' OR (tenant_id=ra4a.scope() AND SESSION_USER IN
 ('ra4b_test_a_app','ra4b_test_b_app','ra4b_test_a_worker','ra4b_test_b_worker')))
 WITH CHECK (SESSION_USER='postgres' OR (tenant_id=ra4a.scope() AND SESSION_USER IN
 ('ra4b_test_a_app','ra4b_test_b_app','ra4b_test_a_worker','ra4b_test_b_worker')));
CREATE POLICY binding_scope ON ra4b_test.request_origins USING (
 SESSION_USER='postgres' OR (tenant_id=ra4a.scope() AND SESSION_USER IN
 ('ra4b_test_a_app','ra4b_test_b_app','ra4b_test_a_worker','ra4b_test_b_worker')))
 WITH CHECK (SESSION_USER='postgres' OR (tenant_id=ra4a.scope() AND SESSION_USER IN
 ('ra4b_test_a_app','ra4b_test_b_app','ra4b_test_a_worker','ra4b_test_b_worker')));
CREATE TRIGGER immutable_origin_binding BEFORE UPDATE OR DELETE ON ra4b_test.request_origins
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable();

CREATE FUNCTION ra4b_test.epoch_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  PERFORM ra4a.require_scope(NEW.tenant_id,'APP');
  IF NEW.origin_role<>SESSION_USER OR NEW.epoch<>1 THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_EPOCH_INITIALIZATION_DENIED'; END IF;
 ELSIF TG_OP='UPDATE' THEN
  IF SESSION_USER<>'postgres' OR pg_trigger_depth()<2 OR NEW.epoch<>OLD.epoch+1
   OR (NEW.tenant_id,NEW.origin_role) IS DISTINCT FROM (OLD.tenant_id,OLD.origin_role) THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_EPOCH_ADVANCE_DENIED'; END IF;
 ELSE RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_EPOCH_RESET_DENIED';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ra4b_epoch_monotonic BEFORE INSERT OR UPDATE OR DELETE ON ra4b_test.origin_epochs
 FOR EACH ROW EXECUTE FUNCTION ra4b_test.epoch_guard();
CREATE TRIGGER ra4b_epoch_no_reset BEFORE TRUNCATE ON ra4b_test.origin_epochs
 FOR EACH STATEMENT EXECUTE FUNCTION ra4b_test.epoch_guard();

CREATE FUNCTION ra4b_test.invalidate_origin() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE old_role name; new_role name;
BEGIN
 IF TG_OP<>'TRUNCATE' THEN
  IF TG_OP<>'INSERT' THEN old_role:=OLD.db_role; END IF;
  IF TG_OP<>'DELETE' THEN new_role:=NEW.db_role; END IF;
  IF coalesce(old_role::text,'') NOT IN ('ra4b_test_a_app','ra4b_test_b_app')
   AND coalesce(new_role::text,'') NOT IN ('ra4b_test_a_app','ra4b_test_b_app') THEN RETURN NULL; END IF;
 END IF;
 -- Refuse unsupported mutators instead of silently filtering an epoch write
 -- through RLS. Runtime roles have no source-table DML or function EXECUTE.
 IF SESSION_USER<>'postgres' THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_TRUSTED_MUTATOR_REQUIRED'; END IF;
 PERFORM 1 FROM ra4b_test.origin_epochs WHERE TG_OP='TRUNCATE' OR origin_role=old_role OR origin_role=new_role
  ORDER BY tenant_id,origin_role FOR UPDATE;
 UPDATE ra4b_test.origin_epochs SET epoch=epoch+1
  WHERE TG_OP='TRUNCATE' OR origin_role=old_role OR origin_role=new_role;
 -- No INSERT: first initialization requires the actual APP require_scope.
 -- Tombstones remain, so replacement/re-enable never resets a prior epoch.
 RETURN NULL;
END $$;
CREATE TRIGGER ra4b_principal_epoch AFTER INSERT OR UPDATE OR DELETE ON ra4a_private.principals
 FOR EACH ROW EXECUTE FUNCTION ra4b_test.invalidate_origin();
CREATE TRIGGER ra4b_assignment_epoch AFTER INSERT OR UPDATE OR DELETE ON ra4a_private.assignments
 FOR EACH ROW EXECUTE FUNCTION ra4b_test.invalidate_origin();
CREATE TRIGGER ra4b_principal_truncate_epoch AFTER TRUNCATE ON ra4a_private.principals
 FOR EACH STATEMENT EXECUTE FUNCTION ra4b_test.invalidate_origin();
CREATE TRIGGER ra4b_assignment_truncate_epoch AFTER TRUNCATE ON ra4a_private.assignments
 FOR EACH STATEMENT EXECUTE FUNCTION ra4b_test.invalidate_origin();

CREATE FUNCTION ra4b_test.require_actor(t text,k text,initialize boolean DEFAULT false) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE grp name;
BEGIN
 grp:=CASE k WHEN 'APP' THEN 'ra4b_app' WHEN 'WORKER' THEN 'ra4b_worker' END;
 IF grp IS NULL OR NOT pg_has_role(SESSION_USER,grp,'MEMBER')
 OR SESSION_USER NOT IN ('ra4b_test_a_app','ra4b_test_b_app','ra4b_test_a_worker','ra4b_test_b_worker')
 OR pg_has_role(SESSION_USER,'ra4a_app','MEMBER') OR pg_has_role(SESSION_USER,'ra4a_worker','MEMBER')
 OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=SESSION_USER AND rolcanlogin
  AND NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_ACTOR_DENIED'; END IF;
 PERFORM ra4a.require_scope(t,k);
 IF k='APP' AND initialize THEN
  INSERT INTO ra4b_test.origin_epochs VALUES(t,SESSION_USER,1) ON CONFLICT DO NOTHING;
 END IF;
 -- Own source authority -> ordered epoch locks -> policy/tenant gate -> job.
 -- Source invalidation takes only the ordered epoch locks, never a tenant
 -- gate afterward. Multi-operation trusted admin callers use this same order.
 PERFORM 1 FROM ra4b_test.origin_epochs WHERE tenant_id=t ORDER BY origin_role FOR SHARE;
 PERFORM 1 FROM ra4a.tenants WHERE tenant_id=t FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_SCOPE_DENIED'; END IF;
END $$;

CREATE FUNCTION ra4b_test.require_source(t text,pid text,pv integer,ref text,rs text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
BEGIN
 IF ref IS NULL OR rs IS NULL OR NOT EXISTS(
  SELECT 1 FROM ra4a.references r JOIN ra4a.policies p
  ON (p.tenant_id,p.policy_id,p.version)=(r.tenant_id,r.policy_id,r.policy_version)
  WHERE r.tenant_id=t AND r.ref_id=ref AND r.ref_sha256=rs
   AND p.policy_id=pid AND p.version=pv AND p.status='ALLOWED' AND p.expires_at>clock_timestamp()
   AND r.metadata->>'authority'='TEST_ONLY_ACCEPTED_SYNTHETIC_SOURCE'
   AND NOT EXISTS(SELECT 1 FROM ra4a.policies n WHERE n.tenant_id=t AND n.policy_id=pid AND n.version>pv)
   AND NOT EXISTS(SELECT 1 FROM ra4a.references n WHERE n.tenant_id=t AND n.report_id=r.report_id AND n.report_version>r.report_version))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_CURRENT_SOURCE_DENIED'; END IF;
END $$;

CREATE FUNCTION ra4b_test.require_run(t text,rid uuid,k text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE r ra4a.requests%ROWTYPE; ref ra4a.references%ROWTYPE;
BEGIN
 PERFORM ra4b_test.require_actor(t,k);
 SELECT q.* INTO r FROM ra4a.requests q JOIN ra4a.runs s USING(tenant_id,request_id)
  JOIN ra4a.jobs j USING(tenant_id,run_id) WHERE q.tenant_id=t AND s.run_id=rid;
 IF NOT FOUND OR r.principal NOT IN ('ra4b_test_a_app','ra4b_test_b_app')
  OR (k='APP' AND r.principal<>SESSION_USER)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_PROVENANCE_DENIED'; END IF;
 PERFORM 1 FROM ra4b_test.request_origins b JOIN ra4b_test.origin_epochs e
  ON (e.tenant_id,e.origin_role,e.epoch)=(b.tenant_id,b.origin_role,b.epoch)
  WHERE b.tenant_id=t AND b.request_id=r.request_id AND b.origin_role=r.principal FOR SHARE OF b,e;
 IF NOT FOUND OR NOT pg_has_role(r.principal,'ra4b_app','MEMBER')
 OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=r.principal AND rolcanlogin
   AND NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_ORIGIN_APP_DENIED'; END IF;
 SELECT * INTO ref FROM ra4a.references WHERE tenant_id=t AND ref_id=r.source_ref;
 PERFORM ra4b_test.require_source(t,r.policy_id,r.policy_version,r.source_ref,ref.ref_sha256);
 IF r.canonical_payload::jsonb IS DISTINCT FROM jsonb_build_object(
   'mode','SYNTHETIC_INTERNAL_ONLY','source_ref',r.source_ref,'expected_ref_sha256',ref.ref_sha256)
 OR r.payload_hash<>encode(sha256(convert_to(r.canonical_payload,'UTF8')),'hex')
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_PAYLOAD_DENIED'; END IF;
END $$;

CREATE FUNCTION ra4b_test.admit(t text,pid text,pv integer,ik text,ph text,payload text)
RETURNS TABLE(request_id uuid,run_id uuid,job_id uuid,event_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE p jsonb; v record;
BEGIN
 PERFORM ra4b_test.require_actor(t,'APP',true);
 IF octet_length(payload)>8192 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='RA4B_PAYLOAD_DENIED'; END IF;
 p:=payload::jsonb;
 PERFORM ra4b_test.require_source(t,pid,pv,p->>'source_ref',p->>'expected_ref_sha256');
 SELECT * INTO STRICT v FROM ra4a.admit(t,pid,pv,ik,ph,payload);
 INSERT INTO ra4b_test.request_origins
  SELECT t,v.request_id,SESSION_USER,e.epoch FROM ra4b_test.origin_epochs e
   WHERE e.tenant_id=t AND e.origin_role=SESSION_USER
  ON CONFLICT DO NOTHING;
 PERFORM ra4b_test.require_run(t,v.run_id,'APP');
 RETURN QUERY SELECT v.request_id,v.run_id,v.job_id,v.event_id;
END $$;

CREATE FUNCTION ra4b_test.status(t text,id uuid)
RETURNS TABLE(request_id uuid,run_id uuid,job_id uuid,status text,job_state text,attempts integer,
 lease_seq integer,source_ref text,report_version integer,kind text,issue_count integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE rid uuid;
BEGIN
 PERFORM ra4b_test.require_actor(t,'APP');
 SELECT s.run_id INTO rid FROM ra4a.requests r JOIN ra4a.runs s USING(tenant_id,request_id)
  WHERE r.tenant_id=t AND r.request_id=id AND r.principal=SESSION_USER;
 IF NOT FOUND THEN RETURN; END IF;
 PERFORM ra4b_test.require_run(t,rid,'APP');
 RETURN QUERY SELECT r.request_id,s.run_id,j.job_id,s.status,j.state,j.attempts,j.lease_seq,
  r.source_ref,f.report_version,f.kind,f.issue_count
  FROM ra4a.requests r JOIN ra4a.runs s USING(tenant_id,request_id)
  JOIN ra4a.jobs j USING(tenant_id,run_id) JOIN ra4a.references f ON f.tenant_id=t AND f.ref_id=r.source_ref
  WHERE r.tenant_id=t AND r.request_id=id AND r.principal=SESSION_USER;
END $$;

CREATE FUNCTION ra4b_test.claim(t text,seconds integer)
RETURNS TABLE(job_id uuid,run_id uuid,lease_token uuid,lease_seq integer,lease_until timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE selected_lease record;
BEGIN
 PERFORM ra4b_test.require_actor(t,'WORKER');
 -- Every mutation by the unchanged P1 claim is checked by the deferred guard,
 -- including exhaustion/dead-letter transitions and the actual selected job.
 FOR selected_lease IN SELECT * FROM ra4a.claim(t,seconds) LOOP
  -- Validate the actual selected origin before any lease row can be returned,
  -- including to a caller that has not yet attempted COMMIT.
  PERFORM ra4b_test.require_run(t,selected_lease.run_id,'WORKER');
  RETURN QUERY SELECT selected_lease.job_id,selected_lease.run_id,selected_lease.lease_token,
   selected_lease.lease_seq,selected_lease.lease_until;
 END LOOP;
END $$;

CREATE FUNCTION ra4b_test.finish(t text,id uuid,token uuid,seq integer) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE rid uuid; event uuid;
BEGIN
 PERFORM ra4b_test.require_actor(t,'WORKER');
 SELECT j.run_id INTO rid FROM ra4a.jobs j WHERE j.tenant_id=t AND j.job_id=id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_JOB_DENIED'; END IF;
 PERFORM ra4b_test.require_run(t,rid,'WORKER');
 event:=ra4a.finish(t,id,token,seq);
 PERFORM ra4b_test.require_run(t,rid,'WORKER');
 RETURN event;
END $$;

CREATE FUNCTION ra4b_test.commit_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4b_test,pg_temp AS $$
DECLARE origin name; k text; actual ra4a.jobs%ROWTYPE;
BEGIN
 SELECT r.principal INTO origin FROM ra4a.requests r JOIN ra4a.runs s USING(tenant_id,request_id)
  WHERE s.tenant_id=NEW.tenant_id AND s.run_id=NEW.run_id;
 IF origin IS NULL OR origin NOT IN ('ra4b_test_a_app','ra4b_test_b_app') THEN
  IF SESSION_USER IN ('ra4b_test_a_app','ra4b_test_b_app','ra4b_test_a_worker','ra4b_test_b_worker') THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_NON_B4_ORIGIN_DENIED';
  END IF;
  RETURN NULL;
 END IF;
 k:=CASE WHEN pg_has_role(SESSION_USER,'ra4b_app','MEMBER') THEN 'APP' ELSE 'WORKER' END;
 PERFORM ra4b_test.require_run(NEW.tenant_id,NEW.run_id,k);
 SELECT * INTO STRICT actual FROM ra4a.jobs WHERE tenant_id=NEW.tenant_id AND job_id=NEW.job_id;
 IF k='APP' AND (actual.state<>'PENDING' OR actual.lease_seq<>0)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4B_APP_MUTATION_DENIED'; END IF;
 IF k='WORKER' AND actual.state IN ('LEASED','TEST_ONLY_DONE') AND
   (actual.lease_owner IS DISTINCT FROM SESSION_USER OR actual.lease_until<=clock_timestamp())
 THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='RA4B_COMMIT_LEASE_STALE'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER ra4b_current_at_commit AFTER INSERT OR UPDATE ON ra4a.jobs
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4b_test.commit_guard();

REVOKE ALL ON SCHEMA ra4b_test FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA ra4b_test FROM PUBLIC,ra4b_app,ra4b_worker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ra4b_test FROM PUBLIC;
GRANT USAGE ON SCHEMA ra4b_test TO ra4b_app,ra4b_worker;
GRANT EXECUTE ON FUNCTION ra4b_test.admit(text,text,integer,text,text,text),ra4b_test.status(text,uuid) TO ra4b_app;
GRANT EXECUTE ON FUNCTION ra4b_test.claim(text,integer),ra4b_test.finish(text,uuid,uuid,integer) TO ra4b_worker;
RESET ROLE;
