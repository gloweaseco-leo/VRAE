"""Read-only P1 source declarations and HTTP measurements, independent of AI."""
from vrae.collection.manifest import document_hash
from vrae.collection.http_measurement import validate
from integration.authorized_targets.form_facts import extract


def build(pack, diagnosis, artifact_sha256):
    pack.verify(expected_ref=diagnosis['expected_pack_ref'])
    doc = pack.document
    result = {'contract': 'vrae.fact-review.v1', 'artifact_sha256': artifact_sha256,
        'pack_ref': pack.ref, 'native_execution_ref': diagnosis['native_execution_ref'],
        'trust': [], 'inquiry': [], 'technical': [], 'native_fact_admission': 'NONE',
        'unknown_is_defect': False, 'inquiry_submitted': False,
        'browser_performance': 'UNKNOWN', 'whole_site_coverage_known': False}
    for ti, task in enumerate(diagnosis['buyer_tasks']):
        for ri, rule in enumerate(task['rules']):
            if rule['rule_id'] != 'TRUST-01':
                continue
            for oi, row in enumerate(rule['observations']):
                result['trust'].append({'source_pointer':
                    f'/deterministic_diagnosis/buyer_tasks/{ti}/rules/{ri}/observations/{oi}',
                    'context_facts': row.get('context_facts', []),
                    'missing_prerequisites': row.get('missing_prerequisites', []),
                    'identity_verified': False, 'materials_authenticated': False})
    for source in doc['sources']:
        if source['kind'] != 'CaptureManifest':
            continue
        for index, page in enumerate(source['document']['pages']):
            snapshots = [s for s in doc['snapshots'] if s['source_ref'] == source['source_ref']
                         and s['locator'] == f'/pages/{index}/snapshot']
            if len(snapshots) != 1:
                raise ValueError('FACT_REVIEW_SOURCE_BINDING')
            snapshot = snapshots[0]
            measurement = page.get('http_measurement')
            if measurement is not None:
                validate(measurement)
            result['technical'].append({'snapshot_ref': snapshot['snapshot_ref'],
                'source_ref': source['source_ref'], 'source_locator': f'/pages/{index}',
                'capture_status': page['snapshot']['status'], 'http_status': page['http_status'],
                'response_body_bytes': page['bytes'],
                'redirect_count': sum(h['status'] in (301,302,303,307,308)
                                      for h in page['redirect_trace']),
                'measurement': measurement, 'timing_state': 'MEASURED' if measurement else 'UNKNOWN',
                'samples': 1 if measurement else 0, 'is_defect': False})
            if page['snapshot']['status'] != 'FETCHED':
                continue
            evidence = [e for e in doc['evidence'] if e['snapshot_ref'] == snapshot['snapshot_ref']
                        and e['kind'] == 'HTTP_BODY']
            if len(evidence) != 1:
                raise ValueError('FACT_REVIEW_SOURCE_BINDING')
            ev = evidence[0]
            raw = pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)['content']
            try:
                if not isinstance(raw, bytes):
                    raise ValueError('FORM_BODY_UNAVAILABLE')
                forms = extract(raw, ev, page['snapshot']['final_url'])
                state = 'STATIC_DECLARATIONS_RECORDED'
            except (ValueError, UnicodeError):
                forms = None
                state = 'PARSER_UNSUPPORTED'
            result['inquiry'].append({'snapshot_ref': snapshot['snapshot_ref'],
                'state': state, 'static_forms': forms,
                'absence_proven': False, 'delivery': 'UNKNOWN'})
    result['review_ref'] = 'frv-'+document_hash(result)
    return result
