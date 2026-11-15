"""Actual integration tests; no mocked business state or substituted protected oracle."""
import os
import pytest
from .runner import Run

@pytest.fixture(scope="module")
def beta():
    run=Run(os.environ["BETA_CODEX3_RUN"],os.environ["BETA_CODEX3_MINOR"])
    try:
        yield run
    finally:
        try:
            run.case("owned_cleanup",run.cleanup)
        finally:
            if all(c["result"]=="PASS" for c in run.cases) and len(run.cases)==7:
                run.result["status"]="COMPONENTS_VERIFIED_CHAIN_BLOCKED"
            else:
                run.result["status"]="STOP_NATIVE_RED_PRESERVED"
            run.publish()

def test_live_offline_source_policy_six_rules_guard_report(beta):
    beta.case("live_offline_source_policy_six_rules_guard_report",beta.pipeline)

def test_owned_pg16_accepted_migrations_loopback(beta):
    beta.case("owned_pg16_accepted_migrations_loopback_network",beta.start_pg)

def test_http202_durable_commit_and_low_uid_worker_security(beta):
    beta.case("real_http202_commit_low_uid_worker_done_security",beta.start_native)

def test_original_ssr_restricted_reviewer_profile(beta):
    beta.case("original_reviewer_ssr_start",beta.start_ssr)

def test_signed_pg_original_version_tenant_share_boundaries(beta):
    beta.case("signed_original_reads_version_tenant_share_denial",beta.signed_reads)

def test_real_chromium_1280_375_320(beta):
    beta.case("chromium_desktop_mobile_readonly",beta.browser)
