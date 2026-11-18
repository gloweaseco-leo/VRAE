"""Escaped UI for the accepted C1 buyer DTO; no new report or review authority."""
from apps.operator_console.views import e, link
from vrae.reporting.s2_candidate import (
    BuyerCandidateError, BuyerCandidatePins, ObservationPin, RULE_VERSION, SOURCE_VERSION,
)


def selection(projection, *, scope, pack_ref, industry_pins, model, snapshot_ref):
    """Trusted server selection from its replayed projection, never an HTTP DTO."""
    observations = []
    for rule in ('INFO-02', 'TRUST-02'):
        rows = [row for row in projection['industrial_projection']['rows']
                if row['observation']['rule_id'] == rule and (
                    row['model'] == model and snapshot_ref in {page['snapshot_ref'] for page in row['source_pages']}
                    or row['observation']['result']=='NOT_APPLICABLE' and row['model'] is None
                    and not row['source_pages'] and row['details'].get('configuration_locator'))]
        if len(rows) != 1:
            raise BuyerCandidateError('S2_BUYER_SELECTION_AMBIGUOUS')
        row = rows[0]
        observations.append(ObservationPin(row['observation']['observation_id'], rule,
                            RULE_VERSION, SOURCE_VERSION,
                            tuple(sorted(page['snapshot_ref'] for page in row['source_pages']))))
    return BuyerCandidatePins(**scope, pack_ref=pack_ref, projection_ref=projection['projection_ref'],
                              projection_version=projection['projection_version'], industry_pins=industry_pins,
                              subject_model=model, subject_snapshot_ref=snapshot_ref,
                              observations=tuple(observations))


def observed(card):
    if card['result'] != 'PASS':
        return card['limitation']['text']
    fields = card['observed_fields']
    if card['rule_id'] == 'INFO-02':
        return '来源列明资料版本 '+str(fields.get('data_revision') or 'UNKNOWN')+'；声明工况：'+str(fields.get('specification_conditions') or 'UNKNOWN')+'。'
    kind = {'certificate':'证书声明', 'case':'案例声明', 'factory':'工厂声明'}.get(fields.get('proof_kind'), '证明声明类型 UNKNOWN')
    date = {'BEFORE_CAPTURE':'声明日期早于采集日', 'AFTER_CAPTURE':'声明日期晚于采集日',
            'ON_CAPTURE_DATE':'声明日期与采集日相同'}.get(fields.get('date_relation'), '日期关系 UNKNOWN')
    return '来源有'+kind+'；'+date+'。日期比较不证明当前有效性。'


def render_card(card, index, root):
    request = ('实际买方工况、当前参数表及其适用条件。' if card['rule_id']=='INFO-02'
               else '原始证明、声明对象、日期和适用范围。')
    html = '<article class="card" id="buyer-card-'+str(index)+'" data-key="buyer-task-card" data-buyer-authority="READ_ONLY_REVIEW_CANDIDATE" data-result="'+e(card['result'])+'">'
    html += '<p class="eyebrow">只读采购来源卡 · '+e(card['model'] or '当前受限来源')+'</p><h3>'+e(card['title'])+'</h3>'
    html += '<p><strong>看到什么：</strong>'+e(observed(card))+'</p>'
    html += '<p><strong>采购帮助（待人工确认）：</strong>'+e(card['review_hypothesis']['text'])+'</p>'
    html += '<p><strong>还不知道什么：</strong>'+e(card['limitation']['text'])+'</p>'
    html += '<p><strong>下一步向企业索取：</strong>'+e(request)+'</p>'
    if card['source_excerpts']:
        html += link(root+'/source-tasks/buyer-cite/'+str(index), '核对本卡原文、时间与字节', key='buyer-card-source')
    else:
        html += '<p>本卡没有材料原文字节；仅保留配置或响应记录。</p>'
    html += '<details><summary>来源范围与版本</summary><p>'+e(card['rule_id'])+' · '+e(card['rule_version'])+' · '+e(card['source_version'])+'</p></details></article>'
    return html


def attach(html, candidate, root, navigation):
    """Compose only verified cards into the existing five SSR sections."""
    cards = candidate['cards']
    info = next((card for card in cards if card['rule_id']=='INFO-02'), None)
    revision = info['observed_fields'].get('data_revision') if info else None
    proof = any(card['rule_id']=='TRUST-02' and card['result']=='PASS' for card in cards)
    summary = ('参数资料版本 '+str(revision)+('；证明声明可回查。' if proof else '；证明仍待核对。') if revision and info['result']=='PASS'
               else '本次材料存在待核实或不适用范围，按各来源卡逐项确认。')
    intro = '<section class="card" data-key="s2-source-workbench" data-buyer-candidate-ref="'+e(candidate['candidate_ref'])+'"><p class="eyebrow">受控工业采购复核</p><h1>五维采购复核</h1>'
    intro += '<p>本次对象（来源声明）：<strong>'+e(candidate['subject_model'] or '当前受限来源')+'</strong></p>'
    intro += '<div data-key="buyer-first-screen"><p><strong>看到什么：</strong>'+e(summary)+'</p>'
    intro += '<p><strong>采购帮助（待确认）：</strong>先对齐资料版本，再整理需要供应方确认的事项。</p>'
    intro += '<p><strong>还不知道：</strong>工程适配、证明真伪和当前有效性均 UNKNOWN。</p>'
    intro += '<p><strong>下一步向企业索取：</strong>实际工况、当前参数表、原始证明及适用范围。</p></div>'
    intro += '<details><summary>本次来源卡范围</summary><p>只读审阅候选，原报告与审核记录保留。</p><p>'+e(candidate['candidate_ref'])+'</p><p>'+e(candidate['reporting_version'])+' · '+e(candidate['profile_id'])+' · '+e(candidate['industry_version'])+'</p></details>'
    intro += navigation+'</section>'
    # The replaced fragment is our own SSR hero, never source-provided HTML.
    end = html.index('</section>')+len('</section>')
    html = intro+html[end:]
    for index, card in enumerate(cards):
        marker = '<section class="card" id="'+card['buyer_task']+'" data-task="'+card['buyer_task']+'">'
        start = html.index(marker)
        heading_end = html.index('</h2>', start)+len('</h2>')
        html = html[:heading_end]+render_card(card,index,root)+html[heading_end:]
    return html
