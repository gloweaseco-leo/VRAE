"""Bounded volatile SYNTHETIC receiver adapter, not a CRM or durable receipt store.

The SSR holds only an optional receiver public key. The independent test
receiver retains its private key. Every operation replays the original current
Brief authority. A receiver ACK never authorizes any commercial operation.
Restart forgets this simulation; the original PG Brief remains authoritative.
"""
from dataclasses import dataclass
import secrets
import threading

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vrae.reviewing.canonical import canonical, parse, sha
from .sources import OperationsDenied


@dataclass(frozen=True)
class SyntheticReceiver:
    public_key: bytes

    def verify(self, document, signature):
        try:
            Ed25519PublicKey.from_public_bytes(self.public_key).verify(signature, canonical(document))
        except Exception:
            raise OperationsDenied('S4_RECEIVER_SIGNATURE_DENIED') from None


class SyntheticIntake:
    def __init__(self, receiver=None):
        if receiver is not None and type(receiver) is not SyntheticReceiver:
            raise OperationsDenied('S4_RECEIVER_REQUIRED')
        self.receiver = receiver
        self._rows = {}
        self._lock = threading.RLock()

    def _identity(self, service, ledger, brief_ref):
        doc = service.load_current(ledger, brief_ref)
        if doc['preparation_status'] != 'INTERNAL_REVIEW_RECORDED' or doc['source']['access_mode'] != 'OFFLINE_SYNTHETIC':
            raise OperationsDenied('S4_SYNTHETIC_APPROVED_INTERNAL_ONLY')
        key = sha(canonical({'pins': doc['pins'], 'brief_sha256': doc['content_sha256']}))
        return doc, key

    def current(self, service, ledger, brief_ref):
        with self._lock:
            doc, key = self._identity(service, ledger, brief_ref)
            row = self._rows.get(key)
            service.read_current(doc)
            return parse(canonical(row)) if row else None

    def transition(self, service, ledger, brief_ref, action):
        with self._lock:
            doc, key = self._identity(service, ledger, brief_ref)
            previous = self._rows.get(key)
            if action == 'submit' and previous:
                service.read_current(doc)
                return parse(canonical(previous))  # idempotent same immutable Brief
            if action == 'retry' and (not previous or previous['state'] not in ('RETRYABLE_FAILED', 'REJECTED')):
                raise OperationsDenied('S4_RETRY_DENIED')
            if action == 'revoke':
                if not previous:
                    raise OperationsDenied('S4_NO_SUBMISSION')
                row = {**previous, 'state': 'REVOKED'}
            elif action in ('submit', 'retry'):
                if not previous and len(self._rows) >= 40:
                    raise OperationsDenied('S4_SIMULATION_BOUND')
                attempt = previous['attempt'] + 1 if previous else 1
                if attempt > 5:
                    raise OperationsDenied('S4_RETRY_BOUND')
                row = {'mode': 'BOUNDED_SYNTHETIC_INTERNAL_ONLY', 'scope_sha256': key,
                       'brief_ref': brief_ref, 'brief_sha256': doc['content_sha256'],
                       'attempt': attempt, 'nonce': secrets.token_urlsafe(32),
                       'state': 'WAITING_ACK', 'receiver_receipt_sha256': None,
                       'customer_approval': False, 'counts_as_e2': False, 'counts_as_e3': False,
                       'quote_allowed': False, 'external_delivery_allowed': False,
                       'material_authorization': False}
            else:
                raise OperationsDenied('S4_ACTION_DENIED')
            service.read_current(doc)
            self._rows[key] = row
            return parse(canonical(row))

    def receive(self, service, ledger, brief_ref, receipt, signature):
        """Private server adapter only. No browser route accepts an ACK or key."""
        with self._lock:
            doc, key = self._identity(service, ledger, brief_ref)
            row = self._rows.get(key)
            if self.receiver is None or not row or row['state'] == 'REVOKED':
                raise OperationsDenied('S4_RECEIVER_UNAVAILABLE_OR_REVOKED')
            if type(receipt) is not dict or set(receipt) != {'scope_sha256', 'brief_sha256', 'attempt', 'nonce', 'state'}:
                raise OperationsDenied('S4_RECEIPT_SHAPE')
            if receipt['state'] not in ('ACKNOWLEDGED', 'REJECTED', 'RETRYABLE_FAILED'):
                raise OperationsDenied('S4_RECEIPT_STATE')
            if any(receipt[k] != row[k] for k in ('scope_sha256', 'brief_sha256', 'attempt', 'nonce')):
                raise OperationsDenied('S4_RECEIPT_STALE_OR_CROSS_TASK')
            self.receiver.verify(receipt, signature)
            digest = sha(canonical(receipt))
            if row['state'] != 'WAITING_ACK':
                if row['receiver_receipt_sha256'] != digest:
                    raise OperationsDenied('S4_RECEIPT_CONFLICT')
                return parse(canonical(row))
            service.read_current(doc)
            row = {**row, 'state': receipt['state'], 'receiver_receipt_sha256': digest}
            self._rows[key] = row
            return parse(canonical(row))
