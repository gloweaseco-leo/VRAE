"""Actual collected C3 inputs through accepted C1 DISC report and B6 denial ports."""
import base64
import json
import pytest
from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.reporting.common import ReportError
from vrae.reporting.disc_report_v1 import ReportDraft
from .pipeline import run

@pytest.fixture(scope='module')
def generated(tmp_path_factory):
    folder=tmp_path_factory.mktemp('accepted-chain')
    records=run(folder)
    return folder,records

def test_accepted_versioned_disc_is_generated_from_current_collector(generated):
    folder,rows=generated
    disc=next(r for r in rows if r['case']=='disc-404')
    assert disc['reporting_version']=='ra3c-disc-1.0.0'
    assert disc['unsupported_rule_findings']==0 and disc['report_issues']==1
    assert disc['execution']=='LIVE_OFFLINE_COLLECTOR_NOT_PRECOMPUTED_REPORT'
    assert disc['pack_ref'] and disc['execution_ref'] and disc['package_ref'] and disc['draft_ref']
    assert len(disc['enabled_rules'])==6 and disc['worker_connection']=='BLOCKED_NO_ACCEPTED_PROCESSING_BRIDGE'

def test_existing_404_200_report_contracts_preserved(generated):
    folder,rows=generated
    legacy=[r for r in rows if r['case'] in ('404','200')]
    assert [r['report_issues'] for r in legacy]==[1,0]
    assert all(r['reporting_version']=='ra3c-1.0.0' for r in legacy)

def test_all_real_b6_operations_still_deny_without_sender(generated):
    folder,rows=generated
    for row in rows:
        deny=row['B6_delivery']
        assert deny['operations']==11 and deny['allowed']==deny['sent']==0
        assert deny['implemented']=='ACCEPTED_B6_DENIAL_GATE_ONLY'
        assert deny['private_candidate_access']=='BLOCKED_PENDING_ACCEPTED_RESULT_REVIEW_PORT'
        assert deny['report_ref']==row['draft_ref'] and len(deny['receipt_sha256'])==11

def test_generated_disc_bytes_replay_and_tamper_fails_closed(generated):
    folder,rows=generated
    path=folder/'disc-404'
    data=json.loads((path/'source.json').read_text())
    pins=data['pins']
    pack=EvidencePack.load(data['pack'],{k:base64.b64decode(v,validate=True) for k,v in data['objects_base64'].items()},expected_ref=pins['expected_pack_ref'])
    package=FindingPackage.load(data['package'],pack,**{k:pins[k] for k in ['expected_pack_ref','expected_execution_ref','expected_evaluator_version','expected_package_ref','expected_builder_version']})
    document=json.loads((path/'draft.json').read_text())
    html=(path/'report.html').read_bytes()
    draft_ref=next(r['draft_ref'] for r in rows if r['case']=='disc-404')
    kwargs=dict(expected_draft_ref=draft_ref,**pins)
    rebuilt=ReportDraft.load(document,html,pack,package,data['guard_inputs'],data['metadata'],**kwargs)
    assert rebuilt.html_bytes==html
    with pytest.raises(ReportError):
        ReportDraft.load(document,html+b'changed',pack,package,data['guard_inputs'],data['metadata'],**kwargs)

