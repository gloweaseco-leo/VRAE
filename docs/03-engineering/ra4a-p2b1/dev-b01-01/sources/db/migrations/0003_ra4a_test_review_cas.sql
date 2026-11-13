-- Additive P2B1. All outcomes are TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL.
-- No native ReviewDecision/ReportVersion changes, no grant/share/external sender.
CREATE ROLE p2b1_review NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
CREATE ROLE p2b1_test_a_reviewer NOLOGIN IN ROLE p2b1_review;
CREATE ROLE p2b1_test_a_peer NOLOGIN IN ROLE p2b1_review;
CREATE ROLE p2b1_test_b_reviewer NOLOGIN IN ROLE p2b1_review;
GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO p2b1_review;
CREATE SCHEMA ra4a_review_test AUTHORIZATION ra4a_owner;
SET ROLE ra4a_owner;

CREATE TABLE ra4a_review_test.assignments(
 tenant_id text REFERENCES ra4a.tenants, report_id text NOT NULL, db_role name NOT NULL,
 active boolean NOT NULL DEFAULT true, authority text NOT NULL CHECK(authority='TEST_ONLY'),
 PRIMARY KEY(tenant_id,report_id,db_role));
CREATE TABLE ra4a_review_test.states(
 tenant_id text REFERENCES ra4a.tenants, report_id text NOT NULL,
 last_closed_version integer NOT NULL DEFAULT 0 CHECK(last_closed_version>=0),
 report_event_seq bigint NOT NULL DEFAULT 0 CHECK(report_event_seq>=0),
 target_digest text, PRIMARY KEY(tenant_id,report_id));
CREATE TABLE ra4a_review_test.proposals(
 tenant_id text NOT NULL, proposal_id uuid NOT NULL DEFAULT gen_random_uuid(),
 source_run_id text NOT NULL, report_id text NOT NULL, report_version integer NOT NULL,
 ref_id text NOT NULL, review_seq integer NOT NULL CHECK(review_seq=1),
 report_event_seq bigint NOT NULL CHECK(report_event_seq>0), db_actor name NOT NULL DEFAULT SESSION_USER,
 target_digest text NOT NULL, source_sha256 text NOT NULL, html_sha256 text NOT NULL,
 manifest_sha256 text NOT NULL, canonical_command bytea NOT NULL CHECK(octet_length(canonical_command)<=131072),
 command_digest text GENERATED ALWAYS AS
 (encode(sha256(decode('767261652e726133642e636f6d6d616e642e6f66666c696e652d76310a','hex')||canonical_command),'hex')) STORED,
 idempotency_key text NOT NULL CHECK(idempotency_key ~ '^[A-Za-z0-9_.-]{8,128}$'),
 status text NOT NULL CHECK(status IN ('SIMULATED_APPROVE_CANDIDATE','SIMULATED_CHANGES_REQUESTED','SIMULATED_REJECTED','SIMULATED_INTERNAL_SCOPE_ACK')),
 authority text NOT NULL DEFAULT 'TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL'
 CHECK(authority='TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL'),
 receipt bytea NOT NULL CHECK(octet_length(receipt)<=262144),
 receipt_sha256 text GENERATED ALWAYS AS (encode(sha256(receipt),'hex')) STORED,
 PRIMARY KEY(tenant_id,proposal_id), UNIQUE(tenant_id,report_id,report_version,review_seq),
 UNIQUE(tenant_id,report_id,report_version), UNIQUE(tenant_id,report_id,report_event_seq),
 UNIQUE(tenant_id,report_id,idempotency_key),
 FOREIGN KEY(tenant_id,source_run_id,report_id,report_version)
 REFERENCES ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version),
 FOREIGN KEY(tenant_id,ref_id) REFERENCES ra4a_bytes.graphs(tenant_id,ref_id));
CREATE TABLE ra4a_review_test.claims(
 tenant_id text NOT NULL, proposal_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal>0),
 guard_ref text NOT NULL, binding_ref text NOT NULL, pointer text NOT NULL, disposition text NOT NULL,
 machine_status text NOT NULL, allowed_acceptance text NOT NULL,
 PRIMARY KEY(tenant_id,proposal_id,ordinal), UNIQUE(tenant_id,proposal_id,guard_ref,binding_ref,pointer),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ra4a_review_test.proposals);
CREATE TABLE ra4a_review_test.sections(
 tenant_id text NOT NULL, proposal_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal>0),
 section_id text NOT NULL, target_digest text NOT NULL, acknowledged boolean NOT NULL CHECK(acknowledged),
 PRIMARY KEY(tenant_id,proposal_id,ordinal), UNIQUE(tenant_id,proposal_id,section_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ra4a_review_test.proposals);
CREATE TABLE ra4a_review_test.audit(
 tenant_id text NOT NULL, proposal_id uuid NOT NULL, entry_id uuid NOT NULL DEFAULT gen_random_uuid(),
 command_digest text NOT NULL, receipt_sha256 text NOT NULL, status text NOT NULL,
 db_actor name NOT NULL DEFAULT SESSION_USER,
 authority text NOT NULL DEFAULT 'TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL'
 CHECK(authority='TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL'),
 PRIMARY KEY(tenant_id,entry_id), UNIQUE(tenant_id,proposal_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ra4a_review_test.proposals);
CREATE TABLE ra4a_review_test.outbox(
 tenant_id text NOT NULL, proposal_id uuid NOT NULL, event_id uuid NOT NULL DEFAULT gen_random_uuid(),
 command_digest text NOT NULL, receipt_sha256 text NOT NULL, status text NOT NULL,
 undelivered boolean NOT NULL DEFAULT true CHECK(undelivered),
 authority text NOT NULL DEFAULT 'TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL'
 CHECK(authority='TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL'),
 PRIMARY KEY(tenant_id,event_id), UNIQUE(tenant_id,proposal_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ra4a_review_test.proposals);

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['assignments','states','proposals','claims','sections','audit','outbox'] LOOP
  EXECUTE format('ALTER TABLE ra4a_review_test.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE ra4a_review_test.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY tenant_scope ON ra4a_review_test.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['proposals','claims','sections','audit','outbox'] LOOP
  EXECUTE format('CREATE TRIGGER immutable_review BEFORE UPDATE OR DELETE ON ra4a_review_test.%I FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable()',t);
 END LOOP;
END $$;
CREATE TRIGGER state_no_delete BEFORE DELETE ON ra4a_review_test.states
 FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable();
CREATE FUNCTION ra4a_review_test.protect_state() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
BEGIN
 IF CURRENT_USER<>'ra4a_owner' THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='P2B1_STATE_TRANSACTION_ONLY';
 END IF;
 IF TG_OP='UPDATE' AND (NEW.report_event_seq<>OLD.report_event_seq+1
  OR NEW.last_closed_version<=OLD.last_closed_version)
 THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='P2B1_STATE_CAS'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER state_transaction BEFORE INSERT OR UPDATE ON ra4a_review_test.states
 FOR EACH ROW EXECUTE FUNCTION ra4a_review_test.protect_state();
CREATE FUNCTION ra4a_review_test.no_truncate() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
DECLARE populated boolean;
BEGIN
 EXECUTE format('SELECT EXISTS(SELECT 1 FROM ra4a_review_test.%I)',TG_TABLE_NAME) INTO populated;
 IF populated THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='P2B1_APPEND_ONLY'; END IF;
 RETURN NULL;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['states','proposals','claims','sections','audit','outbox'] LOOP
  EXECUTE format('CREATE TRIGGER review_no_truncate BEFORE TRUNCATE ON ra4a_review_test.%I FOR EACH STATEMENT EXECUTE FUNCTION ra4a_review_test.no_truncate()',t);
 END LOOP;
END $$;
CREATE FUNCTION ra4a_review_test.no_append() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM ra4a_review_test.outbox o WHERE o.tenant_id=NEW.tenant_id AND o.proposal_id=NEW.proposal_id)
 THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='P2B1_SEALED_PROPOSAL'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER claim_no_append BEFORE INSERT ON ra4a_review_test.claims
 FOR EACH ROW EXECUTE FUNCTION ra4a_review_test.no_append();
CREATE TRIGGER section_no_append BEFORE INSERT ON ra4a_review_test.sections
 FOR EACH ROW EXECUTE FUNCTION ra4a_review_test.no_append();

CREATE FUNCTION ra4a_review_test.require_reviewer(t text, report text) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
BEGIN
 IF NOT pg_has_role(SESSION_USER,'p2b1_review','MEMBER')
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='P2B1_TEST_REVIEWER_REQUIRED'; END IF;
 PERFORM ra4a.require_scope(t,'APP');
 PERFORM 1 FROM ra4a_review_test.assignments a WHERE a.tenant_id=t AND a.report_id=report
  AND a.db_role=SESSION_USER AND a.active AND a.authority='TEST_ONLY' FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='P2B1_REPORT_ASSIGNMENT'; END IF;
END $$;
CREATE FUNCTION ra4a_review_test.load_target(t text, ref text, run text, report text, ver integer, digest text)
RETURNS TABLE(target bytea,manifest_raw bytea,kind text,object_key text,raw bytea,content_sha256 text,length_bytes integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
BEGIN
 PERFORM ra4a_review_test.require_reviewer(t,report);
 RETURN QUERY SELECT * FROM ra4a_bytes.read_graph(t,ref,run,report,ver,digest);
END $$;

-- A raw SQL fixture caller cannot bypass native claim/section ceilings.
CREATE FUNCTION ra4a_review_test.validate_command(c jsonb,t jsonb,digest text) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
DECLARE review boolean; x jsonb; claim jsonb; changes text[]:=ARRAY[]::text[]; action text; r text;
BEGIN
 review:=c->>'kind'='REVIEW_COMMAND_PROPOSAL';
 IF jsonb_typeof(c)<>'object' OR c->>'contract_version' IS DISTINCT FROM 'ra3d-review-proposal-offline-v1'
 OR (SELECT array_agg(k ORDER BY k COLLATE "C") FROM jsonb_object_keys(c) k)
  IS DISTINCT FROM (CASE WHEN review THEN ARRAY['action','contract_version','dispositions','expected_review_seq','idempotency_key','kind','reason','report_id','report_version','sections','target_digest','tenant_id']::text[] ELSE ARRAY['checked_scope','contract_version','dispositions','expected_review_seq','idempotency_key','kind','reason','remaining_unknowns','report_id','report_version','sections','target_digest','tenant_id']::text[] END)
 OR c->>'kind' IS DISTINCT FROM (CASE WHEN review THEN 'REVIEW_COMMAND_PROPOSAL' ELSE 'COVERAGE_ACK_PROPOSAL' END)
 OR c->>'tenant_id' IS DISTINCT FROM t->>'tenant_id' OR c->>'report_id' IS DISTINCT FROM t->>'report_id'
 OR jsonb_typeof(c->'tenant_id') IS DISTINCT FROM 'string' OR jsonb_typeof(c->'report_id') IS DISTINCT FROM 'string'
 OR jsonb_typeof(c->'target_digest') IS DISTINCT FROM 'string' OR jsonb_typeof(c->'idempotency_key') IS DISTINCT FROM 'string'
 OR jsonb_typeof(c->'report_version') IS DISTINCT FROM 'number' OR (c->>'report_version') !~ '^[1-9][0-9]*$'
 OR c->'report_version' IS DISTINCT FROM t->'report_version' OR c->>'target_digest' IS DISTINCT FROM digest
 OR jsonb_typeof(c->'expected_review_seq') IS DISTINCT FROM 'number'
 OR (c->>'expected_review_seq') !~ '^[0-9]{1,4}$'
 OR c->>'idempotency_key' IS NULL OR (c->>'idempotency_key') !~ '^[A-Za-z0-9_.-]{8,128}$'
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_COMMAND_BINDING'; END IF;
 action:=c->>'action';
 IF (review AND (t->>'kind'<>'L1_NATIVE' OR action IS NULL OR action NOT IN ('APPROVE_CANDIDATE','REQUEST_CHANGES','REJECT')))
 OR (NOT review AND (t->>'kind'<>'COVERAGE_ONLY' OR c->>'checked_scope' IS DISTINCT FROM t->>'scope_digest'
  OR c->>'remaining_unknowns' IS DISTINCT FROM t->>'limitations_digest'))
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_KIND_OR_ACTION'; END IF;
 IF c->'reason'<>'null'::jsonb THEN
  r:=c->>'reason';
  IF jsonb_typeof(c->'reason')<>'string' OR char_length(r)>2000 OR r !~ '[^[:space:]]'
   OR EXISTS(SELECT 1 FROM regexp_split_to_table(r,'') ch
      WHERE ascii(ch)<32 OR ascii(ch) BETWEEN 8234 AND 8238 OR ascii(ch) BETWEEN 8294 AND 8297)
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_REASON'; END IF;
 ELSIF review AND action IN ('REQUEST_CHANGES','REJECT') THEN
  RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_REASON_REQUIRED';
 END IF;
 IF jsonb_typeof(c->'dispositions') IS DISTINCT FROM 'array'
  OR jsonb_array_length(c->'dispositions')<>jsonb_array_length(t->'claims')
  OR (SELECT count(*) FROM (SELECT x->'guard_ref',x->'binding_ref',x->'pointer'
      FROM jsonb_array_elements(c->'dispositions') x GROUP BY 1,2,3) s)<>jsonb_array_length(t->'claims')
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_CLAIMS'; END IF;
 FOR x IN SELECT * FROM jsonb_array_elements(c->'dispositions') LOOP
  SELECT q INTO claim FROM jsonb_array_elements(t->'claims') q WHERE
   (q->>'guard_ref',q->>'binding_ref',q->>'pointer')=(x->>'guard_ref',x->>'binding_ref',x->>'pointer');
  IF claim IS NULL OR (SELECT array_agg(k ORDER BY k COLLATE "C") FROM jsonb_object_keys(x) k)
   IS DISTINCT FROM ARRAY['binding_ref','disposition','guard_ref','pointer']::text[]
   OR EXISTS(SELECT 1 FROM jsonb_each(x) e WHERE jsonb_typeof(e.value)<>'string')
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_CLAIMS'; END IF;
  IF x->>'disposition' IN ('CHANGE_REQUESTED','REJECTED') THEN changes:=array_append(changes,x->>'disposition');
  ELSIF x->>'disposition' IS DISTINCT FROM claim->>'allowed_acceptance' THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_CLAIM_CEILING';
  END IF;
 END LOOP;
 IF (NOT review AND cardinality(changes)>0) OR (action='APPROVE_CANDIDATE' AND cardinality(changes)>0)
 OR (action='REQUEST_CHANGES' AND NOT ('CHANGE_REQUESTED'=ANY(changes)))
 OR (action='REJECT' AND NOT ('REJECTED'=ANY(changes)))
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_DISPOSITION_ACTION'; END IF;
 IF jsonb_typeof(c->'sections') IS DISTINCT FROM 'array'
 OR jsonb_array_length(c->'sections')<>jsonb_array_length(t->'required_sections')
 OR (SELECT count(DISTINCT x->>'section_id') FROM jsonb_array_elements(c->'sections') x)<>jsonb_array_length(t->'required_sections')
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_SECTIONS'; END IF;
 FOR x IN SELECT * FROM jsonb_array_elements(c->'sections') LOOP
  IF (SELECT array_agg(k ORDER BY k COLLATE "C") FROM jsonb_object_keys(x) k)
   IS DISTINCT FROM ARRAY['acknowledged','section_id','target_digest']::text[]
   OR jsonb_typeof(x->'section_id') IS DISTINCT FROM 'string'
   OR NOT (t->'required_sections' ? (x->>'section_id'))
   OR x->>'target_digest' IS DISTINCT FROM digest OR x->'acknowledged' IS DISTINCT FROM 'true'::jsonb
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_SECTIONS'; END IF;
 END LOOP;
 RETURN CASE WHEN NOT review THEN 'SIMULATED_INTERNAL_SCOPE_ACK'
  WHEN action='APPROVE_CANDIDATE' THEN 'SIMULATED_APPROVE_CANDIDATE'
  WHEN action='REQUEST_CHANGES' THEN 'SIMULATED_CHANGES_REQUESTED' ELSE 'SIMULATED_REJECTED' END;
END $$;

CREATE FUNCTION ra4a_review_test.check_bytes(t text,ref text,run text,report text,ver integer,digest text) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
DECLARE g ra4a_bytes.graphs%ROWTYPE; actual bytea; d jsonb; s jsonb; x record; n integer;
BEGIN
 -- Current assignment/policy/latest checks and parent lock are retained.
 PERFORM 1 FROM ra4a_bytes.read_graph(t,ref,run,report,ver,digest);
 SELECT * INTO STRICT g FROM ra4a_bytes.graphs WHERE tenant_id=t AND ref_id=ref;
 d:=convert_from(g.target_payload,'UTF8')::jsonb;
 IF NOT EXISTS(SELECT 1 FROM ra4a.references r WHERE r.tenant_id=t AND r.ref_id=ref
  AND r.metadata=d AND r.ref_sha256=g.target_sha256 AND r.target_digest=g.target_digest)
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_TARGET_BINDING'; END IF;
 SELECT ra4a_bytes.canonical_bytes(jsonb_agg(jsonb_build_object('key',object_key,'kind',kind,
   'sha256',encode(sha256(raw),'hex'),'length',octet_length(raw)) ORDER BY kind,object_key)) INTO actual
 FROM ra4a_bytes.objects WHERE tenant_id=t AND source_run_id=run AND report_id=report AND report_version=ver;
 IF actual IS DISTINCT FROM g.manifest THEN
  RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_STORED_GRAPH_CORRUPT';
 END IF;
 SELECT convert_from(raw,'UTF8')::jsonb INTO STRICT s FROM ra4a_bytes.objects
 WHERE tenant_id=t AND source_run_id=run AND report_id=report AND report_version=ver AND kind='SOURCE' AND object_key='source';
 SELECT count(*) INTO n FROM ra4a_bytes.objects
 WHERE tenant_id=t AND source_run_id=run AND report_id=report AND report_version=ver;
 IF n<>9+(SELECT count(*) FROM jsonb_object_keys(s->'objects_base64'))
 OR (SELECT count(DISTINCT kind) FROM ra4a_bytes.objects WHERE tenant_id=t AND source_run_id=run
  AND report_id=report AND report_version=ver AND kind<>'SOURCE_OBJECT')<>9
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_SOURCE_SET'; END IF;
 FOR x IN SELECT * FROM ra4a_bytes.objects WHERE tenant_id=t AND source_run_id=run AND report_id=report AND report_version=ver LOOP
  IF x.kind='SOURCE_OBJECT' THEN
   IF NOT (s->'objects_base64' ? x.object_key) OR x.raw IS DISTINCT FROM decode(s->'objects_base64'->>x.object_key,'base64')
   THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_SOURCE_OBJECT'; END IF;
  ELSIF (x.kind,x.object_key) NOT IN (('DRAFT','draft'),('HTML','html'),('SOURCE','source'),('PACK','pack'),
   ('PACKAGE','package'),('GUARD','guard'),('METADATA','metadata'),('CSS','css'),('TARGET','target')) THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_ARTIFACT_SET';
  ELSIF x.kind='TARGET' AND x.raw<>g.target_payload THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_TARGET_BINDING';
  ELSIF x.kind IN ('PACK','PACKAGE','GUARD','METADATA') AND x.raw IS DISTINCT FROM
   ra4a_bytes.canonical_bytes(s->(CASE x.kind WHEN 'PACK' THEN 'pack' WHEN 'PACKAGE' THEN 'package'
     WHEN 'GUARD' THEN 'guard_inputs' ELSE 'metadata' END)) THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_SOURCE_COMPONENT';
  END IF;
  IF x.kind IN ('DRAFT','HTML','SOURCE','CSS') AND x.content_sha256 IS DISTINCT FROM
    d->>(CASE x.kind WHEN 'DRAFT' THEN 'draft_payload_sha256' WHEN 'HTML' THEN 'html_sha256'
      WHEN 'SOURCE' THEN 'source_record_sha256' ELSE 'renderer_asset_sha256' END)
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_STORED_CONTENT_CORRUPT'; END IF;
 END LOOP;
 RETURN d;
END $$;

CREATE FUNCTION ra4a_review_test.submit(t text,ref text,run text,report text,ver integer,digest text,raw_command bytea)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
DECLARE target jsonb; c jsonb; status_value text; old ra4a_review_test.proposals%ROWTYPE;
 st ra4a_review_test.states%ROWTYPE; pid uuid:=gen_random_uuid(); result bytea;
 ch text; sh text; hh text; mh text; x jsonb; n integer:=0; claim jsonb;
BEGIN
 PERFORM ra4a_review_test.require_reviewer(t,report);
 target:=ra4a_review_test.check_bytes(t,ref,run,report,ver,digest);
 IF raw_command IS NULL OR octet_length(raw_command)>131072 THEN
  RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_COMMAND_BOUND';
 END IF;
 c:=convert_from(raw_command,'UTF8')::jsonb;
 IF ra4a_bytes.canonical_bytes(c) IS DISTINCT FROM raw_command THEN
  RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_CANONICAL_COMMAND_REQUIRED';
 END IF;
 status_value:=ra4a_review_test.validate_command(c,target,digest);
 ch:=encode(sha256(decode('767261652e726133642e636f6d6d616e642e6f66666c696e652d76310a','hex')||raw_command),'hex');
 sh:=target->>'source_record_sha256'; hh:=target->>'html_sha256';
 SELECT manifest_sha256 INTO STRICT mh FROM ra4a_bytes.graphs WHERE tenant_id=t AND ref_id=ref;
 SELECT * INTO old FROM ra4a_review_test.proposals WHERE tenant_id=t AND report_id=report AND idempotency_key=c->>'idempotency_key';
 IF FOUND THEN
  IF old.db_actor<>SESSION_USER OR old.canonical_command<>raw_command OR old.target_digest<>digest
    OR old.source_sha256<>sh OR old.html_sha256<>hh OR old.manifest_sha256<>mh
    OR old.source_run_id<>run OR old.report_version<>ver OR old.ref_id<>ref
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN old.receipt;
 END IF;
 IF (c->>'expected_review_seq')::integer<>0 THEN
  RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='P2B1_REVIEW_CONFLICT';
 END IF;
 INSERT INTO ra4a_review_test.states(tenant_id,report_id) VALUES(t,report) ON CONFLICT DO NOTHING;
 SELECT * INTO STRICT st FROM ra4a_review_test.states WHERE tenant_id=t AND report_id=report FOR UPDATE;
 IF st.last_closed_version>=ver THEN
  RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='P2B1_REVIEW_CLOSED';
 END IF;
 UPDATE ra4a_review_test.states SET last_closed_version=ver,report_event_seq=st.report_event_seq+1,target_digest=digest
 WHERE tenant_id=t AND report_id=report AND report_event_seq=st.report_event_seq AND last_closed_version=st.last_closed_version;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='P2B1_STATE_CAS'; END IF;
 result:=ra4a_bytes.canonical_bytes(jsonb_build_object(
  'contract_version','ra4a-p2b1-test-receipt-v1','authority','TEST_ONLY_SYNTHETIC_DECISIONS_NOT_HUMAN_APPROVAL',
  'tenant_id',t,'report_id',report,'source_run_id',run,'report_version',ver,'target_digest',digest,
  'review_seq',1,'report_event_seq',st.report_event_seq+1,'proposal_id',pid::text,'db_actor',SESSION_USER::text,
  'status',status_value,'command_digest',ch,'source_sha256',sh,'html_sha256',hh,
  'native_decision',NULL,'native_approval',NULL,'share_grant',NULL,'external_visibility',false,'durable',true));
 INSERT INTO ra4a_review_test.proposals(tenant_id,proposal_id,source_run_id,report_id,report_version,ref_id,
   review_seq,report_event_seq,target_digest,source_sha256,html_sha256,manifest_sha256,canonical_command,idempotency_key,status,receipt)
 VALUES(t,pid,run,report,ver,ref,1,st.report_event_seq+1,digest,sh,hh,mh,raw_command,c->>'idempotency_key',status_value,result);
 FOR x IN SELECT * FROM jsonb_array_elements(c->'dispositions') LOOP
  n:=n+1;
  SELECT q INTO STRICT claim FROM jsonb_array_elements(target->'claims') q WHERE
   (q->>'guard_ref',q->>'binding_ref',q->>'pointer')=(x->>'guard_ref',x->>'binding_ref',x->>'pointer');
  INSERT INTO ra4a_review_test.claims VALUES(t,pid,n,x->>'guard_ref',x->>'binding_ref',x->>'pointer',x->>'disposition',
    claim->>'machine_status',claim->>'allowed_acceptance');
 END LOOP;
 n:=0;
 FOR x IN SELECT * FROM jsonb_array_elements(c->'sections') LOOP
  n:=n+1;
  INSERT INTO ra4a_review_test.sections VALUES(t,pid,n,x->>'section_id',digest,true);
 END LOOP;
 INSERT INTO ra4a_review_test.audit(tenant_id,proposal_id,command_digest,receipt_sha256,status)
 VALUES(t,pid,ch,encode(sha256(result),'hex'),status_value);
 INSERT INTO ra4a_review_test.outbox(tenant_id,proposal_id,command_digest,receipt_sha256,status)
 VALUES(t,pid,ch,encode(sha256(result),'hex'),status_value);
 RETURN result;
END $$;

CREATE FUNCTION ra4a_review_test.complete_proposal() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a_review_test,pg_temp AS $$
DECLARE c jsonb; claims jsonb; sections jsonb; n integer;
BEGIN
 c:=convert_from(NEW.canonical_command,'UTF8')::jsonb;
 SELECT coalesce(jsonb_agg(jsonb_build_object('guard_ref',guard_ref,'binding_ref',binding_ref,'pointer',pointer,
  'disposition',disposition) ORDER BY ordinal),'[]'::jsonb) INTO claims FROM ra4a_review_test.claims
  WHERE tenant_id=NEW.tenant_id AND proposal_id=NEW.proposal_id;
 SELECT coalesce(jsonb_agg(jsonb_build_object('section_id',section_id,'target_digest',target_digest,
  'acknowledged',acknowledged) ORDER BY ordinal),'[]'::jsonb) INTO sections FROM ra4a_review_test.sections
  WHERE tenant_id=NEW.tenant_id AND proposal_id=NEW.proposal_id;
 SELECT count(*) INTO n FROM ra4a_review_test.audit a JOIN ra4a_review_test.outbox o USING(tenant_id,proposal_id)
  WHERE a.tenant_id=NEW.tenant_id AND a.proposal_id=NEW.proposal_id
  AND a.command_digest=NEW.command_digest AND o.command_digest=NEW.command_digest
  AND a.receipt_sha256=NEW.receipt_sha256 AND o.receipt_sha256=NEW.receipt_sha256
  AND a.status=NEW.status AND o.status=NEW.status AND o.undelivered;
 IF claims IS DISTINCT FROM c->'dispositions' OR sections IS DISTINCT FROM c->'sections' OR n<>1
  OR NOT EXISTS(SELECT 1 FROM ra4a_review_test.states s WHERE s.tenant_id=NEW.tenant_id AND s.report_id=NEW.report_id
    AND s.last_closed_version=NEW.report_version AND s.report_event_seq=NEW.report_event_seq AND s.target_digest=NEW.target_digest)
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2B1_ATOMIC_PROPOSAL_INCOMPLETE'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER complete_proposal AFTER INSERT ON ra4a_review_test.proposals
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4a_review_test.complete_proposal();
REVOKE ALL ON SCHEMA ra4a_review_test FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA ra4a_review_test FROM PUBLIC,ra4a_app,ra4a_worker,p2b1_review;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ra4a_review_test FROM PUBLIC,ra4a_app,ra4a_worker,p2b1_review;
GRANT USAGE ON SCHEMA ra4a_review_test TO p2b1_review;
GRANT EXECUTE ON FUNCTION ra4a_review_test.load_target(text,text,text,text,integer,text) TO p2b1_review;
GRANT EXECUTE ON FUNCTION ra4a_review_test.submit(text,text,text,text,integer,text,bytea) TO p2b1_review;
RESET ROLE;
