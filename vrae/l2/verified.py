"""Explicit verified-person consumer of the unchanged original NativeSource.

The caller must retain current PG/source/recipient authority. This adapter does
not authenticate a task or mint identity, source permission, or report content.
"""

from .native import NativeSource
from .report import deny

PROFILE = "VERIFIED_HUMAN_CUSTOMER_REPORT"
CURRENT_REPORTS = "CURRENT_AUTHORIZED_TARGET_REPORTS"


class VerifiedNativeSource:
    controlled_only = True  # The original native producer is never relabeled.
    profile = PROFILE

    def __init__(self, native, directory, check_current, recipient, authority_deadline):
        if type(native) is not NativeSource or directory.mode != "VERIFIED_DIRECTORY":
            deny("L2_NATIVE_CONTROLLED_CONTEXT_REQUIRED")
        self.native, self.directory = native, directory
        self._check, self._recipient = check_current, recipient
        self.expected = native.expected
        self.authority_deadline = authority_deadline
        self.check_verified(directory)

    def check_verified(self, directory):
        if directory is not self.directory or directory.mode != "VERIFIED_DIRECTORY":
            deny("L2_NATIVE_CONTROLLED_CONTEXT_REQUIRED")
        self._check()
        return True

    def recipient(self, person, report_id):
        self.check_verified(self.directory)
        if not self._recipient(person, report_id):
            deny("L2_DIRECTED_RECIPIENT_REQUIRED")

    def read(self):
        self.check_verified(self.directory)
        return self.native.read()

    def validate(self, document):
        self.check_verified(self.directory)
        return self.native.validate(document)

    def revision(self, previous, changes, actor_id, created_at):
        self.check_verified(self.directory)
        return self.native.revision(previous, changes, actor_id, created_at)


def require_verified(source, directory, code="L2_NATIVE_CONTROLLED_CONTEXT_REQUIRED"):
    if type(source) is not VerifiedNativeSource:
        deny(code)
    source.check_verified(directory)
    return True
