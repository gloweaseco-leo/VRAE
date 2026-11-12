"""Pin explicit caller source selection, preserving complete all-fact authoring data."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    source = HERE/'fixtures/guard-requests.json'
    target = HERE/'fixtures/admissible-requests.json'
    assert not target.exists(), 'Never overwrite pinned admissible requests'
    document = json.loads(source.read_text(encoding='utf-8'))
    for key,request in document['requests'].items():
        if not key.startswith('positive/'):
            continue
        original = request['bundles']
        chosen,seen_failures,seen_positives = [],set(),set()
        for bundle in original:
            fact = bundle['bindings'][0]['fact']
            if fact['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE':
                identity = fact['observation_id']
                if identity not in seen_failures:
                    chosen.append(deepcopy(bundle))
                    seen_failures.add(identity)
            elif fact['rule_id'] in ('INFO-01','TRUST-01','SEO-01') and fact['observation_result'] == 'PASS':
                if fact['rule_id'] not in seen_positives:
                    chosen.append(deepcopy(bundle))
                    seen_positives.add(fact['rule_id'])
        original_failures = {b['bindings'][0]['fact']['observation_id'] for b in original
            if b['bindings'][0]['fact']['proof_kind'] == 'CAPTURED_CTA_HTTP_FAILURE'}
        assert seen_failures == original_failures
        request.update(all_catalog_fact_count=request['source_fact_count'],bundles=chosen,
            source_fact_count=len(chosen),selected_fact_refs=[b['original_fact_ref'] for b in chosen],
            selection='ALL_REAL_FAILURE_WITNESSES_AND_FIRST_LITERAL_POSITIVE_PER_RULE_NO_TEXT_STATUS_FILTER')
    document['all_fact_authoring_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    target.write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Explicit minimal native witnesses pinned; all original failure facts and authoring guards retained')


if __name__ == '__main__':
    main()
