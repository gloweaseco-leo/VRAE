-- Owner6894393962 conditional experiment. Private nonrecursive predicate must
-- exist and be reviewed first. No positive trusted seal can be seeded.
BEGIN;
SET ROLE ra4a_owner;
CREATE POLICY s2_assigned_epoch_select ON ra4b_test.origin_epochs
 AS PERMISSIVE FOR SELECT TO ra4a_owner USING (
 CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND SESSION_USER IN ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 AND ra4b_p2.current_generated_binding(tenant_id,NULL::uuid,origin_role,epoch));
CREATE POLICY s2_assigned_request_select ON ra4b_test.request_origins
 AS PERMISSIVE FOR SELECT TO ra4a_owner USING (
 CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND SESSION_USER IN ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 AND ra4b_p2.current_generated_binding(tenant_id,request_id,origin_role,epoch));
CREATE POLICY s2_assigned_epoch_lock ON ra4b_test.origin_epochs
 AS PERMISSIVE FOR UPDATE TO ra4a_owner USING (
 CURRENT_USER='ra4a_owner' AND tenant_id=ra4a.scope()
 AND SESSION_USER IN ('p2b1_test_a_reviewer','p2b1_test_a_peer','p2b1_test_b_reviewer')
 AND ra4b_p2.current_generated_binding(tenant_id,NULL::uuid,origin_role,epoch))
 WITH CHECK(false);
RESET ROLE;
COMMIT;
