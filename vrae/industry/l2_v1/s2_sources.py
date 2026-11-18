"""Read-only table candidates using the existing strict static parser and model.

No new facts are added to the original Guard/FindingPackage. Source strings are
only declarations in a caller-pinned EvidencePack, never authenticated entities.
"""
from vrae.rules.execution import _records, _metadata
from vrae.rules.trust_facts import _Static
from .diagnose import normalized

VERSION = 's2-industrial-source-1.0.0'


def extract_tables(pack, profile):
    """Internal source adapter, invoked only after S2 pack/scope/config validation."""
    doc = pack.document
    output = []
    aliases = {normalized(alias): key for key, names in profile['labels'].items() for alias in names}
    if sum(len(names) for names in profile['labels'].values()) != len(aliases):
        raise ValueError('INDUSTRY_ALIAS_COLLISION')
    for record in _records(doc):
        source = _metadata(record)
        row = {'url': source['url'], 'source_page': source, 'fields': {},
               'status': 'UNKNOWN', 'reason': 'RETAINED_STATIC_SOURCE_REQUIRED',
               'unparsed_resources': []}
        output.append(row)
        if record[2]['status'] == 'ACCESS_BLOCKED':
            row.update(status='ACCESS_BLOCKED', reason='SOURCE_ACCESS_BLOCKED')
            continue
        ev = next((e for e in doc['evidence'] if e['snapshot_ref'] == source['snapshot_ref']
                   and e['kind'] == 'HTTP_BODY' and e['status'] == 'OBSERVED' and e['blob_ref']), None)
        if ev is None or source['http_status'] != 200:
            continue
        raw = pack.resolve(ev['evidence_ref'], expected_pack_ref=pack.ref)['content']
        if raw is None or len(raw) > 131072:
            continue
        try:
            parser = _Static(raw)
            tables = [n for n in parser.nodes if n['tag'] == 'table']
            # Several independent records on one page need an explicit record scope
            # contract; do not combine their fields into a fabricated product/entity.
            if len(tables) != 1:
                raise ValueError('ONE_RECORD_TABLE_REQUIRED')
            table_rows = [n for n in parser.nodes if n['tag'] == 'tr']
            if len(table_rows) > 128:
                raise ValueError('FIELD_BOUND')

            def cite(node):
                start, end = node['offset'], node['end']
                return {k: ev[k] for k in ('evidence_ref', 'source_ref', 'snapshot_ref',
                                           'locator', 'content_sha256')} | {
                    'url': source['url'], 'observed_at': source['observed_at'],
                    'element_path': node['path'],
                    'byte_start': len(parser.raw[:start].encode()),
                    'byte_end': len(parser.raw[:end].encode()),
                    'quote': parser.raw[start:end], 'offset_basis': 'ORIGINAL_UTF8_BYTES'}

            fields: dict[str, dict | None] = {}
            for node in table_rows:
                cells = node['children']
                if (len(cells) != 2 or [c['tag'] for c in cells] != ['th', 'td']
                        or any(c['children'] for c in cells)):
                    raise ValueError('PLAIN_LABEL_VALUE_REQUIRED')
                key = aliases.get(normalized(cells[0]['text']))
                if key is None:
                    continue
                if key in fields:
                    fields[key] = None
                else:
                    fields[key] = {'text': cells[1]['text'],
                                   'citations': [cite(cells[0]), cite(cells[1])]}
            for node in parser.nodes:
                attr = 'href' if node['tag'] == 'a' else 'src' if node['tag'] == 'img' else None
                value = node['attrs'].get(attr) if attr else None
                if value and value.lower().split('?', 1)[0].endswith(('.pdf', '.png', '.svg', '.jpg')):
                    row['unparsed_resources'].append({'source_attribute': value, 'citation': cite(node),
                                                      'status': 'UNPARSED_NOT_FETCHED'})
            row.update(fields=fields, status='EXTRACTED', reason='EXPLICIT_SOURCE_TABLE_ONLY')
        except (ValueError, UnicodeError, AssertionError, KeyError):
            row.update(fields={}, status='UNKNOWN', reason='UNSUPPORTED_OR_AMBIGUOUS_STATIC_TABLE')
    return output
