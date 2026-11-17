"""Accepted PR121 Port + PR124 reading authority, without result promotion.

Synthetic browser objects below are unit fixtures, never browser attestation.
Only accepted-main imports are used; signed report access stays in DeepConsole.
"""
import copy
from dataclasses import replace

import pytest

from apps.operator_console.l2_buyer_views import reading
from integration.l2.native_component import source
from integration.l2.support import create, login, REPORT
from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.l2.report import L2Denied
from vrae.rules.s2 import evaluate_s2, verify_s2_projection
from vrae.rules.s2_ux import project_browser
from .test_projection import fixture


def scope(pack):
    return {k: pack.document[k] for k in ('tenant_id', 'run_id', 'policy_id', 'policy_version')}


def test_accepted_port_keeps_native_report_hash_and_five_dimension_reading_unchanged(tmp_path):
    native = source()
    before = native.read()
    pack = native._pack  # test-only use of the accepted immutable source instance
    output = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack))
    verify_s2_projection(output, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                         expected_projection_ref=output['projection_ref'])
    assert output['browser_projection'] is None
    assert output['browser_binding'] == 'NOT_REQUESTED_NO_BROWSER_PINS_INFERRED'
    assert 'execution_ref' not in output
    assert all(r['implementation'] == 'NOT_IMPLEMENTED_P0'
               for r in output['s2_capabilities'] if r['owner'] == 'C2')
    assert native.read().payload == before.payload
    assert reading(before)['display_hash'] == before.display_hash
    assert len(reading(before)['dimensions']) == 5
    with pytest.raises(L2Denied):
        reading(output)  # a genuine verified projection is still not a report


@pytest.mark.parametrize('field', ['result', 'source', 'pointer'])
def test_combined_self_rehash_cannot_promote_browser_candidate_or_change_its_citation(field):
    pack, held = fixture([{'tag': 'A', 'visible': True, 'text': 'Contact 联系'}])
    output = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack), browser_pins=held)
    assert output['browser_projection'] == project_browser(pack, held=held).document
    original = copy.deepcopy(output)
    row = next(r for r in output['browser_projection']['rows'] if r['candidates'])
    if field == 'result':
        row['rules'][0]['result'] = 'PASS'
    elif field == 'source':
        row['candidates'][0]['evidence_ref'] = 'ev-'+'0'*64
    else:
        row['candidates'][0]['json_pointer'] = '/elements/127'
    output['projection_ref'] = 's2p-'+document_hash({k:v for k,v in output.items() if k!='projection_ref'})
    with pytest.raises(EvidenceError):
        verify_s2_projection(output, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                             browser_pins=held, expected_projection_ref=output['projection_ref'])
    verify_s2_projection(original, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                         browser_pins=held, expected_projection_ref=original['projection_ref'])


def test_valid_projection_does_not_restore_a_revoked_signed_report_session(tmp_path):
    issuer, directory, ledger, app = create(tmp_path)
    sid = login(issuer, directory, 'reviewer-demo')
    before = ledger.read(sid, REPORT)
    pack, held = fixture([{'tag': 'A', 'visible': True, 'text': 'RFQ'}])
    output = evaluate_s2(pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack), browser_pins=held)
    directory.people['reviewer-demo'] = replace(directory.people['reviewer-demo'], active=False)
    # Consistency is still replayable; it never constitutes live report permission.
    verify_s2_projection(output, pack, expected_pack_ref=pack.ref, trusted_scope=scope(pack),
                         browser_pins=held, expected_projection_ref=output['projection_ref'])
    reply = app.deep.handle('GET', '/b5a/l2/r/'+REPORT+'/buyer-tasks',
                            {'Cookie':'b5a_l2_session='+sid, 'X-S2-Projection':output['projection_ref']}, b'')
    assert reply.response.status == 403 and b'l2-buyer-dimension' not in reply.response.body
    assert ledger.source.read().payload == before.payload
