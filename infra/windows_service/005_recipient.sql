-- Additive read-only bridge for the CURRENT original invited recipient.
BEGIN;
SET ROLE ra4a_owner;
CREATE FUNCTION target_v1.recipient_context(t text,ref text,cookie text,csrf text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE actor target_v1.sessions%ROWTYPE;ctx jsonb;id uuid;deadline timestamptz;
BEGIN
 IF t IS DISTINCT FROM ra4a.scope() OR NOT pg_has_role(SESSION_USER,'target_v1_reviewer','member') THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CURRENT_RECIPIENT_DENIED';END IF;
 SELECT * INTO STRICT actor FROM target_v1.sessions s
 WHERE s.tenant_id=t AND s.cookie_sha256=cookie AND s.csrf_sha256=csrf
 AND NOT s.revoked AND s.expires_at>clock_timestamp() FOR SHARE;
 id=target_v1.report_job(t,ref);
 ctx=target_v1.report_context(t,id);
 IF actor.subject_ref IS DISTINCT FROM ctx->>'recipient_subject'
 OR actor.invitation_ref IS DISTINCT FROM ctx->>'invitation_ref' THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CURRENT_RECIPIENT_DENIED';END IF;
 SELECT least(s.expires_at,(ctx->>'authority_expires_at')::timestamptz) INTO STRICT deadline
 FROM target_v1.sessions s WHERE tenant_id=t AND cookie_sha256=cookie AND csrf_sha256=csrf
 AND NOT revoked AND expires_at>clock_timestamp() FOR SHARE;
 RETURN jsonb_build_object('tenant_id',t,'job_id',id,'audit_ref',ref,
 'subject_ref',actor.subject_ref,'invitation_ref',actor.invitation_ref,
 'expires_at',deadline,'artifact_sha256',ctx->'commit'->>'artifact_sha256');
END $$;
REVOKE ALL ON FUNCTION target_v1.recipient_context(text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.recipient_context(text,text,text,text) TO target_v1_reviewer;
RESET ROLE;
COMMIT;
