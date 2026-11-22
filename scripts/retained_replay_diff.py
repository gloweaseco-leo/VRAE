"""Host-only read of one retained artifact. Prints a redacted diff and never writes the source."""
import base64
import json
import re
import sys
from pathlib import Path

from contracts.l2_launch.contract import canonical
from vrae.evidence import EvidencePack
from vrae.rules.patch_execution import execute as run_rules

PRIVATE = re.compile(r'<html|mailto:|@|\+\d{8,}', re.I)


def load(path):
    document = json.loads(Path(path).read_bytes())
    objects = {key: base64.b64decode(value, validate=True) for key, value in document['objects_base64'].items()}
    pack = EvidencePack(canonical(document['pack']), tuple(sorted(objects.items())))
    pack.verify(expected_ref=pack.ref)
    return document, pack


def info02(chain):
    execution = chain[0] if isinstance(chain, tuple) else chain
    # source_chain returns a tuple in this codebase.
    return execution


def rows(execution):
    info = next(item for item in execution['executions'] if item['rule_id'] == 'INFO-02')
    exported = []
    for row in info['observations']:
        exported.append({'result': row['observation']['result'], 'reason': row['reason'],
                         'page': (row.get('source_page') or {}).get('snapshot_ref'),
                         'labels': [cite.get('label') for cite in row.get('citations') or []],
                         'citations': [{k: cite[k] for k in ('evidence_ref', 'snapshot_ref', 'byte_start', 'byte_end')
                                        if k in cite} for cite in row.get('citations') or []],
                         'requirements': [{k: item[k] for k in ('stage', 'site_role', 'decision', 'is_defect')}
                                          for item in row.get('buyer_requirements') or []]})
    return exported


def render(stored_version, baseline, candidate):
    lines = ['# 同一份留存证据上的诊断差异', '',
             f'留存诊断版本：{stored_version}',
             '1.0.7 连续重放两次，结果一致。原始工件没有被改写。',
             '线上自动诊断仍使用 1.0.7 / ra2b6-1.0.5。下面是尚未进入 FindingPackage、也未切换 Worker 的 ra2b6-1.0.6 候选。', '']
    before, after = rows(baseline), rows(candidate)
    lines.append(f'INFO-02 旧结果：{before[0]["result"] if before else "无"}')
    defects = [item for row in after for item in row['requirements'] if item['is_defect']]
    lines.append(f'新版本有据缺陷条数：{len(defects)}')
    for row in after:
        if not row['requirements']:
            continue
        lines.append('产品页字段已定位到该页原文，未把字段文字写入这份说明。')
        lines.append('清单未签字，这些条目都是待审候选，不是网站缺陷。')
        for item in row['requirements']:
            lines.append(f'- {item["stage"]} / {item["site_role"]}：{item["decision"]}')
        located = [cite for cite in row['citations'] if 'byte_start' in cite]
        lines.append(f'带字节范围、且与该产品页同一快照的引用：{len(located)}')
    lines += ['', '没有把缺少字段、未解析的 PDF，或无法唯一组合的参数写成网站问题。',
              '粒度与结合剂如何搭配，属于向供方确认，不是公开资料缺口。']
    text = '\n'.join(lines) + '\n'
    if PRIVATE.search(text):
        raise SystemExit(3)
    return text


def main():
    document, pack = load(sys.argv[1])
    baseline = run_rules(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.5')
    repeat = run_rules(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.5')
    if json.dumps(baseline, sort_keys=True) != json.dumps(repeat, sort_keys=True):
        raise SystemExit(2)
    candidate = run_rules(pack, expected_pack_ref=pack.ref, evaluator_version='ra2b6-1.0.6')
    sys.stdout.write(render(document.get('diagnosis', {}).get('diagnostic_version', 'UNKNOWN'), baseline, candidate))


if __name__ == '__main__':
    main()
