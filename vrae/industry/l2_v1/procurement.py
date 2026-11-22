"""Source-bound procurement review; not a new rule PASS or engineering approval."""
from collections import defaultdict
import json
from pathlib import Path
import re

from vrae.collection.manifest import document_hash
from vrae.evidence import EvidenceError
from vrae.intelligence.qwen.source_values import value as safe_value
from vrae.rules.patch_execution import verify_execution
from .diagnose import normalized, quantity

VERSION = 'vrae.l2-procurement-review.v1'
CONFIG = Path(__file__).resolve().parents[3] / 'industry-packs/l2-industrial-v1/procurement-1.0.0.json'
BASE_UNITS = {'length': 'mm', 'flow': 'm3/h', 'head': 'm', 'power': 'kW',
              'voltage': 'V', 'frequency': 'Hz', 'pressure': 'bar', 'temperature': 'degC'}


def bilingual(pair):
    return dict(zip(('zh', 'en'), pair))


def configuration(parent, version='1.0.0'):
    names = {'1.0.0': 'procurement-1.0.0.json', '1.1.0': 'procurement-1.1.0.json', '1.2.0': 'procurement-1.2.0.json'}
    path = CONFIG.with_name(names[version])
    config = json.loads(path.read_text(encoding='utf-8'))
    if version not in ('1.0.0','1.1.0','1.2.0') or config['version'] != version or config['parent_profile_version'] != parent['version']:
        raise EvidenceError('PROCUREMENT_CONFIGURATION')
    labels = {key: parent['labels'][key] for key in config['titles'] if key in parent['labels']}
    labels.update(config['extra_labels'])
    aliases: dict[str, str] = {}
    for key, names in labels.items():
        for name in names:
            alias = normalized(name)
            if alias in aliases and aliases[alias] != key:
                raise EvidenceError('PROCUREMENT_ALIAS_COLLISION')
            aliases[alias] = key
    for profile in config['profiles'].values():
        if 'parent_family' in profile:
            family = profile['parent_family']
            profile.update(declared_families=parent['family_aliases'][family],
                           name_phrases=[p for p in parent['family_aliases'][family] if ' ' in p],
                           review_groups=parent['families'][family]['critical'],
                           dimensions=parent['families'][family]['dimensions'])
        if any(key not in config['titles'] for key in profile['review_groups']):
            raise EvidenceError('PROCUREMENT_GROUP_CONFIGURATION')
    return config, aliases


def text(citation):
    return safe_value({'rule_id': 'INFO-01', 'source': {'citation': citation}})


def select_profile(name, fields, config):
    declared = [f for f in fields if normalized(f['label']) in
                {normalized(x) for x in config['family_labels']}]
    names = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', name['text'])
    names = normalized(re.sub(r'([a-z])([A-Z])', r'\1 \2', names))
    candidates = []
    for key, profile in config['profiles'].items():
        matching = [f for f in declared if normalized(f['value']) in
                    {normalized(x) for x in profile['declared_families']}]
        name_match = any(re.search(r'\b'+re.escape(p)+r'\b', names) for p in profile['name_phrases'])
        if matching or name_match:
            indexes = sorted({i for f in matching for i in f['citation_indexes']}
                             | (set(name['citation_indexes']) if name_match else set()))
            candidates.append((key, indexes))
    # Conflicting declarations never select a convenient profile by name.
    unknown_declaration = any(not any(normalized(f['value']) in
        {normalized(x) for x in p['declared_families']} for p in config['profiles'].values()) for f in declared)
    if unknown_declaration or len(candidates) != 1:
        return {'id': None, 'state': 'AMBIGUOUS' if candidates or len(declared)>1 else 'UNRESOLVED',
                'citation_indexes': sorted({i for f in declared for i in f['citation_indexes']})}
    key, indexes = candidates[0]
    return {'id': key, 'state': 'SOURCE_LABEL_CANDIDATE', 'title': bilingual(config['profiles'][key]['title']),
            'citation_indexes': indexes}


def build(pack, execution, parent, industry_ref, *, version='1.0.0'):
    verify_execution(execution, pack, expected_pack_ref=pack.ref,
                     expected_evaluator_version='ra2b6-1.0.6' if version == '1.2.0' else 'ra2b6-1.0.5')
    config, aliases = configuration(parent, version)
    products = []
    for rule in execution['executions']:
        if rule['rule_id'] != 'INFO-01':
            continue
        for row in rule['observations']:
            citations = row['citations']
            names = [(i, c) for i, c in enumerate(citations) if c.get('fact_role') == 'NAME' and text(c)]
            if len(names) != 1:
                continue
            ni, name_citation = names[0]
            scope = name_citation.get('product_scope_ref')
            if type(scope) is not str or not re.fullmatch(r'ps-[0-9a-f]{64}', scope):
                continue
            name = {'text': text(name_citation), 'citation_indexes': [ni]}
            pairs: dict[int, dict[str, tuple[int, dict]]] = defaultdict(dict)
            for i, c in enumerate(citations):
                if c.get('product_scope_ref') == scope and c.get('fact_role') in ('SPEC_LABEL', 'SPEC_VALUE'):
                    pairs[c['field_index']][c['fact_role']] = (i, c)
            fields = []
            for pair in pairs.values():
                if set(pair) != {'SPEC_LABEL', 'SPEC_VALUE'}:
                    continue
                (ki, label), (vi, val) = pair['SPEC_LABEL'], pair['SPEC_VALUE']
                label_text, val_text = text(label), text(val)
                if normalized(label_text or '') in ('item', 'product', 'product name', 'productname') and val_text == name['text']:
                    continue
                if label_text and val_text:
                    fields.append({'key': aliases.get(normalized(label_text)), 'label': label_text,
                                   'value': val_text, 'citation_indexes': [ki, vi], 'normalization': None})
            profile = select_profile(name, fields, config)
            selected = config['profiles'].get(profile['id'], {})
            keys = list(selected.get('review_groups', []))
            keys += sorted({f['key'] for f in fields if f['key'] and f['key'] not in keys})
            groups = []
            for key in keys:
                indexes = [i for i, f in enumerate(fields) if f['key'] == key]
                distinct = {fields[i]['value'] for i in indexes}
                state = 'AMBIGUOUS' if len(distinct)>1 else 'OBSERVED' if indexes else 'NOT_OBSERVED_IN_CAPTURE'
                title = config['titles'][key]
                next_step = {
                    'OBSERVED': (f'已观察到供方展示的{title[0]}；核对适用型号、单位与资料版本。',
                        f'Supplier-stated {title[1]} was observed; confirm model, units and document revision.'),
                    'NOT_OBSERVED_IN_CAPTURE': (f'本次来源未观察到{title[0]}；核对其他页面或技术资料，当前不判定网站缺失。',
                        f'{title[1]} was not observed in this capture; check other pages or documents. Absence is unproven.'),
                    'AMBIGUOUS': (f'同一产品区域有多个不同的{title[0]}记录；确认条件或型号对应关系。',
                        f'Different {title[1]} entries occur in this region; confirm conditions or model association.')}
                groups.append({'key': key, 'title': bilingual(title), 'state': state,
                    'field_indexes': indexes, 'next_step': bilingual(next_step[state])})
                for i in indexes:
                    parsed = quantity(fields[i]['value'], parent)
                    if parsed and parsed[0] == selected.get('dimensions', {}).get(key):
                        fields[i]['normalization'] = {'dimension': parsed[0], 'value': str(parsed[1]),
                                                      'unit': BASE_UNITS[parsed[0]]}
            model_fields = [f for f in fields if f['key'] == 'model']
            model = model_fields[0] if len({f['value'] for f in model_fields}) == 1 else None
            products.append({'observation_id': row['observation']['observation_id'],
                'product_scope_ref': scope, 'name': name, 'declared_model': model,
                'profile': profile, 'fields': fields, 'groups': groups,
                'state': 'PROFILE_UNRESOLVED' if profile['id'] is None else
                    'CONFIGURED_GROUPS_OBSERVED' if all(g['state']=='OBSERVED' for g in groups) else 'PARTIAL_SOURCE_INFORMATION',
                'verified_sku': False, 'engineering_fit': 'UNKNOWN', 'is_rule_pass': False})
    if version in ('1.1.0', '1.2.0'):
        from .purchase_tasks import evaluate, informative
        for card in products:
            card['purchase_tasks'] = evaluate(card)
            original = next(row for rule in execution['executions'] if rule['rule_id']=='INFO-01'
                for row in rule['observations'] if row['observation']['observation_id']==card['observation_id'])
            snapshot = original['citations'][card['name']['citation_indexes'][0]]['snapshot_ref']
            routes = [row['observation']['observation_id'] for rule in execution['executions']
                if rule['rule_id']=='CTA-02' for row in rule['observations']
                if row['observation']['result']=='PASS'
                and (row.get('source_page') or {}).get('snapshot_ref')==snapshot]
            card['inquiry_preparation'] = {'state':'STATIC_ROUTE_RECORDED' if routes else 'UNKNOWN',
                'path_observation_ids':routes,'available_input_field_indexes':[
                    i for i,f in enumerate(card['fields']) if informative(f['value'])],
                'product_context_transfer':'UNKNOWN','inquiry_submitted':False}
    result = {'contract': VERSION, 'config_version': config['version'],
        'configuration_ref': 'pcfg-'+document_hash({'config': config, 'parent_industry_ref': industry_ref}),
        'pack_ref': pack.ref, 'execution_ref': execution['execution_ref'],
        'products': products[:8], 'coverage': {'eligible_products': len(products),
            'reviewed_products': min(len(products), 8), 'truncated': len(products)>8},
        'unknown_is_defect': False, 'formal_human_review': False,
        'native_fact_admission': 'NONE', 'semantic_approval': False}
    result['review_ref'] = 'prv-'+document_hash(result)
    return result
