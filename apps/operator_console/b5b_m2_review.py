"""Version-bound internal review command, independent of authentication/storage.

A parsed command is untrusted intent. Only the assigned-result transaction port
may authorize it and persist a receipt; construction alone never saves anything.
"""

from dataclasses import dataclass
import re

from .b5a_http import SECRET

DECISIONS = frozenset({"APPROVE_INTERNAL", "REJECT_INTERNAL", "REVISE_INTERNAL"})


@dataclass(frozen=True)
class ReviewCommand:
    report_version: int
    report_sha256: str
    decision: str
    revision: str
    issues: tuple

    @classmethod
    def parse(cls, fields, view):
        ids = view.issue_ids
        expected = {"report_version", "report_sha256", "decision", "revision"}
        expected.update("decision." + i for i in ids)
        expected.update("revision." + i for i in ids)
        if type(fields) is not dict or set(fields) != expected or any(type(v) is not str for v in fields.values()):
            raise ValueError("M2_INVALID_REVIEW_COMMAND")
        if (fields["report_version"] != str(view.pins["report_version"])
                or fields["report_sha256"] != view.pins["report_sha256"]):
            raise ValueError("M2_STALE_REPORT")

        def decision(action, text):
            if (action not in DECISIONS or len(text) > 2000 or SECRET.search(text)
                    or any(ord(c) < 32 and c not in '\n\r\t' for c in text)
                    or (action == "REVISE_INTERNAL" and not text.strip())):
                raise ValueError("M2_INVALID_REVIEW_DECISION")
            return action, text

        action, text = decision(fields["decision"], fields["revision"])
        issues = tuple((i, *decision(fields["decision." + i], fields["revision." + i])) for i in ids)
        return cls(int(fields["report_version"]), fields["report_sha256"], action, text, issues)

    def document(self):
        if (type(self.report_version) is not int or self.report_version < 1
                or not re.fullmatch('[a-f0-9]{64}', self.report_sha256)):
            raise ValueError("M2_INVALID_REVIEW_COMMAND")
        return {
            "scope": "SYNTHETIC_INTERNAL_REVIEW_ONLY",
            "report_version": self.report_version,
            "report_sha256": self.report_sha256,
            "decision": self.decision,
            "revision": self.revision,
            "issues": [{"finding_id": i, "decision": d, "revision": r} for i, d, r in self.issues],
        }
