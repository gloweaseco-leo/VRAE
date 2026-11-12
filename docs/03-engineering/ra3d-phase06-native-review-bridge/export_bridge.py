"""Replay accepted, caller-pinned native synthetic inputs; export read-only displays.

No fixture freeze, network, model, approval, native decision or sharing operation.
"""
import sys
sys.dont_write_bytecode = True
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = '696d4ae695041f0eeefa56d22039682a989380b2'
PREFIX = 'docs/03-engineering/ra3d-phase06-native-review-bridge/'
sys.path.insert(0, str(ROOT))


class BridgeRefusal(ValueError):
    """Display/held-pin refusal, distinct from native validation errors."""


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def held_file(name):
    return git('show', BASE + ':' + name)


def assert_(condition, code):
    if not condition:
        raise BridgeRefusal(code)


def source_provenance():
    rows = []
    for line in git('ls-tree', '-r', '--full-tree', BASE).decode().splitlines():
        meta, name = line.split('\t')
        if name.startswith(('vrae/', 'contracts/', 'tests/reporting/fixtures/')):
            expected = meta.split()[-1]
            actual = git('hash-object', '--path=' + name, name).decode().strip()
            assert_(actual == expected, 'ACCEPTED_SOURCE_WORKTREE_MISMATCH')
            rows.append({'path': name, 'git_blob_sha': expected,
                         'git_bytes_sha256': sha(held_file(name)),
                         'local_bytes_sha256': sha((ROOT / name).read_bytes())})
    return rows


# Verify the exact local production tree before importing from this worktree.
PROVENANCE = source_provenance()
from vrae.evidence import EvidencePack  # noqa: E402
from vrae.evidence.pack import EvidenceError  # noqa: E402
from vrae.findings import FindingPackage  # noqa: E402
from vrae.findings.builder import FindingError  # noqa: E402
from vrae.interpretation import GuardResult  # noqa: E402
from vrae.interpretation.guard import GuardError  # noqa: E402
from vrae.reporting import ReportDraft, build_draft, render  # noqa: E402
from vrae.reporting.common import ReportError  # noqa: E402

SOURCES_RAW = held_file('tests/reporting/fixtures/sources.json')
PINS_RAW = held_file('tests/reporting/fixtures/caller-pins.json')
SOURCES, PINS = json.loads(SOURCES_RAW), json.loads(PINS_RAW)
FINDING_PINS = ('expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
                'expected_builder_version', 'expected_evaluator_version')
GUARD_PINS = FINDING_PINS + ('expected_scope', 'expected_guard_version')


def inputs(case):
    return deepcopy(SOURCES[case]), deepcopy(PINS[case])


def replay(case, source=None, held=None, document=None, html=None):
    source = deepcopy(SOURCES[case]) if source is None else source
    held = deepcopy(PINS[case]) if held is None else held
    pins = held['pins']
    objects = {k: base64.b64decode(v, validate=True) for k, v in source['objects_base64'].items()}
    pack = EvidencePack.load(source['pack'], objects, expected_ref=pins['expected_pack_ref'])
    package = FindingPackage.load(source['package'], pack, **{k: pins[k] for k in FINDING_PINS})
    guards = [GuardResult.load(b['guard'], b['interpretation'], b['bindings'], pack, package,
              expected_guard_ref=ref, **{k: pins[k] for k in GUARD_PINS})
              for b, ref in zip(source['guard_inputs'], pins['expected_guard_refs'])]
    draft = build_draft(pack, package, source['guard_inputs'], source['metadata'], **pins)
    assert_(draft.ref == held['expected_draft_ref'], 'HELD_DRAFT_REF_MISMATCH')
    assert_(sha(draft.html_bytes) == held['expected_html_sha256'], 'HELD_HTML_SHA_MISMATCH')
    assert_(len(draft.document['issues']) == held['expected_issue_count'], 'HELD_ISSUE_COUNT_MISMATCH')
    doc = draft.document if document is None else document
    raw = draft.html_bytes if html is None else html
    loaded = ReportDraft.load(doc, raw, pack, package, source['guard_inputs'], source['metadata'],
                              expected_draft_ref=held['expected_draft_ref'], **pins)
    rendered = render(doc, raw, pack, package, source['guard_inputs'], source['metadata'],
                      expected_draft_ref=held['expected_draft_ref'], **pins)
    assert_(rendered == loaded.html_bytes == draft.html_bytes, 'NATIVE_BYTES_DIFFER')
    assert_(doc['private'] is True and doc['approval_status'] == 'NOT_APPROVED'
            and doc['shareable'] is False and doc['semantic_approval'] is False, 'PRIVATE_STATUS')
    return pack, package, guards, loaded


def resolve(pack, citation, start=None, end=None, quote=None):
    r = pack.resolve(citation['evidence_ref'], expected_pack_ref=pack.ref)
    raw = r['content']
    assert_(isinstance(raw, bytes), 'RAW_SOURCE_NOT_RETAINED')
    assert_(r['evidence']['source_ref'] == citation['source_ref']
            and r['evidence']['snapshot_ref'] == citation['snapshot_ref'], 'CITATION_SCOPE_MISMATCH')
    if start is None:
        # 200 CTA PASS has a rule citation, but deliberately no RA3B CTA fact.
        # Resolve the recorded line/column against held bytes, not a fake Guard.
        text = raw.decode('utf-8-sig')
        offset = sum(len(s) + 1 for s in text.split('\n')[:citation['line'] - 1]) + citation['column']
        close = text.index('>', offset) + 1
        quote = text[offset:close]
        start = len(text[:offset].encode('utf-8')) + (3 if raw.startswith(b'\xef\xbb\xbf') else 0)
        end = start + len(quote.encode('utf-8'))
    assert_(type(start) is int and type(end) is int and 0 <= start < end <= len(raw), 'BYTE_RANGE_INVALID')
    assert_(raw[start:end] == quote.encode('utf-8'), 'QUOTE_BYTE_MISMATCH')
    return {'citation': citation, 'evidence': r['evidence'], 'byteRange': [start, end],
            'quote': quote, 'sourceSha256': sha(raw), 'bodyBase64': base64.b64encode(raw).decode(),
            'source': raw.decode('utf-8'), 'sourceRef': citation['source_ref'],
            'sourceId': citation['evidence_ref'], 'sourceUrl': citation['url']}


def project(case, pack, package, guards, draft):
    d = draft.document
    claims = []
    if d['issues']:
        issue = d['issues'][0]
        selected = [('/issues/0/fact_claim', issue['fact_claim'])] + [
            ('/issues/0/proposals/' + k, issue['proposals'][k]) for k in ('impact', 'action', 'recheck')]
    else:
        selected = []
    selected += [(f'/positive_source_claims/{i}', c) for i, c in enumerate(d['positive_source_claims'])]
    for pointer, claim in selected:
        # Reconcile each displayed statement against actual independently loaded Guard claims.
        bundle = next(b for b in SOURCES[case]['guard_inputs'] if b['guard']['guard_ref'] == claim['guard_ref'])
        matching = next(c for g in guards if g.ref == claim['guard_ref'] for c in g.document['claims']
                        if c['binding_ref'] == claim['binding_ref'] and c['pointer'] == claim['pointer'])
        binding = next(b for b in bundle['bindings'] if b['binding_ref'] == claim['binding_ref'])
        assert_(binding['text'] == claim['text'] and binding['fact'] == claim['fact']
                and matching['status'] == claim['status'], 'DISPLAY_CLAIM_MISMATCH')
        f = claim['fact']['source']
        claims.append({'documentPointer': pointer, 'claim': claim,
                       'source': resolve(pack, f['citation'], f['byte_start'], f['byte_end'], f['quote'])})
    row = next(r['observations'][0] for r in package.document['rule_execution']['executions']
               if r['rule_id'] == 'CTA-02')
    citation = row['citations'][0]
    main_source = resolve(pack, citation)
    if case == '404':
        claim = d['issues'][0]['fact_claim']
        assert_(main_source['quote'] == claim['fact']['source']['quote'], 'CTA_QUOTE_DIFFER')
        binding_ref, guard_ref = claim['binding_ref'], claim['guard_ref']
    else:
        binding_ref = guard_ref = None  # Absence is explicit, never invented.
        assert_(not d['issues'] and d['native_report_version'] is None, 'ZERO_IS_NOT_REPORT')
    main_source.update({'href': citation['raw_href'], 'targetUrl': row['target_response']['url'],
                        'capturedAt': citation['observed_at'], 'sourceHttp': row['source_page']['http_status'],
                        'targetHttp': row['target_response']['http_status'],
                        'bindingRef': binding_ref, 'guardRef': guard_ref,
                        'captureRow': row, 'evidenceRef': citation['evidence_ref']})
    return {'display_schema': 'native-review-display-0.6.1', 'case': case,
            'acceptedSourceSha': BASE, 'native_document': d, 'held': PINS[case],
            'source': main_source, 'shownClaims': claims,
            'native_html_path': f'dossiers/contact-{case}.html',
            'native_json_path': f'dossiers/contact-{case}.draft.json',
            'bridgeLimit': 'READ_ONLY_PROJECTION_NOT_REVIEW_TARGET_NOT_AUTHORIZATION',
            'scopeFields': {'recordedCoverage': d['recorded_coverage'], 'buyerJourney': d['buyer_journey'],
                            'examinedPages': d['examined_pages'], 'limitations': d['limitations']}}


def negative_attempts(positives, attempts):
    def attempt(name, case, mutate, layer='NATIVE_REPLAY'):
        source, held = inputs(case)
        doc, html = deepcopy(positives[case][3].document), positives[case][3].html_bytes
        original_pins = encode(held)
        try:
            source, held, doc, html = mutate(source, held, doc, html)
            replay(case, source, held, doc, html)
        except (EvidenceError, FindingError, GuardError, ReportError, BridgeRefusal) as exc:
            attempts.append({'id': name, 'case': case, 'status': 'REFUSED', 'layer': layer,
                             'error_type': type(exc).__name__, 'error': str(exc),
                             'original_held_pins': json.loads(original_pins), 'attempted_held_pins': held,
                             'mutated_source_sha256': sha(encode(source)),
                             'mutated_document_sha256': sha(encode(doc)), 'mutated_html_sha256': sha(html)})
        else:
            attempts.append({'id': name, 'case': case, 'status': 'FAIL_ACCEPTED_INVALID'})
            raise AssertionError('INVALID_INPUT_ACCEPTED_' + name)
    def change(fn):
        def apply(s, h, d, raw):
            fn(s, h, d)
            return s, h, d, raw
        return apply
    def source_byte(s, h, d):
        key = next(iter(s['objects_base64']))
        raw = base64.b64decode(s['objects_base64'][key])
        s['objects_base64'][key] = base64.b64encode(bytes([raw[0] ^ 1]) + raw[1:]).decode()
    def b0(s):
        return s['guard_inputs'][0]['bindings'][0]
    attempt('N01_SOURCE_BYTE', '404', change(source_byte))
    attempt('N02_QUOTE', '404', change(lambda s,h,d: b0(s)['fact']['source'].__setitem__('quote', 'forged')))
    attempt('N03_UTF8_OFFSET', '404', change(lambda s,h,d: b0(s)['fact']['source'].__setitem__('byte_start',159)))
    attempt('N04_HELD_PACK_REF', '404', change(lambda s,h,d: h['pins'].__setitem__('expected_pack_ref','ep-'+'0'*64)))
    attempt('N05_HELD_GUARD_REF', '404', change(lambda s,h,d: h['pins']['expected_guard_refs'].__setitem__(0,'cg-'+'0'*64)))
    attempt('N06_HELD_DRAFT_REF', '404', change(lambda s,h,d: h.__setitem__('expected_draft_ref','rd-'+'0'*64)), 'BRIDGE_HELD_DRAFT_PIN')
    attempt('N07_HELD_HTML_SHA', '404', change(lambda s,h,d: h.__setitem__('expected_html_sha256','0'*64)), 'BRIDGE_HELD_HTML_PIN')
    attempt('N08_TENANT_SCOPE', '404', change(lambda s,h,d: h['pins']['expected_scope'].__setitem__('tenant_id','tenant-foreign')))
    attempt('N09_CITATION_SCOPE', '404', change(lambda s,h,d: b0(s)['fact']['source']['citation'].__setitem__('source_ref','src-'+'0'*64)))
    attempt('N10_NOT_RUN_GUARD', '404', change(lambda s,h,d: s['guard_inputs'][0]['interpretation'].__setitem__('status','NOT_RUN')))
    attempt('N11_REJECTED_GUARD', '404', change(lambda s,h,d: s['guard_inputs'][0]['guard']['claims'][0].__setitem__('status','REJECTED')))
    attempt('N12_UNAPPROVED_PROSE', '404', change(lambda s,h,d: s['guard_inputs'][1]['interpretation']['hypotheses'].__setitem__(0,'已证明导致收入损失')))
    attempt('N13_HTML_BYTES', '404', lambda s,h,d,raw: (s,h,d,raw+b' '))
    attempt('N14_VERSION', '404', change(lambda s,h,d: s['metadata'].__setitem__('version',2)))
    attempt('N15_ZERO_AS_ISSUE', '200', change(lambda s,h,d: d['issues'].append(deepcopy(positives['404'][3].document['issues'][0]))))
    attempt('N16_RENDERER_VERSION', '404', change(lambda s,h,d: h['pins'].__setitem__('expected_renderer_version','unapproved-renderer')))
    attempt('N17_NATIVE_HASH', '404', change(lambda s,h,d: d['native_report_version'].__setitem__('content_hash','0'*64)))
    attempt('N18_FOREIGN_PACKAGE', '404', change(lambda s,h,d: s.__setitem__('package',deepcopy(SOURCES['200']['package']))))
    return attempts


def main():
    out = HERE / 'dossiers'
    evidence = HERE / 'evidence'
    out.mkdir(exist_ok=True)
    evidence.mkdir(exist_ok=True)
    projections, positive = {}, {}
    result = {'status': 'NOT_PASS', 'acceptedSourceSha': BASE, 'command': sys.argv,
              'python': sys.version, 'positives': [], 'negatives': []}
    try:
        for case in ('404', '200'):
            p, f, g, d = replay(case)
            positive[case] = (p, f, g, d)
            projections[case] = project(case, p, f, g, d)
            (out / f'contact-{case}.html').write_bytes(d.html_bytes)
            (out / f'contact-{case}.draft.json').write_bytes(encode(d.document))
            (out / f'contact-{case}.display.json').write_bytes(encode(projections[case]))
            (out / f'contact-{case}.held-inputs.json').write_bytes(encode(SOURCES[case]))
            (out / f'contact-{case}.held-pins.json').write_bytes(encode(PINS[case]))
            result['positives'].append({'case': case, 'status': 'PASS', 'public_calls': ['EvidencePack.load',
                'FindingPackage.load', 'GuardResult.load', 'build_draft', 'ReportDraft.load', 'render'],
                'draft_ref': d.ref, 'html_sha256': sha(d.html_bytes), 'issue_count': len(d.document['issues']),
                'native_report_version': d.document['native_report_version'],
                'source_byte_range': projections[case]['source']['byteRange'],
                'shown_claim_count': len(projections[case]['shownClaims']),
                'original_held_pins': PINS[case]})
        negative_attempts(positive, result['negatives'])
        module_paths = {name: str(Path(module.__file__).resolve()) for name,module in sys.modules.copy().items()
                        if name.startswith('vrae') and getattr(module,'__file__',None)}
        assert_(all(Path(v).is_relative_to(ROOT / 'vrae') for v in module_paths.values()), 'FOREIGN_MODULE_IMPORT')
        result.update({'status': 'NATIVE_REPLAY_AND_REFUSAL_PASS', 'provenance': PROVENANCE,
                       'imported_module_paths': module_paths, 'actual_approvals': 0, 'actual_shares': 0})
        (HERE / 'dossier-data.js').write_text('window.NATIVE_DOSSIERS = '+encode(projections).decode()+';\n',encoding='utf-8')
        (evidence / 'held-caller-pins.git-bytes.json').write_bytes(PINS_RAW)
    except Exception as exc:
        result['execution_error'] = {'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        raise
    finally:
        # Unique run records preserve every actual failure; dossiers only after native replay.
        import datetime
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        (evidence / f'export-{stamp}.json').write_bytes(encode(result))
        print(json.dumps({'status':result['status'],'positives':len(result['positives']),
                          'refused':len(result['negatives']),'evidence':f'export-{stamp}.json'},ensure_ascii=False))


if __name__ == '__main__':
    main()
