-- Add scoped product profile to the original immutable request-language port.
BEGIN;
SET ROLE ra4a_owner;
CREATE OR REPLACE FUNCTION target_v1.committed_input(t text,id uuid,purpose text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE raw bytea;d jsonb;meta jsonb;value jsonb;lang text;
BEGIN
 IF purpose NOT IN ('HUMAN_REVIEW_INPUT','POST_COMMIT_AI_INPUT') THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='DELIVERY_PURPOSE_REQUIRED'; END IF;
 raw=target_v1.review_source(t,id);d=convert_from(raw,'UTF8')::jsonb;
 SELECT jsonb_build_object('committed_at',z.committed_at,'transaction_id',z.transaction_id,
 'artifact_sha256',z.artifact_sha256,'lease_expires_at',j.lease_until,'lease_started_at',j.lease_until-interval '30 seconds') INTO meta
 FROM target_v1.results z JOIN ra4a.jobs j USING(tenant_id,job_id) WHERE z.tenant_id=t AND z.job_id=id FOR SHARE OF z,j;
 IF purpose='POST_COMMIT_AI_INPUT' AND (meta->>'lease_expires_at')::timestamptz>clock_timestamp() THEN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='ORIGINAL_LEASE_NOT_ENDED'; END IF;
 value=jsonb_build_object('contract','vrae.committed-target-input.v1','purpose',purpose,'commit',meta,
 'task',d->'task','artifact',d,'source_plan',(SELECT document FROM target_v1.plans WHERE tenant_id=t AND target_id=d->'task'->>'source_ref'),'publication','UNPUBLISHED','grants_report_access',false);
 IF d->'diagnosis'->>'diagnostic_version' IN ('l2-industrial-1.0.3','l2-industrial-1.0.4') THEN
 SELECT q.canonical_payload::jsonb->>'language' INTO lang FROM ra4a.requests q
 WHERE q.tenant_id=t AND q.request_id=(d->'task'->>'request_id')::uuid;
 IF lang IS NULL OR lang NOT IN ('zh','en') THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='COMMITTED_REQUEST_LANGUAGE_REQUIRED'; END IF;
 value=value||jsonb_build_object('request_language',lang);
 END IF;
 RETURN value;
END $$;
RESET ROLE;
COMMIT;
