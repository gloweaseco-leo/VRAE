"""Offline source fixtures. Synthetic PNG/DOM are NOT actual browser attestation."""
import json
import struct
import zlib

from vrae.collection.manifest import document_hash, sha256
from tests.browser.test_contracts import bundle as browser_bundle
from tests.collection.test_pipeline import collect


def http(retained=True):
    return collect(retain_raw_html=retained)[0]


def browser(observed=False):
    result = browser_bundle()
    doc = result.manifest
    doc['run_id'] = 'run-synthetic'
    if observed:
        item = doc['observations'][0]
        dom = json.dumps({'title': 'Synthetic fixture', 'url': item['url'], 'elements': []}).encode()
        width, height = item['viewport']['width'], item['viewport']['height']

        def chunk(kind, data):
            return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

        png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
               + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\xff\xff' * width) * height))
               + chunk(b'IEND', b''))
        page = http().manifest['pages'][0]
        item.update(status='OBSERVED', errors=[], dom_ref=sha256(dom), screenshot_ref=sha256(png),
            resources=[{'url': item['url'], 'method': 'GET', 'resource_type': 'Document',
                        'outcome': 'FETCHED', 'error': None, 'redirect_trace': page['redirect_trace'],
                        'sha256': page['snapshot']['sha256']}])
        result.objects = {sha256(dom): dom, sha256(png): png}
    doc['sha256'] = document_hash({k: v for k, v in doc.items() if k != 'sha256'})
    result.verify()
    return result
