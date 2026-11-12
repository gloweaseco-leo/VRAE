"""Explicit immutable evidence transport for ordinary V2 pytest collection.

No browser, network, subprocess, producer-output generation or assertion patching.
The only derived input changes are three local screenshot filesystem paths.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PROFILE_SHA256 = 'f6d9f5432314e567016b3e09a84d753cc54fa6d6bd4543492fc1ee692b781294'
_receipt = None


def canonical_bytes(path, binary=False):
    raw = path.read_bytes()
    return raw if binary else raw.replace(b'\r\n',b'\n')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def configure():
    global _receipt
    if _receipt is not None:
        return _receipt
    profile_path = HERE/'external-inputs-minimal.json'
    raw = canonical_bytes(profile_path)
    assert digest(raw) == PROFILE_SHA256, 'OWNER_V2_EXTERNAL_PROFILE_INTEGRITY'
    profile = json.loads(raw)
    for relative,entry in profile['files'].items():
        path = ROOT/relative
        assert path.resolve().is_relative_to(ROOT), 'OWNER_V2_RESOURCE_SCOPE'
        assert digest(canonical_bytes(path,entry['binary'])) == entry['sha256'], relative
    # These are pre-existing externally pinned feature fingerprints, not hashes
    # minted from the code under test. A changed renderer fails before collection.
    for name,entry in profile['reporting_files'].items():
        path = ROOT/'vrae/reporting'/name
        assert digest(canonical_bytes(path)) == entry['sha256'], name
    expected = profile['frozen_code_identity']
    submitted = os.environ.get('VRAE_RA3C_QA_V2_CANDIDATE_SHA')
    assert submitted in (None,expected), 'OWNER_V2_FOREIGN_CODE_IDENTITY'
    original = json.loads((ROOT/profile['observation_source']).read_text(encoding='utf-8'))
    assert original['candidate_sha'] == expected and original['not_customer_approval']
    relocated = deepcopy(original)
    browser = ROOT/profile['browser_dir']
    transported = []

    def image_path(old,expected_hash,pointer):
        name = PureWindowsPath(old).name
        path = browser/name
        assert path.relative_to(ROOT).as_posix() in profile['files']
        assert digest(path.read_bytes()) == expected_hash, 'OWNER_V2_SCREENSHOT_INTEGRITY'
        transported.append(pointer)
        return str(path)

    for width,view in relocated['viewports'].items():
        view['screenshot_path'] = image_path(view['screenshot_path'],view['screenshot_sha256'],
            '/viewports/'+width+'/screenshot_path')
    comp = relocated['business_review']['value_memo']['comparison']
    comp['zero_screenshot_path'] = image_path(comp['zero_screenshot_path'],comp['zero_screenshot_sha256'],
        '/business_review/value_memo/comparison/zero_screenshot_path')
    # Round trip proves that no metric, code identity, judgement, hash, approval
    # state or oracle was changed while making filesystem references portable.
    restored = deepcopy(relocated)
    for width in restored['viewports']:
        restored['viewports'][width]['screenshot_path'] = original['viewports'][width]['screenshot_path']
    restored['business_review']['value_memo']['comparison']['zero_screenshot_path'] = \
        original['business_review']['value_memo']['comparison']['zero_screenshot_path']
    assert restored == original and len(transported) == 3
    destination = Path(tempfile.mkdtemp(prefix='vrae-owner-v2-inputs-'))/'observations.json'
    destination.write_text(json.dumps(relocated,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    os.environ['VRAE_RA3C_QA_V2_CANDIDATE_SHA'] = expected
    os.environ['VRAE_RA3C_QA_V2_OBSERVATIONS_PATH'] = str(destination)
    _receipt = dict(version=profile['version'],profile_sha256=PROFILE_SHA256,
        frozen_code_identity=expected,source_sha256=profile['v2_module_sha256'],
        source_path=profile['v2_module'],verified_evidence_members=len(profile['files']),
        observation_stage=profile['trusted_browser_stage'],browser_run_during_collection=False,
        transported_json_pointers=transported,historical_v1_omitted_from_default=64,
        frozen_oracles_modified=False,github_checkout_sha=os.environ.get('GITHUB_SHA'),
        approved_browser_receipt_sha256=digest(canonical_bytes(ROOT/profile['observation_source'])))
    (destination.parent/'transport-receipt.json').write_text(json.dumps(_receipt,indent=2)+'\n',encoding='utf-8')
    return _receipt


def load_frozen_suite():
    info = configure()
    path = ROOT/info['source_path']
    assert digest(canonical_bytes(path)) == info['source_sha256']
    spec = importlib.util.spec_from_file_location('owner_frozen_ra3c_v2_unmodified',path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ActualReports:
    """Observe real pytest reports only; never change outcome or selection."""
    def __init__(self,nodeids):
        self.nodeids = set(nodeids)
        self.calls = {}
        self.problems = []

    def pytest_runtest_logreport(self,report):
        if report.nodeid in self.nodeids:
            if report.when == 'call':
                self.calls[report.nodeid] = report.outcome
            if report.failed or report.skipped:
                self.problems.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome))


@contextmanager
def actual_collection_receipt(request,suite):
    items = [item for item in request.session.items if item.module is request.module]
    primary = [item for item in items if item.obj is suite.test_owner_adjudicated_business_objective]
    denials = [item for item in items if item.obj is suite.test_companion_original_invalid_request_denial]
    assert len(items) == 118 and len(primary) == 64 and len(denials) == 54
    assert {item.callspec.params['case']['id'] for item in primary} == {c['id'] for c in suite.CASES}
    assert {item.callspec.params['denial']['id'] for item in denials} == {d['id'] for d in suite.DENIALS}
    assert request.module.subject is suite.subject, 'FROZEN_FIXTURE_IDENTITY_CHANGED'
    terminal = request.config.pluginmanager.getplugin('terminalreporter')
    info = dict(configure(),primary_collected=64,denials_collected=54,
        primary_ids=[item.callspec.params['case']['id'] for item in primary],
        denial_ids=[item.callspec.params['denial']['id'] for item in denials])
    terminal.write_line('OWNER_RA3C_V2_ACTUAL_COLLECTION '+json.dumps(info,sort_keys=True))
    reports = ActualReports([item.nodeid for item in items])
    request.config.pluginmanager.register(reports,'owner-ra3c-v2-read-only-report-receipt')
    try:
        yield
    finally:
        result = dict(source_sha256=info['source_sha256'],actual_call_reports=reports.calls,
            setup_or_call_problems=reports.problems,primary_count=64,denial_count=54)
        # Teardown runs under pytest capture. Disable capture solely while
        # publishing this read-only receipt, so ordinary -q CI retains it.
        capture = request.config.pluginmanager.getplugin('capturemanager')
        with capture.global_and_fixture_disabled():
            terminal.write_line('OWNER_RA3C_V2_ACTUAL_CALL_REPORTS '+json.dumps(result,sort_keys=True))
        request.config.pluginmanager.unregister(reports)
        assert len(reports.calls) == 118 and set(reports.calls.values()) == {'passed'} and not reports.problems
