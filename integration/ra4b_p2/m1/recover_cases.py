"""Second fresh client after actual PostgreSQL restart; never migrate or seed."""

import json
from pathlib import Path

import pytest

from integration.ra4a import support
from integration.ra4b_p2.m1.native_cases import reader
from vrae.identity.boundary import IdentityDenied


@pytest.fixture(scope="module")
def recovered():
    folder = Path("/tmp/m1-recovered")
    folder.mkdir(mode=0o700)
    support.STATE = folder / "state.json"
    support.STATE.write_bytes(Path("/run/m1-state.json").read_bytes())
    support.STATE.chmod(0o600)
    proof = json.loads(Path("/run/m1-before.json").read_bytes())
    m1 = {"runtime": {"held": {}}, "results": proof["results"]}
    yield m1
    state = json.loads(support.STATE.read_bytes())
    Path("/evidence/private-credential-scan-values.json").write_text(
        json.dumps(
            [
                state["admin_password"],
                *state["runtime_passwords"].values(),
                *m1["runtime"]["held"].get("extra_secret_values", []),
            ]
        )
    )


def test_actual_pg_restart_preserves_current_signed_report_bytes(recovered):
    request = recovered["results"]["restart"]
    port, token, nonce = reader(recovered, request)
    report = port.read(token, "tenant-test", request["job_id"], nonce=nonce)
    assert report.locator == request
    assert report.editorial_selection["full_fact_count"] == 17


def test_pg_restart_does_not_resurrect_old_epoch_report(recovered):
    request = recovered["results"]["200"]
    port, token, nonce = reader(recovered, request)
    with pytest.raises(IdentityDenied):
        port.read(token, "tenant-test", request["job_id"], nonce=nonce)
