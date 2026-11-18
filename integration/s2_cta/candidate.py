"""Replayable supplemental samples, never an EvidencePack/Guard promotion path."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
from urllib.parse import urlsplit

from vrae.browser.controller import DOM_SCRIPT

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ('clean', 'hidden', 'covered', 'overflow')
WIDTHS = (390, 375, 320, 1280)
BUNDLED_ROOT = ROOT/'integration/s2_cta/evidence/cta-main-d38'
BUNDLED_SHA256 = '3ef1c739910d9db4581643344a712fd614c922da920d5a34dc03f9043b1f3a6f'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def context(binding, report):
    return {'tenant_id':binding.scope['tenant_id'], 'run_id':binding.scope['run_id'],
            'policy_id':binding.scope['policy_id'], 'policy_version':binding.scope['policy_version'],
            'pack_ref':binding.source.held.native_pack_ref, 'source_digest':report.source_digest,
            'report_version':report.version['report_version_id'], 'content_hash':report.version['content_hash'],
            'display_hash':report.display_hash, 'industry_ref':binding.pins.industry_ref,
            'profile_id':binding.pins.profile_id, 'industry_version':binding.pins.version}


class CTADenied(ValueError):
    pass


class Receipt:
    def __init__(self, directory, *, expected_sha256, held_context, observed_after, observed_before):
        self.root = Path(directory).resolve()
        owned = ROOT/'integration/s2_buyer_workbench/.runtime'
        if self.root == BUNDLED_ROOT.resolve():
            if expected_sha256 != BUNDLED_SHA256:
                raise CTADenied('CTA_BUNDLED_RECEIPT_CHANGED')
        elif not self.root.is_relative_to(owned.resolve()):
            raise CTADenied('CTA_OWNED_RECEIPT_REQUIRED')
        self.expected = expected_sha256
        self.held = dict(held_context)
        self.after, self.before = datetime.fromisoformat(observed_after), datetime.fromisoformat(observed_before)
        if self.after.utcoffset() is None or self.before.utcoffset() is None or self.after > self.before:
            raise CTADenied('CTA_WINDOW_REQUIRED')

    def read(self, binding, report):
        try:
            if context(binding,report) != self.held:
                raise CTADenied('CTA_CONTEXT_CHANGED')
            raw = (self.root/'receipt.json').read_bytes()
            if len(raw)>1_000_000 or sha(raw)!=self.expected:
                raise CTADenied('CTA_RECEIPT_CHANGED')
            data = json.loads(raw)
            if (data['kind']!='CONTROLLED_OFFLINE_CTA_SIDECAR' or data['version']!='c2-cta-offline-1.0.0'
                    or data['nativeFactAdmission']!='NONE'
                    or any(data[k]!='UNKNOWN' for k in ('responseObservation','submission','delivery'))):
                raise CTADenied('CTA_NOT_NATIVE_AUTHORITY')
            if data['fixtureSha256'] != sha((ROOT/'integration/s2_ux/fixture.html').read_bytes().replace(b'\r\n', b'\n')):
                raise CTADenied('CTA_FIXTURE_CHANGED')
            if data['legacyScriptSha256']!=sha(DOM_SCRIPT.encode()) or data['observerSha256']!=sha((ROOT/'integration/s2_cta/capture.mjs').read_bytes()):
                raise CTADenied('CTA_PRODUCER_CHANGED')
            if len(data['records'])!=16 or not data['checks'] or not all(c['pass'] for c in data['checks']):
                raise CTADenied('CTA_INCOMPLETE_CAPTURE')
            seen = set()
            for row in data['records']:
                key=(row['scenario'],row['width'])
                if key in seen or key[0] not in SCENARIOS or key[1] not in WIDTHS:
                    raise CTADenied('CTA_RECORD_SCOPE')
                seen.add(key)
                if row['url']!='https://synthetic.invalid/?case='+key[0] or row['height']!=(720 if key[1]==1280 else 844):
                    raise CTADenied('CTA_RECORD_SCOPE')
                if row['legacyV1DimensionsOnly'] is not (key[1] in (390,1280)):
                    raise CTADenied('CTA_VIEWPORT_AUTHORITY')
                at=datetime.fromisoformat(row['observedAt'])
                if not self.after<=at<=self.before:
                    raise CTADenied('CTA_STALE_CAPTURE')
                dom=row['dom']
                compact=json.dumps(dom,ensure_ascii=False,separators=(',',':')).encode()
                if sha(compact)!=row['domSha256'] or set(dom)!= {'title','url','elements'} or dom['url']!=row['url']:
                    raise CTADenied('CTA_DOM_CHANGED')
                if len(dom['elements'])>128 or any(set(e)!={'tag','visible','text'} or type(e['visible']) is not bool for e in dom['elements']):
                    raise CTADenied('CTA_V1_DOM_EXTENSION')
                metrics=row['metrics']
                if any(type(metrics[k]) not in (int,float) or not math.isfinite(metrics[k]) or not 0<metrics[k]<=100000 for k in ('clientWidth','scrollWidth','innerWidth','innerHeight')):
                    raise CTADenied('CTA_GEOMETRY_BOUND')
                if len(metrics['targets'])!=2 or metrics['clientWidth']<=0 or metrics['scrollWidth']<metrics['clientWidth']:
                    raise CTADenied('CTA_GEOMETRY_BOUND')
                for target, identity in zip(metrics['targets'],('quote','inquiry')):
                    if target['tag']!=('A' if identity=='quote' else 'BUTTON') or type(target['text']) is not str or len(target['text'])>160:
                        raise CTADenied('CTA_TARGET_BOUND')
                    if target['id']!=identity or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100000 for v in target['rect'].values()):
                        raise CTADenied('CTA_GEOMETRY_BOUND')
                    if set(target['rect'])!={'x','y','width','height'} or target['rect']['width']<0 or target['rect']['height']<0:
                        raise CTADenied('CTA_GEOMETRY_BOUND')
                    if target['href']!=('/rfq' if identity=='quote' else None) or target['resolvedHref']!=('https://synthetic.invalid/rfq' if identity=='quote' else None):
                        raise CTADenied('CTA_HREF_SOURCE_MISMATCH')
                    elements=[e for e in dom['elements'] if e['tag']==target['tag'] and e['text']==target['text']]
                    if len(elements)!=1 or elements[0]['visible'] is not (target['rect']['width']>0 and target['rect']['height']>0):
                        raise CTADenied('CTA_ELEMENT_MISMATCH')
                    if type(target['opacity']) not in (int,float) or not math.isfinite(target['opacity']) or not 0<=target['opacity']<=1:
                        raise CTADenied('CTA_STYLE_BOUND')
                    if any(type(target[k]) is not bool for k in ('inViewport','centerOnTarget')):
                        raise CTADenied('CTA_HIT_BOUND')
                self.image(row)
            for request in data['requests']:
                if request['method']!='GET' or urlsplit(request['url']).path=='/rfq':
                    raise CTADenied('CTA_REQUEST_BOUND')
                if request['allowed'] and (request['type']!='Document' or request['url'] not in {'https://synthetic.invalid/?case='+s for s in SCENARIOS}):
                    raise CTADenied('CTA_REQUEST_BOUND')
            return data
        except Exception as exc:
            raise CTADenied('CTA_REPLAY_DENIED') from exc

    def image(self,row):
        name=f"{row['scenario']}-{row['width']}.png"
        if row['screenshot']!=name:
            raise CTADenied('CTA_IMAGE_PATH')
        raw=(self.root/name).read_bytes()
        if len(raw)>2_000_000 or not raw.startswith(b'\x89PNG\r\n\x1a\n') or sha(raw)!=row['screenshotSha256']:
            raise CTADenied('CTA_IMAGE_CHANGED')
        if struct.unpack('>II',raw[16:24])!=(row['width'],row['height']):
            raise CTADenied('CTA_IMAGE_DIMENSIONS')
        return raw


def bundled(binding, report):
    """Pinned public synthetic reference, associated with this current report.

    Association is read authority only: these samples are not observations of
    the current task's website, EvidencePack, or Guard findings.
    """
    raw = (BUNDLED_ROOT/'receipt.json').read_bytes()
    if sha(raw) != BUNDLED_SHA256:
        raise CTADenied('CTA_BUNDLED_RECEIPT_CHANGED')
    data = json.loads(raw)
    reader = Receipt(BUNDLED_ROOT, expected_sha256=BUNDLED_SHA256,
                     held_context=context(binding, report),
                     observed_after=data['startedAt'], observed_before=data['finishedAt'])
    reader.read(binding, report)
    return reader
