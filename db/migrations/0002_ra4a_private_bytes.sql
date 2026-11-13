-- P2A synthetic-only, additive to immutable P1. No authenticated human/store API.
CREATE ROLE p2a_fixture_writer NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE p2a_test_a_writer NOLOGIN IN ROLE p2a_fixture_writer;
CREATE ROLE p2a_test_b_writer NOLOGIN IN ROLE p2a_fixture_writer;
GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO p2a_fixture_writer;
CREATE SCHEMA ra4a_bytes AUTHORIZATION ra4a_owner;
SET ROLE ra4a_owner;
CREATE TABLE ra4a_bytes.graphs(
 tenant_id text NOT NULL, source_run_id text NOT NULL, report_id text NOT NULL,
 report_version integer NOT NULL CHECK(report_version>0), ref_id text NOT NULL,
 target_payload bytea NOT NULL CHECK(octet_length(target_payload) BETWEEN 1 AND 65536),
 target_sha256 text GENERATED ALWAYS AS (encode(sha256(target_payload),'hex')) STORED,
 target_digest text GENERATED ALWAYS AS
  (encode(sha256(decode('767261652e726133642e7461726765742e6f66666c696e652d76310a','hex') || target_payload),'hex')) STORED,
 manifest bytea NOT NULL CHECK(octet_length(manifest) BETWEEN 1 AND 8000000),
 manifest_sha256 text GENERATED ALWAYS AS (encode(sha256(manifest),'hex')) STORED,
 visibility text NOT NULL DEFAULT 'PRIVATE_NOT_APPROVED' CHECK(visibility='PRIVATE_NOT_APPROVED'),
 PRIMARY KEY(tenant_id,source_run_id,report_id,report_version), UNIQUE(tenant_id,ref_id),
 FOREIGN KEY(tenant_id,ref_id) REFERENCES ra4a.references(tenant_id,ref_id));
CREATE TABLE ra4a_bytes.objects(
 tenant_id text NOT NULL, source_run_id text NOT NULL, report_id text NOT NULL, report_version integer NOT NULL,
 kind text NOT NULL CHECK(kind IN ('DRAFT','HTML','SOURCE','PACK','PACKAGE','GUARD','METADATA','CSS','TARGET','SOURCE_OBJECT')),
 object_key text NOT NULL CHECK(length(object_key) BETWEEN 1 AND 128),
 raw bytea NOT NULL CHECK(octet_length(raw)<=8000000 AND (kind<>'TARGET' OR octet_length(raw)<=65536)),
 content_sha256 text GENERATED ALWAYS AS (encode(sha256(raw),'hex')) STORED,
 length_bytes integer GENERATED ALWAYS AS (octet_length(raw)) STORED,
 PRIMARY KEY(tenant_id,source_run_id,report_id,report_version,kind,object_key),
 FOREIGN KEY(tenant_id,source_run_id,report_id,report_version)
 REFERENCES ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version));
CREATE TABLE ra4a_bytes.events(
 tenant_id text NOT NULL, source_run_id text NOT NULL, report_id text NOT NULL, report_version integer NOT NULL,
 action text NOT NULL DEFAULT 'TEST_ONLY_REGISTERED' CHECK(action='TEST_ONLY_REGISTERED'),
 db_principal name NOT NULL DEFAULT SESSION_USER,
 PRIMARY KEY(tenant_id,source_run_id,report_id,report_version),
 FOREIGN KEY(tenant_id,source_run_id,report_id,report_version)
 REFERENCES ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version));

DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['graphs','objects','events'] LOOP
  EXECUTE format('ALTER TABLE ra4a_bytes.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE ra4a_bytes.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY private_tenant ON ra4a_bytes.%I USING(tenant_id=ra4a.scope()) WITH CHECK(tenant_id=ra4a.scope())',t);
  EXECUTE format('CREATE TRIGGER immutable_bytes BEFORE UPDATE OR DELETE ON ra4a_bytes.%I FOR EACH ROW EXECUTE FUNCTION ra4a_private.immutable()',t);
 END LOOP;
END $$;
-- Empty-schema lifecycle reset is allowed; existing bytes cannot be truncated by
-- ordinary fixture-admin SQL. A cluster superuser disabling triggers is outside
-- write-once authorization; independently held read provenance still detects it.
CREATE FUNCTION ra4a_bytes.no_truncate() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a_bytes,pg_temp AS $$
DECLARE present boolean;
BEGIN
 EXECUTE format('SELECT EXISTS(SELECT 1 FROM ra4a_bytes.%I)',TG_TABLE_NAME) INTO present;
 IF present THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='P2A_IMMUTABLE_BYTES'; END IF;
 RETURN NULL;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['graphs','objects','events'] LOOP
  EXECUTE format('CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON ra4a_bytes.%I FOR EACH STATEMENT EXECUTE FUNCTION ra4a_bytes.no_truncate()',t);
 END LOOP;
END $$;

CREATE FUNCTION ra4a_bytes.no_append_after_seal() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a_bytes,pg_temp AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM ra4a_bytes.events e WHERE
  (e.tenant_id,e.source_run_id,e.report_id,e.report_version)=
  (NEW.tenant_id,NEW.source_run_id,NEW.report_id,NEW.report_version))
 THEN RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='P2A_SEALED_GRAPH'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER no_append_after_seal BEFORE INSERT ON ra4a_bytes.objects
 FOR EACH ROW EXECUTE FUNCTION ra4a_bytes.no_append_after_seal();

CREATE FUNCTION ra4a_bytes.check_binding() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a,pg_temp AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM ra4a.references r WHERE r.tenant_id=NEW.tenant_id AND r.ref_id=NEW.ref_id
   AND r.source_run_id=NEW.source_run_id AND r.report_id=NEW.report_id AND r.report_version=NEW.report_version
   AND r.metadata=convert_from(NEW.target_payload,'UTF8')::jsonb
   AND r.ref_sha256=encode(sha256(NEW.target_payload),'hex')
   AND r.target_digest=encode(sha256(convert_to('vrae.ra3d.target.offline-v1'||chr(10),'UTF8')||NEW.target_payload),'hex'))
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_TARGET_BINDING'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER target_binding BEFORE INSERT ON ra4a_bytes.graphs
 FOR EACH ROW EXECUTE FUNCTION ra4a_bytes.check_binding();

-- Exact native integer/string JSON encoding for expanded source components.
CREATE FUNCTION ra4a_bytes.canonical_bytes(v jsonb) RETURNS bytea LANGUAGE plpgsql STABLE
SET search_path=pg_catalog,ra4a_bytes,pg_temp AS $$
DECLARE result text;
BEGIN
 CASE jsonb_typeof(v)
 WHEN 'object' THEN
  SELECT '{'||coalesce(string_agg(to_jsonb(key)::text||':'||convert_from(ra4a_bytes.canonical_bytes(value),'UTF8'),',' ORDER BY key COLLATE "C"),'')||'}'
  INTO result FROM jsonb_each(v);
 WHEN 'array' THEN
  SELECT '['||coalesce(string_agg(convert_from(ra4a_bytes.canonical_bytes(value),'UTF8'),',' ORDER BY ordinal),'')||']'
  INTO result FROM jsonb_array_elements(v) WITH ORDINALITY AS x(value,ordinal);
 ELSE result:=v::text;
 END CASE;
 RETURN convert_to(result,'UTF8');
END $$;
CREATE FUNCTION ra4a_bytes.complete_graph() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ra4a_bytes,pg_temp AS $$
DECLARE g ra4a_bytes.graphs%ROWTYPE; actual jsonb; s jsonb; d jsonb; x record; n integer; total bigint;
BEGIN
 SELECT * INTO STRICT g FROM ra4a_bytes.graphs WHERE tenant_id=NEW.tenant_id AND source_run_id=NEW.source_run_id
  AND report_id=NEW.report_id AND report_version=NEW.report_version;
 IF NOT EXISTS(SELECT 1 FROM ra4a_bytes.events e WHERE
  (e.tenant_id,e.source_run_id,e.report_id,e.report_version)=(g.tenant_id,g.source_run_id,g.report_id,g.report_version))
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_UNSEALED_GRAPH'; END IF;
 SELECT jsonb_agg(jsonb_build_object('key',object_key,'kind',kind,'sha256',content_sha256,'length',length_bytes)
   ORDER BY kind,object_key),count(*),sum(length_bytes) INTO actual,n,total
 FROM ra4a_bytes.objects WHERE tenant_id=g.tenant_id AND source_run_id=g.source_run_id
 AND report_id=g.report_id AND report_version=g.report_version;
 IF g.manifest IS DISTINCT FROM ra4a_bytes.canonical_bytes(actual) OR n NOT BETWEEN 9 AND 137 OR total>64000000
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_INCOMPLETE_MANIFEST'; END IF;
 SELECT convert_from(raw,'UTF8')::jsonb INTO s FROM ra4a_bytes.objects
 WHERE tenant_id=g.tenant_id AND source_run_id=g.source_run_id AND report_id=g.report_id
 AND report_version=g.report_version AND kind='SOURCE' AND object_key='source';
 d:=convert_from(g.target_payload,'UTF8')::jsonb;
 IF s IS NULL OR (SELECT count(*) FROM jsonb_object_keys(s->'objects_base64'))<>n-9
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_SOURCE_SET'; END IF;
 FOR x IN SELECT * FROM ra4a_bytes.objects WHERE tenant_id=g.tenant_id AND source_run_id=g.source_run_id
  AND report_id=g.report_id AND report_version=g.report_version LOOP
  IF x.kind='SOURCE_OBJECT' THEN
   IF NOT (s->'objects_base64' ? x.object_key) OR x.raw IS DISTINCT FROM decode(s->'objects_base64'->>x.object_key,'base64')
   THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_SOURCE_OBJECT'; END IF;
  ELSIF (x.kind,x.object_key) NOT IN (('DRAFT','draft'),('HTML','html'),('SOURCE','source'),('PACK','pack'),
   ('PACKAGE','package'),('GUARD','guard'),('METADATA','metadata'),('CSS','css'),('TARGET','target')) THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_ARTIFACT_SET';
  ELSIF x.kind IN ('DRAFT','HTML','SOURCE','CSS') THEN
   IF x.content_sha256 IS DISTINCT FROM d->>(CASE x.kind WHEN 'DRAFT' THEN 'draft_payload_sha256'
    WHEN 'HTML' THEN 'html_sha256' WHEN 'SOURCE' THEN 'source_record_sha256' ELSE 'renderer_asset_sha256' END)
   THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_CONTENT_BINDING'; END IF;
  ELSIF x.kind='TARGET' THEN
   IF x.raw<>g.target_payload THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_TARGET_BINDING'; END IF;
  ELSIF x.raw IS DISTINCT FROM ra4a_bytes.canonical_bytes(s->(CASE x.kind WHEN 'PACK' THEN 'pack'
    WHEN 'PACKAGE' THEN 'package' WHEN 'GUARD' THEN 'guard_inputs' ELSE 'metadata' END)) THEN
   RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_SOURCE_COMPONENT';
  END IF;
 END LOOP;
 -- Count alone cannot replace the exact fixed typed artifact set.
 IF (SELECT count(DISTINCT kind) FROM ra4a_bytes.objects WHERE tenant_id=g.tenant_id AND source_run_id=g.source_run_id
  AND report_id=g.report_id AND report_version=g.report_version AND kind<>'SOURCE_OBJECT')<>9
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_ARTIFACT_SET'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER complete_bytes AFTER INSERT ON ra4a_bytes.graphs
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ra4a_bytes.complete_graph();

CREATE FUNCTION ra4a_bytes.current_reference(t text, ref text) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog,ra4a,pg_temp AS $$
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 -- Serialize policy/reference publication and reads/registrations, including revoke.
 PERFORM 1 FROM ra4a.tenants WHERE tenant_id=t FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM ra4a.references r JOIN ra4a.policies p
   ON (p.tenant_id,p.policy_id,p.version)=(r.tenant_id,r.policy_id,r.policy_version)
   WHERE r.tenant_id=t AND r.ref_id=ref AND p.status='ALLOWED' AND p.expires_at>clock_timestamp()
   AND NOT EXISTS(SELECT 1 FROM ra4a.references n WHERE n.tenant_id=t AND n.report_id=r.report_id AND n.report_version>r.report_version)
   AND NOT EXISTS(SELECT 1 FROM ra4a.policies n WHERE n.tenant_id=t AND n.policy_id=p.policy_id AND n.version>p.version))
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='P2A_CURRENT_SCOPE_DENIED'; END IF;
END $$;

CREATE FUNCTION ra4a_bytes.register(t text, ref text, target bytea, manifest_raw bytea,
 kinds text[], keys text[], payloads bytea[]) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a_bytes,ra4a,pg_temp AS $$
DECLARE r ra4a.references%ROWTYPE; g ra4a_bytes.graphs%ROWTYPE; i integer; n integer; total bigint:=0;
BEGIN
 IF NOT pg_has_role(SESSION_USER,'p2a_fixture_writer','MEMBER')
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='P2A_FIXTURE_WRITER_ONLY'; END IF;
 PERFORM ra4a_bytes.current_reference(t,ref);
 n:=cardinality(payloads);
 IF n IS NULL OR n NOT BETWEEN 9 AND 137 OR cardinality(kinds)<>n OR cardinality(keys)<>n
 OR array_lower(payloads,1)<>1 OR array_lower(kinds,1)<>1 OR array_lower(keys,1)<>1
 OR octet_length(target) NOT BETWEEN 1 AND 65536 OR octet_length(manifest_raw) NOT BETWEEN 1 AND 8000000
 OR target IS NULL OR manifest_raw IS NULL
 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_BOUNDS'; END IF;
 FOR i IN 1..n LOOP
  IF payloads[i] IS NULL OR octet_length(payloads[i])>8000000 OR kinds[i] IS NULL OR keys[i] IS NULL
   OR (kinds[i]='TARGET' AND octet_length(payloads[i])>65536)
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_BOUNDS'; END IF;
  total:=total+octet_length(payloads[i]);
 END LOOP;
 IF total>64000000 THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_BOUNDS'; END IF;
 SELECT * INTO STRICT r FROM ra4a.references WHERE tenant_id=t AND ref_id=ref;
 SELECT * INTO g FROM ra4a_bytes.graphs WHERE tenant_id=t AND ref_id=ref;
 IF FOUND THEN
  IF g.target_payload IS DISTINCT FROM target OR g.manifest IS DISTINCT FROM manifest_raw
   OR n<>(SELECT count(*) FROM ra4a_bytes.objects o WHERE o.tenant_id=t AND o.report_id=g.report_id
     AND o.source_run_id=g.source_run_id AND o.report_version=g.report_version)
  THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_IMMUTABLE_CONFLICT'; END IF;
  FOR i IN 1..n LOOP
   IF NOT EXISTS(SELECT 1 FROM ra4a_bytes.objects o WHERE o.tenant_id=t AND o.source_run_id=g.source_run_id
     AND o.report_id=g.report_id AND o.report_version=g.report_version AND o.kind=kinds[i]
     AND o.object_key=keys[i] AND o.raw=payloads[i])
   THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='P2A_IMMUTABLE_CONFLICT'; END IF;
  END LOOP;
  RETURN g.target_digest;
 END IF;
 INSERT INTO ra4a_bytes.graphs(tenant_id,source_run_id,report_id,report_version,ref_id,target_payload,manifest)
 VALUES(t,r.source_run_id,r.report_id,r.report_version,ref,target,manifest_raw);
 FOR i IN 1..n LOOP
  INSERT INTO ra4a_bytes.objects(tenant_id,source_run_id,report_id,report_version,kind,object_key,raw)
  VALUES(t,r.source_run_id,r.report_id,r.report_version,kinds[i],keys[i],payloads[i]);
 END LOOP;
 INSERT INTO ra4a_bytes.events(tenant_id,source_run_id,report_id,report_version)
 VALUES(t,r.source_run_id,r.report_id,r.report_version);
 -- Deferred graph constraint validates actual stored bytes at commit, atomically.
 RETURN r.target_digest;
END $$;

CREATE FUNCTION ra4a_bytes.read_graph(t text, ref text, run text, report text, ver integer, digest text)
RETURNS TABLE(target bytea,manifest_raw bytea,kind text,object_key text,raw bytea,content_sha256 text,length_bytes integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,ra4a_bytes,pg_temp AS $$
BEGIN
 PERFORM ra4a_bytes.current_reference(t,ref);
 IF NOT EXISTS(SELECT 1 FROM ra4a_bytes.graphs g WHERE g.tenant_id=t AND g.ref_id=ref AND g.source_run_id=run
  AND g.report_id=report AND g.report_version=ver AND g.target_digest=digest)
 THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='P2A_EXACT_LOCATOR_DENIED'; END IF;
 RETURN QUERY SELECT g.target_payload,g.manifest,o.kind,o.object_key,o.raw,o.content_sha256,o.length_bytes
 FROM ra4a_bytes.graphs g JOIN ra4a_bytes.objects o USING(tenant_id,source_run_id,report_id,report_version)
 WHERE g.tenant_id=t AND g.ref_id=ref AND g.source_run_id=run AND g.report_id=report AND g.report_version=ver
 ORDER BY o.kind,o.object_key;
END $$;

REVOKE ALL ON SCHEMA ra4a_bytes FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA ra4a_bytes FROM PUBLIC,ra4a_app,ra4a_worker,p2a_fixture_writer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ra4a_bytes FROM PUBLIC,ra4a_app,ra4a_worker,p2a_fixture_writer;
GRANT USAGE ON SCHEMA ra4a_bytes TO ra4a_app,p2a_fixture_writer;
GRANT EXECUTE ON FUNCTION ra4a_bytes.register(text,text,bytea,bytea,text[],text[],bytea[]) TO p2a_fixture_writer;
GRANT EXECUTE ON FUNCTION ra4a_bytes.read_graph(text,text,text,text,integer,text) TO ra4a_app;
RESET ROLE;
