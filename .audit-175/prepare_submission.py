"""Prepare non-secret Issue175 report bodies; no network or source mutations."""
import json
from pathlib import Path

root=Path(__file__).resolve().parent
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
for index,name in enumerate(('INVENTORY.md','RUNTIME_PROTECTION.md','CLEANUP_PROPOSAL.md'),1):
    body=f'## Phase A 审计正式交付 {index}/3 · `{name}`\n\n'
    if index==1:
        body+='按Issue175允许的“已有审计Issue提交”方式交付；未创建/切换本机分支或worktree，未fetch/pull，未修改PR172/PR174。完整三份Markdown和脱敏机器快照保存在用户共享工作区 `D:/Projects/VRAE/.audit-175/`。\n\n'
    body+=(root/name).read_text(encoding='utf-8')
    body+=f'\n\n本文件SHA256：`{manifest[name]}`。\n脱敏机器快照 `AUDIT_SNAPSHOT.json` SHA256：`{manifest["AUDIT_SNAPSHOT.json"]}`。\n'
    if index==3:
        body+='\n**Phase A至此停止。没有执行任何删除、移动、归档或运行环境修改；等待Owner对具体路径/动作逐项批准，不自动进入Phase B。**\n'
    assert len(body)<65000
    (root/f'issue175-report-{index}.json').write_text(json.dumps({'body':body},ensure_ascii=False),encoding='utf-8')
print('Prepared 3 non-secret report payloads; no network action performed.')
