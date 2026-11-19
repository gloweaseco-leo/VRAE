"""Submit fresh controlled tasks to the continuously running Worker."""

from copy import deepcopy
from datetime import datetime, UTC
import json
import time
import uuid
from contracts.l2_launch.contract import permission_document
from contracts.l2_launch.vf_b import submission_document
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from integration.authorized_targets.checks import external_client as client
from integration.authorized_targets.checks.issuer import Issuer


def main():
    state = json.loads(client.STATE.read_bytes())
    signer = Issuer("tenant-beta")
    signer.key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(client.CFG["permission_key"]))
    refs = []
    for request, subject in zip(client.CFG["requests"], state["subjects"]):
        s = subject["session"]
        code, frame, _ = client.call("GET", "/v1/source-plans/" + request["target_id"], session=s)
        assert code == 200
        value = deepcopy(subject["submit"])
        uid = uuid.uuid4().hex
        value["command"]["request"].update(
            request_id="service-request-" + uid,
            audit_id="service-audit-" + uid,
            idempotency_key="service-idem-" + uid,
            requested_at=datetime.now(UTC).isoformat(),
        )
        value["command"]["permission_reference"]["proof"] = signer.sign(
            "permission",
            "permission",
            permission_document(value["command"], frame["source_policy"]),
        )
        value["submission_proof"] = signer.sign(
            "permission", "permission", submission_document(value)
        )
        code, accepted, _ = client.call("POST", "/v1/audit-requests", value, s)
        assert code == 202
        assert client.call("POST", "/v1/audit-requests", value, s)[1] == accepted
        refs.append((accepted, s))
    for accepted, s in refs:
        end = time.monotonic() + 50
        while time.monotonic() < end:
            code, status, _ = client.call("GET", "/v1/audits/" + accepted["audit_ref"], session=s)
            assert code == 200
            if status["task"]["status"] == "DRAFT_READY":
                break
            time.sleep(0.5)
        else:
            raise AssertionError("CONTINUOUS_WORKER_DID_NOT_COMMIT")
        assert status["task"]["run_id"] == accepted["run_id"]
    print(
        json.dumps(
            {
                "phase": "continuous_new_tasks",
                "passed": True,
                "new_tasks": [a for a, _ in refs],
                "http": client.events,
                "model_dispatch": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
