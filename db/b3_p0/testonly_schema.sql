-- Disposable B3-P0 bootstrap ONLY, explicitly after accepted 0001-0003.
-- Not a global migration. Never writes ra4a_private.migrations.
CREATE SCHEMA b3_p0 AUTHORIZATION ra4a_owner;
SET ROLE ra4a_owner;
CREATE TABLE b3_p0.bootstrap(schema_sha256 text PRIMARY KEY CHECK(schema_sha256 ~ '^[0-9a-f]{64}$'));
CREATE TABLE b3_p0.authority(
 tenant_id text PRIMARY KEY REFERENCES ra4a.tenants, epoch bigint NOT NULL CHECK(epoch>0),
 anchor_active boolean NOT NULL, anchor_expires timestamptz NOT NULL);
CREATE TABLE b3_p0.witnesses(
 tenant_id text NOT NULL REFERENCES b3_p0.authority, witness_id uuid NOT NULL,
 db_actor name NOT NULL, subject text NOT NULL CHECK(subject ~ '^TEST_ONLY_[a-z0-9_]{1,80}$'),
 epoch bigint NOT NULL, expires timestamptz NOT NULL,
 ref_id text NOT NULL, source_run_id text NOT NULL, report_id text NOT NULL,
 report_version integer NOT NULL, target_digest text NOT NULL,
 PRIMARY KEY(tenant_id,witness_id),
 FOREIGN KEY(tenant_id,source_run_id,report_id,report_version)
 REFERENCES ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version),
 FOREIGN KEY(tenant_id,ref_id) REFERENCES ra4a_bytes.graphs(tenant_id,ref_id));
CREATE TABLE b3_p0.states(
 tenant_id text NOT NULL REFERENCES ra4a.tenants, report_id text NOT NULL,
 report_version integer NOT NULL, seq integer NOT NULL CHECK(seq BETWEEN 0 AND 1),
 PRIMARY KEY(tenant_id,report_id,report_version));
CREATE TABLE b3_p0.intents(
 tenant_id text NOT NULL, intent_id uuid NOT NULL, witness_id uuid NOT NULL,
 db_actor name NOT NULL, subject text NOT NULL, ref_id text NOT NULL,
 source_run_id text NOT NULL, report_id text NOT NULL, report_version integer NOT NULL,
 target_digest text NOT NULL, source_sha256 text NOT NULL, html_sha256 text NOT NULL,
 manifest_sha256 text NOT NULL, canonical_command bytea NOT NULL CHECK(octet_length(canonical_command)<=131072),
 command_digest text NOT NULL, idempotency_key text NOT NULL,
 status text NOT NULL CHECK(status IN ('REVIEW_INTENT_TEST_ONLY','COVERAGE_ACK_TEST_ONLY')),
 receipt bytea NOT NULL, receipt_sha256 text GENERATED ALWAYS AS (encode(sha256(receipt),'hex')) STORED,
 authority text NOT NULL DEFAULT 'TEST_ONLY_REVIEW_INTENT' CHECK(authority='TEST_ONLY_REVIEW_INTENT'),
 effective_approval boolean NOT NULL DEFAULT false CHECK(NOT effective_approval),
 external_visibility boolean NOT NULL DEFAULT false CHECK(NOT external_visibility),
 person_id text CHECK(person_id IS NULL), native_decision text CHECK(native_decision IS NULL),
 share_grant text CHECK(share_grant IS NULL),
 PRIMARY KEY(tenant_id,intent_id), UNIQUE(tenant_id,report_id,report_version),
 UNIQUE(tenant_id,report_id,idempotency_key),
 FOREIGN KEY(tenant_id,witness_id) REFERENCES b3_p0.witnesses,
 FOREIGN KEY(tenant_id,source_run_id,report_id,report_version)
 REFERENCES ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version),
 FOREIGN KEY(tenant_id,ref_id) REFERENCES ra4a_bytes.graphs(tenant_id,ref_id));
CREATE TABLE b3_p0.claims(
 tenant_id text NOT NULL, intent_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal>0),
 disposition jsonb NOT NULL, PRIMARY KEY(tenant_id,intent_id,ordinal),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES b3_p0.intents);
CREATE TABLE b3_p0.sections(
 tenant_id text NOT NULL, intent_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal>0),
 acknowledgement jsonb NOT NULL, PRIMARY KEY(tenant_id,intent_id,ordinal),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES b3_p0.intents);
CREATE TABLE b3_p0.audit(
 tenant_id text NOT NULL, intent_id uuid NOT NULL, db_actor name NOT NULL,
 command_digest text NOT NULL, receipt_sha256 text NOT NULL,
 PRIMARY KEY(tenant_id,intent_id), FOREIGN KEY(tenant_id,intent_id) REFERENCES b3_p0.intents);
CREATE TABLE b3_p0.outbox(
 tenant_id text NOT NULL, intent_id uuid NOT NULL, event_id uuid NOT NULL UNIQUE,
 receipt_sha256 text NOT NULL, internal_only boolean NOT NULL DEFAULT true CHECK(internal_only),
 PRIMARY KEY(tenant_id,intent_id), FOREIGN KEY(tenant_id,intent_id) REFERENCES b3_p0.intents);

ALTER TABLE b3_p0.bootstrap ENABLE ROW LEVEL SECURITY;
ALTER TABLE b3_p0.bootstrap FORCE ROW LEVEL SECURITY;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['authority','witnesses','states','intents','claims','sections','audit','outbox'] LOOP
  EXECUTE format('ALTER TABLE b3_p0.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE b3_p0.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY tenant_scope ON b3_p0.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',t);
 END LOOP;
 FOREACH t IN ARRAY ARRAY['bootstrap','witnesses','intents','claims','sections','audit','outbox'] LOOP
  EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON b3_p0.%I FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable()',t);
 END LOOP;
END $$;
CREATE FUNCTION b3_p0.no_truncate() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='B3_APPEND_ONLY'; END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['bootstrap','authority','witnesses','states','intents','claims','sections','audit','outbox'] LOOP
  EXECUTE format('CREATE TRIGGER no_truncate BEFORE TRUNCATE ON b3_p0.%I FOR EACH STATEMENT EXECUTE FUNCTION b3_p0.no_truncate()',t);
 END LOOP;
END $$;
CREATE FUNCTION b3_p0.no_append() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM b3_p0.outbox WHERE tenant_id=NEW.tenant_id AND intent_id=NEW.intent_id)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='B3_SEALED_INTENT'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sealed_claims BEFORE INSERT ON b3_p0.claims FOR EACH ROW EXECUTE FUNCTION b3_p0.no_append();
CREATE TRIGGER sealed_sections BEFORE INSERT ON b3_p0.sections FOR EACH ROW EXECUTE FUNCTION b3_p0.no_append();

CREATE FUNCTION b3_p0.require_witness(wid uuid,t text,ref text,run text,report text,ver integer,digest text)
RETURNS b3_p0.witnesses LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE w b3_p0.witnesses; a b3_p0.authority;
BEGIN
 -- Lock order: accepted assignment/source parent, then B3 authority/witness/state.
 PERFORM 1 FROM ra4a_review_test.load_target(t,ref,run,report,ver,digest);
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=SESSION_USER AND
  (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='B3_PRIVILEGED_RUNTIME_DENIED'; END IF;
 SELECT * INTO a FROM b3_p0.authority WHERE tenant_id=t FOR SHARE;
 IF NOT FOUND OR NOT a.anchor_active OR a.anchor_expires<=clock_timestamp() THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='B3_ANCHOR_DENIED'; END IF;
 SELECT * INTO w FROM b3_p0.witnesses WHERE tenant_id=t AND witness_id=wid FOR SHARE;
 IF NOT FOUND OR w.db_actor<>SESSION_USER OR w.epoch<>a.epoch OR w.expires<=clock_timestamp()
 OR a.anchor_expires<=clock_timestamp()
 OR (w.ref_id,w.source_run_id,w.report_id,w.report_version,w.target_digest)
 IS DISTINCT FROM (ref,run,report,ver,digest) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='B3_WITNESS_DENIED'; END IF;
 -- Recheck policy time after any authority/witness lock wait as well.
 PERFORM 1 FROM ra4a_review_test.load_target(t,ref,run,report,ver,digest);
 RETURN w;
END $$;

CREATE FUNCTION b3_p0.submit_test(wid uuid,t text,ref text,run text,report text,ver integer,digest text,raw_command bytea)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE w b3_p0.witnesses; target jsonb; c jsonb; old b3_p0.intents; status_value text;
 pid uuid:=gen_random_uuid(); eid uuid:=gen_random_uuid(); result bytea; ch text; mh text; current_seq integer;
BEGIN
 w:=b3_p0.require_witness(wid,t,ref,run,report,ver,digest);
 target:=ra4a_review_test.check_bytes(t,ref,run,report,ver,digest);
 IF raw_command IS NULL OR octet_length(raw_command)>131072 THEN
  RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='B3_COMMAND_BOUND'; END IF;
 c:=convert_from(raw_command,'UTF8')::jsonb;
 IF ra4a_bytes.canonical_bytes(c) IS DISTINCT FROM raw_command THEN
  RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='B3_NONCANONICAL_COMMAND'; END IF;
 PERFORM ra4a_review_test.validate_command(c,target,digest);
 ch:=encode(sha256(decode('767261652e726133642e636f6d6d616e642e6f66666c696e652d76310a','hex')||raw_command),'hex');
 SELECT * INTO old FROM b3_p0.intents WHERE tenant_id=t AND report_id=report AND idempotency_key=c->>'idempotency_key';
 IF FOUND THEN
  IF (old.db_actor,old.subject,old.ref_id,old.source_run_id,old.report_version,old.target_digest,old.canonical_command)
   IS DISTINCT FROM (SESSION_USER,w.subject,ref,run,ver,digest,raw_command) THEN
   RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='B3_IDEMPOTENCY_CONFLICT'; END IF;
  RETURN old.receipt;
 END IF;
 INSERT INTO b3_p0.states VALUES(t,report,ver,0) ON CONFLICT DO NOTHING;
 SELECT seq INTO current_seq FROM b3_p0.states WHERE tenant_id=t AND report_id=report AND report_version=ver FOR UPDATE;
 IF current_seq<>(c->>'expected_review_seq')::integer OR current_seq<>0 THEN
  RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='B3_STALE_CAS'; END IF;
 UPDATE b3_p0.states SET seq=seq+1 WHERE tenant_id=t AND report_id=report AND report_version=ver AND seq=current_seq;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='B3_CAS_LOST'; END IF;
 SELECT encode(sha256(manifest),'hex') INTO mh FROM ra4a_bytes.graphs WHERE tenant_id=t AND ref_id=ref;
 status_value:=CASE WHEN target->>'kind'='COVERAGE_ONLY' THEN 'COVERAGE_ACK_TEST_ONLY' ELSE 'REVIEW_INTENT_TEST_ONLY' END;
 result:=ra4a_bytes.canonical_bytes(jsonb_build_object(
  'contract_version','b3-p0-v1','authority','TEST_ONLY_REVIEW_INTENT','intent_id',pid,'event_id',eid,
  'tenant_id',t,'report_id',report,'report_version',ver,'ref_id',ref,'source_run_id',run,'target_digest',digest,
  'source_sha256',target->>'source_record_sha256','html_sha256',target->>'html_sha256','manifest_sha256',mh,
  'db_actor',SESSION_USER,'subject',w.subject,'command_digest',ch,'idempotency_key',c->>'idempotency_key',
  'status',status_value,'review_seq',1,'durable',true,'effective_approval',false,'external_visibility',false,
  'native_decision',NULL,'person_id',NULL,'share_grant',NULL));
 INSERT INTO b3_p0.intents(tenant_id,intent_id,witness_id,db_actor,subject,ref_id,source_run_id,report_id,report_version,
 target_digest,source_sha256,html_sha256,manifest_sha256,canonical_command,command_digest,idempotency_key,status,receipt)
 VALUES(t,pid,wid,SESSION_USER,w.subject,ref,run,report,ver,digest,target->>'source_record_sha256',target->>'html_sha256',mh,
 raw_command,ch,c->>'idempotency_key',status_value,result);
 INSERT INTO b3_p0.claims SELECT t,pid,n::integer,x FROM jsonb_array_elements(c->'dispositions') WITH ORDINALITY q(x,n);
 INSERT INTO b3_p0.sections SELECT t,pid,n::integer,x FROM jsonb_array_elements(c->'sections') WITH ORDINALITY q(x,n);
 INSERT INTO b3_p0.audit VALUES(t,pid,SESSION_USER,ch,encode(sha256(result),'hex'));
 INSERT INTO b3_p0.outbox VALUES(t,pid,eid,encode(sha256(result),'hex'),true);
 RETURN result;
END $$;

CREATE FUNCTION b3_p0.complete_intent() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE c jsonb; d jsonb; cs jsonb; ss jsonb; n integer;
BEGIN
 PERFORM b3_p0.require_witness(NEW.witness_id,NEW.tenant_id,NEW.ref_id,NEW.source_run_id,NEW.report_id,NEW.report_version,NEW.target_digest);
 d:=ra4a_review_test.check_bytes(NEW.tenant_id,NEW.ref_id,NEW.source_run_id,NEW.report_id,NEW.report_version,NEW.target_digest);
 c:=convert_from(NEW.canonical_command,'UTF8')::jsonb;
 PERFORM ra4a_review_test.validate_command(c,d,NEW.target_digest);
 SELECT jsonb_agg(disposition ORDER BY ordinal) INTO cs FROM b3_p0.claims WHERE tenant_id=NEW.tenant_id AND intent_id=NEW.intent_id;
 SELECT jsonb_agg(acknowledgement ORDER BY ordinal) INTO ss FROM b3_p0.sections WHERE tenant_id=NEW.tenant_id AND intent_id=NEW.intent_id;
 SELECT count(*) INTO n FROM b3_p0.audit a JOIN b3_p0.outbox o USING(tenant_id,intent_id)
 WHERE a.tenant_id=NEW.tenant_id AND a.intent_id=NEW.intent_id AND a.db_actor=NEW.db_actor
 AND a.command_digest=NEW.command_digest AND a.receipt_sha256=NEW.receipt_sha256 AND o.receipt_sha256=NEW.receipt_sha256
 AND o.event_id::text=convert_from(NEW.receipt,'UTF8')::jsonb->>'event_id' AND o.internal_only;
 IF cs IS DISTINCT FROM c->'dispositions' OR ss IS DISTINCT FROM c->'sections' OR n<>1
 OR NOT EXISTS(SELECT 1 FROM b3_p0.states WHERE tenant_id=NEW.tenant_id AND report_id=NEW.report_id
 AND report_version=NEW.report_version AND seq=1) THEN
  RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='B3_INCOMPLETE_TRANSACTION'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER complete_intent AFTER INSERT ON b3_p0.intents
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION b3_p0.complete_intent();

CREATE FUNCTION b3_p0.get_receipt(wid uuid,t text,ref text,run text,report text,ver integer,digest text,key text)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE w b3_p0.witnesses; old b3_p0.intents;
BEGIN
 w:=b3_p0.require_witness(wid,t,ref,run,report,ver,digest);
 SELECT * INTO old FROM b3_p0.intents WHERE tenant_id=t AND report_id=report AND idempotency_key=key;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='P0002',MESSAGE='B3_RECEIPT_UNKNOWN'; END IF;
 IF (old.db_actor,old.subject,old.ref_id,old.source_run_id,old.report_version,old.target_digest)
 IS DISTINCT FROM (SESSION_USER,w.subject,ref,run,ver,digest) THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='B3_RECEIPT_DENIED'; END IF;
 RETURN old.receipt;
END $$;
REVOKE ALL ON SCHEMA b3_p0 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA b3_p0 FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA b3_p0 FROM PUBLIC;
GRANT USAGE ON SCHEMA b3_p0 TO p2b1_review;
GRANT EXECUTE ON FUNCTION b3_p0.submit_test(uuid,text,text,text,text,integer,text,bytea) TO p2b1_review;
GRANT EXECUTE ON FUNCTION b3_p0.get_receipt(uuid,text,text,text,text,integer,text,text) TO p2b1_review;
RESET ROLE;
