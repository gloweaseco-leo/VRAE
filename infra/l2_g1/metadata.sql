GRANT CONNECT ON DATABASE vrae_ra4a_p1 TO g1_http_a;
-- Transport custody in the SAME original PG database. No job state or queue.
CREATE SCHEMA g1_http;
REVOKE ALL ON SCHEMA g1_http FROM PUBLIC;
CREATE TABLE g1_http.settings(key text PRIMARY KEY,value jsonb NOT NULL);
CREATE TABLE g1_http.sourceplans(source_ref text PRIMARY KEY,tenant text NOT NULL,document jsonb NOT NULL);
CREATE TABLE g1_http.invitations(reference text PRIMARY KEY,tenant text NOT NULL,document jsonb NOT NULL);
CREATE TABLE g1_http.admissions(
 tenant text NOT NULL,idem text NOT NULL,intent_hash text NOT NULL,audit_ref text UNIQUE NOT NULL,
 source_ref text NOT NULL,subject_ref text NOT NULL,submission jsonb NOT NULL,native_task jsonb,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(tenant,idem));
CREATE UNIQUE INDEX g1_native_job_once ON g1_http.admissions((native_task->>'job_id')) WHERE native_task IS NOT NULL;
CREATE TABLE g1_http.return_grants(
 tenant text NOT NULL,audit_ref text PRIMARY KEY,document jsonb NOT NULL,proof jsonb NOT NULL,
 used_at timestamptz,revoked boolean NOT NULL DEFAULT false);
CREATE TABLE g1_http.sessions(
 tenant text NOT NULL,hash text PRIMARY KEY,audit_ref text NOT NULL,subject_ref text NOT NULL,
 csrf_hash text NOT NULL,epoch integer NOT NULL,expires_at timestamptz NOT NULL,revoked boolean NOT NULL DEFAULT false);
CREATE TABLE g1_http.preview_permits(
 tenant text NOT NULL,audit_ref text PRIMARY KEY,document jsonb NOT NULL,proof jsonb NOT NULL,revoked boolean NOT NULL DEFAULT false);
CREATE TABLE g1_http.inquiries(
 tenant text NOT NULL,idem text NOT NULL,audit_ref text NOT NULL,intent_hash text NOT NULL,
 command jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant,idem));
CREATE FUNCTION g1_http.immutable_intent() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (OLD.tenant,OLD.idem,OLD.intent_hash,OLD.audit_ref,OLD.source_ref,OLD.subject_ref,OLD.submission,OLD.created_at)
 IS DISTINCT FROM (NEW.tenant,NEW.idem,NEW.intent_hash,NEW.audit_ref,NEW.source_ref,NEW.subject_ref,NEW.submission,NEW.created_at)
 OR (OLD.native_task IS NOT NULL AND OLD.native_task IS DISTINCT FROM NEW.native_task)
 THEN RAISE EXCEPTION 'G1_IMMUTABLE_ADMISSION'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER immutable_intent BEFORE UPDATE ON g1_http.admissions FOR EACH ROW EXECUTE FUNCTION g1_http.immutable_intent();
REVOKE ALL ON FUNCTION g1_http.immutable_intent() FROM PUBLIC;
-- Fixed fixture role; no original raw-table, queue or report grants added.
GRANT USAGE ON SCHEMA g1_http TO g1_http_a;
GRANT SELECT ON g1_http.settings,g1_http.sourceplans,g1_http.invitations TO g1_http_a;
GRANT SELECT,INSERT,UPDATE ON g1_http.admissions,g1_http.return_grants,g1_http.sessions,g1_http.preview_permits,g1_http.inquiries TO g1_http_a;
ALTER TABLE g1_http.sourceplans ENABLE ROW LEVEL SECURITY;
ALTER TABLE g1_http.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE g1_http.admissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE g1_http.return_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE g1_http.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE g1_http.preview_permits ENABLE ROW LEVEL SECURITY;
ALTER TABLE g1_http.inquiries ENABLE ROW LEVEL SECURITY;
CREATE POLICY fixed_tenant ON g1_http.sourceplans TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');
CREATE POLICY fixed_tenant ON g1_http.invitations TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');
CREATE POLICY fixed_tenant ON g1_http.admissions TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');
CREATE POLICY fixed_tenant ON g1_http.return_grants TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');
CREATE POLICY fixed_tenant ON g1_http.sessions TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');
CREATE POLICY fixed_tenant ON g1_http.preview_permits TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');
CREATE POLICY fixed_tenant ON g1_http.inquiries TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');

CREATE TABLE g1_http.challenges(tenant text NOT NULL,hash text PRIMARY KEY,csrf_hash text NOT NULL,expires_at timestamptz NOT NULL,used boolean NOT NULL DEFAULT false);
GRANT SELECT,INSERT,UPDATE ON g1_http.challenges TO g1_http_a;
ALTER TABLE g1_http.challenges ENABLE ROW LEVEL SECURITY;
CREATE POLICY fixed_tenant ON g1_http.challenges TO g1_http_a USING(tenant='tenant-test') WITH CHECK(tenant='tenant-test');

CREATE UNIQUE INDEX unique_client_request ON g1_http.admissions(tenant,(submission->'command'->'request'->>'request_id'));
CREATE UNIQUE INDEX unique_client_audit ON g1_http.admissions(tenant,(submission->'command'->'request'->>'audit_id'));
