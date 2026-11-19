"""Root-signed verified identity configuration + held original PG recipient scope."""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, UTC
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from contracts.l2_launch.contract import canonical, digest
from integration.authorized_targets.source_authority import root_document, authorization
from integration.authorized_targets.store import connect
from integration.authorized_targets.review import committed_source
from vrae.l2.ledger import Ledger
from vrae.l2.verified import PROFILE, CURRENT_REPORTS, VerifiedNativeSource

TRUST = Path("/run/vrae-reports/trust.json")
AUTHORITY = Path("/run/vrae-reports/authority.json")


def verified_authority():
    envelope = root_document(AUTHORITY)
    key = root_document(TRUST)["keys"][envelope["key_id"]]
    if key["role"] != "REPORT_AUTHORITY" or key["revoked"]:
        raise PermissionError("VERIFIED_REPORT_AUTHORITY_REQUIRED")
    doc = envelope["document"]
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key["public"])).verify(
            bytes.fromhex(envelope["signature"]), canonical(doc)
        )
    except (InvalidSignature, ValueError, TypeError):
        raise PermissionError("VERIFIED_REPORT_AUTHORITY_REQUIRED") from None
    now = datetime.now(UTC)
    if (
        doc["contract"] != "vrae.verified-report-authority.v1"
        or doc["profile"] != PROFILE
        or not doc["reference"]
        or not doc["allowed_source_classes"]
        or not datetime.fromisoformat(doc["not_before"])
        <= now
        < datetime.fromisoformat(doc["expires_at"])
        or doc["directory"]["mode"] != "VERIFIED_DIRECTORY"
        or doc["directory"]["expires"] > datetime.fromisoformat(doc["expires_at"]).timestamp()
    ):
        raise PermissionError("VERIFIED_REPORT_AUTHORITY_REQUIRED")
    return doc


class Authority:
    def __init__(self):
        self.document = verified_authority()
        self.expected = digest(self.document)
        self.scope = ContextVar("verified-current-recipient", default=None)

    def check(self):
        if digest(verified_authority()) != self.expected:
            raise PermissionError("VERIFIED_REPORT_AUTHORITY_CHANGED")

    def permits(self, person, report_id):
        self.check()
        scope = self.scope.get()
        if (
            not scope
            or CURRENT_REPORTS not in person.report_ids
            or not person.verification_ref
            or person.tenant_id != scope["tenant_id"]
            or report_id != scope["report_id"]
        ):
            return False
        return person.role in ("OWNER", "REVIEWER") or (
            person.role == "READER" and person.subject == scope["recipient_subject"]
        )

    @contextmanager
    def current(self, binding, job, path, directory):
        self.check()
        with connect(binding) as c, c.transaction():

            def read():
                self.check()
                data = c.execute(
                    "SELECT target_v1.report_context(%s,%s)", (binding["tenant_id"], job)
                ).fetchone()[0]
                artifact = data["artifact"]
                if (
                    data["task"]["tenant_id"] != binding["tenant_id"]
                    or data["task"]["job_id"] != job
                    or hashlib.sha256(canonical(artifact)).hexdigest()
                    != data["commit"]["artifact_sha256"]
                    or datetime.now(UTC) >= datetime.fromisoformat(data["authority_expires_at"])
                ):
                    raise PermissionError("CURRENT_REPORT_SCOPE_DENIED")
                proof = artifact["source_authority"]
                authorization(
                    proof["authorization"], data["source_plan"], plan_sha256=proof["plan_sha256"]
                )
                if (
                    data["source_plan"]["source_class"]
                    not in self.document["allowed_source_classes"]
                ):
                    raise PermissionError("CURRENT_REPORT_SOURCE_DENIED")
                return data

            first = read()
            native, rid = committed_source(first, binding, job)
            scope = {
                "tenant_id": binding["tenant_id"],
                "report_id": rid,
                "recipient_subject": first["recipient_subject"],
                "invitation_ref": first["invitation_ref"],
            }
            token = self.scope.set(scope)
            try:

                def guard():
                    if read() != first:
                        raise PermissionError("CURRENT_REPORT_AUTHORITY_CHANGED")

                def recipient(person, report_id):
                    return (
                        person.role == "READER"
                        and person.active
                        and person.verification_ref
                        and person.subject == scope["recipient_subject"]
                        and person.tenant_id == scope["tenant_id"]
                        and report_id == rid
                    )

                source = VerifiedNativeSource(
                    native,
                    directory,
                    guard,
                    recipient,
                    datetime.fromisoformat(first["authority_expires_at"]).timestamp(),
                )
                ledger = Ledger(path, source, directory)
                yield ledger, rid
                guard()
            finally:
                self.scope.reset(token)
