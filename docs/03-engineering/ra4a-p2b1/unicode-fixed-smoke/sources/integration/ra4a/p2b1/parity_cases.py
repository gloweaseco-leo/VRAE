"""Additional native/SQL parity cases after actual Unicode classification probe."""

import json
import os
from pathlib import Path

import psycopg
import pytest

from integration.ra4a.p2b1.cases import changed, empty, one
from integration.ra4a.p2b1_support import connect, counts, graph, proposal, raw_submit, submit
from vrae.reviewing import ReviewError

# Python 3.11/3.13 str.isspace repertoire, not locale-sensitive POSIX classes.
WHITESPACE = (
    9,
    10,
    11,
    12,
    13,
    28,
    29,
    30,
    31,
    32,
    133,
    160,
    5760,
    *range(8192, 8203),
    8232,
    8233,
    8239,
    8287,
    12288,
)


@pytest.mark.parametrize("point", WHITESPACE, ids=lambda p: "U%04X" % p)
def test_b27_unicode_blank_reason_native_and_sql_both_refuse(isolated, point):
    name, admin = isolated
    char = chr(point)
    assert char.isspace() and not char.strip()
    cmd = changed(proposal(), lambda d: d.update(reason=char))
    with pytest.raises(ReviewError):
        submit(name, cmd=cmd)
    denied = False
    with connect("p2b1_test_a_reviewer", dbname=name) as c:
        try:
            receipt = raw_submit(c, graph(), cmd)
        except psycopg.Error:
            denied = True
    if not denied:
        proof = {
            "point": hex(point),
            "native": "D_UNTRUSTED_TEXT",
            "raw_sql_receipt": json.loads(receipt),
            "actual_ledger_counts": counts(admin),
        }
        (
            Path(os.environ["RA4A_P2B1_EVIDENCE_DIR"])
            / ("unexpected-blank-reason-%04X.json" % point)
        ).write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    assert denied, "Raw SQL committed a reason rejected by frozen native validate_proposal"
    empty(admin)


def test_b28_unicode_padded_actual_text_stays_valid(isolated):
    name, admin = isolated
    padding = "".join(chr(p) for p in WHITESPACE if p >= 32)
    cmd = changed(
        proposal(), lambda d: d.update(reason=padding + "Actual test-only review note" + padding)
    )
    r = submit(name, cmd=cmd).document
    assert r["status"] == "SIMULATED_APPROVE_CANDIDATE" and r["native_approval"] is None
    one(admin)


@pytest.mark.parametrize("field", ("checked_scope", "remaining_unknowns", "section_target_digest"))
def test_b29_hash_binding_does_not_coerce_json_numbers(isolated, field):
    name, admin = isolated
    g = graph("200")

    def mutate(d):
        if field == "section_target_digest":
            d["sections"][0]["target_digest"] = 123
        else:
            d[field] = 123

    cmd = changed(proposal(g), mutate)
    with pytest.raises(ReviewError):
        submit(name, g, cmd)
    with connect("p2b1_test_a_reviewer", dbname=name) as c, pytest.raises(psycopg.Error):
        raw_submit(c, g, cmd)
    empty(admin)
