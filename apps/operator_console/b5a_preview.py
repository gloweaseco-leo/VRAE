"""Signed-session adapter to the accepted pure proposal validator, no commit port.

The old ProposalPreview explicitly supports fixture authority only. This new
adapter uses its public native validator and existing SSR composer, never bypasses
that constructor, impersonates FixtureAuthority, or calls B3 CAS/decision APIs.
"""

from vrae.reviewing import (
    ReviewTarget,
    ReviewCommandProposal,
    CoverageAcknowledgementProposal,
    ReviewError,
    validate_proposal,
)
from vrae.reviewing.canonical import canonical, COMMAND_LIMIT

from .contracts import refuse


class SignedPreview:
    def __init__(self, service):
        self.service = service

    def read(self, context, task_id, version, draft, target):
        return self.service.target(context, task_id, version, draft, target)

    def validate(self, context, task_id, fields):
        self.service.detail(context, task_id)
        if (
            not {"version", "draft", "target", "action", "reason"} <= fields.keys()
            or not fields["version"].isascii()
            or not fields["version"].isdigit()
            or len(fields["version"]) > 4
        ):
            refuse("INVALID_INPUT")
        task, dossier = self.read(
            context, task_id, int(fields["version"]), fields["draft"], fields["target"]
        )
        t = dossier["review_target"]["target"]
        base = {"version", "draft", "target", "action", "reason"}
        base.update(
            f"{key}.{i}"
            for i in range(len(t["claims"]))
            for key in ["guard", "binding", "pointer", "disposition"]
        )
        sections = {"section." + s for s in t["required_sections"]}
        if not base <= fields.keys() or fields.keys() - base - sections:
            refuse("INVALID_INPUT")
        review = t["kind"] == "L1_NATIVE"
        if not review and fields["action"] != "SIMULATED_INTERNAL_SCOPE_ACK":
            refuse("INVALID_INPUT")
        command = {
            "contract_version": "ra3d-review-proposal-offline-v1",
            "kind": "REVIEW_COMMAND_PROPOSAL" if review else "COVERAGE_ACK_PROPOSAL",
            "tenant_id": t["tenant_id"],
            "report_id": t["report_id"],
            "report_version": int(fields["version"]),
            "target_digest": fields["target"],
            "expected_review_seq": 0,
            "idempotency_key": "b5a-unsaved-preview",
            "reason": fields["reason"] or None,
            "dispositions": [
                {
                    "guard_ref": fields["guard." + str(i)],
                    "binding_ref": fields["binding." + str(i)],
                    "pointer": fields["pointer." + str(i)],
                    "disposition": fields["disposition." + str(i)],
                }
                for i in range(len(t["claims"]))
            ],
            "sections": [
                {"section_id": s, "target_digest": fields["section." + s], "acknowledged": True}
                for s in t["required_sections"]
                if "section." + s in fields
            ],
        }
        if review:
            command["action"] = fields["action"]
            proposal = ReviewCommandProposal(canonical(command, limit=COMMAND_LIMIT))
        else:
            command.update(
                checked_scope=t["scope_digest"], remaining_unknowns=t["limitations_digest"]
            )
            proposal = CoverageAcknowledgementProposal(canonical(command, limit=COMMAND_LIMIT))
        try:
            validate_proposal(proposal, ReviewTarget(canonical(t)))
            outcome = "CONTRACT_VALID_ONLY"
        except ReviewError as exc:
            outcome = exc.code
        return task, dossier, command, outcome
