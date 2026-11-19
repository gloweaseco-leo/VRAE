-- One current recipient/context port on existing committed results, no new store.
BEGIN;
SET ROLE ra4a_owner;
CREATE FUNCTION target_v1.report_context(t text,id uuid) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE d jsonb;b target_v1.bindings%ROWTYPE;i target_v1.invitations%ROWTYPE;deadline timestamptz;
BEGIN
 d=target_v1.committed_input(t,id,'HUMAN_REVIEW_INPUT');
 SELECT * INTO STRICT b FROM target_v1.bindings WHERE tenant_id=t AND request_id=(d->'task'->>'request_id')::uuid FOR SHARE;
 SELECT * INTO STRICT i FROM target_v1.invitations WHERE tenant_id=t AND reference=b.invitation_ref
 AND subject_ref=b.subject_ref AND NOT revoked AND (document->>'expires_at')::timestamptz>clock_timestamp() FOR SHARE;
 SELECT least((p.document->>'expires_at')::timestamptz,(p.document->'policy'->>'expires_at')::timestamptz,
 a.expires_at,a.retention_until,origin.expires_at,caller.expires_at,(i.document->>'expires_at')::timestamptz)
 INTO deadline FROM target_v1.plans p JOIN target_v1.authorizations a USING(tenant_id,target_id)
 JOIN target_v1.actors origin ON origin.db_role=b.origin_role AND origin.tenant_id=t
 JOIN target_v1.actors caller ON caller.db_role=SESSION_USER AND caller.tenant_id=t
 WHERE p.tenant_id=t AND p.target_id=b.target_id AND NOT a.revoked;
 IF deadline IS NULL OR deadline<=clock_timestamp() THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='CURRENT_REPORT_AUTHORITY_DENIED'; END IF;
 RETURN d||jsonb_build_object('recipient_subject',b.subject_ref,'invitation_ref',b.invitation_ref,'authority_expires_at',deadline);
END $$;
REVOKE ALL ON FUNCTION target_v1.report_context(text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.report_context(text,uuid) TO target_v1_reviewer;
RESET ROLE;
COMMIT;
