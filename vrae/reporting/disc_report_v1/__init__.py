"""Versioned DISC report route; legacy APIs do not dispatch to this version."""

from vrae.reporting import draft as legacy
from vrae.reporting.common import ReportError, detach, encode, fail
from .policy import VERSION as VERSION, RENDERER_VERSION as RENDERER_VERSION


class ReportDraft(legacy.ReportDraft):
    @classmethod
    def load(
        cls,
        document,
        html_bytes,
        pack,
        package,
        guard_inputs,
        metadata,
        *,
        expected_draft_ref,
        **pins,
    ):
        rebuilt = build_draft(pack, package, guard_inputs, metadata, **pins)
        try:
            if (
                rebuilt.ref != expected_draft_ref
                or encode(detach(document)) != rebuilt._payload
                or html_bytes != rebuilt.html_bytes
            ):
                fail("REPORT_REPLAY_MISMATCH")
        except ReportError:
            raise
        except Exception:
            raise ReportError("REPORT_REPLAY_MISMATCH") from None
        return rebuilt


def build_draft(pack, package, guard_inputs, metadata, **pins):
    try:
        from .draft import _project

        document, html = _project(pack, package, guard_inputs, metadata, pins, _disc=True)
        return ReportDraft(encode(document), html)
    except ReportError:
        raise
    except Exception:
        raise ReportError("REPORT_INTEGRITY") from None


def render(
    document, html_bytes, pack, package, guard_inputs, metadata, *, expected_draft_ref, **pins
):
    return ReportDraft.load(
        document,
        html_bytes,
        pack,
        package,
        guard_inputs,
        metadata,
        expected_draft_ref=expected_draft_ref,
        **pins,
    ).html_bytes
