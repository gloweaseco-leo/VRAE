-- Same-subject automatic diagnosis read; no report approval or table grants.
BEGIN;
SET ROLE ra4a_owner;
-- Retain expired source plans instead of replacing their historic task pins.
ALTER TABLE target_v1.plans DROP CONSTRAINT plans_tenant_id_origin_key;
CREATE OR REPLACE FUNCTION target_v1.plan_v1(t text,cookie text,csrf text,site text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE actor jsonb;p target_v1.plans%ROWTYPE;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 SELECT * INTO p FROM target_v1.plans WHERE tenant_id=t AND origin||'/'=site AND NOT revoked
 AND (actor->'invitation'->'target_ids') ? target_id
 AND (document->>'expires_at')::timestamptz>clock_timestamp()
 ORDER BY document->'policy'->>'created_at' DESC,target_id LIMIT 1 FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 RETURN jsonb_build_object('plan',p.document,'actor',actor);
END $$;
CREATE FUNCTION target_v1.submission_plan(t text,cookie text,csrf text,site text,policy text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE actor jsonb;p target_v1.plans%ROWTYPE;d jsonb;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 SELECT * INTO p FROM target_v1.plans WHERE tenant_id=t AND origin||'/'=site AND NOT revoked
 AND document->'policy'->>'policy_id'=policy
 AND (actor->'invitation'->'target_ids') ? target_id
 AND (document->>'expires_at')::timestamptz>clock_timestamp() FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 d=jsonb_build_object('plan',p.document,'actor',actor);
 IF p.document->>'execution_profile'='ADMIN_TARGET_V2' THEN
 d=d||jsonb_build_object('source_authorization',target_v1.authorization_current(t,p.target_id),
 'plan_sha256',encode(sha256(convert_to(p.document::text,'UTF8')),'hex')); END IF;
 RETURN d;
END $$;
REVOKE ALL ON FUNCTION target_v1.submission_plan(text,text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.submission_plan(text,text,text,text,text) TO target_v1_app;
CREATE OR REPLACE FUNCTION target_v1.source_context(t text,cookie text,csrf text,target text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE p jsonb;
BEGIN
 SELECT document INTO p FROM target_v1.plans WHERE tenant_id=t AND target_id=target AND NOT revoked;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_CONTEXT_DENIED'; END IF;
 RETURN target_v1.submission_plan(t,cookie,csrf,(p->>'origin')||'/',p->'policy'->>'policy_id');
END $$;
CREATE OR REPLACE FUNCTION target_v1.admit(t text,cookie text,csrf text,ph text,payload text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE actor jsonb; plan jsonb; p jsonb; r ra4a.requests%ROWTYPE; b target_v1.bindings%ROWTYPE;
 rid uuid;jid uuid;eid uuid;ik text;key text;origin_epoch bigint;pol jsonb;active_count integer;maximum integer;
BEGIN
 IF octet_length(payload)>8192 OR encode(sha256(convert_to(payload,'UTF8')),'hex')<>ph THEN
 RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='TARGET_INVALID_INPUT'; END IF;
 p=payload::jsonb; actor=target_v1.session(t,cookie,csrf);
 IF (p->>'subject_ref') IS DISTINCT FROM (actor->>'subject_ref') OR (p->>'invitation_ref') IS DISTINCT FROM (actor->>'invitation_ref')
 OR (p->'command'->'request'->>'tenant_id') IS DISTINCT FROM t THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='TARGET_ACCESS_DENIED'; END IF;
 plan=target_v1.submission_plan(t,cookie,csrf,p->'command'->'request'->>'site_url',p->'command'->'request'->>'source_policy_ref')->'plan';pol=plan->'policy';
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
CREATE FUNCTION target_v1.automatic_retry(t text,cookie text,csrf text,external_key text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE actor jsonb;payload jsonb;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 SELECT q.canonical_payload::jsonb INTO payload
 FROM target_v1.bindings b JOIN ra4a.requests q USING(tenant_id,request_id)
 WHERE b.tenant_id=t AND b.subject_ref=actor->>'subject_ref'
 AND b.invitation_ref=actor->>'invitation_ref' AND b.external_key=automatic_retry.external_key;
 RETURN payload;
END $$;
REVOKE ALL ON FUNCTION target_v1.automatic_retry(text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.automatic_retry(text,text,text,text) TO target_v1_app;
CREATE FUNCTION target_v1.automatic_diagnosis(t text,cookie text,csrf text,ref text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a,target_v1,pg_temp AS $$
DECLARE s jsonb;raw bytea;d jsonb;r jsonb;p jsonb;submission jsonb;actor jsonb;
BEGIN
 actor=target_v1.session(t,cookie,csrf);
 s=target_v1.status(t,cookie,csrf,ref);
 SELECT q.canonical_payload::jsonb,x.document INTO submission,p
 FROM target_v1.bindings b JOIN ra4a.requests q USING(tenant_id,request_id)
 JOIN target_v1.plans x USING(tenant_id,target_id)
 WHERE b.tenant_id=t AND b.audit_ref=ref
 AND b.subject_ref=actor->>'subject_ref' AND b.invitation_ref=actor->>'invitation_ref'
 FOR SHARE OF b,q,x;
 IF submission IS NULL OR submission->'diagnosis_consent'->>'consent_version'
 IS DISTINCT FROM 'VRAE-AUTO-DIAGNOSIS-1'
 OR submission->'diagnosis_consent'->>'text_sha256' IS DISTINCT FROM p->'automatic_result'->>'text_sha256'
 OR p->>'path_scope' IS DISTINCT FROM 'PUBLIC_SAME_ORIGIN'
 OR s->>'access_state' IS DISTINCT FROM 'ACTIVE'
 OR NOT ((actor->'invitation'->'target_ids') ? (p->>'target_id'))
 OR actor->'invitation'->'model_processing_targets'->>(p->>'target_id')
 IS DISTINCT FROM encode(sha256(convert_to(p::text,'UTF8')),'hex') THEN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='AUTOMATIC_DIAGNOSIS_ACCESS_DENIED'; END IF;
 IF s->>'state'<>'DRAFT_READY' THEN RETURN jsonb_build_object('status',s,'artifact',NULL,'receipt',NULL); END IF;
 -- Reuse the full current source/policy/actor/epoch/COMMIT fence, holding its
 -- locks until the HTTP response is written. APP gets no raw artifact privilege.
 raw=target_v1.review_source(t,(s->>'job_id')::uuid);d=convert_from(raw,'UTF8')::jsonb;
 SELECT receipt INTO r FROM target_v1.ai_receipts WHERE tenant_id=t AND job_id=(s->>'job_id')::uuid
 AND operation_id='service-ai-'||(s->>'job_id')
 AND artifact_sha256=encode(sha256(raw),'hex')
 AND report_content_hash=d->'version'->>'content_hash' AND display_hash=d->>'display_hash'
 FOR SHARE;
 RETURN jsonb_build_object('status',s,'artifact',d,'receipt',r,
 'artifact_sha256',encode(sha256(raw),'hex'),'plan',p);
END $$;
REVOKE ALL ON FUNCTION target_v1.automatic_diagnosis(text,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.automatic_diagnosis(text,text,text,text) TO target_v1_app;
RESET ROLE;
COMMIT;
