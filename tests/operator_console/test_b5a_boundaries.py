"""Pure boundary cases, also run by the unchanged dependency-light default CI."""

from dataclasses import replace

import pytest

from apps.operator_console.b5a_http import BODY_LIMIT, form
from apps.operator_console.b5a_reader import ReviewerSettings
from apps.operator_console.contracts import ConsoleError


@pytest.mark.parametrize(
    "raw",
    [
        b"role=postgres",
        b"tenant=other",
        b"dsn=postgresql%3A%2F%2Fx",
        b"actor=other",
        b"issuer=other",
        b"sub=other",
        b"db_role=postgres",
        b"x=1&x=2",
        b"x=%GG",
        b"x=%ff",
        b"x=Bearer%20secret",
        b"x=-----BEGIN+PRIVATE+KEY",
        b"broken",
        b"x=" + b"a" * BODY_LIMIT,
    ],
)
def test_untrusted_authority_and_malformed_forms_are_not_accepted(raw):
    with pytest.raises(ConsoleError):
        form(raw)


def test_utf8_preview_text_is_preserved():
    assert form(b"reason=%E6%A0%B8%E5%AF%B9&action=RETURN_CANDIDATE") == {
        "reason": "核对",
        "action": "RETURN_CANDIDATE",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"host": "localhost"},
        {"host": "0.0.0.0"},
        {"user": "postgres"},
        {"user": "ra4a_test_a_app"},
        {"dbname": "vrae_p2a_123456789abc"},
        {"port": True},
        {"password": "short"},
    ],
)
def test_profile_cannot_select_app_superuser_or_non_loopback(change):
    settings = ReviewerSettings(
        "127.0.0.1",
        5432,
        "vrae_p2b1_123456789abc",
        "p2b1_test_a_reviewer",
        "synthetic-not-used-password",
    )
    with pytest.raises(ValueError):
        replace(settings, **change)
    assert "synthetic-not-used-password" not in repr(settings)
