-- API readiness and task-scoped one-use session recovery. No report authority.
BEGIN;
SET ROLE ra4a_owner;
CREATE TABLE target_v1.return_tokens(
 tenant_id text NOT NULL,token_sha256 text PRIMARY KEY CHECK(token_sha256~'^[0-9a-f]{64}$'),
 audit_ref text NOT NULL,subject_ref text NOT NULL,invitation_ref text NOT NULL,
 origin_role name NOT NULL,origin_epoch bigint NOT NULL,expires_at timestamptz NOT NULL,
 used boolean NOT NULL DEFAULT false,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(tenant_id,invitation_ref) REFERENCES target_v1.invitations);
ALTER TABLE target_v1.return_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE target_v1.return_tokens FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON target_v1.return_tokens USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope());
CREATE FUNCTION target_v1.readiness(t text) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
BEGIN PERFORM ra4a.require_scope(t,'APP');RETURN true;END $$;
CREATE FUNCTION target_v1.source_context(t text,cookie text,csrf text,target text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE actor jsonb;site text;d jsonb;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 IF NOT ((actor->'invitation'->'target_ids') ? target) THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_CONTEXT_DENIED'; END IF;
 SELECT origin||'/' INTO site FROM target_v1.plans WHERE tenant_id=t AND target_id=target AND NOT revoked;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_CONTEXT_DENIED'; END IF;
 d=target_v1.plan(t,cookie,csrf,site);
 RETURN d;
END $$;
REVOKE ALL ON FUNCTION target_v1.source_context(text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.source_context(text,text,text,text) TO target_v1_app;
CREATE FUNCTION target_v1.make_return(t text,cookie text,csrf text,ref text,token text,ttl integer) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE actor jsonb;status jsonb;expiry timestamptz;epoch bigint;
BEGIN
 actor=target_v1.session(t,cookie,csrf);status=target_v1.status(t,cookie,csrf,ref);
 IF ttl NOT BETWEEN 1 AND 900 OR token !~ '^[0-9a-f]{64}$' THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='RETURN_INPUT_REQUIRED'; END IF;
 expiry=least(clock_timestamp()+make_interval(secs=>ttl),(actor->'invitation'->>'expires_at')::timestamptz);
 SELECT x.epoch INTO STRICT epoch FROM target_v1.actors x WHERE x.db_role=SESSION_USER AND active FOR SHARE;
 INSERT INTO target_v1.return_tokens(tenant_id,token_sha256,audit_ref,subject_ref,invitation_ref,origin_role,origin_epoch,expires_at)
 VALUES(t,token,ref,actor->>'subject_ref',actor->>'invitation_ref',SESSION_USER,epoch,expiry);
 RETURN jsonb_build_object('audit_ref',ref,'expires_at',expiry,'grants_report_access',false);
END $$;
CREATE FUNCTION target_v1.exchange_return(t text,token text,cookie text,csrf text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE r target_v1.return_tokens%ROWTYPE;i target_v1.invitations%ROWTYPE;expiry timestamptz;
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 SELECT * INTO r FROM target_v1.return_tokens WHERE tenant_id=t AND token_sha256=token AND NOT used AND expires_at>clock_timestamp() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RETURN_ACCESS_DENIED'; END IF;
 SELECT * INTO i FROM target_v1.invitations WHERE tenant_id=t AND reference=r.invitation_ref AND subject_ref=r.subject_ref AND NOT revoked
 AND (document->>'expires_at')::timestamptz>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RETURN_ACCESS_DENIED'; END IF;
 PERFORM 1 FROM target_v1.actors WHERE db_role=r.origin_role AND tenant_id=t AND active AND epoch=r.origin_epoch AND expires_at>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='RETURN_ACCESS_DENIED'; END IF;
 expiry=least(clock_timestamp()+interval '30 minutes',(i.document->>'expires_at')::timestamptz);
 INSERT INTO target_v1.sessions VALUES(t,cookie,csrf,r.subject_ref,r.invitation_ref,expiry,false);
 UPDATE target_v1.return_tokens SET used=true WHERE token_sha256=token;
 RETURN jsonb_build_object('subject_ref',r.subject_ref,'expires_at',expiry,'audit_ref',r.audit_ref,'grants_report_access',false);
END $$;
CREATE FUNCTION target_v1.completion_facts(t text,id uuid) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE d jsonb;deadline timestamptz;
BEGIN
 d=target_v1.committed_input(t,id,'POST_COMMIT_AI_INPUT');
 SELECT least((p.document->>'expires_at')::timestamptz,(p.document->'policy'->>'expires_at')::timestamptz,
 a.expires_at,a.retention_until,origin.expires_at,caller.expires_at,(i.document->>'expires_at')::timestamptz)
 INTO deadline FROM target_v1.bindings b JOIN target_v1.plans p USING(tenant_id,target_id)
 JOIN target_v1.authorizations a USING(tenant_id,target_id)
 JOIN target_v1.actors origin ON origin.db_role=b.origin_role AND origin.tenant_id=t
 JOIN target_v1.actors caller ON caller.db_role=SESSION_USER AND caller.tenant_id=t
 JOIN target_v1.invitations i ON i.tenant_id=t AND i.reference=b.invitation_ref
 WHERE b.tenant_id=t AND b.request_id=(d->'task'->>'request_id')::uuid;
 IF deadline IS NULL OR deadline<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='COMPLETION_AUTHORITY_UNAVAILABLE'; END IF;
 RETURN d||jsonb_build_object('authority_expires_at',deadline);
END $$;
REVOKE ALL ON FUNCTION target_v1.completion_facts(text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.completion_facts(text,uuid) TO target_v1_ai;
REVOKE ALL ON target_v1.return_tokens FROM PUBLIC,target_v1_app,target_v1_worker,target_v1_reviewer,target_v1_ai;
REVOKE ALL ON FUNCTION target_v1.readiness(text),target_v1.make_return(text,text,text,text,text,integer),target_v1.exchange_return(text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.readiness(text),target_v1.make_return(text,text,text,text,text,integer),target_v1.exchange_return(text,text,text,text) TO target_v1_app;
RESET ROLE;
COMMIT;
