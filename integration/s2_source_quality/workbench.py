"""Opt-in view inside original DeepConsole; no new report or identity service."""
import json
import re
from dataclasses import replace

from apps.operator_console.views import e, link
from integration.s2_buyer_workbench.workbench import Workbench
from vrae.rules.s2.source_quality import evaluate_source_quality, verify_source_quality

TASKS = [('DISCOVER', '找到产品'), ('UNDERSTAND', '读懂技术资料'), ('TRUST', '核对资料可信范围'),
         ('INQUIRE', '准备询价'), ('SEARCH_TECHNICAL', '核对图片与标题来源')]


def describe(item):
    d, reason = item['details'], item['reason']
    if item['kind'] == 'DECLARED_LANGUAGE':
        return '源码声明语言为 '+str(d['declared_language'])+'；实际语言和技术表达质量尚未判断。'
    if item['kind'] == 'TECHNICAL_TEXT_REVIEW':
        words = '、'.join(d['acronyms'])
        return ('原文出现 '+words+' 等大写表达，请确认是否需要面向采购者展开。' if words else '原文保留了配置术语或多语种文本线索。') + '含义、翻译和实际可理解性均待人工核对。'
    if item['kind'] == 'ABBREVIATION_TITLE':
        return '原文缩写标签的说明为 '+str(d['source_title'] or '未提供')+'；说明是否正确、是否足以帮助采购者仍待核对。'
    if item['kind'] == 'HEADING_SOURCE_ORDER':
        return '源码标题标签 '+('h'+str(d['previous_level'])+' → ' if d['previous_level'] else '')+'h'+str(d['level'])+(' 存在源码层级跳跃。' if reason == 'SOURCE_LEVEL_SKIP' else ' 已保留。')+'实际视觉结构和无障碍符合性未知。'
    if item['kind'] == 'IMAGE_ALT_SOURCE':
        text = {'ALT_ATTRIBUTE_ABSENT': '这个源码图片标签未写alt属性。',
                'ALT_EMPTY_PURPOSE_REVIEW': '这个源码图片标签的alt为空；不能据此认定是正确的装饰图。',
                'ALT_TEXT_PRESENT_MEANING_UNREVIEWED': '源码保留alt文本：'+str(d['alt'])+'；是否恰当仍待核对。'}[reason]
        resource = d['resource']
        if resource['state'] == 'CAPTURE_METADATA_ONLY':
            meta = resource['response_metadata']
            text += '同次采集记录的该URL响应状态为 HTTP '+str(meta['http_status'])+'，记录时间 '+meta['observed_at']+'；这是采集元数据，不是图片加载证明。'
        else:
            text += '本次未取得可明确绑定的资源响应，不据此宣称坏图。'
        return text+'图像用途、正文/解码和实际浏览器加载保持UNKNOWN。'
    if item['kind'] == 'IMAGE_ALT_SUBSET':
        return '完整选中源码没有literal img标签：仅这个alt子集不适用。CSS、SVG、canvas或JS图像仍未知。'
    if item['kind'].startswith('RENDERED'):
        return '页面可能依赖脚本；本次没有新增渲染或资源加载观察，继续UNKNOWN。'
    return '观察不足或当前格式不支持；保持UNKNOWN，不将其解释为网站缺陷。'


def render(value, root):
    coverage = value['coverage']
    body = '<section class="card" data-key="source-quality"><h1>技术资料与图片来源复核</h1>'
    body += '<p>只读候选 · 不是原Guard事实、语言评分、WCAG合规或搜索排名结论。</p>'
    body += '<p>本次选择 '+str(coverage['selected'])+' 个保存页面，支持读取 '+str(coverage['supported_source'])+' 个；全站分母未知。原始图像与实际加载不因源码标记而得到证明。</p>'
    body += '<nav class="l2-nav">'+''.join(link('#'+task, label) for task, label in TASKS)+'</nav></section>'
    for task, label in TASKS:
        body += '<section class="card" data-task="'+task+'" id="'+task+'"><h2>'+label+'</h2>'
        chosen = [(i, row) for i, row in enumerate(value['rows'])
                  if ('UNDERSTAND' if row['rule_id'] == 'INFO-03' else 'SEARCH_TECHNICAL') == task]
        for i, row in chosen:
            body += '<article data-rule="'+row['rule_id']+'"><h3>'+row['rule_id']+' · '+e(row['selection']['url'])+'</h3>'
            body += '<p>采集角色：'+e(row['selection']['role'])+'；采集时间：'+e(row['selection']['observed_at'])+'；来源状态：'+e(row['state'])+'</p>'
            if row['selection']['model']:
                body += '<p>服务端已固定型号 '+e(row['selection']['model'])+' / 资料版次 '+e(row['selection']['data_revision'])+'</p>'
            for j, item in enumerate(row['items']):
                body += '<p data-key="quality-clue" data-state="'+e(item['state'])+'">'+e(describe(item))+'</p>'
                if item['citations']:
                    body += link(root+'/source-quality/cite/'+str(i)+'/'+str(j), '查看保留字节和原始定位', key='quality-citation')
            body += '<p><strong>采购影响假设：</strong>'+e(row['buyer_impact'])+'</p>'
            body += '<p><strong>需核实：</strong>'+e(row['questions'])+'</p>'
            proposal = row['rebuild_proposal']
            body += '<p><strong>Rebuild候选：</strong>'+e(proposal['action'])+'责任：'+e(proposal['owner'])+'。验收：'+e(proposal['acceptance'])+'</p>'
            body += '<p>'+e(proposal['service_fit'])+'；报价/工期 UNKNOWN。Gold不足，精度 NOT_EVALUABLE。</p></article>'
        if not chosen:
            body += '<p>本增量不补造此维度评价；请回到同一报告的原采购复核与来源。</p>'
        body += '</section>'
    body += '<section class="card">'+link(root+'/source-tasks', '回到原五维来源复核')+link(root, '回到同一原报告')+'</section>'
    return body


class QualityWorkbench(Workbench):
    def __init__(self, deep, binding, *, held, expected_quality_ref):
        super().__init__(deep, binding)
        self.held, self.expected_quality_ref = held, expected_quality_ref
        value = evaluate_source_quality(binding.pack, json.loads(binding.payload), held=held)
        verify_source_quality(value, binding.pack, json.loads(binding.payload), held=held,
                              expected_quality_ref=expected_quality_ref)
        self.payload = json.dumps(value, ensure_ascii=False).encode()

    @staticmethod
    def quality_route(path):
        return re.fullmatch(r'/b5a/l2/r/([A-Za-z0-9_.-]{3,128})/source-quality(?:/cite/(\d{1,2})/(\d{1,3}))?', path)

    def route(self, path):
        return self.quality_route(path) or super().route(path)

    def handle(self, method, path, headers, raw):
        match = self.quality_route(path)
        if match is None:
            reply = super().handle(method, path, headers, raw)
            old = super().route(path)
            if reply.response.status == 200 and old is not None and old[2] is None and old[3] is None:
                nav = ('<section class="card">'+link('/b5a/l2/r/'+old[1]+'/source-quality',
                    '继续核对英文术语与图片技术来源', key='quality-entry')+'</section>').encode()
                reply = replace(reply, response=replace(reply.response,
                    body=reply.response.body.replace(b'</body>', nav+b'</body>', 1)))
            return reply
        with self.deep.directory.lock:
            try:
                self.deep.refresh()
                if method not in ('GET', 'HEAD') or raw or headers.get('Authorization') is not None:
                    raise ValueError('READ_ONLY')
                sid, rid = self.deep.sid(headers), match[1]
                _, report = self.deep.current(sid, rid)
                parent = self.binding.read(report)
                value = json.loads(self.payload)
                verify_source_quality(value, self.binding.pack, parent, held=self.held,
                                      expected_quality_ref=self.expected_quality_ref)
                root = '/b5a/l2/r/'+rid
                body = render(value, root)
                if match[2] is not None:
                    item = value['rows'][int(match[2])]['items'][int(match[3])]
                    if not item['citations']:
                        raise ValueError('NO_RETAINED_BYTES')
                    body = '<section class="card"><h1>保留源码原文与定位</h1><p>原文是来源声明，不是真实性或语义认证。</p>'
                    for c in item['citations']:
                        original = self.binding.pack.resolve(c['evidence_ref'], expected_pack_ref=value['pack_ref'])['content']
                        if original[c['byte_start']:c['byte_end']].decode() != c['quote']:
                            raise ValueError('SOURCE_BYTES')
                        body += '<p>'+e(c['url'])+' · '+e(c['observed_at'])+'</p><blockquote data-key="quality-quote">'+e(c['quote'])+'</blockquote>'
                        body += '<p>原始UTF-8字节 '+str(c['byte_start'])+'–'+str(c['byte_end'])+'</p>'
                    body += link(root+'/source-quality', '返回来源质量复核')+'</section>'
                _, current = self.deep.current(sid, rid)
                if current.version != report.version or current.display_hash != report.display_hash:
                    raise ValueError('STALE_VERSION')
                return self.deep.reply('技术资料与图片来源复核', body)
            except Exception:  # noqa: BLE001 -- original signed boundary denies without leaking data
                return self.deep.reply('未提供来源质量候选', '<p>当前签名、版本或来源绑定未通过；没有返回候选。</p>', 403)
