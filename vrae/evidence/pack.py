"""Content-addressed projection with replayed source verification, not provenance signatures."""
from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from vrae.browser.observation import BrowserBundle, VIEWPORTS
from vrae.collection.manifest import CaptureBundle, document_hash, sha256
from vrae.collection.policy import canonical_url

LIMITATIONS = (
    'CONSISTENCY_NOT_SIGNED_PROVENANCE', 'NO_BUSINESS_OR_COMPLETENESS_ASSERTION',
    'PRIVATE_URL_DOM_SCREENSHOT_MAY_CONTAIN_PII', 'NO_CURRENT_POLICY_AUTHORIZATION_CHECK',
)
SCOPE = ('tenant_id', 'run_id', 'policy_id', 'policy_version')


class EvidenceError(ValueError):
    """Safe vocabulary; never return page text or URLs in error messages."""


def _fail():
    raise EvidenceError('EVIDENCE_INTEGRITY')


def _encode(doc: dict) -> bytes:
    return json.dumps(doc, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _source(bundle: CaptureBundle | BrowserBundle) -> tuple[dict, dict[str, bytes]]:
    kind = 'CaptureManifest' if isinstance(bundle, CaptureBundle) else 'BrowserObservation'
    if not isinstance(bundle, (CaptureBundle, BrowserBundle)):
        _fail()
    # Copy mutable inputs before verification. Source objects are immutable bytes.
    doc = json.loads(_encode(bundle.manifest))
    objects = dict(bundle.objects)
    if any(not isinstance(body, bytes) for body in objects.values()):
        _fail()
    clone = CaptureBundle(doc, objects) if kind == 'CaptureManifest' else BrowserBundle(doc, objects)
    clone.verify()
    digest = document_hash(doc)
    return {'source_ref': 'src-' + digest, 'kind': kind, 'schema_version': doc['schema_version'],
            'document_sha256': digest, 'document': doc,
            'object_refs': {k: sha256(v) for k, v in sorted(objects.items())}}, {
                sha256(v): v for v in objects.values()}


def _project(sources: list[dict], blobs: Mapping[str, bytes]) -> dict:
    if not 1 <= len(sources) <= 16 or len(blobs) > 512:
        _fail()
    if sum(len(v) for v in blobs.values()) > 64_000_000:
        _fail()
    if any(not isinstance(v, bytes) or sha256(v) != k for k, v in blobs.items()):
        _fail()
    normalized, snapshots, evidence, coverage = [], [], [], []
    source_ids: set[str] = set()
    page_keys: set[tuple] = set()
    original_ids: set[tuple] = set()
    used_blobs: set[str] = set()
    scope = None
    site_hosts: set[str | None] = set()

    def check_page(url):
        # SourceAccess bounds an audited site by exact canonical hostname, not
        # registrable domain or a shared policy ID. This is not authorization.
        if canonical_url(url) != url:
            _fail()
        site_hosts.add(urlsplit(url).hostname)
        if len(site_hosts) != 1:
            _fail()

    for source in sources:
        doc = source['document']
        objects = {k: blobs[v] for k, v in source['object_refs'].items()}
        if source['kind'] == 'CaptureManifest':
            bundle: CaptureBundle | BrowserBundle = CaptureBundle(doc, objects)
        elif source['kind'] == 'BrowserObservation':
            bundle = BrowserBundle(doc, objects)
        else:
            _fail()
        rebuilt, _ = _source(bundle)
        if source != rebuilt or source['source_ref'] in source_ids:
            _fail()
        normalized.append(rebuilt)
        ref = source['source_ref']
        source_ids.add(ref)
        used_blobs.update(source['object_refs'].values())
        current = tuple(doc[k] for k in SCOPE)
        if scope is not None and current != scope:
            _fail()
        scope = current
        if source['kind'] == 'CaptureManifest':
            for page in doc['pages']:
                check_page(page['snapshot']['url'])
                if page['snapshot']['final_url'] is not None:
                    check_page(page['snapshot']['final_url'])
            for item in doc['inventory']:
                check_page(item['url'])
                check_page(item['discovered_from'])
        else:
            for url in doc['approved_urls']:
                check_page(url)
            for item in doc['observations']:
                check_page(item['url'])
                # Page documents belong to the site; CDN subresources do not
                # establish the audited site's identity.
                for resource in item['resources']:
                    if resource['resource_type'] == 'Document':
                        check_page(resource['url'])
                        for hop in resource['redirect_trace']:
                            check_page(hop['url'])

        def add_snapshot(pointer, url, observed_at, status, mode, original_id=None,
                         final_url=None,
                         viewport=None, reason=None):
            if canonical_url(url) != url:
                _fail()
            key = (mode, url, viewport)
            if key in page_keys:  # No ambiguous old/new captures in a single run pack.
                _fail()
            page_keys.add(key)
            if original_id is not None:
                if (mode, original_id) in original_ids:
                    _fail()
                original_ids.add((mode, original_id))
            page_ref = 'page-' + document_hash({'source_ref': ref, 'locator': pointer})
            snapshots.append({'snapshot_ref': page_ref, 'source_ref': ref, 'locator': pointer,
                'source_snapshot_id': original_id, 'url': url, 'final_url': final_url,
                'observed_at': observed_at,
                'capture_mode': mode, 'viewport': viewport, 'status': status})
            coverage.append({'source_ref': ref, 'locator': pointer, 'scope': 'PAGE',
                'url': url, 'viewport': viewport, 'role': None, 'snapshot_ref': page_ref,
                'status': status, 'reason': reason or 'BOUNDED_CAPTURE_ONLY'})
            return page_ref

        def add_evidence(page_ref, pointer, kind, digest, blob, status, original_id=None):
            if original_id is not None:
                if ('EVIDENCE', original_id) in original_ids:
                    _fail()
                original_ids.add(('EVIDENCE', original_id))
            limits = ['NO_BUSINESS_OR_COMPLETENESS_ASSERTION']
            if blob is None:
                limits.append('RAW_BODY_NOT_RETAINED')
            if status != 'OBSERVED':
                limits.append('INCOMPLETE_CAPTURE_NOT_FACT_EVIDENCE')
            item = {'source_ref': ref, 'snapshot_ref': page_ref, 'locator': pointer,
                    'kind': kind, 'content_sha256': digest, 'blob_ref': blob,
                    'content_verification': 'HASH_VERIFIED' if blob else 'NOT_RECOMPUTABLE',
                    'source_evidence_id': original_id, 'status': status, 'limitations': limits}
            item['evidence_ref'] = 'ev-' + document_hash(item)
            evidence.append(item)

        if source['kind'] == 'CaptureManifest':
            visited = set()
            for index, page in enumerate(doc['pages']):
                snap = page['snapshot']
                if snap['capture_mode'] != 'HTTP':
                    _fail()
                visited.add(snap['url'])
                status = 'OBSERVED' if snap['status'] == 'FETCHED' else snap['status']
                page_ref = add_snapshot(f'/pages/{index}/snapshot', snap['url'], snap['captured_at'],
                    status, 'HTTP', snap['snapshot_id'], final_url=snap['final_url'],
                    reason=page['error']['code'] if page['error'] else None)
                if page['evidence'] is not None:
                    ev = page['evidence']
                    # The HTTP producer only locates the whole response body. Free-text
                    # legacy locators must not be promoted into precise provenance.
                    if ev['locator'] != 'http-response-body' or ev['excerpt'] is not None:
                        _fail()
                    add_evidence(page_ref, f'/pages/{index}/evidence', 'HTTP_BODY',
                        snap['sha256'], source['object_refs'].get(snap['private_object_ref']),
                        status, ev['evidence_id'])
            for index, item in enumerate(doc['inventory']):
                if item['url'] not in visited:
                    coverage.append({'source_ref': ref, 'locator': f'/inventory/{index}',
                        'scope': 'PAGE', 'url': item['url'], 'viewport': None, 'role': item['role'],
                        'snapshot_ref': None, 'status': 'NOT_VISITED', 'reason': 'INVENTORY_ONLY'})
            for index, role in enumerate(doc['coverage']['unverified_roles']):
                coverage.append({'source_ref': ref, 'locator': f'/coverage/unverified_roles/{index}',
                    'scope': 'ROLE', 'url': None, 'viewport': None, 'role': role,
                    'snapshot_ref': None, 'status': 'UNKNOWN', 'reason': 'ROLE_NOT_VERIFIED'})
        else:
            seen = set()
            for index, item in enumerate(doc['observations']):
                viewport = item['viewport']['name']
                seen.add((item['url'], viewport))
                status = item['status']
                if status == 'OBSERVED':
                    dom_bytes = objects[item['dom_ref']]
                    png = objects[item['screenshot_ref']]
                    dom = json.loads(dom_bytes)
                    if (not isinstance(dom, dict) or dom.get('url') != item['url']
                            or not isinstance(dom.get('elements'), list)
                            or not isinstance(dom.get('title'), str)
                            or len(dom['elements']) > 128 or len(dom['title']) > 256
                            or len(dom_bytes) > 65536 or len(png) > 2_000_000
                            or not png.startswith(b'\x89PNG\r\n\x1a\n')
                            or png[12:16] != b'IHDR'
                            or int.from_bytes(png[16:20], 'big') != item['viewport']['width']
                            or int.from_bytes(png[20:24], 'big') != item['viewport']['height']):
                        _fail()
                page_ref = add_snapshot(f'/observations/{index}', item['url'], item['observed_at'],
                    status, 'BROWSER', final_url=item['url'], viewport=viewport,
                    reason='BROWSER_INCOMPLETE' if status != 'OBSERVED' else None)
                for field, kind in (('dom_ref', 'BROWSER_DOM'), ('screenshot_ref', 'BROWSER_SCREENSHOT')):
                    if item[field] is not None:
                        add_evidence(page_ref, f'/observations/{index}/{field}', kind,
                            item[field], item[field], status)
            for index, url in enumerate(doc['approved_urls']):
                if canonical_url(url) != url:
                    _fail()
                for viewport in VIEWPORTS:
                    if (url, viewport['name']) not in seen:
                        coverage.append({'source_ref': ref, 'locator': f'/approved_urls/{index}',
                            'scope': 'PAGE', 'url': url, 'viewport': viewport['name'], 'role': None,
                            'snapshot_ref': None, 'status': 'NOT_VISITED', 'reason': 'VIEWPORT_NOT_VISITED'})
    if used_blobs != set(blobs):
        _fail()
    assert scope is not None
    result = {'schema_version': '1.0', **dict(zip(SCOPE, scope)), 'private': True,
        'sources': sorted(normalized, key=lambda s: s['source_ref']),
        'snapshots': sorted(snapshots, key=lambda s: s['snapshot_ref']),
        'evidence': sorted(evidence, key=lambda e: e['evidence_ref']),
        'coverage': sorted(coverage, key=lambda c: _encode(c)),
        'integrity': {'status': 'VERIFIED', 'checks': ['SOURCE_VERIFIERS', 'RETAINED_BLOB_HASHES',
            'SCOPE_AND_REFERENCES', 'DETERMINISTIC_PROJECTION'], 'limitations': list(LIMITATIONS)}}
    result['pack_ref'] = 'ep-' + document_hash(result)
    return result


@dataclass(frozen=True, slots=True)
class EvidencePack:
    """Immutable canonical bytes and blob tuples. Public document views are detached copies."""
    _payload: bytes
    _blobs: tuple[tuple[str, bytes], ...]

    def __post_init__(self):
        if (not isinstance(self._payload, bytes) or not isinstance(self._blobs, tuple)
                or any(not isinstance(pair, tuple) or len(pair) != 2
                       or not isinstance(pair[0], str) or not isinstance(pair[1], bytes)
                       for pair in self._blobs)):
            _fail()

    @property
    def document(self) -> dict:
        return json.loads(self._payload)

    @property
    def objects(self) -> Mapping[str, bytes]:
        return MappingProxyType(dict(self._blobs))

    @property
    def ref(self) -> str:
        return self.document['pack_ref']

    @classmethod
    def load(cls, document: dict, objects: Mapping[str, bytes], *, expected_ref: str | None = None):
        try:
            pack = cls(_encode(document), tuple(sorted(objects.items())))
            pack.verify(expected_ref=expected_ref)
            return pack
        except (ValueError, TypeError, KeyError, IndexError, AssertionError) as exc:
            raise EvidenceError('EVIDENCE_INTEGRITY') from exc

    def verify(self, *, expected_ref: str | None = None) -> None:
        try:
            if len(self._payload) > 8_000_000 or len(dict(self._blobs)) != len(self._blobs):
                _fail()
            doc = self.document
            schema = json.loads((Path(__file__).parents[2] /
                'contracts/v1/evidence/EvidencePack.schema.json').read_text(encoding='utf-8'))
            Draft202012Validator(schema, format_checker=FormatChecker()).validate(doc)
            if expected_ref is not None and doc['pack_ref'] != expected_ref:
                _fail()
            rebuilt = _project(doc['sources'], self.objects)
            if _encode(doc) != _encode(rebuilt):
                _fail()
        except Exception as exc:
            # Schema/source errors are normalized; no source contents leak in safe errors.
            raise EvidenceError('EVIDENCE_INTEGRITY') from exc

    def resolve(self, evidence_ref: str, *, expected_pack_ref: str) -> dict:
        self.verify(expected_ref=expected_pack_ref)
        for item in self.document['evidence']:
            if item['evidence_ref'] == evidence_ref:
                if item['status'] != 'OBSERVED':
                    raise EvidenceError('EVIDENCE_INSUFFICIENT')
                doc = self.document
                source = next(s for s in doc['sources'] if s['source_ref'] == item['source_ref'])
                target = source['document']
                for token in item['locator'].split('/')[1:]:
                    target = target[int(token)] if isinstance(target, list) else target[token]
                return {'evidence': item, 'source_record': target,
                        'snapshot': next(s for s in doc['snapshots'] if s['snapshot_ref'] == item['snapshot_ref']),
                        'content': self.objects.get(item['blob_ref'])}
        raise EvidenceError('EVIDENCE_REFERENCE_INVALID')


def build_pack(bundles: Sequence[CaptureBundle | BrowserBundle]) -> EvidencePack:
    try:
        if not 1 <= len(bundles) <= 16:
            _fail()
        sources, blobs = [], {}
        for bundle in bundles:
            source, objects = _source(bundle)
            sources.append(source)
            blobs.update(objects)
        return EvidencePack.load(_project(sources, blobs), blobs)
    except Exception as exc:
        raise EvidenceError('EVIDENCE_INTEGRITY') from exc
