"""Read-only pilot replay. No network, no model call, no artifact rewrite.

Old-version replay that disagrees with the stored receipt exits non-zero.
Quotes are hashed unless --include-public-quotes is set. Raw HTML, contact
details and form values are never written.
"""
import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

from vrae.collection.discovery import select_next
from vrae.evidence import EvidencePack
from vrae.industry.l2_v1.diagnose import SOURCE_VERSIONS
from vrae.reporting.common import encode
from vrae.rules.patch_execution import execute

TASKS = ('DISCOVER', 'UNDERSTAND', 'TRUST', 'INQUIRE', 'SEARCH_TECHNICAL')
NON_DEFECT = {'UNKNOWN', 'ACCESS_BLOCKED', 'NOT_APPLICABLE'}
EMAIL = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
PHONE = re.compile(r'\+\d[\d\s().-]{6,}\d')
HTML = re.compile(r'<\s*/?\s*[a-zA-Z][^>]*>')
PUBLIC_LIMIT = 80


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _public_quote(text):
    if not isinstance(text, str) or not text.strip() or len(text) > PUBLIC_LIMIT:
        return None
    if HTML.search(text) or EMAIL.search(text) or PHONE.search(text) or 'secret-form' in text.casefold():
        return None
    return ' '.join(text.split())


def redact(value, *, public_quotes, audit):
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            if key in ('objects_base64', 'raw_html', 'html', 'body', 'form_value', 'form_values', 'email', 'phone'):
                audit.append('AUDIT action=DROPPED field=' + key)
                continue
            if key in ('quote', 'text', 'public_quote') and isinstance(item, str):
                digest = _sha(item)
                output[key + '_sha256'] = digest
                if public_quotes:
                    short = _public_quote(item)
                    if short:
                        output['public_quote'] = short
                        audit.append('AUDIT action=INCLUDE_PUBLIC_QUOTES sha256=' + digest)
                continue
            output[key] = redact(item, public_quotes=public_quotes, audit=audit)
        return output
    if isinstance(value, list):
        return [redact(item, public_quotes=public_quotes, audit=audit) for item in value]
    if isinstance(value, str):
        if HTML.search(value) or EMAIL.search(value) or PHONE.search(value):
            return '[redacted]'
        return value
    return value


def _fingerprint(execution):
    rows = []
    for rule in execution['executions']:
        for observation in rule['observations']:
            rows.append({'rule_id': rule['rule_id'], 'buyer_task': rule['buyer_task'],
                         'result': observation['observation']['result'], 'reason': observation.get('reason')})
    return rows


def _distribution(rows):
    counts = {task: {} for task in TASKS}
    for row in rows:
        bucket = counts.setdefault(row['buyer_task'], {})
        bucket[row['result']] = bucket.get(row['result'], 0) + 1
    return {'tasks': counts, 'non_defect_results': sorted(NON_DEFECT), 'non_defect_is_score': False}


def _inventory(document):
    if document.get('inventory'):
        return document['inventory']
    pack = document.get('pack') or {}
    items = []
    for source in pack.get('sources') or []:
        if source.get('kind') == 'CaptureManifest':
            items.extend(source.get('document', {}).get('inventory') or [])
    return items


def _simulate(items, page_cap):
    attempted, covered, order = set(), set(), []
    cap = min(page_cap, 6)
    while len(order) < cap:
        choice = select_next(items, attempted, covered)
        if choice is None:
            break
        order.append({'url': choice['url'], 'role': choice['role']})
        attempted.add(choice['url'])
        covered.add(choice['role'])
    return {'sampling': None, 'select_next_default_representative': False, 'page_cap': cap,
            'requests_sent': 0, 'order': order}


def _load_pack(document):
    if 'pack' not in document or 'objects_base64' not in document:
        return None
    objects = {key: base64.b64decode(value) for key, value in document['objects_base64'].items()}
    return EvidencePack.load(document['pack'], objects, expected_ref=document['pack'].get('pack_ref'))


def _replay(pack, version):
    evaluator = SOURCE_VERSIONS[version][0]
    return execute(pack, expected_pack_ref=pack.ref, evaluator_version=evaluator)


def build_report(document, target_version, *, public_quotes):
    if target_version not in SOURCE_VERSIONS:
        raise SystemExit(1)
    audit = []
    historical = document.get('diagnostic_version') or (document.get('diagnosis') or {}).get('diagnostic_version')
    pack = _load_pack(document)
    mismatch = None
    if pack is not None and historical:
        old = _replay(pack, historical)
        receipt = (document.get('diagnosis') or {}).get('native_execution_ref')
        if receipt and old['execution_ref'] != receipt:
            mismatch = {'historical_execution_ref': receipt, 'replayed_execution_ref': old['execution_ref']}
        old_rows = _fingerprint(old)
        new_rows = _fingerprint(_replay(pack, target_version)) if target_version != historical else old_rows
    else:
        old_rows = document.get('historical_rules') or []
        stored = document.get('receipt_sha256')
        if stored and hashlib.sha256(encode(old_rows)).hexdigest() != stored:
            mismatch = {'receipt': 'HISTORICAL_RULES_MISMATCH'}
        new_rows = old_rows if target_version == historical else []
    paired = []
    keys = {(row['rule_id'], row.get('buyer_task')) for row in old_rows + new_rows}
    for rule_id, task in sorted(keys):
        before = [row for row in old_rows if row['rule_id'] == rule_id]
        after = [row for row in new_rows if row['rule_id'] == rule_id]
        paired.append({'rule_id': rule_id, 'buyer_task': task,
                       'old': before, 'new': after,
                       'unchanged': encode(before) == encode(after)})
    report = {'read_only': True, 'requests_sent': 0, 'target_version': target_version,
              'historical_version': historical, 'rules': paired,
              'stages': _distribution(old_rows), 'target_stages': _distribution(new_rows),
              'coverage': document.get('coverage') or {'unvisited_is_defect': False},
              'page_selection': _simulate(_inventory(document), int(document.get('page_cap') or 6)),
              'audit': audit, 'mismatch': mismatch}
    return redact(report, public_quotes=public_quotes, audit=audit), mismatch


def _markdown(report):
    lines = ['# 试点重放', '', '只读。未发送请求。未访问、UNKNOWN、ACCESS_BLOCKED、NOT_APPLICABLE 不是缺陷。', '']
    for rule in report['rules']:
        old = ', '.join(f"{row['result']}/{row['reason']}" for row in rule['old']) or '无'
        new = ', '.join(f"{row['result']}/{row['reason']}" for row in rule['new']) or '无'
        quotes = [row.get('public_quote') for row in rule['old'] + rule['new'] if row.get('public_quote')]
        suffix = ('；公开短引用 ' + ' / '.join(quotes)) if quotes else ''
        lines.append(f"- {rule['rule_id']} ({rule['buyer_task']}): 旧 {old}；新 {new}{suffix}")
    lines.append('')
    lines.append('五环节：' + json.dumps(report['stages']['tasks'], ensure_ascii=False, sort_keys=True))
    coverage = report['coverage']
    lines.append('覆盖：' + json.dumps(coverage, ensure_ascii=False, sort_keys=True))
    order = ' → '.join(item['role'] for item in report['page_selection']['order'])
    lines.append('选页模拟（select_next 默认顺序）：' + order)
    lines.extend(['', *report['audit']])
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only pilot replay')
    parser.add_argument('artifact')
    parser.add_argument('--target-version', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--include-public-quotes', action='store_true')
    args = parser.parse_args(argv)
    document = json.loads(Path(args.artifact).read_text(encoding='utf-8'))
    report, mismatch = build_report(document, args.target_version, public_quotes=args.include_public_quotes)
    destination = Path(args.out)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'pilot-replay.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (destination / 'pilot-replay.md').write_text(_markdown(report), encoding='utf-8')
    return 2 if mismatch else 0


if __name__ == '__main__':
    sys.exit(main())
