-- Restart-safe discovery on the original result ledger, not another job queue.
BEGIN;
SET ROLE ra4a_owner;
CREATE FUNCTION target_v1.ai_pending(t text) RETURNS SETOF uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,ra4a,pg_temp AS $$
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 IF NOT pg_has_role(SESSION_USER,'target_v1_ai','MEMBER') THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='AI_PORT_REQUIRED'; END IF;
 RETURN QUERY SELECT z.job_id FROM target_v1.results z JOIN ra4a.jobs j USING(tenant_id,job_id)
 WHERE z.tenant_id=t AND j.state='DRAFT_READY' AND j.lease_until<clock_timestamp()
 AND NOT EXISTS(SELECT 1 FROM target_v1.ai_receipts a WHERE a.tenant_id=t AND a.job_id=z.job_id)
 ORDER BY z.committed_at LIMIT 20;
END $$;
REVOKE ALL ON FUNCTION target_v1.ai_pending(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.ai_pending(text) TO target_v1_ai;
RESET ROLE;
COMMIT;
