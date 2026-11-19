-- Versioned AUTHORIZED_TARGET_V1 bridge on the original queue, not a second queue.
-- Install after original migration0001; the legacy test-only path remains valid.
BEGIN;
CREATE ROLE target_v1_reviewer NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE target_v1_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE target_v1_worker NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO target_v1_app,target_v1_worker,target_v1_reviewer;
GRANT USAGE ON SCHEMA ra4a TO target_v1_app,target_v1_worker,target_v1_reviewer;
CREATE SCHEMA target_v1 AUTHORIZATION ra4a_owner;
REVOKE ALL ON SCHEMA target_v1 FROM PUBLIC;
-- New authority/state tags are explicit; actual captures are not relabeled TEST_ONLY.
ALTER TABLE ra4a_private.principals DROP CONSTRAINT principals_authority_check;
ALTER TABLE ra4a_private.principals ADD CONSTRAINT principals_authority_check CHECK(authority IN ('TEST_ONLY','AUTHORIZED_TARGET_V1'));
ALTER TABLE ra4a.tenants DROP CONSTRAINT tenants_authority_check;
ALTER TABLE ra4a.tenants ADD CONSTRAINT tenants_authority_check CHECK(authority IN ('TEST_ONLY','AUTHORIZED_TARGET_V1'));
ALTER TABLE ra4a.policies DROP CONSTRAINT policies_scope_check;
ALTER TABLE ra4a.policies ADD CONSTRAINT policies_scope_check CHECK(scope IN ('SYNTHETIC_INTERNAL_ONLY','AUTHORIZED_READONLY'));
ALTER TABLE ra4a.jobs DROP CONSTRAINT jobs_state_check;
ALTER TABLE ra4a.jobs ADD CONSTRAINT jobs_state_check CHECK(state IN ('PENDING','LEASED','TEST_ONLY_DONE','DRAFT_READY','DEAD_LETTER'));
ALTER TABLE ra4a.runs DROP CONSTRAINT runs_status_check;
ALTER TABLE ra4a.runs ADD CONSTRAINT runs_status_check CHECK(status IN ('QUEUED','LEASED','TEST_ONLY_CONSUMED','DRAFT_READY','DEAD_LETTER'));
ALTER TABLE ra4a.outbox DROP CONSTRAINT outbox_kind_check;
ALTER TABLE ra4a.outbox ADD CONSTRAINT outbox_kind_check CHECK(kind IN ('TEST_ONLY_ADMITTED','TEST_ONLY_CONSUMED','TARGET_ADMITTED','DRAFT_GENERATED'));
ALTER TABLE ra4a.audit DROP CONSTRAINT audit_action_check;
ALTER TABLE ra4a.audit ADD CONSTRAINT audit_action_check CHECK(action IN ('ADMITTED','LEASED','TEST_ONLY_CONSUMED','DEAD_LETTER','DRAFT_GENERATED'));
SET ROLE ra4a_owner;
CREATE TABLE target_v1.actors(
 db_role name PRIMARY KEY,tenant_id text NOT NULL REFERENCES ra4a.tenants,kind text NOT NULL CHECK(kind IN ('APP','WORKER')),
 epoch bigint NOT NULL CHECK(epoch>0),active boolean NOT NULL,expires_at timestamptz NOT NULL);
ALTER TABLE target_v1.actors ENABLE ROW LEVEL SECURITY;
ALTER TABLE target_v1.actors FORCE ROW LEVEL SECURITY;
CREATE POLICY actor_session ON target_v1.actors USING(db_role=SESSION_USER OR tenant_id=(
 SELECT p.tenant_id FROM ra4a_private.principals p WHERE p.db_role=SESSION_USER AND p.enabled))
 WITH CHECK(db_role=SESSION_USER);
CREATE OR REPLACE FUNCTION ra4a.scope() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,ra4a_private,target_v1,pg_temp AS $$
 SELECT p.tenant_id FROM ra4a_private.principals p JOIN ra4a_private.assignments a
 ON a.db_role=p.db_role AND a.tenant_id=p.tenant_id
 WHERE p.db_role=SESSION_USER AND p.enabled AND a.active AND
 (p.authority='TEST_ONLY' OR (p.authority='AUTHORIZED_TARGET_V1' AND EXISTS(
 SELECT 1 FROM target_v1.actors x WHERE x.db_role=p.db_role AND x.tenant_id=p.tenant_id AND x.kind=p.kind
 AND x.active AND x.expires_at>statement_timestamp())))
$$;
CREATE OR REPLACE FUNCTION ra4a.require_scope(t text,k text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a_private,target_v1,pg_temp AS $$
DECLARE auth text;
BEGIN
 SELECT p.authority INTO auth FROM ra4a_private.principals p JOIN ra4a_private.assignments a
 ON a.db_role=p.db_role AND a.tenant_id=p.tenant_id WHERE p.db_role=SESSION_USER AND p.tenant_id=t AND p.kind=k
 AND p.enabled AND a.active FOR SHARE OF p,a;
 IF t IS NULL OR NOT FOUND OR t IS DISTINCT FROM ra4a.scope() THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4A_SCOPE_DENIED'; END IF;
 IF auth='AUTHORIZED_TARGET_V1' THEN
 PERFORM 1 FROM target_v1.actors x WHERE x.db_role=SESSION_USER AND x.tenant_id=t AND x.kind=k
 AND x.active AND x.expires_at>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACTOR_DENIED'; END IF;
 ELSIF auth<>'TEST_ONLY' THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RA4A_SCOPE_DENIED'; END IF;
END $$;
CREATE FUNCTION target_v1.actor_changed() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
BEGIN
 IF SESSION_USER<>'postgres' AND EXISTS(SELECT 1 FROM target_v1.actors WHERE db_role=OLD.db_role) THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_TRUSTED_MUTATOR_REQUIRED'; END IF;
 UPDATE target_v1.actors SET epoch=epoch+1,active=false WHERE db_role=OLD.db_role;
 RETURN NULL;
END $$;
CREATE TRIGGER target_actor_invalidation AFTER UPDATE OR DELETE ON ra4a_private.principals
 FOR EACH ROW EXECUTE FUNCTION target_v1.actor_changed();
CREATE TRIGGER target_assignment_invalidation AFTER UPDATE OR DELETE ON ra4a_private.assignments
 FOR EACH ROW EXECUTE FUNCTION target_v1.actor_changed();
CREATE TABLE target_v1.capacity(tenant_id text PRIMARY KEY REFERENCES ra4a.tenants,max_pending integer NOT NULL CHECK(max_pending BETWEEN 1 AND 100000));
CREATE TABLE target_v1.plans(tenant_id text NOT NULL,target_id text NOT NULL,origin text NOT NULL,document jsonb NOT NULL,revoked boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,target_id),UNIQUE(tenant_id,origin));
CREATE TABLE target_v1.invitations(tenant_id text NOT NULL,reference text NOT NULL,subject_ref text NOT NULL,
 token_sha256 text UNIQUE NOT NULL,document jsonb NOT NULL,used boolean NOT NULL DEFAULT false,revoked boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,reference));
CREATE TABLE target_v1.sessions(tenant_id text NOT NULL,cookie_sha256 text PRIMARY KEY,csrf_sha256 text NOT NULL,
 subject_ref text NOT NULL,invitation_ref text NOT NULL,expires_at timestamptz NOT NULL,revoked boolean NOT NULL DEFAULT false,
 FOREIGN KEY(tenant_id,invitation_ref) REFERENCES target_v1.invitations);
CREATE TABLE target_v1.bindings(tenant_id text NOT NULL,request_id uuid NOT NULL,subject_ref text NOT NULL,invitation_ref text NOT NULL,
 target_id text NOT NULL,external_key text NOT NULL,intent_sha256 text NOT NULL,audit_ref text UNIQUE NOT NULL,origin_role name NOT NULL,
 origin_epoch bigint NOT NULL,plan_sha256 text NOT NULL,PRIMARY KEY(tenant_id,request_id),UNIQUE(tenant_id,subject_ref,external_key),
 FOREIGN KEY(tenant_id,request_id) REFERENCES ra4a.requests,FOREIGN KEY(tenant_id,target_id) REFERENCES target_v1.plans);
CREATE TABLE target_v1.results(tenant_id text NOT NULL,job_id uuid NOT NULL,run_id uuid NOT NULL,request_id uuid NOT NULL,
 worker_role name NOT NULL,lease_seq integer NOT NULL,artifact bytea NOT NULL CHECK(octet_length(artifact) BETWEEN 1 AND 8000000),
 artifact_sha256 text GENERATED ALWAYS AS(encode(sha256(artifact),'hex')) STORED,
 transaction_id bigint NOT NULL DEFAULT txid_current(),committed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,job_id),FOREIGN KEY(tenant_id,job_id) REFERENCES ra4a.jobs);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['capacity','plans','invitations','sessions','bindings','results'] LOOP
 EXECUTE format('ALTER TABLE target_v1.%I ENABLE ROW LEVEL SECURITY',tab);
 EXECUTE format('ALTER TABLE target_v1.%I FORCE ROW LEVEL SECURITY',tab);
 EXECUTE format('CREATE POLICY tenant_scope ON target_v1.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',tab);
 END LOOP;
 FOREACH tab IN ARRAY ARRAY['bindings','results'] LOOP
 EXECUTE format('CREATE TRIGGER immutable_target BEFORE UPDATE OR DELETE ON target_v1.%I FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable()',tab);
 END LOOP;
END $$;
CREATE FUNCTION target_v1.session(t text,cookie text,csrf text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE s target_v1.sessions%ROWTYPE; i target_v1.invitations%ROWTYPE;
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 SELECT * INTO s FROM target_v1.sessions WHERE tenant_id=t AND cookie_sha256=cookie AND csrf_sha256=csrf
 AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 SELECT * INTO i FROM target_v1.invitations WHERE tenant_id=t AND reference=s.invitation_ref
 AND NOT revoked AND (document->>'expires_at')::timestamptz>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 RETURN jsonb_build_object('tenant_id',t,'subject_ref',s.subject_ref,'invitation',i.document,'invitation_ref',i.reference);
END $$;
CREATE FUNCTION target_v1.exchange(t text,token text,cookie text,csrf text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE i target_v1.invitations%ROWTYPE; expiry timestamptz;
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 SELECT * INTO i FROM target_v1.invitations WHERE tenant_id=t AND token_sha256=token AND NOT used AND NOT revoked
 AND (document->>'expires_at')::timestamptz>clock_timestamp() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 expiry=least((i.document->>'expires_at')::timestamptz,clock_timestamp()+interval '30 minutes');
 INSERT INTO target_v1.sessions VALUES(t,cookie,csrf,i.subject_ref,i.reference,expiry,false);
 UPDATE target_v1.invitations SET used=true WHERE tenant_id=t AND reference=i.reference;
 RETURN jsonb_build_object('subject_ref',i.subject_ref,'expires_at',expiry);
END $$;
CREATE FUNCTION target_v1.plan(t text,cookie text,csrf text,site text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE actor jsonb; p target_v1.plans%ROWTYPE;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 SELECT * INTO p FROM target_v1.plans WHERE tenant_id=t AND origin||'/'=site AND NOT revoked FOR SHARE;
 IF NOT FOUND OR NOT ((actor->'invitation'->'target_ids') ? p.target_id) OR (p.document->>'expires_at')::timestamptz<=clock_timestamp() THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 RETURN jsonb_build_object('plan',p.document,'actor',actor);
END $$;
CREATE FUNCTION target_v1.admit(t text,cookie text,csrf text,ph text,payload text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE actor jsonb; plan jsonb; p jsonb; r ra4a.requests%ROWTYPE; b target_v1.bindings%ROWTYPE;
 rid uuid;jid uuid;eid uuid;ik text;key text;origin_epoch bigint;pol jsonb;active_count integer;maximum integer;
BEGIN
 IF octet_length(payload)>8192 OR encode(sha256(convert_to(payload,'UTF8')),'hex')<>ph THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='TARGET_INVALID_INPUT'; END IF;
 p=payload::jsonb; actor=target_v1.session(t,cookie,csrf);
 IF (p->>'subject_ref') IS DISTINCT FROM (actor->>'subject_ref') OR (p->>'invitation_ref') IS DISTINCT FROM (actor->>'invitation_ref')
 OR (p->'command'->'request'->>'tenant_id') IS DISTINCT FROM t THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 plan=target_v1.plan(t,cookie,csrf,p->'command'->'request'->>'site_url')->'plan';pol=plan->'policy';
 PERFORM 1 FROM ra4a.tenants WHERE tenant_id=t AND authority='AUTHORIZED_TARGET_V1' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 PERFORM 1 FROM ra4a.policies WHERE tenant_id=t AND policy_id=pol->>'policy_id' AND version=(pol->>'policy_version')::integer
 AND status='ALLOWED' AND scope='AUTHORIZED_READONLY' AND expires_at>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_POLICY_DENIED'; END IF;
 key=p->'command'->'request'->>'idempotency_key';ik='target-'||encode(sha256(convert_to((actor->>'subject_ref')||':'||key,'UTF8')),'hex');
 SELECT * INTO b FROM target_v1.bindings WHERE tenant_id=t AND subject_ref=actor->>'subject_ref' AND external_key=key;
 IF FOUND THEN
 IF b.intent_sha256<>ph THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='TARGET_IDEMPOTENCY_CONFLICT'; END IF;
 SELECT * INTO STRICT r FROM ra4a.requests WHERE tenant_id=t AND request_id=b.request_id;
 ELSE
 SELECT count(*) INTO active_count FROM ra4a.jobs WHERE tenant_id=t AND state IN ('PENDING','LEASED');
 SELECT max_pending INTO maximum FROM target_v1.capacity WHERE tenant_id=t;
 IF maximum IS NULL OR active_count>=maximum THEN RAISE EXCEPTION USING ERRCODE='53000',MESSAGE='TARGET_CAPACITY_EXCEEDED'; END IF;
 SELECT epoch INTO STRICT origin_epoch FROM target_v1.actors WHERE db_role=SESSION_USER AND active FOR SHARE;
 INSERT INTO ra4a.requests(tenant_id,principal,idempotency_key,payload_hash,canonical_payload,policy_id,policy_version,source_ref)
 VALUES(t,SESSION_USER,ik,ph,payload,pol->>'policy_id',(pol->>'policy_version')::integer,NULL) RETURNING * INTO r;
 INSERT INTO ra4a.runs(tenant_id,request_id,status) VALUES(t,r.request_id,'QUEUED') RETURNING run_id INTO rid;
 INSERT INTO ra4a.jobs(tenant_id,run_id) VALUES(t,rid) RETURNING job_id INTO jid;
 INSERT INTO ra4a.outbox(tenant_id,run_id,kind) VALUES(t,rid,'TARGET_ADMITTED') RETURNING event_id INTO eid;
 INSERT INTO ra4a.audit(tenant_id,run_id,action) VALUES(t,rid,'ADMITTED');
 INSERT INTO target_v1.bindings VALUES(t,r.request_id,actor->>'subject_ref',actor->>'invitation_ref',plan->>'target_id',key,ph,
 'aref-'||replace(gen_random_uuid()::text,'-',''),SESSION_USER,origin_epoch,
 (SELECT encode(sha256(convert_to(document::text,'UTF8')),'hex') FROM target_v1.plans WHERE tenant_id=t AND target_id=plan->>'target_id'));
 SELECT * INTO STRICT b FROM target_v1.bindings WHERE tenant_id=t AND request_id=r.request_id;
 END IF;
 SELECT s.run_id,j.job_id,e.event_id INTO rid,jid,eid FROM ra4a.runs s JOIN ra4a.jobs j USING(tenant_id,run_id)
 JOIN ra4a.outbox e USING(tenant_id,run_id) WHERE s.tenant_id=t AND s.request_id=r.request_id AND e.kind='TARGET_ADMITTED';
 RETURN jsonb_build_object('audit_ref',b.audit_ref,'request_id',r.request_id,'run_id',rid,'job_id',jid,'event_id',eid);
END $$;
CREATE FUNCTION target_v1.status(t text,cookie text,csrf text,ref text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE actor jsonb; result jsonb;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 SELECT jsonb_build_object('audit_ref',b.audit_ref,'run_id',r.run_id,'job_id',j.job_id,'request_id',r.request_id,
 'input_hash',q.payload_hash,'state',j.state,'attempts',j.attempts,'publication','UNPUBLISHED','subject_ref',b.subject_ref)
 INTO result FROM target_v1.bindings b JOIN ra4a.runs r USING(tenant_id,request_id) JOIN ra4a.jobs j USING(tenant_id,run_id) JOIN ra4a.requests q USING(tenant_id,request_id)
 WHERE b.tenant_id=t AND b.audit_ref=ref AND b.subject_ref=actor->>'subject_ref';
 IF result IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 RETURN result;
END $$;
CREATE FUNCTION target_v1.load(t text,id uuid,token uuid,seq integer) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE result jsonb;
BEGIN
 PERFORM ra4a.require_scope(t,'WORKER');
 SELECT jsonb_build_object('task',jsonb_build_object('tenant_id',t,'request_id',q.request_id,'run_id',j.run_id,'job_id',j.job_id,
 'event_id',e.event_id,'source_ref',b.target_id),'plan',p.document,'submission',q.canonical_payload::jsonb,
 'lease_until',j.lease_until,'worker_role',SESSION_USER,'loaded_at',clock_timestamp()) INTO result
 FROM ra4a.jobs j JOIN ra4a.runs r USING(tenant_id,run_id) JOIN ra4a.requests q USING(tenant_id,request_id)
 JOIN target_v1.bindings b USING(tenant_id,request_id) JOIN target_v1.plans p USING(tenant_id,target_id)
 JOIN ra4a.policies pol ON (pol.tenant_id,pol.policy_id,pol.version)=(q.tenant_id,q.policy_id,q.policy_version)
 JOIN target_v1.actors a ON a.db_role=b.origin_role AND a.tenant_id=t
 JOIN target_v1.invitations i ON i.tenant_id=t AND i.reference=b.invitation_ref
 JOIN ra4a.outbox e ON e.tenant_id=t AND e.run_id=j.run_id AND e.kind='TARGET_ADMITTED'
 WHERE j.tenant_id=t AND j.job_id=id AND j.state='LEASED' AND j.lease_owner=SESSION_USER AND j.lease_token=token
 AND j.lease_seq=seq AND j.lease_until>clock_timestamp() AND NOT p.revoked AND NOT i.revoked
 AND (i.document->>'expires_at')::timestamptz>clock_timestamp()
 AND (p.document->>'expires_at')::timestamptz>clock_timestamp()
 AND b.plan_sha256=encode(sha256(convert_to(p.document::text,'UTF8')),'hex')
 AND pol.scope='AUTHORIZED_READONLY' AND (p.document->'policy'->>'policy_id')=q.policy_id
 AND (p.document->'policy'->>'policy_version')::integer=q.policy_version
 AND (p.document->'policy'->>'expires_at')::timestamptz=pol.expires_at
 AND pol.status='ALLOWED' AND pol.expires_at>clock_timestamp() AND a.active AND a.epoch=b.origin_epoch
 AND a.expires_at>clock_timestamp() FOR SHARE OF p,pol,a,i;
 IF result IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_CURRENT_LEASE_DENIED'; END IF;
 RETURN result;
END $$;
CREATE FUNCTION target_v1.commit(t text,id uuid,token uuid,seq integer,artifact bytea) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE context jsonb;d jsonb;rid uuid;
BEGIN
 PERFORM 1 FROM ra4a.jobs WHERE tenant_id=t AND job_id=id FOR UPDATE;
 context=target_v1.load(t,id,token,seq);d=convert_from(artifact,'UTF8')::jsonb;
 rid=(context->'task'->>'run_id')::uuid;
 IF octet_length(artifact)>8000000 OR d->'task' IS DISTINCT FROM context->'task' OR d->'version'->>'status' IS DISTINCT FROM 'REVIEW_REQUIRED'
 OR d->'publication' IS DISTINCT FROM '"UNPUBLISHED"'::jsonb OR d->'external_release' IS DISTINCT FROM 'false'::jsonb
 OR d->'pack'->>'tenant_id' IS DISTINCT FROM t OR d->'pack'->>'run_id' IS DISTINCT FROM rid::text
 OR d->'native_document'->'meta'->>'run_id' IS DISTINCT FROM rid::text THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='TARGET_DRAFT_BINDING_DENIED'; END IF;
 INSERT INTO target_v1.results(tenant_id,job_id,run_id,request_id,worker_role,lease_seq,artifact)
 VALUES(t,id,rid,(context->'task'->>'request_id')::uuid,SESSION_USER,seq,artifact);
 UPDATE ra4a.jobs SET state='DRAFT_READY' WHERE tenant_id=t AND job_id=id;
 UPDATE ra4a.runs SET status='DRAFT_READY' WHERE tenant_id=t AND run_id=rid;
 INSERT INTO ra4a.outbox(tenant_id,run_id,kind) VALUES(t,rid,'DRAFT_GENERATED');
 INSERT INTO ra4a.audit(tenant_id,run_id,action,lease_seq) VALUES(t,rid,'DRAFT_GENERATED',seq);
 RETURN encode(sha256(artifact),'hex');
END $$;
-- Enforce the original lease deadline at the actual transaction boundary.
CREATE FUNCTION target_v1.result_fence() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
BEGIN
 PERFORM ra4a.require_scope(NEW.tenant_id,'WORKER');
 PERFORM 1 FROM ra4a.jobs j JOIN ra4a.runs r USING(tenant_id,run_id)
 JOIN ra4a.requests q USING(tenant_id,request_id)
 JOIN target_v1.bindings b USING(tenant_id,request_id)
 JOIN target_v1.plans p USING(tenant_id,target_id)
 JOIN ra4a.policies pol ON (pol.tenant_id,pol.policy_id,pol.version)=(q.tenant_id,q.policy_id,q.policy_version)
 JOIN target_v1.actors a ON a.db_role=b.origin_role AND a.tenant_id=b.tenant_id
 JOIN target_v1.invitations i ON i.tenant_id=b.tenant_id AND i.reference=b.invitation_ref
 WHERE j.tenant_id=NEW.tenant_id AND j.job_id=NEW.job_id AND j.run_id=NEW.run_id
 AND j.state='DRAFT_READY' AND j.lease_owner=SESSION_USER AND NEW.worker_role=SESSION_USER
 AND j.lease_seq=NEW.lease_seq AND j.lease_until>clock_timestamp()
 AND NOT p.revoked AND NOT i.revoked AND pol.status='ALLOWED'
 AND (p.document->>'expires_at')::timestamptz>clock_timestamp()
 AND (i.document->>'expires_at')::timestamptz>clock_timestamp() AND pol.expires_at>clock_timestamp()
 AND a.active AND a.epoch=b.origin_epoch AND a.expires_at>clock_timestamp()
 AND b.plan_sha256=encode(sha256(convert_to(p.document::text,'UTF8')),'hex');
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_COMMIT_FENCE'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER current_result_commit AFTER INSERT ON target_v1.results
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION target_v1.result_fence();
-- A distinct function group opens retained results only for an authenticated
-- operator review service. Customer/BFF and Worker groups cannot call this.
CREATE FUNCTION target_v1.review_source(t text,id uuid) RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE result bytea;
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 SELECT z.artifact INTO result FROM target_v1.results z JOIN ra4a.jobs j USING(tenant_id,job_id)
 JOIN ra4a.requests q USING(tenant_id,request_id)
 JOIN target_v1.bindings b USING(tenant_id,request_id)
 JOIN target_v1.plans p USING(tenant_id,target_id)
 JOIN ra4a.policies pol ON (pol.tenant_id,pol.policy_id,pol.version)=(q.tenant_id,q.policy_id,q.policy_version)
 JOIN target_v1.actors a ON a.tenant_id=t AND a.db_role=b.origin_role
 JOIN target_v1.invitations i ON i.tenant_id=t AND i.reference=b.invitation_ref
 WHERE z.tenant_id=t AND z.job_id=id AND j.state='DRAFT_READY' AND NOT p.revoked AND NOT i.revoked
 AND (p.document->>'expires_at')::timestamptz>clock_timestamp()
 AND (i.document->>'expires_at')::timestamptz>clock_timestamp()
 AND b.plan_sha256=encode(sha256(convert_to(p.document::text,'UTF8')),'hex')
 AND pol.status='ALLOWED' AND pol.scope='AUTHORIZED_READONLY' AND pol.expires_at>clock_timestamp()
 AND a.active AND a.epoch=b.origin_epoch AND a.expires_at>clock_timestamp()
 FOR SHARE OF z,j,p,pol,a,i;
 IF result IS NULL THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_REVIEW_SOURCE_DENIED'; END IF;
 RETURN result;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA target_v1 FROM PUBLIC,target_v1_app,target_v1_worker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA target_v1 FROM PUBLIC;
GRANT USAGE ON SCHEMA target_v1 TO target_v1_app,target_v1_worker,target_v1_reviewer;
GRANT EXECUTE ON FUNCTION ra4a.scope() TO target_v1_app,target_v1_worker,target_v1_reviewer;
GRANT EXECUTE ON FUNCTION ra4a.claim(text,integer) TO target_v1_worker;
GRANT EXECUTE ON FUNCTION target_v1.session(text,text,text),target_v1.exchange(text,text,text,text),
 target_v1.plan(text,text,text,text),target_v1.admit(text,text,text,text,text),target_v1.status(text,text,text,text) TO target_v1_app;
GRANT EXECUTE ON FUNCTION target_v1.load(text,uuid,uuid,integer),target_v1.commit(text,uuid,uuid,integer,bytea) TO target_v1_worker;
GRANT EXECUTE ON FUNCTION target_v1.review_source(text,uuid) TO target_v1_reviewer;
RESET ROLE;
COMMIT;
