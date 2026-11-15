from dataclasses import replace
from uuid import uuid4
import pytest

from apps.operator_console.b5p0_binding import Binding, mapping_subject
from apps.operator_console.b5p0_journal import Journal
from vrae.b3_p0.contracts import Witness
from vrae.persistence.private_bytes import Locator


def test_synthetic_mapping_is_deterministic_and_exactly_scoped():
    loc = Locator("tenant-test", "run", "report", 1, "ref", "0" * 64)
    subject = mapping_subject("local-issuer", "synthetic-subject", "p2b1_test_a_reviewer", loc)
    assert subject.startswith("TEST_ONLY_") and len(subject) == 74
    assert subject != mapping_subject(
        "other-issuer", "synthetic-subject", "p2b1_test_a_reviewer", loc
    )
    assert subject != mapping_subject("local-issuer", "synthetic-subject", "p2b1_test_a_peer", loc)
    assert subject != mapping_subject(
        "local-issuer", "synthetic-subject", "p2b1_test_a_reviewer", replace(loc, version=2)
    )
    with pytest.raises(ValueError):
        Binding(
            "local-issuer",
            "synthetic-subject",
            "p2b1_test_a_reviewer",
            Witness(uuid4(), loc),
            "real-person",
        )


def test_recovery_journal_preserves_original_key_across_new_instance(tmp_path):
    path = tmp_path / "private.sqlite"
    journal = Journal(path)
    raw = b'{"idempotency_key":"server-original-key"}'
    journal.attempted("scope", "semantic", raw, "old-generation")
    again = Journal(path)
    assert again.key(again.read("scope")) == "server-original-key"
    from apps.operator_console.contracts import ConsoleError

    with pytest.raises(ConsoleError):
        again.attempted("scope", "conflicting", b"{}", "new-generation")
