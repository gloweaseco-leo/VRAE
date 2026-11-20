-- Trusted BFF creates fresh isolated principals without a shared invitation.
BEGIN;
CREATE ROLE target_v1_session_issuer NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA target_v1 TO target_v1_session_issuer;
SET ROLE ra4a_owner;
CREATE INDEX automatic_session_expiry ON target_v1.sessions(tenant_id,expires_at)
 WHERE invitation_ref LIKE 'auto-session-%';
CREATE FUNCTION target_v1.automatic_session(t text,cookie text,csrf text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,target_v1,pg_temp AS $$
DECLARE a target_v1.actors%ROWTYPE;ref text;subject text;expiry timestamptz;inv_end timestamptz;
BEGIN
 PERFORM ra4a.require_scope(t,'APP');
 -- Original per-tenant capacity lock serializes issuance without upgrading
 -- actor SHARE locks held by require_scope (including concurrent callers).
 PERFORM 1 FROM target_v1.capacity WHERE tenant_id=t FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='AUTOMATIC_SESSION_DENIED'; END IF;
 SELECT * INTO a FROM target_v1.actors WHERE db_role=SESSION_USER AND tenant_id=t
 AND kind='APP' AND active AND expires_at>clock_timestamp() FOR SHARE;
 IF NOT FOUND OR cookie !~ '^[0-9a-f]{64}$' OR csrf !~ '^[0-9a-f]{64}$'
 OR cookie=csrf OR cookie IS NULL OR csrf IS NULL THEN
  RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='AUTOMATIC_SESSION_DENIED';
 END IF;
 IF (SELECT count(*) FROM target_v1.sessions WHERE tenant_id=t
     AND invitation_ref LIKE 'auto-session-%' AND NOT revoked AND expires_at>clock_timestamp())>=1000 THEN
  RAISE EXCEPTION USING ERRCODE='53000',MESSAGE='AUTOMATIC_SESSION_CAPACITY';
 END IF;
 ref='auto-session-'||gen_random_uuid()::text;
 subject='automatic-'||gen_random_uuid()::text;
 inv_end=least(a.expires_at,clock_timestamp()+interval '24 hours');
 expiry=least(inv_end,clock_timestamp()+interval '30 minutes');
 -- Internal compatibility context for original same-subject ports. No token
 -- is handed out; used=true makes the legacy one-use exchange refuse replay.
 INSERT INTO target_v1.invitations VALUES(t,ref,subject,
  encode(sha256(gen_random_uuid()::text::bytea),'hex'),
  jsonb_build_object('tenant_id',t,'reference',ref,'subject_ref',subject,'target_ids','[]'::jsonb,
   'expires_at',inv_end,'revoked',false,'session_origin_role',SESSION_USER,'session_origin_epoch',a.epoch),true,false);
 INSERT INTO target_v1.sessions VALUES(t,cookie,csrf,subject,ref,expiry,false);
 RETURN jsonb_build_object('expires_at',expiry);
END $$;
REVOKE ALL ON FUNCTION target_v1.automatic_session(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION target_v1.automatic_session(text,text,text) TO target_v1_session_issuer;
RESET ROLE;
COMMIT;
