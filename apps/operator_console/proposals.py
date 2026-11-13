"""Loopback fixture-only form adapter to the accepted pure proposal validator.

No decision/session/ledger/repository write. Inputs never confer authority.
"""

from urllib.parse import parse_qsl, urlsplit, unquote

from vrae.reviewing import (
    ReviewCommandProposal,
    CoverageAcknowledgementProposal,
    ReviewTarget,
    ReviewError,
    validate_proposal,
)
from vrae.reviewing.canonical import canonical, COMMAND_LIMIT

from .contracts import ConsoleError, refuse
from .fixtures import FixtureAuthority, FixtureRepository
from .native import NativeVerifier

BODY_LIMIT = 24_576
CONTENT_TYPE = "application/x-www-form-urlencoded"


class ProposalPreview:
    def __init__(self, service, context, *, test_only=False, synthetic_fixtures=False):
        from .pg_read import PgReadRepository
        if (
            test_only is not True
            or synthetic_fixtures is not True
            or type(service.authority) is not FixtureAuthority
            or type(service.repository) not in (FixtureRepository, PgReadRepository)
            or type(service.native) is not NativeVerifier
        ):
            raise ValueError("TEST_ONLY_FIXTURE_REQUIRED")
        service._scope(context)
        self.service, self.context = service, context

    def _context(self, context):
        if context is not self.context:
            refuse("UNAUTHORIZED")
        self.service._scope(context)

    def read(self, context, task_id, version, draft, target):
        self._context(context)
        return self.service.target(context, task_id, version, draft, target)

    def validate(self, context, task_id, raw, content_type):
        """Untrusted bounded form -> native command -> native pure validator.

        Claim identities are submitted explicitly, never silently repaired. The
        target is reloaded/replayed on every action. No caller trust or actor.
        """
        self._context(context)
        # Assignment check precedes parsing or any report/source read.
        self.service.detail(context, task_id)
        if type(raw) is not bytes or len(raw) > BODY_LIMIT or content_type != CONTENT_TYPE:
            refuse("INVALID_INPUT")
        try:
            value = raw.decode("utf-8", errors="strict")
            # parse_qsl alone tolerates malformed percent escapes.
            import re

            if re.search(r"%(?![0-9a-fA-F]{2})", value):
                refuse("INVALID_INPUT")
            pairs = parse_qsl(
                value,
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=64,
            )
            if len(dict(pairs)) != len(pairs):
                refuse("INVALID_INPUT")
            f = dict(pairs)
            if not {"version", "draft", "target"} <= f.keys():
                refuse("INVALID_INPUT")
            if not f["version"].isascii() or not f["version"].isdigit() or len(f["version"]) > 4:
                refuse("INVALID_INPUT")
            task, dossier = self.read(context, task_id, int(f["version"]), f["draft"], f["target"])
            t = dossier["review_target"]["target"]
            expected = {"version", "draft", "target", "action", "reason"}
            expected.update(
                f"{k}.{i}"
                for i in range(len(t["claims"]))
                for k in ("guard", "binding", "pointer", "disposition")
            )
            section_fields = {"section." + s for s in t["required_sections"]}
            # Missing sections go to the native validator; extra fields fail closed.
            if set(f) - section_fields != expected or set(f) - expected - section_fields:
                refuse("INVALID_INPUT")
            is_review = t["kind"] == "L1_NATIVE"
            if not is_review and f["action"] != "SIMULATED_INTERNAL_SCOPE_ACK":
                refuse("INVALID_INPUT")
            command = {
                "contract_version": "ra3d-review-proposal-offline-v1",
                "kind": "REVIEW_COMMAND_PROPOSAL" if is_review else "COVERAGE_ACK_PROPOSAL",
                "tenant_id": t["tenant_id"],
                "report_id": t["report_id"],
                "report_version": int(f["version"]),
                "target_digest": f["target"],
                # Synthetic shape values only, not a real sequence or replay receipt.
                "expected_review_seq": 0,
                "idempotency_key": "test-only-unsaved-preview",
                "reason": f["reason"] if f["reason"] else None,
                "dispositions": [
                    {
                        "guard_ref": f["guard." + str(i)],
                        "binding_ref": f["binding." + str(i)],
                        "pointer": f["pointer." + str(i)],
                        "disposition": f["disposition." + str(i)],
                    }
                    for i in range(len(t["claims"]))
                ],
                "sections": [
                    {"section_id": s, "target_digest": f["section." + s], "acknowledged": True}
                    for s in t["required_sections"]
                    if "section." + s in f
                ],
            }
            if is_review:
                command["action"] = f["action"]
                proposal = ReviewCommandProposal(canonical(command, limit=COMMAND_LIMIT))
            else:
                command.update(
                    checked_scope=t["scope_digest"], remaining_unknowns=t["limitations_digest"]
                )
                proposal = CoverageAcknowledgementProposal(canonical(command, limit=COMMAND_LIMIT))
            # Pure validation only. Do not issue a digest receipt or simulate commit.
            try:
                validate_proposal(proposal, ReviewTarget(canonical(t)))
                outcome = "CONTRACT_VALID_ONLY"
            except ReviewError as exc:
                outcome = exc.code
            return task, dossier, command, outcome
        except (ConsoleError, ReviewError):
            raise
        except (ValueError, UnicodeError, TypeError, KeyError):
            refuse("INVALID_INPUT")

    def post(self, context, target, raw, content_type, *, prefix):
        """Only the harness calls this after HTTP Host/Origin/body checks.

        ConsoleInterface.dispatch and ConsoleService.mutate still always deny POST.
        """
        self._context(context)
        url = urlsplit(target)
        if (
            len(target) > 2048
            or url.scheme
            or url.netloc
            or url.query
            or url.fragment
            or not url.path.startswith(prefix)
        ):
            refuse("INVALID_INPUT")
        parts = unquote(url.path[len(prefix) :], errors="strict").split("/")
        if len(parts) != 3 or parts[0] != "tasks" or parts[2] != "proposal-preview":
            refuse("NOT_IMPLEMENTED")
        return self.validate(context, parts[1], raw, content_type)
