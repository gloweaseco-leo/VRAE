"""Candidate reader only; original DeepConsole owns every identity and report read."""
import json
import re

from apps.operator_console.views import e, link
from vrae.evidence import EvidenceError
from vrae.l2.native import NativeSource
from vrae.l2.report import TASKS, deny
from vrae.rules.s2 import INDUSTRIAL_PROJECTION_VERSION, evaluate_s2, verify_s2_projection
from vrae.reporting.s2_candidate import build_candidate, verify_candidate
from . import buyer_cards

LABELS = {'DISCOVER': '找到产品与型号', 'UNDERSTAND': '核对规格与工况',
          'TRUST': '核对供应商资料', 'INQUIRE': '准备型号询价',
          'SEARCH_TECHNICAL': '核对搜索与技术观察范围'}
RULES = {'INFO-02': ('UNDERSTAND', '参数、单位与资料版本', '核对型号、额定值、单位及资料版本，补充买方实际工况后交工程责任人确认。'),
         'TRUST-02': ('TRUST', '来源声明的证明材料', '向供应方核对声明对象、机构、编号和日期；证书真实性、有效性及资质仍需独立核验。'),
         'TRUST-03': ('TRUST', '主体与联系资料', '逐处核对相同自报标识下的主体及联系方式；字符串一致不证明法定主体或联系送达。'),
         'DISC-03': ('DISCOVER', '保留来源中的产品路径', '按来源路径核对目标型号；未采集页面不判为不存在。'),
         'SEO-02': ('SEARCH_TECHNICAL', '来源中的页面标题', '人工复核标题与实际内容的关系，不据此推断搜索排名。'),
         'TECH-01': ('SEARCH_TECHNICAL', '已保留的技术响应', '结合本次响应核对技术状态，不推断全站或长期可用性。')}
RESULTS = {'PASS': '来源候选符合本项展示条件', 'UNKNOWN': 'UNKNOWN · 资料或观察不足，待核实',
           'NOT_APPLICABLE': '此项不适用（按固定行业配置）',
           'ACCESS_BLOCKED': '来源访问受阻，不能判断页面内容',
           'FAIL_WITH_EVIDENCE': '原来源候选记录了有据差异，需核对其限定范围'}


class SourceBinding:
    def __init__(self, source, pack, *, trusted_scope, industry_pins):
        if type(source) is not NativeSource or source.held.native_pack_ref != pack.ref:
            deny('S2_REPORT_SOURCE_BINDING')
        if (trusted_scope['tenant_id'], trusted_scope['run_id']) != (source.held.tenant_id, source.held.run_id):
            deny('S2_REPORT_SOURCE_BINDING')
        self.source, self.pack = source, pack
        self.scope, self.pins = dict(trusted_scope), industry_pins
        out = evaluate_s2(pack, expected_pack_ref=source.held.native_pack_ref,
                          trusted_scope=self.scope, projection_version=INDUSTRIAL_PROJECTION_VERSION,
                          industry_pins=industry_pins)
        self.payload = json.dumps(out, ensure_ascii=False, sort_keys=True).encode()
        self.expected_ref = out['projection_ref']
        self.buyer_pins = self.buyer_payload = self.expected_buyer_ref = None

    def enable_buyer_cards(self, *, model, snapshot_ref):
        projection = self.read(self.source.read())
        self.buyer_pins = buyer_cards.selection(projection, scope=self.scope,
            pack_ref=self.source.held.native_pack_ref, industry_pins=self.pins,
            model=model, snapshot_ref=snapshot_ref)
        candidate = build_candidate(self.pack, projection, held=self.buyer_pins)
        self.buyer_payload = json.dumps(candidate, ensure_ascii=False, sort_keys=True).encode()
        self.expected_buyer_ref = candidate['candidate_ref']

    def read_buyer(self, projection):
        if self.buyer_pins is None:
            return None
        candidate = json.loads(self.buyer_payload)
        verify_candidate(candidate, self.pack, projection, held=self.buyer_pins,
                         expected_candidate_ref=self.expected_buyer_ref)
        return candidate

    def read(self, report):
        if (report.source_digest != self.source.expected or
                (report.document['meta']['tenant_id'], report.document['meta']['run_id']) !=
                (self.scope['tenant_id'], self.scope['run_id'])):
            deny('S2_REPORT_SOURCE_BINDING')
        out = json.loads(self.payload)
        verify_s2_projection(out, self.pack, expected_pack_ref=self.source.held.native_pack_ref,
                             trusted_scope=self.scope, expected_projection_ref=self.expected_ref,
                             expected_projection_version=INDUSTRIAL_PROJECTION_VERSION,
                             industry_pins=self.pins)
        return out


def candidate_rows(projection):
    return projection['industrial_projection']['rows'] + projection['static_projection']['rows']


def render(report, projection, root, buyer=None):
    snapshots = {snapshot['id']: snapshot for snapshot in report.document['snapshots']}
    rows = candidate_rows(projection)
    displayed = {card['observation_id'] for card in buyer['cards']} if buyer else set()
    ready = [row for row in rows if row['observation']['rule_id']=='INFO-02' and row['observation']['result']=='PASS']
    body = '<section class="card" data-key="s2-source-workbench"><p class="eyebrow">受控工业采购复核</p>'
    body += '<h1>五维采购复核</h1><p>先核对型号、规格和供应商声明，再整理询价资料。</p>'
    if ready:
        body += '<p class="l2-lead">已定位参数资料：'+e(' / '.join(row['model']+'（'+str(row['details'].get('data_revision') or '版本 UNKNOWN')+'）' for row in ready))+'。</p>'
        body += '<p><strong>当前待办：</strong>补充实际买方工况，再核对供应商证明；工程适配仍 UNKNOWN。</p>'
    else:
        body += '<p>UNKNOWN · 尚无符合本项来源展示条件的参数资料，不判为网站缺陷。</p>'
    body += '<p>CONTROLLED · 合成资料，仅供来源复核；原报告与责任人决定保留。</p>'
    body += '<details><summary>本次未核实的范围</summary><p>工程适配 UNKNOWN · 证书真伪 UNKNOWN · 联系送达 UNKNOWN · 全站覆盖分母 UNKNOWN。非正式人审，不可客户外发。</p></details>'
    body += '<nav class="l2-nav" aria-label="五维采购任务">' + ''.join(link('#'+task, LABELS[task]) for task in TASKS) + '</nav></section>'
    for task in TASKS:
        body += '<section class="card" id="'+task+'" data-task="'+task+'"><h2>'+e(LABELS[task])+'</h2>'
        selected = [(i, row) for i, row in enumerate(rows) if RULES.get(row['observation']['rule_id'], ('',))[0] == task
                    and row['observation']['observation_id'] not in displayed]
        for i, row in selected:
            observation = row['observation']
            _, label, next_step = RULES[observation['rule_id']]
            body += '<article data-key="s2-source-candidate" data-result="'+e(observation['result'])+'"><h3>'+e(label)
            if row.get('model'):
                body += ' · '+e(row['model'])
            body += '</h3><p>'+e(RESULTS.get(observation['result'], observation['result']))+'</p>'
            details = row.get('details', {})
            if observation['rule_id'] == 'INFO-02':
                body += '<p>来源资料版本：'+e(details.get('data_revision') or 'UNKNOWN')+'</p>'
                body += '<p>来源声明条件：'+e(details.get('specification_conditions') or 'UNKNOWN')+'</p>'
            body += '<p><strong>下一步：</strong>'+e(next_step)+'</p>'
            if row['citations']:
                first = row['citations'][0]
                snapshot = snapshots[first['snapshot_ref']]
                body += '<p>来源：'+e(snapshot['url'])+' · 采集时间：'+e(snapshot['captured_at'])+'</p>'
                body += link(root+'/source-tasks/cite/'+str(i), '核对原文与定位', key='s2-source-citation')
            else:
                body += '<p>UNKNOWN · 本项没有可展示的原文字节引用，不判为网站缺陷。</p>'
            body += '<details><summary>核对范围与版本</summary><p>'+e(observation['rule_id'])+' · '+e(observation['rule_version'])+'</p><p>'+e(row['reason'])+'</p></details></article>'
        if task == 'INQUIRE':
            body += '<p>核对目标型号、数量、介质、流量/扬程或压力、温度、电气条件与目的地。未填写的买方需求保持待补，不归为网站缺陷；没有提交 RFQ。</p>'
            body += link(root+'/blueprint', '在原 Rebuild 蓝图中整理询价准备', key='s2-blueprint')
        if not selected and task != 'INQUIRE':
            body += '<p>UNKNOWN · 本次来源候选没有覆盖这一项，不补造评价。</p>'
        if task == 'UNDERSTAND':
            body += '<p>INFO-03 英语及术语质量仍需人工复核；缺少观察不升级为 FAIL。</p>'
        if task == 'INQUIRE':
            body += '<p>CTA-01/CTA-03 的可见询价入口、可提交性、遮挡与几何仍 UNKNOWN。</p>'
        if task == 'SEARCH_TECHNICAL':
            body += '<p>TECH-02 图片 alt、资源加载及搜索排名仍 UNKNOWN；此工作台页面截图不替代来源站观察。</p>'
        body += '</section>'
    body += '<section class="card"><h2>回到原报告与责任人决定</h2>'
    body += link(root, '读取同一原报告', key='s2-original-report') + link(root+'/review', '按原版本逐项 Controlled 审阅', key='s2-original-review')
    body += '<p>来源候选不会自动加入原审核项；所有决定和蓝图修订仍使用原接口。</p>'
    body += '<details><summary>来源与报告绑定</summary><p>原报告 '+e(report.version['report_version_id'])+'</p><p>报告显示 hash '+e(report.display_hash)+'</p>'
    body += '<p>来源 pack '+e(projection['pack_ref'])+'</p><p>只读候选 '+e(projection['projection_ref'])+'</p><p>固定行业配置 '+e(projection['industrial_projection']['industry_ref'])+'</p></details></section>'
    if buyer is not None:
        navigation = '<nav class="l2-nav" aria-label="五维采购任务">'+''.join(link('#'+task, LABELS[task]) for task in TASKS)+'</nav>'
        return buyer_cards.attach(body, buyer, root, navigation)
    return body


class Workbench:
    """Additive existing B5B native_business hook; no replacement auth path."""
    def __init__(self, deep, binding):
        if deep.directory.mode != 'CONTROLLED' or binding.source.held.source_access_mode != 'OFFLINE_SYNTHETIC':
            deny('S2_CONTROLLED_COMPONENT_ONLY')
        self.deep, self.binding = deep, binding

    def route(self, path):
        return re.fullmatch(r'/b5a/l2/r/([A-Za-z0-9_.-]{3,128})/source-tasks(?:/cite/(\d{1,3})|/buyer-cite/([01]))?', path)

    def decorate(self, path, reply):
        return reply

    def handle(self, method, path, headers, raw):
        with self.deep.directory.lock:
            try:
                self.deep.refresh()
                if method not in ('GET', 'HEAD') or raw or headers.get('Authorization') is not None:
                    deny()
                match = self.route(path)
                if match is None or match[1] not in self.deep.ledgers:
                    deny()
                sid, rid = self.deep.sid(headers), match[1]
                _, report = self.deep.current(sid, rid)
                projection = self.binding.read(report)
                buyer = self.binding.read_buyer(projection)
                root = '/b5a/l2/r/'+rid
                if match[2] is None and match[3] is None:
                    body = render(report, projection, root, buyer)
                else:
                    if match[3] is not None:
                        index = int(match[3])
                        if buyer is None or index >= len(buyer['cards']):
                            deny()
                        citations = buyer['cards'][index]['source_excerpts']
                        context = buyer_cards.render_card(buyer['cards'][index], index, root)
                    else:
                        rows = candidate_rows(projection)
                        index = int(match[2])
                        if index >= len(rows) or not rows[index]['citations']:
                            deny()
                        citations = rows[index]['citations']
                        context = ''
                    body = '<section class="card"><h1>保留来源的原文定位</h1><p>以下仅为原始来源声明，不认证其真实性。</p>'
                    body += context
                    if not citations:
                        body += '<p>本卡仅有配置或响应记录，没有可展示的材料原文。</p>'
                    snapshots = {snapshot['id']:snapshot for snapshot in report.document['snapshots']}
                    for citation in citations:
                        raw_source = self.binding.pack.resolve(citation['evidence_ref'], expected_pack_ref=projection['pack_ref'])['content']
                        if raw_source[citation['byte_start']:citation['byte_end']].decode() != citation['quote']:
                            raise EvidenceError('S2_SOURCE_QUOTE')
                        snapshot = snapshots[citation['snapshot_ref']]
                        body += '<article data-key="s2-original-citation"><p>'+e(snapshot['url'])+' · '+e(snapshot['captured_at'])+'</p>'
                        body += '<blockquote>'+e(citation['quote'])+'</blockquote><p>原始 UTF-8 字节 '+str(citation['byte_start'])+'–'+str(citation['byte_end'])+'</p></article>'
                    body += link(root+'/source-tasks', '返回五维采购复核')+'</section>'
                _, current = self.deep.current(sid, rid)
                if current.version != report.version or current.display_hash != report.display_hash:
                    deny('L2_STALE_VERSION')
                return self.deep.reply('来源候选五维采购复核', body)
            except Exception:
                return self.deep.reply('请求未提供数据', '<section class="notice"><h1>请求未提供来源或报告</h1><p>请核对当前签名身份、报告版本与来源绑定。</p></section>', 403)


def install(app, binding):
    if app.native_business is not None or app.native_tasks is not None or app.deep is None:
        deny('S2_EXISTING_NATIVE_PORT_MUST_NOT_BE_REPLACED')
    if not any(ledger.source is binding.source for ledger in app.deep.ledgers.values()):
        deny('S2_REPORT_SOURCE_BINDING')
    app.native_business = Workbench(app.deep, binding)
