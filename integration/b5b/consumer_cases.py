"""UI preparation and RED-publication tests, not generated Worker evidence."""

import hashlib
import json
import xml.etree.ElementTree as ET

import pytest

from apps.operator_console.b5b_m2_views import workspace, decision_fields
from integration.b5b.publication import browser_failure_view, native_failure_views


def test_missing_port_cannot_offer_a_fake_review_receipt_or_download():
    html = workspace('task-404')
    assert 'BLOCKED_NO_ACCEPTED_LEASE_BOUND_RESULT_PORT' in html
    assert 'BLOCKED_NO_ACCEPTED_REVIEWER_TASK_STATUS_PORT' in html
    assert '<fieldset disabled>' in html and '<select id="m2-source" disabled>' in html
    assert '<form' not in html and 'download=' not in html and '<script' not in html
    assert 'UNKNOWN' in html and 'NOT APPROVED' in html
    assert 'APP 凭据' in html and '不是新任务审核' in html


@pytest.mark.parametrize('version,digest,issues', [
    (True, 'a'*64, []), (0, 'a'*64, []), (1, 'tampered', []),
    (1, 'a'*64, ['issue']*2), (1, 'a'*64, ['1','2','3','4']),
    (1, 'a'*64, ['<script>']),
])
def test_unbound_render_preparation_rejects_invalid_version_or_issue_pins(version, digest, issues):
    with pytest.raises(ValueError, match='M2_EXACT_REPORT_PINS_REQUIRED'):
        decision_fields('task', version, digest, issues, 'csrf')


def test_prepared_submission_is_explicitly_internal_and_version_bound():
    html = decision_fields('task', 7, 'a'*64, ['issue-1'], '<script>')
    assert 'name="report_version" value="7"' in html and 'a'*64 in html
    assert all(v in html for v in ('APPROVE_INTERNAL', 'REJECT_INTERNAL', 'REVISE_INTERNAL'))
    assert '<script>' not in html and 'NOT APPROVED' in html


def test_actual_failure_outcome_survives_sanitizing_without_raw_traceback(tmp_path):
    # Deliberate serializer unit fixture, never reported as a native test run.
    raw = b'<testsuites><testsuite><testcase classname="fixture" name="red"><failure>PRIVATE_TRACE</failure></testcase><testcase classname="fixture" name="pass"/></testsuite></testsuites>'
    p = tmp_path/'fixture.xml'
    p.write_bytes(raw)
    views = native_failure_views(p)
    cases = list(ET.fromstring(views['native-junit.xml']).iter('testcase'))
    assert len(cases) == 2 and sum(c.find('failure') is not None for c in cases) == 1
    assert b'PRIVATE_TRACE' not in views['native-junit.xml']
    r = json.loads(views['native-retention.json'])
    assert r['passed'] == 1 and r['cases'] == 2 and not r['stdout_constructed_xml']
    assert r['raw_native_sha256'] == hashlib.sha256(raw).hexdigest()


def test_browser_red_retains_first_phase_and_failed_cleanup_without_headers(tmp_path):
    folder = tmp_path/'b5b-browser'
    folder.mkdir()
    (folder/'browser-failure.json').write_text(json.dumps({
        'code':'CDP_TIMEOUT_Page.navigate','phase':'375/404','step':'session',
        'records':[{'name':'check', 'pass':True}],
        'network':[{'Authorization':'PRIVATE_HEADER'}],
    }))
    (folder/'browser-process-cleanup.json').write_text(json.dumps({'exit_observed':False,'graceful':True,'forced':True}))
    raw = browser_failure_view(tmp_path)
    result = json.loads(raw)
    row = result['suites'][1]
    assert row['status'] == 'RED' and row['phase'] == '375/404'
    assert row['completed_assertions'] == 1 and not row['cleanup']['exit_observed']
    assert result['suites'][0]['status'] == 'NOT_STARTED'
    assert b'PRIVATE_HEADER' not in raw and b'Authorization' not in raw


def test_browser_failure_can_retain_exact_original_passed_xml_but_never_raw_red(tmp_path):
    # Deliberate serializer fixtures, not evidence of a real native test run.
    passed = b'<testsuites><testsuite><testcase classname="fixture" name="pass"/></testsuite></testsuites>'
    p = tmp_path/'fixture.xml'
    p.write_bytes(passed)
    v = native_failure_views(p, retain_passed_original=True)
    r = json.loads(v['native-retention.json'])
    assert v['native-junit.xml'] == passed and not r['raw_xml_private']
    assert r['public_original_passed_sha256'] == hashlib.sha256(passed).hexdigest()
    red = passed.replace(b'/></testsuite>', b'><failure>PRIVATE_TRACE</failure></testcase></testsuite>')
    p.write_bytes(red)
    v = native_failure_views(p, retain_passed_original=True)
    assert v['native-junit.xml'] != red and b'PRIVATE_TRACE' not in v['native-junit.xml']
    assert json.loads(v['native-retention.json'])['raw_xml_private']
