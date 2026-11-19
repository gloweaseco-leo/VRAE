-- Additive execution/delivery ports on accepted AUTHORIZED_TARGET_V1.
BEGIN;
CREATE ROLE target_v1_ai NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO target_v1_ai;
GRANT USAGE ON SCHEMA ra4a,target_v1 TO target_v1_ai;
GRANT EXECUTE ON FUNCTION ra4a.scope() TO target_v1_ai;
SET ROLE ra4a_owner;
CREATE TABLE target_v1.authorizations(
 tenant_id text NOT NULL,target_id text NOT NULL,reference text NOT NULL,plan_sha256 text NOT NULL,
 envelope jsonb NOT NULL,not_before timestamptz NOT NULL,expires_at timestamptz NOT NULL,
 retention_until timestamptz NOT NULL,revoked boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,target_id),UNIQUE(tenant_id,reference),
 FOREIGN KEY(tenant_id,target_id) REFERENCES target_v1.plans,CHECK(not_before<expires_at AND expires_at<=retention_until));
CREATE TABLE target_v1.capture_audit(
 tenant_id text NOT NULL,job_id uuid NOT NULL,entry_id uuid DEFAULT gen_random_uuid(),
 phase text NOT NULL CHECK(phase IN ('CAPTURE_FAILED','CAPTURE_COMMITTED','AUTHORIZATION_REVOKED')),
 safe_code text NOT NULL,authorization_ref text NOT NULL,retention_until timestamptz NOT NULL,
 artifact_sha256 text,recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(tenant_id,entry_id),
 FOREIGN KEY(tenant_id,job_id) REFERENCES ra4a.jobs);
CREATE TABLE target_v1.ai_receipts(
 tenant_id text NOT NULL,job_id uuid NOT NULL,operation_id text NOT NULL,
 artifact_sha256 text NOT NULL,report_content_hash text NOT NULL,display_hash text NOT NULL,
 state text NOT NULL CHECK(state IN ('AI_UNAVAILABLE','AI_CANDIDATES_FOR_HUMAN_REVIEW')),
 receipt jsonb NOT NULL,recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,job_id,operation_id),FOREIGN KEY(tenant_id,job_id) REFERENCES target_v1.results);
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['authorizations','capture_audit','ai_receipts'] LOOP
 EXECUTE format('ALTER TABLE target_v1.%I ENABLE ROW LEVEL SECURITY',tab);
 EXECUTE format('ALTER TABLE target_v1.%I FORCE ROW LEVEL SECURITY',tab);
 EXECUTE format('CREATE POLICY tenant_scope ON target_v1.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',tab);
 END LOOP;
 FOREACH tab IN ARRAY ARRAY['capture_audit','ai_receipts'] LOOP
 EXECUTE format('CREATE TRIGGER immutable_delivery BEFORE UPDATE OR DELETE ON target_v1.%I FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable()',tab);
 END LOOP;
END $$;
CREATE FUNCTION target_v1.authorization_current(t text,target text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE a target_v1.authorizations%ROWTYPE;p target_v1.plans%ROWTYPE;
BEGIN
 IF t IS DISTINCT FROM ra4a.scope() THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_AUTHORIZATION_DENIED'; END IF;
 SELECT * INTO p FROM target_v1.plans WHERE tenant_id=t AND target_id=target AND NOT revoked FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_AUTHORIZATION_DENIED'; END IF;
 SELECT * INTO a FROM target_v1.authorizations WHERE tenant_id=t AND target_id=target AND NOT revoked
 AND not_before<=clock_timestamp() AND expires_at>clock_timestamp() AND retention_until>clock_timestamp() FOR SHARE;
 IF NOT FOUND OR a.plan_sha256 IS DISTINCT FROM encode(sha256(convert_to(p.document::text,'UTF8')),'hex')
 OR a.envelope->'document'->>'origin' IS DISTINCT FROM p.origin
 OR a.envelope->'document'->'exact_paths' IS DISTINCT FROM p.document->'exact_paths'
 OR a.reference IS DISTINCT FROM p.document->'policy'->>'authorization_reference' THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_AUTHORIZATION_DENIED'; END IF;
 RETURN a.envelope;
END $$;
ALTER FUNCTION target_v1.plan(text,text,text,text) RENAME TO plan_v1;
CREATE FUNCTION target_v1.plan(t text,cookie text,csrf text,site text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE d jsonb;
BEGIN
 d=target_v1.plan_v1(t,cookie,csrf,site);
 IF d->'plan'->>'execution_profile'='ADMIN_TARGET_V2' THEN
 d=d||jsonb_build_object('source_authorization',target_v1.authorization_current(t,d->'plan'->>'target_id'),
 'plan_sha256',(SELECT encode(sha256(convert_to(document::text,'UTF8')),'hex') FROM target_v1.plans WHERE tenant_id=t AND target_id=d->'plan'->>'target_id')); END IF;
 RETURN d;
END $$;
ALTER FUNCTION target_v1.status(text,text,text,text) RENAME TO status_v1;
CREATE FUNCTION target_v1.status(t text,cookie text,csrf text,ref text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE d jsonb;p jsonb;a target_v1.authorizations%ROWTYPE;access text='ACTIVE';
BEGIN
 d=target_v1.status_v1(t,cookie,csrf,ref);
 SELECT x.document INTO p FROM target_v1.bindings b JOIN target_v1.plans x USING(tenant_id,target_id)
 WHERE b.tenant_id=t AND b.audit_ref=ref;
 IF p->>'execution_profile'='ADMIN_TARGET_V2' THEN
 SELECT * INTO a FROM target_v1.authorizations WHERE tenant_id=t AND target_id=p->>'target_id';
 IF NOT FOUND OR a.revoked THEN access='WITHDRAWN';
 ELSIF a.expires_at<=clock_timestamp() OR a.retention_until<=clock_timestamp() THEN access='EXPIRED'; END IF;
 END IF;
 RETURN d||jsonb_build_object('access_state',access);
END $$;
ALTER FUNCTION target_v1.load(text,uuid,uuid,integer) RENAME TO load_v1;
CREATE FUNCTION target_v1.load(t text,id uuid,token uuid,seq integer) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE d jsonb;
BEGIN
 d=target_v1.load_v1(t,id,token,seq);
 IF d->'plan'->>'execution_profile'='ADMIN_TARGET_V2' THEN
 d=d||jsonb_build_object('source_authorization',target_v1.authorization_current(t,d->'plan'->>'target_id'),
 'plan_sha256',(SELECT encode(sha256(convert_to(document::text,'UTF8')),'hex') FROM target_v1.plans WHERE tenant_id=t AND target_id=d->'plan'->>'target_id')); END IF;
 RETURN d;
END $$;
ALTER FUNCTION target_v1.review_source(text,uuid) RENAME TO review_source_v1;
CREATE FUNCTION target_v1.review_source(t text,id uuid) RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE raw bytea;d jsonb;a jsonb;
BEGIN
 raw=target_v1.review_source_v1(t,id);d=convert_from(raw,'UTF8')::jsonb;
 IF d ? 'source_authority' THEN
 a=target_v1.authorization_current(t,d->'task'->>'source_ref');
 IF a IS DISTINCT FROM d->'source_authority'->'authorization' THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_AUTHORIZATION_CHANGED'; END IF;
 END IF;
 RETURN raw;
END $$;
CREATE FUNCTION target_v1.capture_failure(t text,id uuid,token uuid,seq integer,code text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE target text;a target_v1.authorizations%ROWTYPE;
BEGIN
 PERFORM ra4a.require_scope(t,'WORKER');
 IF code NOT IN ('SOURCE_AUTHORITY_DENIED','CAPTURE_FAILED','COMMIT_REFUSED') THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='SAFE_CAPTURE_CODE_REQUIRED'; END IF;
 SELECT b.target_id INTO target FROM ra4a.jobs j JOIN ra4a.runs r USING(tenant_id,run_id)
 JOIN target_v1.bindings b USING(tenant_id,request_id)
 WHERE j.tenant_id=t AND j.job_id=id AND j.state='LEASED' AND j.lease_owner=SESSION_USER
 AND j.lease_token=token AND j.lease_seq=seq AND j.lease_until>clock_timestamp() FOR SHARE OF j;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CURRENT_CAPTURE_LEASE_REQUIRED'; END IF;
 SELECT * INTO STRICT a FROM target_v1.authorizations WHERE tenant_id=t AND target_id=target;
 INSERT INTO target_v1.capture_audit(tenant_id,job_id,phase,safe_code,authorization_ref,retention_until)
 VALUES(t,id,'CAPTURE_FAILED',code,a.reference,a.retention_until);
END $$;
CREATE FUNCTION target_v1.delivery_fence() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE d jsonb;a jsonb;v jsonb;
BEGIN
 d=convert_from(NEW.artifact,'UTF8')::jsonb;
 SELECT document INTO v FROM target_v1.plans WHERE tenant_id=NEW.tenant_id AND target_id=d->'task'->>'source_ref';
 IF v->>'execution_profile'='ADMIN_TARGET_V2' THEN
 a=target_v1.authorization_current(NEW.tenant_id,d->'task'->>'source_ref');
 IF d->'source_authority'->'authorization' IS DISTINCT FROM a THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CAPTURE_AUTHORITY_COMMIT_FENCE'; END IF;
 INSERT INTO target_v1.capture_audit(tenant_id,job_id,phase,safe_code,authorization_ref,retention_until,artifact_sha256)
 SELECT NEW.tenant_id,NEW.job_id,'CAPTURE_COMMITTED','READONLY_CAPTURE_COMMITTED',reference,retention_until,NEW.artifact_sha256
 FROM target_v1.authorizations WHERE tenant_id=NEW.tenant_id AND target_id=d->'task'->>'source_ref';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER source_authority_commit AFTER INSERT ON target_v1.results
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION target_v1.delivery_fence();
CREATE FUNCTION target_v1.committed_input(t text,id uuid,purpose text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE raw bytea;d jsonb;meta jsonb;
BEGIN
 IF purpose NOT IN ('HUMAN_REVIEW_INPUT','POST_COMMIT_AI_INPUT') THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='DELIVERY_PURPOSE_REQUIRED'; END IF;
 raw=target_v1.review_source(t,id);d=convert_from(raw,'UTF8')::jsonb;
 SELECT jsonb_build_object('committed_at',z.committed_at,'transaction_id',z.transaction_id,
 'artifact_sha256',z.artifact_sha256,'lease_expires_at',j.lease_until,'lease_started_at',j.lease_until-interval '30 seconds') INTO meta
 FROM target_v1.results z JOIN ra4a.jobs j USING(tenant_id,job_id) WHERE z.tenant_id=t AND z.job_id=id FOR SHARE OF z,j;
 IF purpose='POST_COMMIT_AI_INPUT' AND (meta->>'lease_expires_at')::timestamptz>clock_timestamp() THEN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='ORIGINAL_LEASE_NOT_ENDED'; END IF;
 RETURN jsonb_build_object('contract','vrae.committed-target-input.v1','purpose',purpose,'commit',meta,
 'task',d->'task','artifact',d,'source_plan',(SELECT document FROM target_v1.plans WHERE tenant_id=t AND target_id=d->'task'->>'source_ref'),'publication','UNPUBLISHED','grants_report_access',false);
END $$;
CREATE FUNCTION target_v1.ai_record(t text,id uuid,operation text,receipt jsonb) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE d jsonb;r jsonb;
BEGIN
 d=target_v1.committed_input(t,id,'POST_COMMIT_AI_INPUT');r=d->'artifact';
 IF octet_length(receipt::text)>131072 OR length(operation) NOT BETWEEN 8 AND 128 OR receipt->>'state' IS NULL OR receipt->>'state' NOT IN ('AI_UNAVAILABLE','AI_CANDIDATES_FOR_HUMAN_REVIEW')
 OR receipt->>'artifact_sha256' IS DISTINCT FROM d->'commit'->>'artifact_sha256'
 OR receipt->>'report_content_hash' IS DISTINCT FROM r->'version'->>'content_hash'
 OR receipt->>'display_hash' IS DISTINCT FROM r->>'display_hash'
 OR receipt->'task' IS DISTINCT FROM d->'task'
 OR receipt->>'model_constraint' IS DISTINCT FROM 'qwen4-max'
 OR receipt->'grants_report_access' IS DISTINCT FROM 'false'::jsonb THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='SAME_COMMITTED_AI_BINDING_REQUIRED'; END IF;
 INSERT INTO target_v1.ai_receipts VALUES(t,id,operation,d->'commit'->>'artifact_sha256',r->'version'->>'content_hash',r->>'display_hash',receipt->>'state',receipt,clock_timestamp());
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA target_v1 FROM PUBLIC,target_v1_app,target_v1_worker,target_v1_reviewer,target_v1_ai;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA target_v1 FROM PUBLIC;
REVOKE ALL ON FUNCTION target_v1.status_v1(text,text,text,text),target_v1.plan_v1(text,text,text,text),target_v1.load_v1(text,uuid,uuid,integer),target_v1.review_source_v1(text,uuid)
 FROM target_v1_app,target_v1_worker,target_v1_reviewer,target_v1_ai;
GRANT EXECUTE ON FUNCTION target_v1.plan(text,text,text,text),target_v1.status(text,text,text,text) TO target_v1_app;
GRANT EXECUTE ON FUNCTION target_v1.load(text,uuid,uuid,integer),target_v1.capture_failure(text,uuid,uuid,integer,text) TO target_v1_worker;
GRANT EXECUTE ON FUNCTION target_v1.review_source(text,uuid),target_v1.committed_input(text,uuid,text) TO target_v1_reviewer;
GRANT EXECUTE ON FUNCTION target_v1.committed_input(text,uuid,text),target_v1.ai_record(text,uuid,text,jsonb) TO target_v1_ai;
RESET ROLE;
COMMIT;
