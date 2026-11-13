"""Accepted native replay adapter; no new evidence/Guard engine or trusted rehash."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from vrae.evidence import EvidencePack
from vrae.findings import FindingPackage
from vrae.interpretation import GuardResult
from vrae.reporting import ReportDraft, build_draft, render
from .contracts import ConsoleError, canonical, refuse

ROOT = Path(__file__).resolve().parents[2]
_PIN_FILE = Path(__file__).with_name('native-pins.json')


class NativeVerifier:
    """Expected values are separately held fixture pins, never task/body supplied."""
    def __init__(self):
        self._holds = json.loads(_PIN_FILE.read_text(encoding='utf-8'))

    def held(self, case):
        if case not in ('404', '200'):
            refuse('SOURCE_INTEGRITY')
        return deepcopy(self._holds['cases'][case]['held'])

    def prepare(self, case, source):
        try:
            held = self.held(case)
            pins = held['pins']
            if hashlib.sha256(canonical(source)).hexdigest() != self._holds['cases'][case]['source_sha256']:
                refuse('SOURCE_INTEGRITY')
            pack = EvidencePack.load(source['pack'], {k: base64.b64decode(v, validate=True)
                for k,v in source['objects_base64'].items()}, expected_ref=pins['expected_pack_ref'])
            package = FindingPackage.load(source['package'], pack, **{k:pins[k] for k in (
                'expected_pack_ref', 'expected_execution_ref', 'expected_package_ref',
                'expected_builder_version', 'expected_evaluator_version')})
            for bundle, ref in zip(source['guard_inputs'], pins['expected_guard_refs']):
                GuardResult.load(bundle['guard'], bundle['interpretation'], bundle['bindings'], pack, package,
                    expected_guard_ref=ref, **{k:pins[k] for k in (
                    'expected_pack_ref','expected_execution_ref','expected_package_ref','expected_builder_version',
                    'expected_evaluator_version','expected_scope','expected_guard_version')})
            built = build_draft(pack, package, source['guard_inputs'], source['metadata'], **pins)
            if (built.ref != held['expected_draft_ref'] or built.document['html_sha256'] != held['expected_html_sha256']
                    or len(built.document['issues']) != held['expected_issue_count']):
                refuse('SOURCE_INTEGRITY')
            loaded = ReportDraft.load(built.document, built.html_bytes, pack, package, source['guard_inputs'],
                source['metadata'], expected_draft_ref=held['expected_draft_ref'], **pins)
            raw = render(loaded.document, loaded.html_bytes, pack, package, source['guard_inputs'],
                source['metadata'], expected_draft_ref=held['expected_draft_ref'], **pins)
            if raw != built.html_bytes or hashlib.sha256(raw).hexdigest() != held['expected_html_sha256']:
                refuse('SOURCE_INTEGRITY')
            return self._present(loaded, raw, pack, package, source, held)
        except ConsoleError:
            raise
        except Exception:
            raise ConsoleError('SOURCE_INTEGRITY') from None

    def load_original(self, case, artifacts):
        """Load the actual verified database snapshot; never generate a new draft."""
        try:
            held = self.held(case)
            pins = held['pins']
            raw_source = artifacts[('SOURCE','source')]
            if hashlib.sha256(raw_source).hexdigest() != self._holds['cases'][case]['source_sha256']:
                refuse('SOURCE_INTEGRITY')
            source = json.loads(raw_source)
            pack = EvidencePack.load(source['pack'], {k: base64.b64decode(v, validate=True)
                for k,v in source['objects_base64'].items()}, expected_ref=pins['expected_pack_ref'])
            package = FindingPackage.load(source['package'], pack, **{k:pins[k] for k in (
                'expected_pack_ref','expected_execution_ref','expected_package_ref',
                'expected_builder_version','expected_evaluator_version')})
            document, raw = artifacts[('DRAFT','draft')], artifacts[('HTML','html')]
            loaded = ReportDraft.load(json.loads(document), raw, pack, package, source['guard_inputs'],
                source['metadata'], expected_draft_ref=held['expected_draft_ref'], **pins)
            if loaded._payload != document or hashlib.sha256(raw).hexdigest() != held['expected_html_sha256']:
                refuse('SOURCE_INTEGRITY')
            result = self._present(loaded, raw, pack, package, source, held)
            result['public_calls'] = ['TestOnlyPrivateBytes.read','verify','EvidencePack.load',
                                      'FindingPackage.load','ReportDraft.load']
            return result
        except ConsoleError:
            raise
        except Exception:
            raise ConsoleError('SOURCE_INTEGRITY') from None

    def _present(self, loaded, raw, pack, package, source, held):
        pins = held['pins']
        d = loaded.document
        if not d['private'] or d['shareable'] or d['approval_status'] != 'NOT_APPROVED':
            refuse('SOURCE_INTEGRITY')
        claims = []
        for i, issue in enumerate(d['issues']):
            claims.append((f'/issues/{i}/fact_claim',issue['fact_claim']))
            claims.extend((f'/issues/{i}/proposals/{k}',issue['proposals'][k]) for k in ('impact','action','recheck'))
        claims.extend((f'/positive_source_claims/{i}',c) for i,c in enumerate(d['positive_source_claims']))
        evidence = []
        for pointer, claim in claims:
            f = claim['fact']['source']
            resolved = pack.resolve(f['citation']['evidence_ref'], expected_pack_ref=held['pins']['expected_pack_ref'])
            body = resolved['content']
            if (body is None or body[f['byte_start']:f['byte_end']] != f['quote'].encode('utf-8')
                    or resolved['evidence']['source_ref'] != f['citation']['source_ref']):
                refuse('SOURCE_INTEGRITY')
            evidence.append({'pointer':pointer,'claim':claim,'citation':f['citation'],
                'byte_start':f['byte_start'],'byte_end':f['byte_end'],'quote':f['quote'],
                'body':body.decode('utf-8'),'body_sha256':hashlib.sha256(body).hexdigest(),
                'evidence':resolved['evidence']})
        # Rule-only 200 CTA citation is real, but has no RA3B CTA claim. Do not invent one.
        row = next(r['observations'][0] for r in package.document['rule_execution']['executions'] if r['rule_id']=='CTA-02')
        cite = row['citations'][0]
        captured = pack.resolve(cite['evidence_ref'], expected_pack_ref=pins['expected_pack_ref'])
        capture_source = {'citation': cite, 'evidence': captured['evidence'],
            'body': captured['content'].decode('utf-8'),
            'body_sha256': hashlib.sha256(captured['content']).hexdigest()}
        return {'dto_version':'operator-console-dossier-0.1','document':d,'held':held,
                '_artifacts':{'document':loaded._payload,'html':raw},
                'evidence':evidence,'contact_capture':row,'capture_source':capture_source,
                'public_calls':['EvidencePack.load','FindingPackage.load','GuardResult.load',
                                'build_draft','ReportDraft.load','render']}
