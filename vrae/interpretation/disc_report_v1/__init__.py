"""Explicit DISC static 404/410 facts; the legacy public Guard stays versioned."""

from vrae.collection.manifest import document_hash
from vrae.interpretation import guard as legacy

from . import _guard_core as core

VERSION = core.VERSION
GuardError = legacy.GuardError


def catalog(pack, package, **pins):
    return core.catalog(pack, package, **pins)


def binding(*, pointer, text, claim_type, fact, context):
    value = dict(
        binding_version=VERSION,
        pointer=pointer,
        text=text,
        claim_type=claim_type,
        context=context,
        fact=fact,
    )
    value["binding_ref"] = "cb-" + document_hash(value)
    return legacy._detach(value)


class GuardResult(legacy.GuardResult):
    @classmethod
    def load(cls, document, interpretation, bindings, pack, package, *, expected_guard_ref, **pins):
        rebuilt = validate(interpretation, bindings, pack, package, **pins)
        try:
            if (
                rebuilt.ref != expected_guard_ref
                or legacy._encode(legacy._detach(document)) != rebuilt._payload
            ):
                legacy._fail("GUARD_INTEGRITY")
        except GuardError:
            raise
        except Exception:
            raise GuardError("GUARD_INTEGRITY") from None
        return rebuilt


def validate(interpretation, bindings, pack, package, **pins):
    try:
        return GuardResult(
            legacy._encode(
                core._project(interpretation, bindings, pack, package, pins)
            )
        )
    except GuardError:
        raise
    except Exception:
        raise GuardError("INPUT_INTEGRITY") from None
