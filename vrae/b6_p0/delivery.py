"""A real in-process denial sink. No sender callback, DB, token or network port."""

from .contracts import LIMIT, canonical, parse, sha, validate, IntendedEnvelope

OPERATIONS = frozenset({"CREATE_GRANT", "ISSUE_TOKEN", "REDEEM_TOKEN", "RECIPIENT_ACCESS",
                        "PUBLIC_LINK", "CUSTOMER_NOTIFICATION", "VF_SEND", "MARK_APPROVED",
                        "MARK_SHARED", "SEND", "REVOKE_TOKEN"})


class DenyOnlySink:
    def __init__(self):
        self._records: dict[str, bytes] = {}

    @property
    def records(self):
        return tuple(self._records.values())

    def _record(self, receipt):
        # Finite private diagnostics, never a durable business outbox/audit event.
        validate("B6PrivateDenialReceipt", parse(receipt))
        if len(self._records) < 256:
            self._records[sha(receipt)] = receipt


class DeliveryAuthorizationGate:
    __slots__ = ("_sink",)

    def __init__(self, sink=None):
        if sink is not None and type(sink) is not DenyOnlySink:
            raise ValueError("B6_NO_EXTERNAL_SINK")
        self._sink = sink if sink is not None else DenyOnlySink()

    @property
    def sink(self):
        return self._sink

    def attempt(self, operation, raw=b"{}"):
        # Even perfectly schema-valid APPROVED/ShareGrant-shaped input is never
        # consumed as authority. Malformed values also get a bounded DENY receipt.
        valid = type(operation) is str and operation in OPERATIONS
        operation = operation if valid else "UNKNOWN"
        digest = sha(raw) if type(raw) is bytes and len(raw) <= LIMIT else None
        try:
            if digest is None or type(parse(raw)) is not dict:
                valid = False
        except Exception:
            valid = False
        doc = {
            "contract_version": "b6-private-denial-v1", "authority": "TEST_ONLY_PRIVATE_PREVIEW",
            "decision": "DENY", "reason": "B6_AUTHORITY_UNAVAILABLE" if valid else "B6_INPUT_DENIED",
            "operation": operation, "receipt_id": "b6deny-" + sha(canonical([operation, digest, valid])),
            "request_sha256": digest, "allowed": False, "sent": False, "side_effect": "IN_MEMORY_DENIAL_ONLY",
            "approval_proven": False, "external_visibility": False, "grant": None, "token": None,
            "is_token": False, "recipient": None, "external_url": None, "native_decision": None, "outbox_event": None,
        }
        validate("B6PrivateDenialReceipt", doc)
        receipt = canonical(doc)
        self.sink._record(receipt)
        return receipt

    def consume_intended_envelope(self, raw):
        try:
            IntendedEnvelope(raw)
        except Exception:
            # Rejected inputs still cannot select a transport, token or recipient.
            return self.attempt("UNKNOWN", raw)
        return self.attempt("VF_SEND", raw)
