-- Additive synthetic internal review ledger. No report mutation, human
-- approval, delivery or grant. Install only after the Owner-accepted M1 SQL.
BEGIN;
CREATE SCHEMA b5b_m2 AUTHORIZATION ra4a_owner;
REVOKE ALL ON SCHEMA b5b_m2 FROM PUBLIC;
SET LOCAL ROLE ra4a_owner;
CREATE TABLE b5b_m2.receipts (
 tenant_id text NOT NULL,
 job_id uuid NOT NULL,
 reviewer name NOT NULL,
 command_id uuid NOT NULL,
 command jsonb NOT NULL,
 receipt jsonb NOT NULL,
 session_until timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,reviewer,command_id)
);
ALTER TABLE b5b_m2.receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE b5b_m2.receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON b5b_m2.receipts FOR ALL TO ra4a_owner
 USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope());
CREATE FUNCTION b5b_m2.immutable() RETURNS trigger
 LANGUAGE plpgsql SET search_path=pg_catalog,b5b_m2,pg_temp AS $$ BEGIN
 RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_IMMUTABLE_RECEIPT'; END $$;
CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON b5b_m2.receipts
 FOR EACH ROW EXECUTE FUNCTION b5b_m2.immutable();
CREATE FUNCTION b5b_m2.current_at_commit() RETURNS trigger
 LANGUAGE plpgsql SET search_path=pg_catalog,b5b_m2,pg_temp AS $$ BEGIN
 IF NEW.session_until<=clock_timestamp() THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_SESSION_EXPIRED_AT_COMMIT'; END IF;
 RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER session_current_at_commit AFTER INSERT ON b5b_m2.receipts
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION b5b_m2.current_at_commit();

CREATE FUNCTION b5b_m2.submit(t text,id uuid,cmd_id uuid,cmd jsonb,
 session_deadline timestamptz DEFAULT clock_timestamp()+interval '120 seconds')
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,b5b_m2,pg_temp AS $$
DECLARE result record; doc jsonb; item jsonb; actual text[]; submitted text[];
 saved b5b_m2.receipts%ROWTYPE; receipt jsonb; pins jsonb;
BEGIN
 -- Holds the original origin/assignment/tenant locks until the real caller's
 -- COMMIT. Signature validity is ALSO required by the public signed service;
 -- direct SQL tests verify DB authorization, not browser identity.
 SELECT * INTO STRICT result FROM ra4b_p2.m1_read_assigned(t,id);
 doc:=convert_from(result.report,'UTF8')::jsonb;
 pins:=result.locator;
 IF session_deadline IS NULL OR session_deadline<=clock_timestamp()
 OR session_deadline>clock_timestamp()+interval '120 seconds'
 OR cmd_id IS NULL OR cmd IS NULL OR jsonb_typeof(cmd)<>'object'
 OR octet_length(cmd::text)>24576
 OR (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(cmd) k)
    IS DISTINCT FROM ARRAY['decision','issues','report_sha256','report_version','revision','scope']::text[]
 OR cmd->>'scope' IS DISTINCT FROM 'SYNTHETIC_INTERNAL_REVIEW_ONLY'
 OR cmd->'report_version' IS DISTINCT FROM pins->'report_version'
 OR cmd->>'report_sha256' IS DISTINCT FROM pins->>'report_sha256'
 OR jsonb_typeof(cmd->'issues') IS DISTINCT FROM 'array'
 OR jsonb_array_length(cmd->'issues')>3
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_COMMAND_DENIED'; END IF;
 SELECT array_agg(x->'finding'->>'finding_id' ORDER BY x->'finding'->>'finding_id') INTO actual
 FROM jsonb_array_elements(doc->'issues') x;
 SELECT array_agg(x->>'finding_id' ORDER BY x->>'finding_id') INTO submitted
 FROM jsonb_array_elements(cmd->'issues') x;
 IF actual IS DISTINCT FROM submitted THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_ISSUE_SET_DENIED'; END IF;
 FOR item IN SELECT cmd UNION ALL SELECT value FROM jsonb_array_elements(cmd->'issues') LOOP
  IF jsonb_typeof(item->'decision') IS DISTINCT FROM 'string'
   OR item->>'decision' NOT IN('APPROVE_INTERNAL','REJECT_INTERNAL','REVISE_INTERNAL')
   OR jsonb_typeof(item->'revision') IS DISTINCT FROM 'string'
   OR length(item->>'revision')>2000
   OR (item->>'decision'='REVISE_INTERNAL' AND btrim(item->>'revision')='')
   OR replace(replace(replace(item->>'revision',chr(10),''),chr(13),''),chr(9),'') ~ '[[:cntrl:]]'
  THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_DECISION_DENIED'; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(cmd->'issues') x
   WHERE (SELECT array_agg(k ORDER BY k) FROM jsonb_object_keys(x) k)
   IS DISTINCT FROM ARRAY['decision','finding_id','revision']::text[]) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_ISSUE_COMMAND_DENIED'; END IF;
 SELECT * INTO saved FROM b5b_m2.receipts
 WHERE(tenant_id,reviewer,command_id)=(t,SESSION_USER,cmd_id);
 IF FOUND THEN
  IF saved.job_id<>id OR saved.command IS DISTINCT FROM cmd THEN
   RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN saved.receipt;
 END IF;
 receipt:=jsonb_build_object('scope','SYNTHETIC_INTERNAL_REVIEW_ONLY',
  'receipt_id',gen_random_uuid(),'command_id',cmd_id,'recorded_at',clock_timestamp(),
  'report',pins,'decision',cmd->>'decision','revision',cmd->>'revision','issues',cmd->'issues',
  'report_approval_status','NOT_APPROVED','human_approval',false,'external_delivery',false);
 INSERT INTO b5b_m2.receipts VALUES(t,id,SESSION_USER,cmd_id,cmd,receipt,session_deadline);
 RETURN receipt;
END $$;

CREATE FUNCTION b5b_m2.read_receipt(t text,id uuid,cmd_id uuid)
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,b5b_m2,pg_temp AS $$
DECLARE result record; saved b5b_m2.receipts%ROWTYPE; BEGIN
 SELECT * INTO STRICT result FROM ra4b_p2.m1_read_assigned(t,id);
 SELECT * INTO saved FROM b5b_m2.receipts
 WHERE(tenant_id,job_id,reviewer,command_id)=(t,id,SESSION_USER,cmd_id);
 IF NOT FOUND OR saved.receipt->'report' IS DISTINCT FROM result.locator THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='M2_RECEIPT_DENIED'; END IF;
 RETURN saved.receipt;
END $$;
CREATE FUNCTION b5b_m2.list_receipts(t text,id uuid)
 RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
 SET search_path=pg_catalog,b5b_m2,pg_temp AS $$
DECLARE result record; items jsonb; BEGIN
 SELECT * INTO STRICT result FROM ra4b_p2.m1_read_assigned(t,id);
 SELECT coalesce(jsonb_agg(row.receipt),'[]'::jsonb) INTO items FROM (
  SELECT r.receipt FROM b5b_m2.receipts r
  WHERE(r.tenant_id,r.job_id,r.reviewer)=(t,id,SESSION_USER)
   AND r.receipt->'report'=result.locator
  ORDER BY (r.receipt->>'recorded_at')::timestamptz DESC,r.command_id DESC LIMIT 20
 ) row;
 RETURN items;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA b5b_m2 FROM PUBLIC,p2b1_review,ra4b_app,ra4b_worker;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA b5b_m2 FROM PUBLIC,p2b1_review,ra4b_app,ra4b_worker;
GRANT USAGE ON SCHEMA b5b_m2 TO p2b1_review;
GRANT EXECUTE ON FUNCTION b5b_m2.submit(text,uuid,uuid,jsonb,timestamptz),
 b5b_m2.read_receipt(text,uuid,uuid),b5b_m2.list_receipts(text,uuid) TO p2b1_review;
RESET ROLE;
COMMIT;
