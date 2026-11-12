"""D1: read accepted Git bytes and replay native sources before any D2 code exists."""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.interpretation import GuardResult
from vrae.reporting import ReportDraft, build_draft, render
from vrae.domain.reviews import report_content_hash

BASE = 'e40201bf399cc8c5d11a708fcbe33c31f01e67b2'
HERE = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def main():
    rows = []
    prefixes = ('vrae/', 'contracts/', 'tests/', 'docs/03-engineering/ra3d-phase0/')
    for line in git('ls-tree', '-r', BASE).decode().splitlines():
        meta, path = line.split('\t')
        if path.startswith(prefixes):
            blob = meta.split()[-1]
            assert git('hash-object', '--path=' + path, path).decode().strip() == blob, path
            raw = git('show', BASE + ':' + path)
            rows.append({'path': path, 'git_blob': blob, 'git_sha256': sha(raw)})
    sources = json.loads(git('show', BASE + ':tests/reporting/fixtures/sources.json'))
    held = json.loads(git('show', BASE + ':tests/reporting/fixtures/caller-pins.json'))
    output = {'accepted_main': BASE, 'source_blobs': rows, 'cases': {}}
    for case in ('404', '200'):
        s, h = sources[case], held[case]
        pins = h['pins']
        pack = EvidencePack.load(s['pack'], {k: base64.b64decode(v, validate=True)
            for k, v in s['objects_base64'].items()}, expected_ref=pins['expected_pack_ref'])
        keys = ('expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
                'expected_builder_version', 'expected_evaluator_version')
        package = FindingPackage.load(s['package'], pack, **{k: pins[k] for k in keys})
        guards = [GuardResult.load(b['guard'], b['interpretation'], b['bindings'], pack, package,
            expected_guard_ref=ref, **{k: pins[k] for k in
            keys + ('expected_scope', 'expected_guard_version')})
            for b, ref in zip(s['guard_inputs'], pins['expected_guard_refs'])]
        draft = build_draft(pack, package, s['guard_inputs'], s['metadata'], **pins)
        d = draft.document
        assert draft.ref == h['expected_draft_ref']
        assert sha(draft.html_bytes) == h['expected_html_sha256']
        assert len(d['issues']) == h['expected_issue_count'] == (1 if case == '404' else 0)
        assert ReportDraft.load(d, draft.html_bytes, pack, package, s['guard_inputs'], s['metadata'],
            expected_draft_ref=h['expected_draft_ref'], **pins)._payload == draft._payload
        assert render(d, draft.html_bytes, pack, package, s['guard_inputs'], s['metadata'],
                      expected_draft_ref=h['expected_draft_ref'], **pins) == draft.html_bytes
        native = d['native_report_version']
        if case == '404':
            assert native['content_hash'] == report_content_hash(native, [i['finding'] for i in d['issues']])
            assert native['status'] == 'REVIEW_REQUIRED' and native['approved_by'] is None
        else:
            assert native is None
        assert d['private'] is True and d['approval_status'] == 'NOT_APPROVED'
        assert d['shareable'] is False and d['semantic_approval'] is False
        for issue in d['issues']:
            f = issue['fact_claim']['fact']['source']
            resolved = pack.resolve(f['citation']['evidence_ref'], expected_pack_ref=pack.ref)
            assert resolved['content'][f['byte_start']:f['byte_end']] == f['quote'].encode('utf-8')
            assert issue['target_response']['http_status'] == int(case)
        record = {'source': s, 'held': {**h, 'expected_payload_sha256': sha(draft._payload)}}
        fixture = ROOT / 'tests/reviewing/fixtures' / (case + '.json')
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_bytes(encode(record) + b'\n')
        (HERE / (case + '.draft.json')).write_bytes(draft._payload)
        (HERE / (case + '.html')).write_bytes(draft.html_bytes)
        output['cases'][case] = {'status': 'D1_NATIVE_REPLAY_PASS', 'pins': h,
            'payload_sha256': sha(draft._payload), 'fixture_sha256': sha(encode(record) + b'\n'),
            'native_h0': native['content_hash'] if native else None,
            'guard_refs': [g.ref for g in guards], 'source_keys': list(pack.document['sources'][0]['document']),
            'native_bytes_unchanged': True, 'actual_human_approvals': 0}
    (HERE / ('D1-python' + str(sys.version_info.major) + str(sys.version_info.minor) + '.json')).write_bytes(
        encode({**output, 'python': sys.version}) + b'\n')
    print(json.dumps({'python': sys.version, 'cases': output['cases']}, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
