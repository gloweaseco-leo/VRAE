"""Private, bounded observations. A hash checks consistency, not remote truth."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from vrae.collection.errors import CollectionError
from vrae.collection.manifest import document_hash, sha256, _verify_trace

VIEWPORTS = ({'name': 'desktop', 'width': 1280, 'height': 720, 'mobile': False},
             {'name': 'mobile', 'width': 390, 'height': 844, 'mobile': True})


@dataclass
class BrowserBundle:
    manifest: dict
    objects: dict[str, bytes]

    def verify(self):
        import json
        schema = json.loads((Path(__file__).parents[2] /
            'contracts/v1/browser/BrowserObservation.schema.json').read_text())
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(self.manifest)
        doc = {k:v for k,v in self.manifest.items() if k != 'sha256'}
        if document_hash(doc) != self.manifest['sha256']:
            raise CollectionError('EVIDENCE_INTEGRITY')
        referenced = set()
        seen = set()
        for item in doc['observations']:
            key = (item['url'], item['viewport']['name'])
            if key in seen or item['url'] not in doc['approved_urls'] or item['viewport'] not in VIEWPORTS:
                raise CollectionError('EVIDENCE_INTEGRITY')
            seen.add(key)
            datetime.fromisoformat(item['observed_at'])
            if item['status'] == 'OBSERVED' and (not item['dom_ref'] or not item['screenshot_ref']
                    or item['errors'] or any(r['outcome'] != 'FETCHED' for r in item['resources'])
                    or not any(r['url'] == item['url'] and r['resource_type'] == 'Document'
                               and r['outcome'] == 'FETCHED' for r in item['resources'])):
                raise CollectionError('EVIDENCE_INTEGRITY')
            for resource in item['resources']:
                if resource['outcome'] == 'FETCHED':
                    hops = resource['redirect_trace']
                    if (resource['method'] not in ('GET', 'HEAD') or resource['error'] is not None
                            or resource['sha256'] is None or not hops):
                        raise CollectionError('EVIDENCE_INTEGRITY')
                    _verify_trace(hops, resource['url'], hops[-1]['url'], 200)
                elif resource['sha256'] is not None:
                    raise CollectionError('EVIDENCE_INTEGRITY')
            for field in ('dom_ref', 'screenshot_ref'):
                ref = item[field]
                if ref is not None:
                    if ref not in self.objects or sha256(self.objects[ref]) != ref:
                        raise CollectionError('EVIDENCE_INTEGRITY')
                    referenced.add(ref)
        if referenced != set(self.objects):
            raise CollectionError('EVIDENCE_INTEGRITY')


def seal(broker, run_id, renderer, observations, objects):
    access = broker.budget.access
    doc = {'schema_version': '1.0', 'tenant_id': access.audit['tenant_id'], 'run_id': run_id,
           'policy_id': access.audit['source_policy_ref'], 'policy_version': access.audit['source_policy_version'],
           'approved_urls': list(broker.urls), 'renderer': renderer, 'private': True,
           'observations': observations, 'verification_limit': 'Consistency only; not signed provenance or diagnosis.'}
    doc['sha256'] = document_hash(doc)
    bundle = BrowserBundle(doc, objects)
    bundle.verify()
    return bundle
