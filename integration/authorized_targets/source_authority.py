"""Root-provisioned signatures, exact target scope and separately signed deployment GO.

No trust key, legal allowance or deployment GO is accepted from HTTP/model input.
The shipped lab registry contains only CONTROLLED_NON_CUSTOMER keys.
"""

from datetime import datetime, UTC
import hashlib
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from contracts.l2_launch.contract import canonical, digest
from vrae.collection.limits import Limits
from vrae.collection.policy import canonical_url
from vrae.collection.resolver import public_addresses

TRUST = Path("/run/vrae-targets/trust.json")
DEPLOYMENT = Path("/run/vrae-targets/deployment.json")


class AuthorityDenied(PermissionError):
    def __init__(self):
        super().__init__("LIVE_CAPTURE_DISABLED")


def root_document(path):
    if os.name != "posix":
        raise AuthorityDenied()
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022 or s.st_size > 131072:
            raise AuthorityDenied()
        raw = os.read(fd, 131073)
    finally:
        os.close(fd)
    return json.loads(raw)


def verify(envelope, role, source_class, now=None):
    now = now or datetime.now(UTC)
    try:
        if set(envelope) != {"key_id", "document", "signature"}:
            raise AuthorityDenied()
        registry = root_document(TRUST)
        key = registry["keys"][envelope["key_id"]]
        if key["role"] != role or key["source_class"] != source_class or key["revoked"]:
            raise AuthorityDenied()
        d = envelope["document"]
        if d["source_class"] != source_class or not datetime.fromisoformat(
            d["not_before"]
        ) <= now < datetime.fromisoformat(d["expires_at"]):
            raise AuthorityDenied()
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key["public"])).verify(
            bytes.fromhex(envelope["signature"]), canonical(d)
        )
        return d
    except (KeyError, ValueError, TypeError, OSError, InvalidSignature):
        raise AuthorityDenied() from None


def authorization(envelope, plan, *, plan_sha256, now=None):
    try:
        d = verify(envelope, "SOURCE_ADMIN", plan["source_class"], now)
        required = {
            "contract",
            "reference",
            "tenant_id",
            "target_id",
            "source_class",
            "origin",
            "exact_paths",
            "plan_sha256",
            "purpose",
            "methods",
            "legal_reference",
            "terms_reference",
            "robots",
            "not_before",
            "expires_at",
            "retention_until",
            "destination_ips",
            "limits",
        }
        if set(d) != required or d["contract"] != "vrae.target-authorization.v2":
            raise AuthorityDenied()
        if any(
            d[k] != plan[k] for k in ("tenant_id", "target_id", "origin", "exact_paths", "limits")
        ):
            raise AuthorityDenied()
        if (
            d["plan_sha256"] != plan_sha256
            or d["reference"] != plan["policy"]["authorization_reference"]
            or d["purpose"] != "READONLY_DIAGNOSIS"
            or d["methods"] != ["GET", "HEAD"]
            or d["robots"] != "ENFORCE"
            or not d["legal_reference"]
            or d["terms_reference"] != plan["terms_reference"]
            or datetime.fromisoformat(d["expires_at"]) > datetime.fromisoformat(plan["expires_at"])
            or datetime.fromisoformat(d["retention_until"])
            < datetime.fromisoformat(d["expires_at"])
        ):
            raise AuthorityDenied()
        if canonical_url(d["origin"] + "/") != d["origin"] + "/" or not d["origin"].startswith(
            "https://"
        ):
            raise AuthorityDenied()
        if "/robots.txt" not in d["exact_paths"] or len(set(d["exact_paths"])) != len(
            d["exact_paths"]
        ):
            raise AuthorityDenied()
        for path in d["exact_paths"]:
            if urlsplit(canonical_url(d["origin"] + path)).path != path:
                raise AuthorityDenied()
        public_addresses(d["destination_ips"])
        Limits(**d["limits"])
        return d
    except (KeyError, ValueError, TypeError):
        raise AuthorityDenied() from None


def deployment(envelope, grant, plan, now=None):
    d = verify(envelope, "DEPLOYMENT_OWNER", plan["source_class"], now)
    try:
        if (
            d["contract"] != "vrae.bounded-egress-deployment.v2"
            or d["purpose"] != "READONLY_DIAGNOSIS"
            or digest(grant) not in d["authorization_hashes"]
            or d["deployment_go"] != "GRANTED"
            or d["source_network_fee_go"] != "GRANTED"
            or d["model_fee_go"] != "NOT_GRANTED"
            or d["namespace_inode"] != os.stat("/proc/self/ns/net").st_ino
            or sorted(os.listdir("/sys/class/net")) != sorted(d["interfaces"])
            or d["parent_network_mode"] not in ("none", "isolated-egress")
            or hashlib.sha256(Path(d["cafile"]).read_bytes()).hexdigest() != d["ca_sha256"]
        ):
            raise AuthorityDenied()
        policy = d["firewall_policy"]
        if (
            digest(policy) != d["firewall_policy_sha256"]
            or policy["namespace_inode"] != d["namespace_inode"]
            or policy["worker_uid"] != 65532
            or policy["default"] != "REJECT"
        ):
            raise AuthorityDenied()
        expected = [{"ip": "127.0.0.1", "protocol": "tcp", "port": 5432}]
        grants = d["permitted_destination_ips"]
        expected += [{"ip": ip, "protocol": "tcp", "port": 443} for ip in sorted(set(grants))]
        expected += [
            {"ip": ip, "protocol": proto, "port": 53}
            for ip in sorted(set(d["nameservers"]))
            for proto in ("udp", "tcp")
        ]
        if policy["rules"] != expected or not set(grant["document"]["destination_ips"]) <= set(
            grants
        ):
            raise AuthorityDenied()
        public_addresses(d["nameservers"])
        status = Path("/proc/self/status").read_text()
        if (
            os.geteuid() != 65532
            or "CapEff:\t0000000000000000" not in status
            or "NoNewPrivs:\t1" not in status
        ):
            raise AuthorityDenied()
        if Path("/var/run/docker.sock").exists():
            raise AuthorityDenied()
        # Test authority cannot be used on a routable/customer namespace.
        if plan["source_class"] == "CONTROLLED_NON_CUSTOMER" and (
            d["parent_network_mode"] != "none" or d["interfaces"] != ["lo"]
        ):
            raise AuthorityDenied()
        return d
    except (KeyError, ValueError, TypeError, OSError, InvalidSignature):
        raise AuthorityDenied() from None
