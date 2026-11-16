"""Allowlisted, source-replayed L2 product outputs. No profiles, tokens or logs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET

from vrae.l2.report import DeepReport, OfflineSource
from .support import ROOT, PIN


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def report_md(view):
    d=view.document
    lines=['# '+d['meta']['title'],'',
        '> 合成离线工业网站样本。受控审核演练，未发生正式人审或真实客户交付。',
        '',f"报告版本：{d['meta']['version']}。完整展示哈希：`{view.display_hash}`。",'',
        '## 核心判断','',d['summary'],'','## 工业采购任务','',d['buyer']['label'],'',
        d['buyer']['scenario'],'',d['buyer']['assumption'],'']
    lines += ['- '+q for q in d['buyer']['questions']]
    lines += ['','## 五段采购旅程','']
    for j in d['journey']:
        lines += ['### '+j['goal'],'',j['assessment'],'']
    by_ev={e['id']:e for e in d['evidence']}
    snapshots={s['id']:s for s in d['snapshots']}
    lines += ['## 观察、风险与未知','']
    for f in d['findings']:
        lines += ['### '+f['title'],'',f"类型：{f['kind']}；优先级：{f['priority']}。",'',f['statement'],'','范围：'+f['scope'],'']
        for key in f['evidence_ids']:
            ev=by_ev[key]
            s=snapshots[ev['snapshot_id']]
            lines += ['证据来源：'+s['url']+'；记录时间：'+s['captured_at']+'。',
                '', '```html',ev['quote'],'```','',f"定位：{ev['locator']}；字节 [{ev['byte_start']}, {ev['byte_end']})。",'']
        for key,label in [('buyer_impact','可能影响（假设）'),('priority_basis','优先级依据'),
                          ('uncertainty','尚不能确认'),('recommendation','建议'),('recheck','复验')]:
            lines += ['**'+label+'**：'+f[key],'']
    lines += ['## 分析边界','']+['- '+x for x in d['limitations']]
    lines += ['','IndustryPack：'+d['industry_pack']['industry_id']+' / '+d['industry_pack']['version']+'。',
        '', '来源束 SHA-256：`'+view.source_digest+'`。',
        '', '此文件是内部静态样本，不是访问授权；在线撤销不能远程收回已经下载的文件。','']
    return '\n'.join(lines).encode('utf-8')


def blueprint_md(view):
    d=view.document
    by_id={f['id']:f for f in d['findings']}
    lines=['# 工业泵网站 Rebuild 改造蓝图','',
        '> 合成离线样本；内部讨论材料。不是已获客户授权的 RebuildBrief，不自动建站或发布。','',
        f"报告版本：{d['meta']['version']}；完整展示哈希：`{view.display_hash}`。",'',
        d['service_catalog']['verification'],'','报价：UNKNOWN；工期：UNKNOWN。','']
    for n,b in enumerate(d['blueprint'],1):
        lines += [f"## {n}. {b['title']}",'','阶段：'+b['phase'],'','改善页面／信息：'+b['page'],'',
            '### 为什么值得讨论','']
        for key in b['finding_ids']:
            f=by_id[key]
            lines += ['- '+f['title']+'（'+f['kind']+'）','',f['statement'],'','可能影响（假设）：'+f['buyer_impact'],'']
        lines += ['### 建议怎么改','',b['change'],'','### 需要企业补充或确认','']
        lines += ['- '+v for v in b['customer_inputs']]
        lines += ['','### 服务范围','',('标准 Rebuild 候选（按合同确认）' if b['service_fit']=='STANDARD_CANDIDATE' else '需定制评估；不默认必须购买'),
            '',b['service_basis'],'','责任角色：'+b['owner_role'],'','依赖：'+b['dependency'],'','### 如何复验','']
        lines += ['- '+v for v in b['acceptance']]+['']
    lines += ['本蓝图不承诺转化、排名或销售结果。未取得的工程、资质、收件和经营资料保持 UNKNOWN，不妨碍其他有据分析。','']
    return '\n'.join(lines).encode('utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('label')
    parser.add_argument('--junit',required=True)
    parser.add_argument('--sample',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch('[a-z0-9-]{3,50}',args.label):
        raise ValueError('L2_PUBLICATION_LABEL_DENIED')
    source=ROOT/'integration/l2/.runtime'/args.label
    public=ROOT/'docs/03-engineering/l2-deep-audit'/('sample' if args.sample else 'evidence/'+args.label)
    public.mkdir(parents=True,exist_ok=False)
    metadata={'status':'INCOMPLETE_NOT_PASS','source_label':args.label,'files':{}}
    try:
        raw_xml=Path(args.junit).read_bytes()
        cases=list(ET.fromstring(raw_xml).iter('testcase'))
        assert cases and len(cases)==len({(c.get('classname'),c.get('name')) for c in cases})
        assert all(c.find(k) is None for c in cases for k in ('failure','error','skipped','system-out','system-err'))
        browser=json.loads((source/'browser.json').read_bytes())
        run=json.loads((source/'run.json').read_bytes())
        assert run['result']['pass'] and browser['formalHumanReviewsClaimed']==0 and browser['realExternalCustomers']==0
        assert browser['records'] and all(r['pass'] for r in browser['records']) and not browser['exceptions']
        assert len(run['restarts'])==1 and all(run['restarts'][0].values())
        cleanup=json.loads((source/'process-cleanup.json').read_bytes())
        chrome=json.loads((source/'browser-cleanup.json').read_bytes())
        assert all(cleanup.values()) and chrome['exitObserved']
        held=OfflineSource(ROOT/'fixtures/l2/pump-maker-v1',PIN)
        with sqlite3.connect('file:'+str((source/'l2.sqlite').as_posix())+'?mode=ro',uri=True) as c:
            versions=[]
            for row in c.execute('SELECT payload,display_hash,source_hash FROM versions ORDER BY version'):
                assert sha(row[0])==row[1] and row[2]==PIN
                view=DeepReport(bytes(row[0]),row[2])
                held.validate(view.document)
                versions.append(view)
            receipts=[json.loads(r[0]) for r in c.execute('SELECT receipt FROM decisions ORDER BY seq')]
            grants=[json.loads(r[0]) for r in c.execute('SELECT grant_json FROM grants ORDER BY id')]
        assert len(versions)==2 and len(receipts)==2
        assert all(x['scope']=='CONTROLLED_REVIEW_SIMULATION' and not x['formal_human_review']
                   and not x['external_delivery'] for x in receipts)
        assert {x['decision']['version'] for x in receipts}=={1,2}
        files={'native.xml':raw_xml,'browser.json':(source/'browser.json').read_bytes(),
            'run.json':(source/'run.json').read_bytes(),'process-cleanup.json':(source/'process-cleanup.json').read_bytes(),
            'browser-cleanup.json':(source/'browser-cleanup.json').read_bytes(),
            'versioned-decisions.json':json.dumps(receipts,ensure_ascii=False,indent=2).encode(),
            'controlled-grants.json':json.dumps(grants,ensure_ascii=False,indent=2).encode(),
            'report-version-2.json':versions[-1].payload,
            'l2-deep-report.md':report_md(versions[-1]),'l2-rebuild-blueprint.md':blueprint_md(versions[-1])}
        for item in browser['shots']:
            name=item['file']
            assert re.fullmatch('[a-z0-9-]+\.png',name)
            raw=(source/name).read_bytes()
            assert sha(raw)==item['sha256']
            files[name]=raw
        pages={}
        for name in ('l2-deep-report.pdf','l2-rebuild-blueprint.pdf'):
            raw=(source/name).read_bytes()
            record=next(r for r in browser['records'] if r['name']==name+'-actual-multipage-A4')
            assert record['metadata']['sha256']==sha(raw) and record['metadata']['pages']>1
            pages[name]=record['metadata']['pages']
            files[name]=raw
        for name,raw in files.items():
            text=raw.decode('utf-8',errors='ignore')
            assert '-----BEGIN PRIVATE KEY' not in text and 'Bearer ' not in text
            assert not re.search(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',text)
            (public/name).write_bytes(raw)
            metadata['files'][name]={'bytes':len(raw),'sha256':sha(raw)}
        metadata.update(status='L2_OFFLINE_PRODUCT_REVIEW_CANDIDATE',native_tests=len(cases),
            browser_checks=len(browser['records']),screenshots=len(browser['shots']),actual_pdf_pages=pages,
            source_bundle_sha256=PIN,report_version=2,display_hash=versions[-1].display_hash,
            content_hash=versions[-1].version['content_hash'],formal_human_reviews_claimed=0,
            actual_external_customers=0,source_integrity_replayed=True,owner_acceptance_pending=True)
        from .native_publish import publish as publish_native
        metadata['native_component']=publish_native(args.label,public)
        metadata['status']='L2_LEGACY_AND_NATIVE_COMPONENT_PASS_NOT_WORKER_E2E'
        metadata['primary_report']='native/l2-deep-report.pdf'
        metadata['primary_blueprint']='native/l2-rebuild-blueprint.pdf'
    finally:
        (public/'publication.json').write_bytes(json.dumps(metadata,ensure_ascii=False,indent=2).encode())
    print(json.dumps({'status':metadata['status'],'public':str(public.relative_to(ROOT)),'pdf_pages':metadata.get('actual_pdf_pages')}))


if __name__=='__main__':
    main()
